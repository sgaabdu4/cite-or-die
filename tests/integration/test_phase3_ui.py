from pathlib import Path

from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.core.config import get_settings


def test_phase3_ui_wires_streaming_and_pdfjs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/")

    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")
    layout_resizer_js = Path("src/cite_or_die/ui/layout_resizer.js").read_text(encoding="utf-8")
    settings_panel_js = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")
    source_viewer_js = Path("src/cite_or_die/ui/source_viewer.js").read_text(encoding="utf-8")
    workspace_setup_js = Path("src/cite_or_die/ui/workspace_setup.js").read_text(encoding="utf-8")
    workspace_css = Path("src/cite_or_die/ui/workspace.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'href="/static/workspace.css?v=workspace-setup-v1"' in response.text
    assert 'type="module" src="/static/app.js?v=workspace-setup-v1"' in response.text
    assert 'id="workspace-summary"' in response.text
    assert 'id="open-workspace-setup"' in response.text
    assert 'id="workspace-setup-modal"' in response.text
    assert "Tenants separate provider credentials." in response.text
    assert "Provider settings" in response.text
    assert "Upload sources" in response.text
    assert "Choose file" in response.text
    assert "Ask from this matter" in response.text
    assert "No citation selected" in response.text
    assert "Access token" in response.text
    assert 'id="sources-resizer"' in response.text
    assert "Resize sources panel" in response.text
    assert "/chat/stream" in app_js
    assert "layout_resizer.js" in app_js
    assert "settings_panel.js" in app_js
    assert "workspace_setup.js" in app_js
    assert "doc_ids" in app_js
    assert "selectedDocIds" in app_js
    assert "beginSourcesResize" in layout_resizer_js
    assert "handleSourcesResizeKey" in layout_resizer_js
    assert "initSettingsPanel" in settings_panel_js
    assert "initWorkspaceSetup" in workspace_setup_js
    assert "workspaceSummary" in workspace_setup_js
    assert "onScopeChange" in workspace_setup_js
    assert "dispatchEvent" in workspace_setup_js
    assert ".workspace-switcher" in workspace_css
    assert ".setup-modal" in workspace_css
    assert "pdfjsLib.getDocument" in app_js
    assert "GlobalWorkerOptions.workerSrc" in app_js
    assert "renderPdfTextLayer" in app_js
    assert "resetCitationViewer" in app_js
    assert "resetCitationViewer();" in app_js
    assert "catch (error)" in app_js
    assert "finally" in app_js
    assert "No answer returned." in app_js
    assert "Chat API is offline or unreachable." in app_js
    assert "Chat response was not valid JSON." in app_js
    assert "segmentRanges" in source_viewer_js
    assert 'document.createElement("mark")' in app_js
