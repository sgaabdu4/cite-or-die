import fcntl
import hashlib
import json
import os
import stat
import struct
import sys
from pathlib import Path

from typing_extensions import override

from cite_or_die.core.models import AuditEvent
from cite_or_die.observability.metrics import AUDIT_EVENTS
from cite_or_die.security.redaction import redact_payload
from cite_or_die.security.walls import TamperDetectedError
from cite_or_die.storage.sqlite import SqliteStore


class AuditLog(SqliteStore):
    """Append-only hash-chain audit log stored in local SQLite."""

    @override
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
        AUDIT_EVENTS.labels(event.tenant_id, event.event_type.value).inc()
        return event_hash

    def append_event(
        self, tenant_id: str, actor: str, event_type: str, payload: dict[str, object]
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
            rows = conn.execute(
                """
                SELECT id, tenant_id, actor, event_type, payload_json, created_at,
                    previous_hash, event_hash
                FROM audit_events ORDER BY id ASC
                """
            ).fetchall()
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
                raise TamperDetectedError(
                    "audit chain tampered at "
                    f"row_id={row['id']} expected_hash={expected} "
                    f"actual_hash={row['event_hash']}"
                )
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

    def recent(self, limit: int = 50) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, tenant_id, actor, event_type, payload_json, created_at,
                    previous_hash, event_hash
                FROM audit_events ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def seal_filesystem_immutable(self) -> bool:
        # Source: https://www.mexc.com/news/920094 motivates court-provable wall audit logs.
        try:
            if sys.platform == "darwin":
                _append_only_bsd(self.sqlite_path)
            elif sys.platform == "linux":
                _append_only_linux(self.sqlite_path)
            else:
                return False
        except OSError:
            return False
        return True


def _bsd_flags(path: Path) -> int:
    if sys.platform == "darwin":
        return os.stat(path).st_flags
    raise OSError("BSD file flags need macOS")


def _append_only_bsd(path: Path) -> None:
    if sys.platform == "darwin":
        os.chflags(path, _bsd_flags(path) | stat.UF_APPEND)
        return
    raise OSError("BSD file flags need macOS")


FS_APPEND_FL = 0x20


def _ioctl_number(direction: int, number: int) -> int:
    size = struct.calcsize("l")
    return (direction << 30) | (size << 16) | (ord("f") << 8) | number


def _append_only_linux(path: Path) -> None:
    get_flags, set_flags = _ioctl_number(2, 1), _ioctl_number(1, 2)
    fd = os.open(path, os.O_RDONLY)
    try:
        current = struct.unpack("l", fcntl.ioctl(fd, get_flags, struct.pack("l", 0)))[0]
        fcntl.ioctl(fd, set_flags, struct.pack("l", current | FS_APPEND_FL))
    finally:
        os.close(fd)
