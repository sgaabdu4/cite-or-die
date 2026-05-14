import sqlite3
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
