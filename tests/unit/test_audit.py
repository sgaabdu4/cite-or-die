import sqlite3

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
