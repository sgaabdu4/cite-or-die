"""Integration tests for the /settings/provider endpoints."""

from __future__ import annotations

import socket
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

import cite_or_die.api.app as app_module
import cite_or_die.providers.url_policy as url_policy
from cite_or_die.api.app import app
from cite_or_die.auth.jwt import issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import Role

LEAK_CANARY = "sk-leak-canary-9999999999"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


def _env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv(
        "CITE_OR_DIE_PROVIDER_BASE_URL_ALLOWED_HOSTS",
        "provider-a.example,provider-b.example,provider.example,"
        "generativelanguage.googleapis.com",
    )
    get_settings.cache_clear()


def _auth(tenant: str, subject: str, roles: list[Role], matter: str = "m_default") -> dict:
    token = issue_token(tenant, subject, roles, Settings(), matter)
    return {"Authorization": f"Bearer {token}"}


def _tamper_provider_config(tmp_path: Path, tenant: str = "tenant-a") -> None:
    path = tmp_path / "tenants" / tenant / "provider.enc"
    path.write_bytes(b"bad")


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


def test_unreadable_existing_config_is_not_first_setup(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        first = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        _tamper_provider_config(tmp_path)
        analyst_put = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-2",
                "llm_api_key": "sk-second-1234",
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        admin_put = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-2",
                "llm_api_key": "sk-second-1234",
            },
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
        get = client.get("/settings/provider", headers=_auth("tenant-a", "alice", [Role.analyst]))

    assert first.status_code == 200
    assert analyst_put.status_code == 403
    assert admin_put.status_code == 409
    assert get.status_code == 409
    assert admin_put.json()["detail"] == "provider config is unreadable"
    assert get.json()["detail"] == "provider config is unreadable"


def test_put_provider_change_requires_fresh_key(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        first = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        same_provider = client.put(
            "/settings/provider",
            json={"llm_provider": "openai", "llm_model": "gpt-test-2"},
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
        changed_provider = client.put(
            "/settings/provider",
            json={"llm_provider": "anthropic", "llm_model": "claude-test"},
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
    assert first.status_code == 200
    assert same_provider.status_code == 200
    assert changed_provider.status_code == 400
    assert LEAK_CANARY not in changed_provider.text


def test_put_openai_compatible_base_change_without_key_clears_saved_key(
    monkeypatch,
    tmp_path,
) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        first = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "https://provider-a.example/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        same_base = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-b",
                "llm_base_url": "https://provider-a.example/v1",
            },
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
        changed_base_without_key = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-b",
                "llm_base_url": "https://provider-b.example/v1",
            },
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
    assert first.status_code == 200
    assert same_base.status_code == 200
    assert changed_base_without_key.status_code == 200
    assert changed_base_without_key.json()["llm_api_key_fingerprint"] is None
    assert LEAK_CANARY not in changed_base_without_key.text


def test_put_rejects_unsafe_provider_base_url(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        metadata_host = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "http://169.254.169.254/latest",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        localhost = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "http://localhost:8000/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-b", "alice", [Role.analyst]),
        )
    assert metadata_host.status_code == 400
    assert (
        metadata_host.json()["detail"] == "HTTP base URL is only allowed for localhost providers."
    )
    assert LEAK_CANARY not in metadata_host.text
    assert localhost.status_code == 200


