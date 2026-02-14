from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from contracts.models import PatternRecord


class PatternStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = Lock()
        self._ensure_db()

    def _ensure_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pattern_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    fix_signature TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, record: PatternRecord) -> None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pattern_records (fingerprint, root_cause, fix_signature, outcome, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.fingerprint,
                    record.root_cause,
                    record.fix_signature,
                    record.outcome,
                    record.created_at,
                ),
            )
            conn.commit()

    def find_latest(self, fingerprint: str) -> PatternRecord | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT fingerprint, root_cause, fix_signature, outcome, created_at
                FROM pattern_records
                WHERE fingerprint = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (fingerprint,),
            ).fetchone()
        if not row:
            return None
        return PatternRecord(
            fingerprint=row[0],
            root_cause=row[1],
            fix_signature=row[2],
            outcome=row[3],
            created_at=row[4],
        )

    def list_recent(self, limit: int = 20) -> list[PatternRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT fingerprint, root_cause, fix_signature, outcome, created_at
                FROM pattern_records
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PatternRecord(
                fingerprint=row[0],
                root_cause=row[1],
                fix_signature=row[2],
                outcome=row[3],
                created_at=row[4],
            )
            for row in rows
        ]
