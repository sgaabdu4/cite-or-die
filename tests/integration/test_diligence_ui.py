from pathlib import Path

from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.core.config import get_settings


def test_diligence_workspace_is_wired_to_app_shell(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/")

    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")
    diligence_js = Path("src/cite_or_die/ui/diligence.js").read_text(encoding="utf-8")
    diligence_css = Path("src/cite_or_die/ui/diligence.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'href="/static/diligence.css?v=diligence-workspace-v1"' in response.text
    assert 'id="diligence-workspace"' in response.text
    assert "AI-enabled Due Diligence Acceleration" in response.text
    assert "Load synthetic deal room" in response.text
    assert "Run accelerator" in response.text
    assert "Risk register" in response.text
    assert "Cross-workstream insights" in response.text
    assert "Report drafts" in response.text
    assert "initDiligenceWorkspace" in app_js
    assert "refreshDocuments" in app_js
    assert "cod:open-citation" in app_js
    assert "/diligence/deals" in diligence_js
    assert "/sources/classify" in diligence_js
    assert "/run" in diligence_js
    assert "refreshDocuments" in diligence_js
    assert "knowledge_base" in diligence_js
    assert "source_doc_ids" in diligence_js
    assert "information_requests" in diligence_js
    assert "report_drafts" in diligence_js
    assert "review_status" in diligence_js
    assert "evidence" in diligence_js
    assert "formatFactValue(fact)" in diligence_js
    assert "fact.unit" in diligence_js
    assert "fact.period" in diligence_js
    assert "new CustomEvent(\"cod:open-citation\"" in diligence_js
    assert "cod:workspace-changed" in app_js
    assert "Northstar Managed Services" in diligence_js
    assert "var(--green)" in diligence_css
    assert "@media (max-width: 880px)" in diligence_css
