from __future__ import annotations

from pathlib import Path

from contracts import IncidentEnvelope, IncidentStatus, PipelineEvent, utcnow_iso
from services.orchestrator.config import Settings
from services.orchestrator.engine import SentinelEngine
from services.tools import CIRunner, GitHubClient, MockAzureMonitorTool
from storage import PatternStore


def build_incident(
    incident_id: str,
    signal_type: str = "http_5xx_rate",
    env: str = "prod",
    error_rate: float = 0.21,
) -> IncidentEnvelope:
    return IncidentEnvelope(
        incident_id=incident_id,
        service="checkout-api",
        env=env,
        start_time=utcnow_iso(),
        signal_type=signal_type,
        signal_payload={
            "error_rate": error_rate,
            "baseline_error_rate": 0.01,
            "endpoint": "/checkout",
            "latency_p95_ms": 1450,
        },
        runbook_hint="rollback_recent_release_or_adjust_timeout",
    )


def build_engine(
    tmp_path: Path,
    *,
    azure_tool: MockAzureMonitorTool | None = None,
    ci_runner: CIRunner | None = None,
    confidence_threshold: float = 0.65,
    tool_retry_attempts: int = 2,
) -> SentinelEngine:
    db_path = str(tmp_path / "patterns.db")
    settings = Settings(
        confidence_threshold=confidence_threshold,
        max_patch_attempts=2,
        tool_retry_attempts=tool_retry_attempts,
        dedupe_window_minutes=20,
        base_branch="main",
        github_owner="demo-org",
        github_repo="demo-service",
        github_mode="mock",
        github_token=None,
        pattern_db_path=db_path,
        autonomous_envs=("prod", "staging"),
    )
    return SentinelEngine(
        settings=settings,
        azure_tool=azure_tool or MockAzureMonitorTool(),
        github_client=GitHubClient(owner="demo-org", repo="demo-service", mode="mock"),
        ci_runner=ci_runner or CIRunner(),
        pattern_store=PatternStore(db_path),
    )


def test_triage_dedupes_and_blocks_non_autonomous(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    first = engine.ingest_incident(build_incident("inc-001"))
    second = engine.ingest_incident(build_incident("inc-002"))
    third = engine.ingest_incident(build_incident("inc-003", signal_type="cpu_high"))

    assert first.status == IncidentStatus.PR_READY
    assert second.status == IncidentStatus.DUPLICATE
    assert "duplicate" in (second.last_error or "").lower()
    assert third.status == IncidentStatus.BLOCKED
    assert "unsupported signal type" in (third.last_error or "").lower()


def test_investigation_links_latest_deployment(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    packet = engine.investigation_agent.investigate(build_incident("inc-004"))
    assert packet.suspected_release == "2026.02.14.2"
    assert packet.correlated_metrics["max_5xx_rate"] >= 0.18
    assert packet.confidence >= 0.65


def test_patch_proposal_has_rationale_and_constrained_scope(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    incident = build_incident("inc-005")
    investigation = engine.investigation_agent.investigate(incident)
    patch = engine.patch_agent.propose_patch(incident, investigation, attempt=1)

    assert patch.hypothesis
    assert patch.diff_summary
    assert patch.changed_files
    assert len(patch.changed_files) <= 2
    assert all(path.startswith("config/") for path in patch.changed_files)


def test_verification_failure_blocks_pr_creation(tmp_path: Path) -> None:
    engine = build_engine(tmp_path, ci_runner=CIRunner(force_test_failure=True))
    record = engine.ingest_incident(build_incident("inc-006"))

    assert record.status == IncidentStatus.ESCALATED
    assert record.approval_package is None
    assert "pr_url" not in record.linked_artifacts
    assert record.patch_attempts == 2


def test_verification_success_creates_evidence_backed_pr(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    record = engine.ingest_incident(build_incident("inc-007"))

    assert record.status == IncidentStatus.PR_READY
    assert record.processing_seconds < 600
    assert record.approval_package is not None
    assert record.approval_package.pr_url.startswith("https://github.com/")
    assert record.approval_package.rollback_steps
    assert "metrics_dashboard" in record.approval_package.evidence_links
    assert "logs_query" in record.approval_package.evidence_links
    assert record.linked_artifacts["pr_url"] == record.approval_package.pr_url


def test_pattern_store_persists_incident_resolution_signature(tmp_path: Path) -> None:
    engine = build_engine(tmp_path)
    record = engine.ingest_incident(build_incident("inc-008"))
    saved = engine.pattern_store.find_latest(record.incident.fingerprint)

    assert record.status == IncidentStatus.PR_READY
    assert saved is not None
    assert saved.outcome == "pending_approval"
    assert "deployment" in saved.root_cause.lower()


def test_low_confidence_path_escalates_without_pr(tmp_path: Path) -> None:
    dataset = {
        ("checkout-api", "prod"): {"deployments": [], "metrics": [], "logs": []},
    }
    engine = build_engine(tmp_path, azure_tool=MockAzureMonitorTool(dataset=dataset))
    record = engine.ingest_incident(build_incident("inc-009"))

    assert record.status == IncidentStatus.ESCALATED
    assert "confidence below threshold" in (record.last_error or "").lower()
    assert record.approval_package is None


def test_tool_outage_retries_then_escalates_safely(tmp_path: Path) -> None:
    class FailingAzureTool(MockAzureMonitorTool):
        def get_recent_deployments(self, service: str, env: str):
            raise TimeoutError("Azure Monitor query timeout")

    engine = build_engine(
        tmp_path,
        azure_tool=FailingAzureTool(),
        tool_retry_attempts=2,
    )
    record = engine.ingest_incident(build_incident("inc-010"))
    failures = [
        event
        for event in record.events
        if event.event == PipelineEvent.INVESTIGATION_COMPLETED and event.payload.get("status") == "failed"
    ]

    assert record.status == IncidentStatus.ESCALATED
    assert len(failures) == 2
    assert "investigation attempt 2 failed" in (record.last_error or "").lower()


def test_bad_patch_path_stops_after_retry_limit(tmp_path: Path) -> None:
    engine = build_engine(tmp_path, ci_runner=CIRunner(force_canary_failure=True))
    record = engine.ingest_incident(build_incident("inc-011"))
    verification_events = [
        event
        for event in record.events
        if event.event == PipelineEvent.VERIFICATION_COMPLETED
    ]

    assert record.status == IncidentStatus.ESCALATED
    assert record.patch_attempts == 2
    assert len(verification_events) == 2
    assert "verification failed after maximum patch attempts" in (record.last_error or "").lower()
