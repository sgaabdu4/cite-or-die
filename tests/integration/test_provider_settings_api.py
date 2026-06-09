"""Integration tests for the /settings/provider endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.auth.jwt import issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import Role

LEAK_CANARY = "sk-leak-canary-9999999999"


def _env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()


def _auth(tenant: str, subject: str, roles: list[Role], matter: str = "m_default") -> dict:
    token = issue_token(tenant, subject, roles, Settings(), matter)
    return {"Authorization": f"Bearer {token}"}


def test_get_returns_404_when_no_config(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/settings/provider", headers=_auth("tenant-a", "alice", [Role.analyst]))
    assert r.status_code == 404


def test_put_first_time_succeeds_as_analyst_wizard(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm_provider"] == "openai"
    assert body["llm_model"] == "gpt-test-1"
    assert "llm_api_key" not in body
    assert LEAK_CANARY not in r.text
    assert body["llm_api_key_fingerprint"]
    assert LEAK_CANARY[-4:] in body["llm_api_key_fingerprint"]


def test_put_after_config_requires_admin(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        as_analyst = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-2",
                "llm_api_key": "sk-second-1234",
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        as_admin = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-2",
                "llm_api_key": "sk-second-1234",
            },
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
    assert as_analyst.status_code == 403
    assert as_admin.status_code == 200
    assert as_admin.json()["llm_model"] == "gpt-test-2"


def test_delete_requires_admin(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/settings/provider",
            json={"llm_provider": "openai", "llm_model": "m", "llm_api_key": LEAK_CANARY},
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        not_admin = client.delete(
            "/settings/provider", headers=_auth("tenant-a", "alice", [Role.analyst])
        )
        admin = client.delete(
            "/settings/provider", headers=_auth("tenant-a", "admin-bob", [Role.admin])
        )
        gone = client.get("/settings/provider", headers=_auth("tenant-a", "alice", [Role.analyst]))
    assert not_admin.status_code == 403
    assert admin.status_code == 200
    assert admin.json() == {"deleted": True}
    assert gone.status_code == 404


def test_on_disk_blob_has_no_plaintext_key(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    enc = tmp_path / "tenants" / "tenant-a" / "provider.enc"
    assert enc.exists()
    blob = enc.read_bytes()
    assert LEAK_CANARY.encode("utf-8") not in blob


def test_cross_tenant_isolation(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": "sk-tenant-a-only",
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        other = client.get(
            "/settings/provider", headers=_auth("tenant-b", "bob", [Role.analyst])
        )
    assert other.status_code == 404


def test_audit_event_recorded_without_key(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    settings = Settings(
        app_env="test",
        data_dir=tmp_path,
        auth_secret="test-secret-with-at-least-32-bytes",
    )
    import sqlite3

    conn = sqlite3.connect(settings.sqlite_path)
    rows = conn.execute(
        "SELECT event_type, payload_json FROM audit_events "
        "WHERE event_type='runtime_config_changed'"
    ).fetchall()
    conn.close()
    assert rows, "no runtime_config_changed audit row"
    for _, payload_json in rows:
        assert LEAK_CANARY not in payload_json


def test_service_resolves_overridden_provider(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    settings = Settings(
        app_env="test",
        data_dir=tmp_path,
        auth_secret="test-secret-with-at-least-32-bytes",
        vector_backend="memory",
        embedding_provider="hash",
        llm_provider="fake",
        allow_hosted_llm=True,
    )
    from cite_or_die.core.service import CiteOrDieService

    service = CiteOrDieService(settings)
    assert service.resolve_provider("tenant-a").name == "fake"

    from pydantic import SecretStr

    from cite_or_die.core.models import ProviderConfigInput

    service.runtime_config.save(
        "tenant-a",
        ProviderConfigInput(
            llm_provider="openai", llm_model="gpt-test-1", llm_api_key=SecretStr(LEAK_CANARY)
        ),
        actor="alice",
    )
    service.invalidate_runtime_config("tenant-a")

    resolved = service.resolve_provider("tenant-a")
    assert resolved.name == "openai"
    # other tenant unaffected
    assert service.resolve_provider("tenant-b").name == "fake"


def test_traversal_tenant_id_rejected(monkeypatch, tmp_path) -> None:
    """JWT-carried tenant_id with unsafe chars must be refused before touching disk."""

    _env(monkeypatch, tmp_path)
    bad = "../pwn"
    with TestClient(app) as client:
        get = client.get("/settings/provider", headers=_auth(bad, "alice", [Role.analyst]))
        put = client.put(
            "/settings/provider",
            json={"llm_provider": "openai", "llm_model": "m", "llm_api_key": "sk"},
            headers=_auth(bad, "alice", [Role.analyst]),
        )
    assert get.status_code == 400
    assert put.status_code == 400
    # Nothing should land outside data_dir/tenants/<safe-id>.
    pwn_path = tmp_path.parent / "pwn"
    assert not pwn_path.exists()


def test_reindex_flag_returned_on_embedding_change(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        first = client.put(
            "/settings/provider",
            json={"llm_provider": "fake", "embedding_provider": "hash", "embedding_dim": 384},
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        second = client.put(
            "/settings/provider",
            json={"llm_provider": "fake", "embedding_provider": "bge-m3", "embedding_dim": 1024},
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
    assert first.status_code == 200
    assert first.json()["requires_reindex"] is False
    assert second.status_code == 200
    assert second.json()["requires_reindex"] is True
