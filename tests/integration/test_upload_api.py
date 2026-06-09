from pathlib import Path

from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.auth.jwt import issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import Role


def _env(monkeypatch, tmp_path: Path, max_upload_mb: int = 25) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("CITE_OR_DIE_MAX_UPLOAD_MB", str(max_upload_mb))
    get_settings.cache_clear()


def _auth(tenant: str = "tenant-a") -> dict[str, str]:
    token = issue_token(tenant, "alice", [Role.admin], Settings())
    return {"Authorization": f"Bearer {token}"}


def test_upload_rejects_oversized_body_before_ingest(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, tmp_path, max_upload_mb=0)
    with TestClient(app) as client:
        response = client.post(
            "/upload",
            headers=_auth(),
            files={"file": ("too-large.txt", b"x", "text/plain")},
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "upload exceeds 0 MB"
    assert not (tmp_path / "uploads").exists()
