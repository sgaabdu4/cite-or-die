import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError
from unittest.mock import Mock

from cite_or_die.core.models import AuditEvent, AuditEventType
from cite_or_die.storage.audit import AuditLog


def test_audit_redacts_payload_and_verifies_chain(settings) -> None:
    audit = AuditLog(settings.sqlite_path)
    audit.append(
        AuditEvent(
            tenant_id="tenant-a",
            actor="alice",
            event_type=AuditEventType.chat,
            payload={
                "request_id": "req-1",
                "prompt": "secret prompt",
                "doc_content": "secret doc",
            },
        )
    )

    row = audit.recent(1)[0]

    assert "secret prompt" not in row["payload_json"]
    assert "secret doc" not in row["payload_json"]
    assert audit.verify_chain()


def test_audit_chain_detects_tampering(settings) -> None:
    audit = AuditLog(settings.sqlite_path)
    audit.append(
        AuditEvent(
            tenant_id="tenant-a",
            actor="alice",
            event_type=AuditEventType.chat,
            payload={"request_id": "req-1"},
        )
    )

    with sqlite3.connect(settings.sqlite_path) as conn:
        conn.execute(
            "UPDATE audit_events SET payload_json = ? WHERE id = 1", ('{"request_id":"x"}',)
        )

    assert not audit.verify_chain()


def test_audit_appends_serialize_hash_chain_under_concurrency(settings, monkeypatch) -> None:
    worker_count = 8
    audit = AuditLog(settings.sqlite_path)
    logs = [AuditLog(settings.sqlite_path) for _ in range(worker_count)]
    barrier = Barrier(worker_count)
    original_hash_event = AuditLog._hash_event

    def hash_event_with_race_window(
        tenant_id: str,
        actor: str,
        event_type: str,
        payload_json: str,
        created_at: str,
        previous_hash: str,
    ) -> str:
        if previous_hash == "GENESIS":
            try:
                barrier.wait(timeout=0.25)
            except BrokenBarrierError:
                pass
        return original_hash_event(
            tenant_id,
            actor,
            event_type,
            payload_json,
            created_at,
            previous_hash,
        )

    monkeypatch.setattr(AuditLog, "_hash_event", staticmethod(hash_event_with_race_window))

    def append_event(index: int) -> str:
        return logs[index].append(
            AuditEvent(
                tenant_id="tenant-a",
                actor=f"analyst-{index}",
                event_type=AuditEventType.diligence,
                payload={"request_id": f"req-{index}"},
            )
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        event_hashes = list(executor.map(append_event, range(worker_count)))

    assert len(set(event_hashes)) == worker_count
    assert audit.verify_chain()


def test_audit_seal_uses_platform_immutable_flag(settings, monkeypatch) -> None:
    audit = AuditLog(settings.sqlite_path)
    run = Mock()
    monkeypatch.setattr("cite_or_die.storage.audit.platform.system", lambda: "Darwin")
    monkeypatch.setattr("cite_or_die.storage.audit.subprocess.run", run)

    assert audit.seal_filesystem_immutable()
    run.assert_called_once_with(
        ["chflags", "uappnd", str(settings.sqlite_path)],
        check=True,
        capture_output=True,
    )
