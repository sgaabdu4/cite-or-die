import os
from collections.abc import Callable
import sqlite3
import stat
import struct
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from cite_or_die.core.config import Settings
from cite_or_die.core.models import AuditEvent, AuditEventType
from cite_or_die.storage.audit import FS_APPEND_FL, AuditLog, _ioctl_number


def test_audit_redacts_payload_and_verifies_chain(settings: Settings) -> None:
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

    payload_json = row["payload_json"]
    assert isinstance(payload_json, str)
    assert "secret prompt" not in payload_json
    assert "secret doc" not in payload_json
    assert audit.verify_chain()


def test_audit_chain_detects_tampering(settings: Settings) -> None:
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


def _flags_of(value: int) -> Callable[[Path], int]:
    def flags(_path: Path) -> int:
        return value

    return flags


def test_audit_seal_sets_the_bsd_append_flag_on_darwin(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = AuditLog(settings.sqlite_path)
    chflags = Mock()
    monkeypatch.setattr("cite_or_die.storage.audit.sys.platform", "darwin")
    monkeypatch.setattr(os, "chflags", chflags, raising=False)
    monkeypatch.setattr("cite_or_die.storage.audit._bsd_flags", _flags_of(0x2))

    assert audit.seal_filesystem_immutable()
    chflags.assert_called_once_with(settings.sqlite_path, 0x2 | stat.UF_APPEND)


def test_audit_seal_sets_the_append_bit_through_ioctl_on_linux(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = AuditLog(settings.sqlite_path)
    calls: list[tuple[int, bytes]] = []

    def fake_ioctl(_fd: int, request: int, argument: bytes) -> bytes:
        calls.append((request, argument))
        return struct.pack("l", 0x10) if len(calls) == 1 else argument

    monkeypatch.setattr("cite_or_die.storage.audit.sys.platform", "linux")
    monkeypatch.setattr("cite_or_die.storage.audit.fcntl.ioctl", fake_ioctl)

    assert audit.seal_filesystem_immutable()
    assert [request for request, _ in calls] == [
        _ioctl_number(2, 1),
        _ioctl_number(1, 2),
    ]
    assert struct.unpack("l", calls[1][1])[0] == 0x10 | FS_APPEND_FL


@pytest.mark.parametrize("system", ["darwin", "linux"])
def test_audit_seal_returns_false_when_the_call_fails(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, system: str
) -> None:
    audit = AuditLog(settings.sqlite_path)
    monkeypatch.setattr("cite_or_die.storage.audit.sys.platform", system)
    monkeypatch.setattr("cite_or_die.storage.audit._bsd_flags", _flags_of(0))

    def refuse(*_args: object) -> None:
        raise PermissionError

    monkeypatch.setattr(os, "chflags", refuse, raising=False)
    monkeypatch.setattr("cite_or_die.storage.audit.fcntl.ioctl", refuse)

    assert not audit.seal_filesystem_immutable()


def test_audit_seal_returns_false_on_another_platform(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("cite_or_die.storage.audit.sys.platform", "win32")
    assert not AuditLog(settings.sqlite_path).seal_filesystem_immutable()


def test_audit_seal_with_the_real_platform_call(tmp_path: Path) -> None:
    if sys.platform != "darwin":
        assert (_ioctl_number(2, 1), _ioctl_number(1, 2)) == (0x80086601, 0x40086602)
        return
    audit = AuditLog(tmp_path / "audit.sqlite3")
    try:
        assert audit.seal_filesystem_immutable()
        assert os.stat(audit.sqlite_path).st_flags & stat.UF_APPEND
    finally:
        os.chflags(audit.sqlite_path, os.stat(audit.sqlite_path).st_flags & ~stat.UF_APPEND)
