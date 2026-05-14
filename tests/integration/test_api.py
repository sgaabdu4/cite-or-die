from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.core.config import get_settings


def test_api_upload_chat_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        token_response = client.post(
            "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
        )
        token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/upload",
            files={"file": ("source.txt", b"The board approved Project Falcon.", "text/plain")},
            headers=headers,
        )
        assert upload.status_code == 200
        doc_id = upload.json()["document"]["doc_id"]

        chat = client.post(
            "/chat",
            json={"question": "What did the board approve?"},
            headers=headers,
        )
        stream = client.post(
            "/chat/stream",
            json={"question": "What did the board approve?"},
            headers=headers,
        )
        source = client.get(f"/docs/{doc_id}/file", headers=headers)
        other_token = client.post(
            "/dev/token",
            data={"tenant_id": "tenant-a", "matter_id": "matter-other", "subject": "alice"},
        ).json()["access_token"]
        other_source = client.get(
            f"/docs/{doc_id}/file",
            headers={"Authorization": f"Bearer {other_token}"},
        )

    assert chat.status_code == 200
    body = chat.json()
    assert "Project Falcon" in body["answer"]
    assert body["citations"]
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "event: answer" in stream.text
    assert source.status_code == 200
    assert source.content == b"The board approved Project Falcon."
    assert other_source.status_code == 404


def test_dev_token_endpoint_is_not_available_in_prod(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "prod")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post("/dev/token", data={"tenant_id": "tenant-a"})

    assert response.status_code == 404