def test_put_rejects_non_allowlisted_provider_base_url(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "https://unapproved.example/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "Provider base URL host is not allowlisted."
    assert LEAK_CANARY not in response.text


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
        other = client.get("/settings/provider", headers=_auth("tenant-b", "bob", [Role.analyst]))
    assert other.status_code == 404


def test_provider_connection_test_fake_provider(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/settings/provider/test",
            json={"llm_provider": "fake"},
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["detail"] == "Offline provider ready."
    assert "llm_api_key" not in body


def test_provider_connection_test_and_save_share_default_model(
    monkeypatch,
    tmp_path,
) -> None:
    _env(monkeypatch, tmp_path)

    async def assert_default_model(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> None:
        assert url == "https://api.openai.com/v1/responses"
        assert headers == {"Authorization": f"Bearer {LEAK_CANARY}"}
        assert payload["model"] == "gpt-5.5"

    monkeypatch.setattr(app_module, "_post_provider_test_json", assert_default_model)
    body = {"llm_provider": "openai", "llm_api_key": LEAK_CANARY}
    with TestClient(app) as client:
        tested = client.post(
            "/settings/provider/test",
            json=body,
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        saved = client.put(
            "/settings/provider",
            json=body,
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )

    assert tested.status_code == 200, tested.text
    assert saved.status_code == 200, saved.text
    assert tested.json()["llm_model"] == "gpt-5.5"
    assert saved.json()["llm_model"] == "gpt-5.5"
    assert LEAK_CANARY not in tested.text
    assert LEAK_CANARY not in saved.text


def test_provider_connection_test_reports_missing_gemini_key(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/settings/provider/test",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "gemini-3.5-flash",
                "llm_base_url": GEMINI_BASE_URL,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert body["detail"] == "Gemini API key required."


def test_provider_connection_test_reuses_saved_key_for_model_change(
    monkeypatch,
    tmp_path,
) -> None:
    _env(monkeypatch, tmp_path)

    async def assert_saved_key_reused(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> None:
        assert url == "https://api.openai.com/v1/responses"
        assert headers == {"Authorization": f"Bearer {LEAK_CANARY}"}
        assert payload["model"] == "gpt-test-2"

    monkeypatch.setattr(app_module, "_post_provider_test_json", assert_saved_key_reused)
    with TestClient(app) as client:
        first = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        test = client.post(
            "/settings/provider/test",
            json={"llm_provider": "openai", "llm_model": "gpt-test-2"},
            headers=_auth("tenant-a", "admin-bob", [Role.admin]),
        )
    assert first.status_code == 200
    assert test.status_code == 200, test.text
    assert test.json()["ok"] is True
    assert LEAK_CANARY not in test.text


def test_provider_connection_test_sends_only_minimal_gemini_probe(
    monkeypatch,
    tmp_path,
) -> None:
    _env(monkeypatch, tmp_path)

    async def assert_minimal_probe(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> None:
        assert url == f"{GEMINI_BASE_URL}/chat/completions"
        assert headers == {"Authorization": f"Bearer {LEAK_CANARY}"}
        assert payload == {
            "model": "gemini-3.5-flash",
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 8,
            "temperature": 0,
        }

    monkeypatch.setattr(app_module, "_post_provider_test_json", assert_minimal_probe)
    with TestClient(app) as client:
        test = client.post(
            "/settings/provider/test",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "gemini-3.5-flash",
                "llm_base_url": GEMINI_BASE_URL,
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert test.status_code == 200, test.text
    assert test.json()["ok"] is True
    assert LEAK_CANARY not in test.text


def test_provider_connection_test_rejects_unsafe_base_url(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/settings/provider/test",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "https://10.0.0.5/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert (
        r.json()["detail"] == "Provider base URL cannot target non-public IP addresses."
    )
    assert LEAK_CANARY not in r.text


def test_provider_connection_test_rejects_non_allowlisted_base_url(
    monkeypatch,
    tmp_path,
) -> None:
    _env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/settings/provider/test",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "https://unapproved.example/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert r.json()["detail"] == "Provider base URL host is not allowlisted."
    assert LEAK_CANARY not in r.text


def test_provider_connection_test_rejects_hostname_resolving_private(
    monkeypatch,
    tmp_path,
) -> None:
    _env(monkeypatch, tmp_path)

    def private_dns(hostname: str, port: int | None) -> list:
        assert hostname == "provider.example"
        assert port is None
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.9", 0))]

    monkeypatch.setattr(url_policy.socket, "getaddrinfo", private_dns)
    with TestClient(app) as client:
        r = client.post(
            "/settings/provider/test",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "https://provider.example/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert (
        r.json()["detail"]
        == "Provider base URL cannot resolve to non-public IP addresses."
    )
    assert LEAK_CANARY not in r.text


def test_provider_connection_test_masks_provider_failure(
    monkeypatch,
    tmp_path,
) -> None:
    _env(monkeypatch, tmp_path)

    async def fail_provider_call(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> None:
        assert url == "https://provider.example/v1/chat/completions"
        assert headers == {"Authorization": f"Bearer {LEAK_CANARY}"}
        assert payload["model"] == "model-a"
        request = httpx.Request("POST", url)
        response = httpx.Response(401, request=request, text=f"denied {LEAK_CANARY}")
        raise httpx.HTTPStatusError("denied", request=request, response=response)

    monkeypatch.setattr(app_module, "_post_provider_test_json", fail_provider_call)
    with TestClient(app) as client:
        r = client.post(
            "/settings/provider/test",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "https://provider.example/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
    assert r.status_code == 200, r.text
    assert r.json()["detail"] == "Provider returned HTTP 401."
    assert LEAK_CANARY not in r.text


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
