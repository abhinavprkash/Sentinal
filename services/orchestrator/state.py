from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock

from contracts.events import PipelineEvent
from contracts.models import EventLog, IncidentRecord, IncidentStatus, parse_iso


ACTIVE_STATUSES = {
    IncidentStatus.RECEIVED,
    IncidentStatus.INVESTIGATING,
    IncidentStatus.PATCHING,
    IncidentStatus.VERIFYING,
    IncidentStatus.PR_READY,
}


class IncidentStateStore:
    def __init__(self) -> None:
        self._records: dict[str, IncidentRecord] = {}
        self._lock = RLock()

    def create(self, record: IncidentRecord) -> None:
        with self._lock:
            if record.incident.incident_id in self._records:
                raise ValueError(f"Incident already exists: {record.incident.incident_id}")
            self._records[record.incident.incident_id] = record

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self._lock:
            return self._records.get(incident_id)

    def list_all(self) -> list[IncidentRecord]:
        with self._lock:
            return list(self._records.values())

    def append_event(
        self,
        incident_id: str,
        event: PipelineEvent,
        payload: dict | None = None,
    ) -> EventLog:
        with self._lock:
            record = self._records[incident_id]
            event_entry = EventLog(event=event, payload=payload or {})
            record.events.append(event_entry)
            record.mark_updated()
            return event_entry

    def find_recent_duplicates(
        self,
        fingerprint: str,
        exclude_incident_id: str,
        dedupe_window_minutes: int,
    ) -> list[IncidentRecord]:
        with self._lock:
            matches: list[IncidentRecord] = []
            for record in self._records.values():
                if record.incident.incident_id == exclude_incident_id:
                    continue
                if record.incident.fingerprint != fingerprint:
                    continue
                if record.status not in ACTIVE_STATUSES:
                    continue
                updated_at = parse_iso(record.updated_at)
                now = datetime.now(timezone.utc)
                if now - updated_at > timedelta(minutes=dedupe_window_minutes):
                    continue
                matches.append(record)
            return matches
