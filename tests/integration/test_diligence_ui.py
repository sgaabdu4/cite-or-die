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
    settings_panel_js = Path("src/cite_or_die/ui/settings_panel.js").read_text(
        encoding="utf-8"
    )
    workbench_css = Path("src/cite_or_die/ui/workbench.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'href="/static/diligence.css?v=diligence-workspace-v1"' in response.text
    assert 'href="/static/workbench.css?v=deal-command-v6"' in response.text
    assert 'id="setup-strip" class="setup-strip"' in response.text
    assert 'id="setup-heading"' in response.text
    assert 'class="setup-step-copy"' in response.text
    assert 'id="setup-provider-action"' in response.text
    assert 'id="setup-deal-title"' in response.text
    assert 'id="setup-run-title"' in response.text
    assert 'id="diligence-load-selected"' in response.text
    assert 'class="setup-step-actions"' in response.text
    assert 'class="workbench-grid"' in response.text
    assert 'id="diligence-workspace"' in response.text
    assert "Diligence Accelerator" in response.text
    assert "Deal command center" in response.text
    assert "AI-enabled Due Diligence Acceleration" in response.text
    assert "Evidence tools" in response.text
    assert "Cited questions" in response.text
    assert 'aria-label="Model provider"' in response.text
    assert 'class="settings-setup-list"' in response.text
    assert 'id="settings-guide-provider"' in response.text
    assert 'id="settings-guide-key"' in response.text
    assert 'id="settings-guide-test"' in response.text
    assert '<details class="settings-advanced-section">' in response.text
    assert "Advanced retrieval settings" in response.text
    assert "Server defaults are usually right" in response.text
    assert "Load sample deal room" in response.text
    assert "Run diligence review" in response.text
    assert "Gemini" in response.text
    assert 'id="settings-test"' in response.text
    assert 'id="settings-key-guidance"' in response.text
    assert 'id="settings-key-toggle"' in response.text
    assert 'id="settings-key-clear"' in response.text
    assert 'id="settings-save-guidance"' in response.text
    assert 'aria-label="API key entry controls"' in response.text
    assert "Deal-room sources are not sent" in response.text
    assert "during setup" in response.text
    assert 'class="provider-readiness"' in response.text
    assert 'id="settings-readiness-key"' in response.text
    assert 'id="settings-readiness-test"' in response.text
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
    assert "updateSetupState" in diligence_js
    assert "updateSetupProgressDisclosure" in diligence_js
    assert "setup-progress-v2" in diligence_js
    assert 'card.dataset.setupState = "locked"' in diligence_js
    assert "formatFactValue(fact)" in diligence_js
    assert "fact.unit" in diligence_js
    assert "fact.period" in diligence_js
    assert "nodes.run.disabled = state.busy || !state.deal" in diligence_js
    assert "loadSelectedSources" in diligence_js
    assert "createSelectedDeal" in diligence_js
    assert "Selected Source Review" in diligence_js
    assert "selectedSourceIds()" in diligence_js
    assert 'new CustomEvent("cod:open-citation"' in diligence_js
    assert "cod:workspace-changed" in app_js
    assert "cod:source-selection-changed" in app_js
    assert "selectedDocIds" in app_js
    assert "diligence-workspace-v3" in app_js
    assert "provider-setup-v8" in response.text
    assert "provider-setup-v7" in app_js
    assert "Northstar Managed Services" in diligence_js
    assert "GEMINI_BASE_URL" in settings_panel_js
    assert "/settings/provider/test" in settings_panel_js
    assert "PROVIDER_GUIDANCE" in settings_panel_js
    assert "OpenAI uses the default OpenAI API endpoint" in settings_panel_js
    assert "OpenAI Responses API" in settings_panel_js
    assert "Use a Gemini API key from Google AI Studio." in settings_panel_js
    assert "Anthropic uses the native Claude Messages API." in settings_panel_js
    assert "Ollama runs locally" in settings_panel_js
    assert "updateProviderGuidance(provider)" in settings_panel_js
    assert "Connection verified" in settings_panel_js
    assert "canReuseSavedKey" in settings_panel_js
    assert "apiKeyInputIssue" in settings_panel_js
    assert "setKeyVisibility" in settings_panel_js
    assert "keyEntryVersion" in settings_panel_js
    assert "clearUnsavedKey" in settings_panel_js
    assert "clearKeyEntry" in settings_panel_js
    assert "canSaveCurrentConfig" in settings_panel_js
    assert "Test this provider before saving." in settings_panel_js
    assert "This looks like JSON or a multi-line credential" in settings_panel_js
    assert "This looks like an OAuth token" in settings_panel_js
    assert "Test connection before saving" in settings_panel_js
    assert "New write-only key entered" in settings_panel_js
    assert "Retest after changes" in settings_panel_js
    assert "Change provider" in settings_panel_js
    assert "updateSetupProgressDisclosure" in settings_panel_js
    assert "setup-progress-v2" in settings_panel_js
    assert ".advanced-controls" in workbench_css
    assert ".workbench-grid:has(.diligence-workspace[data-deal-state=\"empty\"])" in workbench_css
    assert ".diligence-empty-start" in workbench_css
    assert ".setup-strip" in workbench_css
    assert ".provider-readiness" in workbench_css
    assert ".settings-field-note" in workbench_css
    assert ".settings-secret-control" in workbench_css
    assert ".settings-secret-actions" in workbench_css
    assert ".settings-save-note" in workbench_css
    assert ".settings-test-scope" in workbench_css
    assert ".settings-setup-list" in workbench_css
    assert ".settings-advanced-section" in workbench_css
    assert ".settings-advanced-section:not([open]) fieldset" in workbench_css
    assert '[data-guidance-state="warning"]' in workbench_css
    assert '[data-readiness-state="ready"]' in workbench_css
    assert ".setup-step-card" in workbench_css
    assert ".setup-step-copy" in workbench_css
    assert ".setup-step-actions" in workbench_css
    assert ".setup-strip-head::-webkit-details-marker" in workbench_css
    assert '[data-setup-complete="true"]:not([open])' in workbench_css
    assert "repeat(auto-fit, minmax(250px, 1fr))" in workbench_css
    assert '.setup-step-card[data-setup-state="locked"]' in workbench_css
    assert "display: none" in workbench_css
    assert "grid-template-columns: minmax(0, 1fr) auto" in workbench_css
    assert "text-overflow: ellipsis" in workbench_css
    assert "align-items: start" in workbench_css
    assert '.setup-step-card[data-setup-state="ready"] button' in workbench_css
    assert "Reload sample deal room" in diligence_js
    assert "Rerun diligence review" in diligence_js
    assert "var(--green)" in diligence_css
    assert "@media (max-width: 880px)" in diligence_css
