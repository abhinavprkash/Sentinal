from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from contracts.events import PipelineEvent


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def dataclass_from_dict(data_class: type[Any], payload: dict[str, Any]) -> Any:
    kwargs: dict[str, Any] = {}
    for data_field in fields(data_class):
        raw = payload.get(data_field.name)
        if raw is None:
            continue
        if isinstance(data_field.type, type) and issubclass(data_field.type, Enum):
            kwargs[data_field.name] = data_field.type(raw)
        elif hasattr(data_field.type, "__origin__") and data_field.type.__origin__ is list:
            kwargs[data_field.name] = list(raw)
        else:
            kwargs[data_field.name] = raw
    return data_class(**kwargs)


def to_primitive(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_primitive(val) for key, val in value.__dict__.items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: to_primitive(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_primitive(item) for item in value]
    return value


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    RECEIVED = "received"
    DUPLICATE = "duplicate"
    BLOCKED = "blocked"
    INVESTIGATING = "investigating"
    PATCHING = "patching"
    VERIFYING = "verifying"
    PR_READY = "pr_ready"
    ESCALATED = "escalated"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class Decision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass
class IncidentEnvelope:
    incident_id: str
    service: str
    env: str
    start_time: str
    signal_type: str
    signal_payload: dict[str, Any]
    runbook_hint: str | None = None

    @property
    def fingerprint(self) -> str:
        endpoint = self.signal_payload.get("endpoint", "global")
        return f"{self.service}:{self.env}:{self.signal_type}:{endpoint}"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IncidentEnvelope":
        required = ("incident_id", "service", "env", "signal_type", "signal_payload")
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"Missing required incident fields: {', '.join(missing)}")
        start_time = payload.get("start_time", utcnow_iso())
        return cls(
            incident_id=str(payload["incident_id"]),
            service=str(payload["service"]),
            env=str(payload["env"]),
            start_time=str(start_time),
            signal_type=str(payload["signal_type"]),
            signal_payload=dict(payload["signal_payload"]),
            runbook_hint=payload.get("runbook_hint"),
        )


@dataclass
class InvestigationPacket:
    suspected_release: str
    affected_endpoints: list[str]
    correlated_metrics: dict[str, Any]
    log_evidence: list[str]
    confidence: float
    reason: str


@dataclass
class PatchProposal:
    repo: str
    branch: str
    changed_files: list[str]
    diff_summary: str
    hypothesis: str
    risk_level: str
    patch_text: str


@dataclass
class VerificationReport:
    test_results: dict[str, str]
    canary_replay_result: dict[str, Any]
    regression_flags: list[str]
    pass_fail: bool


@dataclass
class ApprovalPackage:
    pr_url: str
    rca_summary: str
    evidence_links: dict[str, str]
    rollback_steps: list[str]
    telemetry_snapshot: dict[str, Any]


@dataclass
class PatternRecord:
    fingerprint: str
    root_cause: str
    fix_signature: str
    outcome: str
    created_at: str = field(default_factory=utcnow_iso)


@dataclass
class EventLog:
    event: PipelineEvent
    timestamp: str = field(default_factory=utcnow_iso)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidentRecord:
    incident: IncidentEnvelope
    status: IncidentStatus = IncidentStatus.RECEIVED
    stage: str = "received"
    confidence: float = 0.0
    last_error: str | None = None
    linked_artifacts: dict[str, Any] = field(default_factory=dict)
    events: list[EventLog] = field(default_factory=list)
    investigation: InvestigationPacket | None = None
    patch: PatchProposal | None = None
    verification: VerificationReport | None = None
    approval_package: ApprovalPackage | None = None
    patch_attempts: int = 0
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    started_at: str = field(default_factory=utcnow_iso)
    finished_at: str | None = None

    @property
    def processing_seconds(self) -> float:
        end = parse_iso(self.finished_at) if self.finished_at else datetime.now(timezone.utc)
        start = parse_iso(self.started_at)
        return max(0.0, (end - start).total_seconds())

    def mark_updated(self) -> None:
        self.updated_at = utcnow_iso()


@dataclass
class ApproveRequest:
    approved_by: str
    decision: Decision
    notes: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ApproveRequest":
        return cls(
            approved_by=str(payload.get("approved_by", "unknown")),
            decision=Decision(str(payload["decision"])),
            notes=payload.get("notes"),
        )


@dataclass
class RetryRequest:
    stage: str = "triage"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RetryRequest":
        return cls(stage=str(payload.get("stage", "triage")))
