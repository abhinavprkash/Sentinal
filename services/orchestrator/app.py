from __future__ import annotations

import uuid

from contracts import (
    ApprovalPackage,
    ApproveRequest,
    IncidentEnvelope,
    RetryRequest,
    to_primitive,
    utcnow_iso,
)
from services.orchestrator.engine import SentinelEngine

try:
    from fastapi import FastAPI, HTTPException
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise RuntimeError("FastAPI is required to run the Sentinel API service.") from exc


app = FastAPI(title="Sentinel Orchestrator", version="0.1.0")
engine = SentinelEngine()


def _ensure_incident_payload(payload: dict) -> dict:
    result = dict(payload)
    result.setdefault("incident_id", f"inc-{uuid.uuid4().hex[:10]}")
    result.setdefault("start_time", utcnow_iso())
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/incidents")
def create_incident(payload: dict) -> dict:
    try:
        normalized = _ensure_incident_payload(payload)
        incident = IncidentEnvelope.from_dict(normalized)
        record = engine.ingest_incident(incident)
        return {"incident_id": incident.incident_id, "status": record.status.value}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - API guardrail
        raise HTTPException(status_code=500, detail=f"Pipeline failure: {exc}") from exc


@app.get("/api/v1/incidents")
def list_incidents() -> dict:
    records = engine.list_incidents()
    return {"incidents": [to_primitive(record) for record in records]}


@app.get("/api/v1/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    record = engine.get_incident(incident_id)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return to_primitive(record)


@app.post("/api/v1/incidents/{incident_id}/approve")
def approve_incident(incident_id: str, payload: dict) -> dict:
    try:
        request = ApproveRequest.from_dict(payload)
        transition = engine.approve_incident(incident_id, request)
        return {"state_transition": transition}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/incidents/{incident_id}/retry")
def retry_incident(incident_id: str, payload: dict) -> dict:
    try:
        request = RetryRequest.from_dict(payload)
        record = engine.retry_incident(incident_id, request)
        return {"incident_id": incident_id, "status": record.status.value, "stage": record.stage}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/incidents/synthetic/5xx")
def generate_synthetic_5xx(payload: dict | None = None) -> dict:
    payload = payload or {}
    incident_payload = {
        "incident_id": payload.get("incident_id", f"inc-synth-{uuid.uuid4().hex[:8]}"),
        "service": payload.get("service", "checkout-api"),
        "env": payload.get("env", "prod"),
        "start_time": utcnow_iso(),
        "signal_type": "http_5xx_rate",
        "signal_payload": {
            "error_rate": float(payload.get("error_rate", 0.21)),
            "baseline_error_rate": float(payload.get("baseline_error_rate", 0.01)),
            "endpoint": payload.get("endpoint", "/checkout"),
            "latency_p95_ms": float(payload.get("latency_p95_ms", 1480.0)),
        },
        "runbook_hint": payload.get("runbook_hint", "rollback_recent_release_or_adjust_timeout"),
    }
    incident = IncidentEnvelope.from_dict(incident_payload)
    record = engine.ingest_incident(incident)
    response = {"incident_id": incident.incident_id, "status": record.status.value}
    if isinstance(record.approval_package, ApprovalPackage):
        response["pr_url"] = record.approval_package.pr_url
    return response
