from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import services.orchestrator.app as orchestrator_app_module
from services.orchestrator.config import Settings
from services.orchestrator.engine import SentinelEngine
from services.tools import CIRunner, GitHubClient, MockAzureMonitorTool
from storage import PatternStore


def build_test_engine(tmp_path: Path, *, ci_runner: CIRunner | None = None) -> SentinelEngine:
    db_path = str(tmp_path / "api_patterns.db")
    settings = Settings(
        confidence_threshold=0.65,
        max_patch_attempts=2,
        tool_retry_attempts=2,
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
        azure_tool=MockAzureMonitorTool(),
        github_client=GitHubClient(owner="demo-org", repo="demo-service", mode="mock"),
        ci_runner=ci_runner or CIRunner(),
        pattern_store=PatternStore(db_path),
    )


def test_incident_create_get_and_approve_api(tmp_path: Path) -> None:
    orchestrator_app_module.engine = build_test_engine(tmp_path)
    client = TestClient(orchestrator_app_module.app)

    create_response = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "inc-api-001",
            "service": "checkout-api",
            "env": "prod",
            "signal_type": "http_5xx_rate",
            "signal_payload": {
                "error_rate": 0.21,
                "baseline_error_rate": 0.01,
                "endpoint": "/checkout",
                "latency_p95_ms": 1500,
            },
        },
    )
    assert create_response.status_code == 200
    create_body = create_response.json()
    assert create_body["incident_id"] == "inc-api-001"
    assert create_body["status"] in {"pr_ready", "escalated"}

    get_response = client.get("/api/v1/incidents/inc-api-001")
    assert get_response.status_code == 200
    get_body = get_response.json()
    assert get_body["incident"]["incident_id"] == "inc-api-001"
    assert "stage" in get_body
    assert "confidence" in get_body
    assert "linked_artifacts" in get_body

    if create_body["status"] == "pr_ready":
        approve_response = client.post(
            "/api/v1/incidents/inc-api-001/approve",
            json={"approved_by": "oncall@example.com", "decision": "approve", "notes": "LGTM"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["state_transition"] == "approved_waiting_manual_merge"


def test_retry_api_returns_rerun_status(tmp_path: Path) -> None:
    orchestrator_app_module.engine = build_test_engine(tmp_path, ci_runner=CIRunner(force_test_failure=True))
    client = TestClient(orchestrator_app_module.app)

    create_response = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "inc-api-002",
            "service": "checkout-api",
            "env": "prod",
            "signal_type": "http_5xx_rate",
            "signal_payload": {
                "error_rate": 0.2,
                "baseline_error_rate": 0.01,
                "endpoint": "/checkout",
                "latency_p95_ms": 1400,
            },
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["status"] == "escalated"

    retry_response = client.post(
        "/api/v1/incidents/inc-api-002/retry",
        json={"stage": "triage"},
    )
    assert retry_response.status_code == 200
    retry_body = retry_response.json()
    assert retry_body["incident_id"] == "inc-api-002"
    assert retry_body["status"] in {"escalated", "pr_ready"}
