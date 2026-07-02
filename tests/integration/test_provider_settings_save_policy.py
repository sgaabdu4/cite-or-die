from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.auth.jwt import issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import Role

LEAK_CANARY = "sk-leak-canary-9999999999"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _auth(tenant: str, subject: str, roles: list[Role]) -> dict:
    token = issue_token(tenant, subject, roles, Settings(), "m_default")
    return {"Authorization": f"Bearer {token}"}


def test_put_openai_compatible_local_endpoint_can_save_without_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "prod")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("CITE_OR_DIE_ALLOW_HOSTED_LLM", "false")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "http://localhost:8000/v1",
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )

    assert response.status_code == 200, response.text
    assert response.json()["llm_api_key_fingerprint"] is None


def test_put_first_provider_config_rejects_viewer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        save = client.put(
            "/settings/provider",
            json={"llm_provider": "fake"},
            headers=_auth("tenant-a", "alice", [Role.viewer]),
        )
        status = client.get(
            "/settings/provider",
            headers=_auth("tenant-a", "alice", [Role.viewer]),
        )

    assert save.status_code == 403
    assert save.json()["detail"] == "role not permitted"
    assert status.status_code == 404


def test_put_openai_compatible_remote_endpoint_respects_prod_hosted_block(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "prod")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("CITE_OR_DIE_ALLOW_HOSTED_LLM", "false")
    monkeypatch.setenv("CITE_OR_DIE_PROVIDER_BASE_URL_ALLOWED_HOSTS", "models.example.test")
    get_settings.cache_clear()

    with TestClient(app) as client:
        save = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai-compatible",
                "llm_model": "model-a",
                "llm_base_url": "https://models.example.test/v1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )

    assert save.status_code == 400
    assert save.json()["detail"] == "Hosted model providers are blocked in production."
    assert LEAK_CANARY not in save.text


def test_put_ollama_remote_endpoint_respects_prod_hosted_block(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "prod")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("CITE_OR_DIE_ALLOW_HOSTED_LLM", "false")
    monkeypatch.setenv("CITE_OR_DIE_PROVIDER_BASE_URL_ALLOWED_HOSTS", "models.example.test")
    get_settings.cache_clear()

    with TestClient(app) as client:
        save = client.put(
            "/settings/provider",
            json={
                "llm_provider": "ollama",
                "llm_model": "remote-model",
                "llm_base_url": "https://models.example.test",
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )

    assert save.status_code == 400
    assert save.json()["detail"] == "Hosted model providers are blocked in production."


def test_put_rejects_hosted_provider_when_prod_blocks_hosted_llm(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "prod")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("CITE_OR_DIE_ALLOW_HOSTED_LLM", "false")
    get_settings.cache_clear()

    with TestClient(app) as client:
        save = client.put(
            "/settings/provider",
            json={
                "llm_provider": "openai",
                "llm_model": "gpt-test-1",
                "llm_api_key": LEAK_CANARY,
            },
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )
        status = client.get(
            "/settings/provider",
            headers=_auth("tenant-a", "alice", [Role.analyst]),
        )

    assert save.status_code == 400
    assert save.json()["detail"] == "Hosted model providers are blocked in production."
    assert LEAK_CANARY not in save.text
    assert status.status_code == 404
