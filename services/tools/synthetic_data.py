from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from contracts.models import IncidentEnvelope, utcnow_iso


def default_telemetry_dataset() -> dict[tuple[str, str], dict[str, list[dict[str, Any]]]]:
    return {
        ("checkout-api", "prod"): {
            "deployments": [
                {
                    "deployment_id": "dep-2026-02-14-01",
                    "version": "2026.02.14.1",
                    "timestamp": "2026-02-14T11:15:00+00:00",
                    "commit": "a12b34c",
                },
                {
                    "deployment_id": "dep-2026-02-14-02",
                    "version": "2026.02.14.2",
                    "timestamp": "2026-02-14T11:42:00+00:00",
                    "commit": "d98e76f",
                },
            ],
            "metrics": [
                {
                    "timestamp": "2026-02-14T11:45:00+00:00",
                    "name": "http_5xx_rate",
                    "value": 0.18,
                    "endpoint": "/checkout",
                },
                {
                    "timestamp": "2026-02-14T11:46:00+00:00",
                    "name": "p95_latency_ms",
                    "value": 1480,
                    "endpoint": "/checkout",
                },
                {
                    "timestamp": "2026-02-14T11:47:00+00:00",
                    "name": "http_5xx_rate",
                    "value": 0.21,
                    "endpoint": "/checkout",
                },
            ],
            "logs": [
                {
                    "timestamp": "2026-02-14T11:46:30+00:00",
                    "level": "ERROR",
                    "message": "Upstream timeout when contacting payments dependency",
                    "endpoint": "/checkout",
                },
                {
                    "timestamp": "2026-02-14T11:47:10+00:00",
                    "level": "ERROR",
                    "message": "Retry budget exhausted for payment provider",
                    "endpoint": "/checkout",
                },
            ],
        }
    }


def synthetic_5xx_incident(
    incident_id: str = "inc-5xx-0001",
    service: str = "checkout-api",
    env: str = "prod",
) -> IncidentEnvelope:
    return IncidentEnvelope(
        incident_id=incident_id,
        service=service,
        env=env,
        start_time=utcnow_iso(),
        signal_type="http_5xx_rate",
        signal_payload={
            "error_rate": 0.21,
            "endpoint": "/checkout",
            "baseline_error_rate": 0.01,
            "latency_p95_ms": 1480,
        },
        runbook_hint="rollback_recent_release_or_increase_upstream_timeout",
    )


class InMemoryPatternCache:
    def __init__(self) -> None:
        self.records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(self, fingerprint: str, payload: dict[str, Any]) -> None:
        self.records[fingerprint].append(deepcopy(payload))

    def get_latest(self, fingerprint: str) -> dict[str, Any] | None:
        history = self.records.get(fingerprint)
        if not history:
            return None
        return deepcopy(history[-1])
