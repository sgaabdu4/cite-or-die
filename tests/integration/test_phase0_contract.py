from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app as phase0_app
from cite_or_die.core.config import get_settings


def test_phase0_smoke_contract_response_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "dev")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(phase0_app) as client:
        upload = client.post(
            "/upload",
            files={
                "file": (
                    "tesla_10k.html",
                    b"Tesla disclosed customer concentration risk in this filing.",
                    "text/html",
                )
            },
        )
        assert upload.status_code == 200

        chat = client.post(
            "/chat",
            json={
                "question": "customer concentration?",
                "matter_id": "m_default",
                "session_id": "00000000-0000-0000-0000-000000000001",
                "stream": False,
            },
        )

    assert chat.status_code == 200
    body = chat.json()
    assert body["citation_valid_count"] > 0
    assert body["citations"][0]["text_excerpt"]


def test_phase0_make_targets_exist() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "seed-tesla: download-tesla" in makefile
    assert "scripts/download_corpus.py --tesla-only" in makefile
    assert "e2e-local: setup seed-tesla" in makefile
    assert "pytest tests/unit tests/integration tests/eval" in makefile
