from fastapi import HTTPException
from fastapi.testclient import TestClient

from cite_or_die.api.app import app, get_service
from cite_or_die.auth.jwt import issue_token
from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import DocumentChunk, DocumentRecord, Role
from cite_or_die.security.pseudonymization import pseudonymize_pages_for_matter


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


def test_doc_file_serves_pseudonymized_evidence_view(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        token = client.post(
            "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/upload",
            files={
                "file": (
                    "customer.txt",
                    (
                        b"Acme Ltd generated GBP 12m revenue from Barclays. "
                        b"Jane Smith approved the contract."
                    ),
                    "text/plain",
                )
            },
            headers=headers,
        )
        doc_id = upload.json()["document"]["doc_id"]
        evidence = client.get(f"/docs/{doc_id}/file", headers=headers)
        raw = client.get(f"/docs/{doc_id}/raw", headers=headers)

    assert upload.status_code == 200
    assert evidence.status_code == 200
    assert "<TARGET_COMPANY>" in evidence.text
    assert "<CUSTOMER_001>" in evidence.text
    assert "<PERSON_001>" in evidence.text
    assert "Acme Ltd" not in evidence.text
    assert "Barclays" not in evidence.text
    assert "Jane Smith" not in evidence.text
    assert raw.status_code == 200
    assert b"Acme Ltd" in raw.content


def test_doc_file_falls_back_to_scoped_chunks_without_evidence_file(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        token = client.post(
            "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/upload",
            files={
                "file": (
                    "legacy.txt",
                    b"Legacy citation text remains inspectable.",
                    "text/plain",
                )
            },
            headers=headers,
        )
        doc_id = upload.json()["document"]["doc_id"]
        (tmp_path / "uploads" / "evidence" / f"{doc_id}.txt").unlink()
        evidence = client.get(f"/docs/{doc_id}/file", headers=headers)
        other_token = client.post(
            "/dev/token",
            data={"tenant_id": "tenant-a", "matter_id": "matter-other", "subject": "alice"},
        ).json()["access_token"]
        other_source = client.get(
            f"/docs/{doc_id}/file",
            headers={"Authorization": f"Bearer {other_token}"},
        )

    assert evidence.status_code == 200
    assert "Legacy citation text remains inspectable." in evidence.text
    assert other_source.status_code == 404


def test_doc_file_legacy_fallback_does_not_persist_pseudonym_map(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "m_default" / "entities.enc"

    with TestClient(app) as client:
        token = client.post(
            "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        service = client.app.state.service
        service.repository.save_document(
            DocumentRecord(
                doc_id="legacy-doc",
                tenant_id="tenant-a",
                filename="legacy.txt",
                content_type="text/plain",
                sha256="abc",
            ),
            [
                DocumentChunk(
                    tenant_id="tenant-a",
                    doc_id="legacy-doc",
                    filename="legacy.txt",
                    text="Revenue from Barclays was GBP 12m.",
                    ordinal=0,
                )
            ],
        )
        assert not map_path.exists()
        evidence = client.get("/docs/legacy-doc/file", headers=headers)

    assert evidence.status_code == 200
    assert "Revenue from Barclays was GBP 12m." in evidence.text
    assert not map_path.exists()


def test_doc_file_legacy_fallback_reuses_persisted_pseudonym_map(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        token = client.post(
            "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        service = client.app.state.service
        pseudonymize_pages_for_matter(
            [("Revenue from Barclays was GBP 12m.", 1)],
            settings=service.settings,
            tenant_id="tenant-a",
            matter_id="m_default",
        )
        service.repository.save_document(
            DocumentRecord(
                doc_id="legacy-doc",
                tenant_id="tenant-a",
                filename="legacy.txt",
                content_type="text/plain",
                sha256="abc",
            ),
            [
                DocumentChunk(
                    tenant_id="tenant-a",
                    doc_id="legacy-doc",
                    filename="legacy.txt",
                    text="Revenue from Barclays was GBP 12m.",
                    ordinal=0,
                )
            ],
        )
        evidence = client.get("/docs/legacy-doc/file", headers=headers)

    assert evidence.status_code == 200
    assert "Revenue from <CUSTOMER_001> was GBP 12m." in evidence.text


def test_chat_rejects_invalid_scope_id_before_pseudonym_map_access(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()
    settings = Settings(
        app_env="test",
        data_dir=tmp_path,
        auth_secret="test-secret-with-at-least-32-bytes",
    )
    token = issue_token("tenant-a", "alice", [Role.admin], settings, "../bad")

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"question": "What changed?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "matter_id must match ^[A-Za-z0-9_-]{1,64}$"


def test_doc_file_rejects_invalid_scope_id_before_pseudonym_map_access(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()
    settings = Settings(
        app_env="test",
        data_dir=tmp_path,
        auth_secret="test-secret-with-at-least-32-bytes",
    )
    token = issue_token("tenant-a", "alice", [Role.admin], settings, "../bad")

    with TestClient(app) as client:
        response = client.get(
            "/docs/source-doc/file",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "matter_id must match ^[A-Za-z0-9_-]{1,64}$"


def test_upload_returns_409_for_invalid_pseudonym_map(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "m_default" / "entities.enc"
    map_path.parent.mkdir(parents=True)
    map_path.write_bytes(b"bad")

    with TestClient(app) as client:
        token = client.post(
            "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
        ).json()["access_token"]
        response = client.post(
            "/upload",
            files={
                "file": (
                    "customer.txt",
                    b"Acme Ltd generated GBP 12m revenue from Barclays.",
                    "text/plain",
                )
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "pseudonym map is invalid"


def test_chat_returns_409_for_invalid_pseudonym_map(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "m_default" / "entities.enc"
    map_path.parent.mkdir(parents=True)
    map_path.write_bytes(b"bad")

    with TestClient(app) as client:
        token = client.post(
            "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
        ).json()["access_token"]
        response = client.post(
            "/chat",
            json={"question": "What revenue came from Barclays?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "pseudonym map is invalid"


def test_chat_stream_returns_error_event_for_generation_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    class FailingService:
        async def chat(self, _ctx, _request):
            raise HTTPException(status_code=503, detail="provider unavailable")

    app.dependency_overrides[get_service] = lambda: FailingService()
    try:
        with TestClient(app) as client:
            token = client.post(
                "/dev/token", data={"tenant_id": "tenant-a", "subject": "alice"}
            ).json()["access_token"]
            response = client.post(
                "/chat/stream",
                json={"question": "What happened?"},
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: error" in response.text
    assert "provider unavailable" in response.text


def test_dev_token_endpoint_is_not_available_in_prod(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "prod")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post("/dev/token", data={"tenant_id": "tenant-a"})

    assert response.status_code == 404
