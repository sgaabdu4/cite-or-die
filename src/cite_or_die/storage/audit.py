import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from cite_or_die.core.models import AuditEvent
from cite_or_die.security.redaction import redact_payload
from cite_or_die.security.walls import TamperDetectedError


class AuditLog:
    """Append-only hash-chain audit log stored in local SQLite."""

    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                )
                """
            )

    def append(self, event: AuditEvent) -> str:
        payload = redact_payload(event.payload)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            row = conn.execute(
                "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            previous_hash = row["event_hash"] if row else "GENESIS"
            event_hash = self._hash_event(
                event.tenant_id,
                event.actor,
                event.event_type.value,
                payload_json,
                event.created_at.isoformat(),
                previous_hash,
            )
            conn.execute(
                """
                INSERT INTO audit_events (
                    tenant_id, actor, event_type, payload_json, created_at,
                    previous_hash, event_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.tenant_id,
                    event.actor,
                    event.event_type.value,
                    payload_json,
                    event.created_at.isoformat(),
                    previous_hash,
                    event_hash,
                ),
            )
        return event_hash

    def append_event(
        self, tenant_id: str, actor: str, event_type: str, payload: dict[str, Any]
    ) -> str:
        from cite_or_die.core.models import AuditEventType

        return self.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor=actor,
                event_type=AuditEventType(event_type),
                payload=payload,
            )
        )

    def verify_chain(self) -> bool:
        try:
            self.verify_audit_chain()
        except TamperDetectedError:
            return False
        return True

    def verify_audit_chain(self) -> None:
        previous_hash = "GENESIS"
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY id ASC").fetchall()
        for row in rows:
            expected = self._hash_event(
                row["tenant_id"],
                row["actor"],
                row["event_type"],
                row["payload_json"],
                row["created_at"],
                previous_hash,
            )
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                raise TamperDetectedError(f"audit chain tampered at row {row['id']}")
            previous_hash = row["event_hash"]

    @staticmethod
    def _hash_event(
        tenant_id: str,
        actor: str,
        event_type: str,
        payload_json: str,
        created_at: str,
        previous_hash: str,
    ) -> str:
        canonical = json.dumps(
            {
                "tenant_id": tenant_id,
                "actor": actor,
                "event_type": event_type,
                "payload": payload_json,
                "created_at": created_at,
                "previous_hash": previous_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
