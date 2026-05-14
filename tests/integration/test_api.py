from fastapi.testclient import TestClient

from cite_or_die.api.app import app


def test_api_upload_chat_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")

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

        chat = client.post(
            "/chat",
            json={"question": "What did the board approve?"},
            headers=headers,
        )

    assert chat.status_code == 200
    body = chat.json()
    assert "Project Falcon" in body["answer"]
    assert body["citations"]
