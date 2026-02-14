from __future__ import annotations

from contracts import (
    ApproveRequest,
    Decision,
    IncidentEnvelope,
    IncidentRecord,
    IncidentStatus,
    PatternRecord,
    PipelineEvent,
    RetryRequest,
    to_primitive,
    utcnow_iso,
)
from services.orchestrator.agents import (
    ApprovalAgent,
    InvestigationAgent,
    PatchAgent,
    TriageAgent,
)
from services.orchestrator.config import Settings
from services.orchestrator.framework_adapters import detect_framework_status
from services.orchestrator.state import IncidentStateStore
from services.orchestrator.telemetry import traced_span
from services.tools import CIRunner, CopilotPatchGenerator, GitHubClient, MockAzureMonitorTool
from services.tools.github_client import PullRequestInfo
from services.verification import VerificationRunner
from storage import PatternStore


class SentinelEngine:
    def __init__(
        self,
        settings: Settings | None = None,
        azure_tool: MockAzureMonitorTool | None = None,
        github_client: GitHubClient | None = None,
        ci_runner: CIRunner | None = None,
        pattern_store: PatternStore | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.framework_status = detect_framework_status()
        self.state_store = IncidentStateStore()
        self.pattern_store = pattern_store or PatternStore(self.settings.pattern_db_path)
        self.azure_tool = azure_tool or MockAzureMonitorTool()
        self.github_client = github_client or GitHubClient(
            owner=self.settings.github_owner,
            repo=self.settings.github_repo,
            token=self.settings.github_token,
            mode=self.settings.github_mode,
        )
        self.ci_runner = ci_runner or CIRunner()

        self.triage_agent = TriageAgent(self.settings.autonomous_envs)
        self.investigation_agent = InvestigationAgent(self.azure_tool, self.pattern_store)
        self.patch_agent = PatchAgent(
            CopilotPatchGenerator(repo_slug=self.github_client.repo_slug),
        )
        self.verification_runner = VerificationRunner(self.ci_runner)
        self.approval_agent = ApprovalAgent(base_branch=self.settings.base_branch)

    def ingest_incident(self, incident: IncidentEnvelope) -> IncidentRecord:
        record = IncidentRecord(incident=incident, started_at=utcnow_iso())
        self.state_store.create(record)
        self.state_store.append_event(
            incident.incident_id,
            PipelineEvent.INCIDENT_RECEIVED,
            payload={
                "signal_type": incident.signal_type,
                "semantic_kernel_available": self.framework_status.semantic_kernel_available,
                "autogen_available": self.framework_status.autogen_available,
            },
        )
        self._run_pipeline(incident.incident_id, start_stage="triage")
        return self.require_incident(incident.incident_id)

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        return self.state_store.get(incident_id)

    def require_incident(self, incident_id: str) -> IncidentRecord:
        record = self.state_store.get(incident_id)
        if not record:
            raise KeyError(f"Incident not found: {incident_id}")
        return record

    def list_incidents(self) -> list[IncidentRecord]:
        return self.state_store.list_all()

    def approve_incident(self, incident_id: str, approve_request: ApproveRequest) -> str:
        record = self.require_incident(incident_id)
        if record.status != IncidentStatus.PR_READY:
            raise ValueError("Incident is not awaiting approval.")
        if approve_request.decision == Decision.APPROVE:
            record.status = IncidentStatus.APPROVED
            record.stage = "approved"
            transition = "approved_waiting_manual_merge"
            self.state_store.append_event(
                incident_id,
                PipelineEvent.INCIDENT_APPROVED,
                payload={"approved_by": approve_request.approved_by, "notes": approve_request.notes},
            )
        else:
            record.status = IncidentStatus.REJECTED
            record.stage = "rejected"
            transition = "rejected_manual_followup_required"
            self.state_store.append_event(
                incident_id,
                PipelineEvent.INCIDENT_REJECTED,
                payload={"approved_by": approve_request.approved_by, "notes": approve_request.notes},
            )
        record.mark_updated()
        return transition

    def retry_incident(self, incident_id: str, retry_request: RetryRequest) -> IncidentRecord:
        record = self.require_incident(incident_id)
        self.state_store.append_event(
            incident_id,
            PipelineEvent.RETRY_TRIGGERED,
            payload={"requested_stage": retry_request.stage},
        )
        record.last_error = None
        record.finished_at = None
        record.patch = None
        record.verification = None
        record.approval_package = None
        record.linked_artifacts = {}
        self._run_pipeline(incident_id, start_stage=retry_request.stage)
        return record

    def _run_pipeline(self, incident_id: str, start_stage: str = "triage") -> None:
        record = self.require_incident(incident_id)
        incident = record.incident

        if start_stage in {"received", "triage"}:
            with traced_span("triage", {"incident_id": incident_id, "service": incident.service}):
                duplicates = self.state_store.find_recent_duplicates(
                    incident.fingerprint,
                    exclude_incident_id=incident_id,
                    dedupe_window_minutes=self.settings.dedupe_window_minutes,
                )
                triage_result = self.triage_agent.evaluate(incident, has_duplicates=bool(duplicates))
                self.state_store.append_event(
                    incident_id,
                    PipelineEvent.TRIAGE_COMPLETED,
                    payload={
                        "status": triage_result.status.value,
                        "severity": triage_result.severity.value,
                        "reason": triage_result.reason,
                    },
                )
                record.status = triage_result.status
                record.stage = "triage"
                if triage_result.status in {IncidentStatus.DUPLICATE, IncidentStatus.BLOCKED}:
                    record.last_error = triage_result.reason
                    record.finished_at = utcnow_iso()
                    record.mark_updated()
                    return

        investigation = None
        with traced_span("investigation", {"incident_id": incident_id}):
            record.status = IncidentStatus.INVESTIGATING
            record.stage = "investigating"
            record.mark_updated()

            investigation_error = None
            for attempt in range(1, self.settings.tool_retry_attempts + 1):
                try:
                    investigation = self.investigation_agent.investigate(incident)
                    break
                except Exception as exc:  # pragma: no cover - defensive path
                    investigation_error = f"Investigation attempt {attempt} failed: {exc}"
                    self.state_store.append_event(
                        incident_id,
                        PipelineEvent.INVESTIGATION_COMPLETED,
                        payload={
                            "attempt": attempt,
                            "status": "failed",
                            "error": str(exc),
                        },
                    )

            if investigation is None:
                self._escalate(record, investigation_error or "Investigation failed.")
                return

            record.investigation = investigation
            record.confidence = investigation.confidence
            self.state_store.append_event(
                incident_id,
                PipelineEvent.INVESTIGATION_COMPLETED,
                payload={"status": "completed", "confidence": investigation.confidence},
            )

            if investigation.confidence < self.settings.confidence_threshold:
                self._escalate(
                    record,
                    (
                        "Confidence below threshold: "
                        f"{investigation.confidence:.2f} < {self.settings.confidence_threshold:.2f}"
                    ),
                )
                return

        with traced_span("patch_and_verify", {"incident_id": incident_id}):
            for attempt in range(1, self.settings.max_patch_attempts + 1):
                record.status = IncidentStatus.PATCHING
                record.stage = "patching"
                patch = self.patch_agent.propose_patch(
                    incident=incident,
                    investigation=record.investigation,
                    attempt=attempt,
                )
                record.patch_attempts += 1
                record.patch = patch
                self.state_store.append_event(
                    incident_id,
                    PipelineEvent.PATCH_GENERATED,
                    payload={"attempt": attempt, "branch": patch.branch, "files": patch.changed_files},
                )

                record.status = IncidentStatus.VERIFYING
                record.stage = "verifying"
                verification = self.verification_runner.verify(incident, patch)
                record.verification = verification
                self.state_store.append_event(
                    incident_id,
                    PipelineEvent.VERIFICATION_COMPLETED,
                    payload={
                        "attempt": attempt,
                        "pass_fail": verification.pass_fail,
                        "regressions": verification.regression_flags,
                    },
                )
                if verification.pass_fail:
                    self._create_approval_package(record)
                    return

            self._escalate(record, "Verification failed after maximum patch attempts.")

    def _create_approval_package(self, record: IncidentRecord) -> None:
        incident = record.incident
        investigation = record.investigation
        patch = record.patch
        verification = record.verification
        if not investigation or not patch or not verification:
            self._escalate(record, "Missing artifacts for approval package generation.")
            return

        placeholder_pr = PullRequestInfo(
            pr_url="pending",
            number=None,
            title=f"[Sentinel] Fix 5xx regression for {incident.service}",
            head_branch=patch.branch,
            base_branch=self.settings.base_branch,
        )
        provisional_package = self.approval_agent.build_approval_package(
            incident=incident,
            investigation=investigation,
            patch=patch,
            verification=verification,
            pr_info=placeholder_pr,
        )
        pr_body = self.approval_agent.build_pr_body(
            incident=incident,
            investigation=investigation,
            patch=patch,
            verification=verification,
            package=provisional_package,
        )
        pr_info = self.github_client.create_draft_pr(
            title=f"[Sentinel] Fix 5xx regression for {incident.service}",
            body=pr_body,
            head_branch=patch.branch,
            base_branch=self.settings.base_branch,
        )
        approval_package = self.approval_agent.build_approval_package(
            incident=incident,
            investigation=investigation,
            patch=patch,
            verification=verification,
            pr_info=pr_info,
        )
        self.state_store.append_event(
            incident.incident_id,
            PipelineEvent.APPROVAL_PACKAGE_READY,
            payload={"pr_url": approval_package.pr_url, "body_preview": pr_body[:200]},
        )

        record.approval_package = approval_package
        record.linked_artifacts = {
            "pr_url": approval_package.pr_url,
            "evidence_links": approval_package.evidence_links,
        }
        record.status = IncidentStatus.PR_READY
        record.stage = "approval"
        record.finished_at = utcnow_iso()
        record.mark_updated()

        self.pattern_store.save(
            PatternRecord(
                fingerprint=incident.fingerprint,
                root_cause=investigation.reason,
                fix_signature=patch.diff_summary,
                outcome="pending_approval",
            )
        )

    def _escalate(self, record: IncidentRecord, reason: str) -> None:
        record.status = IncidentStatus.ESCALATED
        record.stage = "escalated"
        record.last_error = reason
        record.finished_at = utcnow_iso()
        record.mark_updated()
        self.state_store.append_event(
            record.incident.incident_id,
            PipelineEvent.INCIDENT_ESCALATED,
            payload={"reason": reason},
        )

    def snapshot(self, incident_id: str) -> dict:
        record = self.require_incident(incident_id)
        return to_primitive(record)
