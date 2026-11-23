from pathlib import Path

from fastapi.testclient import TestClient


def test_phase3_ui_wires_streaming_and_pdfjs(api_client: TestClient) -> None:
    response = api_client.get("/")

    assert response.status_code == 200
    assert 'href="/static/tokens.css?v=ui-tokens"' in response.text
    assert 'href="/static/workspace.css?v=ui-tokens"' in response.text
    assert 'type="module" src="/static/app.js?v=shared-controls"' in response.text
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
    static_index = api_client.get("/static/index.html")
    assert static_index.text == response.text
    assert api_client.get("/static/index.html/").text == response.text
    assert api_client.get("/static//index.html").text == response.text
    upper_index = api_client.get("/static/INDEX.HTML")
    if upper_index.status_code == 200:
        assert upper_index.text == response.text
    assert "$workspace_controls" not in response.text
    etag = static_index.headers["etag"]
    assert "last-modified" not in static_index.headers
    assert api_client.get("/static/index.html/", headers={"If-None-Match": "*"}).status_code == 304
    assert api_client.get("/static/index.html", headers={"If-None-Match": etag}).status_code == 304
    assert (
        api_client.get("/static/index.html", headers={"If-None-Match": '"stale"'}).status_code
        == 200
    )
    assert api_client.get("/static/tokens.css").status_code == 200
    assert api_client.get("/static/library/controls.js").status_code == 200


def test_phase3_ui_modules_wire_streaming_pdfjs_and_workspace_controls() -> None:
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")
    layout_resizer_js = Path("src/cite_or_die/ui/layout_resizer.js").read_text(encoding="utf-8")
    settings_panel_js = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")
    source_viewer_js = Path("src/cite_or_die/ui/source_viewer.js").read_text(encoding="utf-8")
    workspace_setup_js = Path("src/cite_or_die/ui/workspace_setup.js").read_text(encoding="utf-8")
    workspace_css = Path("src/cite_or_die/ui/workspace.css").read_text(encoding="utf-8")

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


def test_closed_citation_drawer_is_hidden_by_css_not_aria_hidden(api_client: TestClient) -> None:
    html = api_client.get("/").text
    drawer = html[html.index('<aside id="citation-drawer"') :].split(">", 1)[0]
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")
    citation_css = Path("src/cite_or_die/ui/citation.css").read_text(encoding="utf-8")
    closed = citation_css[citation_css.index("\n.citation-drawer {") :].split("}", 1)[0]
    open_rule = citation_css[citation_css.index("\n.citation-drawer.open {") :].split("}", 1)[0]

    assert "aria-hidden" not in drawer
    assert "aria-hidden" not in app_js
    assert "visibility: hidden;" in closed
    assert "visibility: visible;" in open_rule


def test_base_controls_meet_the_44_pixel_tap_size() -> None:
    ui = Path("src/cite_or_die/ui")
    tokens = (ui / "tokens.css").read_text(encoding="utf-8")
    styles = (ui / "styles.css").read_text(encoding="utf-8")

    assert "--size-44: 44px;" in tokens
    for selector in ("button", "input", ".ghost-button", ".token-details summary"):
        rule = styles[styles.index(f"\n{selector} {{") :].split("}", 1)[0]
        assert "min-height: var(--size-44);" in rule
    button = styles[styles.index("\nbutton {") :].split("}", 1)[0]
    assert "min-width: var(--size-44);" in button
    dialog_fields = styles[styles.index("\n.settings-modal input,") :].split("}", 1)[0]
    assert "min-height: var(--size-44);" in dialog_fields


def test_provider_status_has_no_second_setup_link() -> None:
    settings_panel_js = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")

    assert "settings-open-link" not in settings_panel_js
    assert "<a " not in settings_panel_js


def test_sources_refresh_sits_next_to_its_heading_and_the_drawer_toolbar_keeps_its_edge() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")

    assert "\n.pane-head {\n  justify-content: flex-start;\n}" in styles
    assert "\n.viewer-toolbar {\n  justify-content: space-between;\n}" in styles


def test_empty_viewer_text_uses_the_darker_hint_colour_for_contrast() -> None:
    citation_css = Path("src/cite_or_die/ui/citation.css").read_text(encoding="utf-8")
    empty = citation_css[citation_css.index("\n#viewer-empty {") :].split("}", 1)[0]

    assert "color: var(--color-hint-text);" in empty


def test_upload_and_ask_stay_disabled_until_there_is_something_to_send(
    api_client: TestClient,
) -> None:
    html = api_client.get("/").text
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")

    assert '<button id="upload-button" type="submit" disabled>' in html
    assert '<button id="ask-button" type="submit" disabled>' in html
    assert "uploadButton.disabled = !nodes.file.files[0];" in app_js
    assert "askButton.disabled = !nodes.question.value.trim();" in app_js
    assert "Choose a file first." not in app_js


def test_empty_transcript_names_the_next_step_and_the_first_message_removes_it(
    api_client: TestClient,
) -> None:
    html = api_client.get("/").text
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")

    assert (
        '<p id="transcript-empty" class="transcript-empty">Add a source, then ask a question.</p>'
        in html
    )
    assert "nodes.transcriptEmpty.remove();" in app_js


def test_provider_button_is_the_filled_action_while_no_provider_is_set() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")

    assert '.settings-status[data-state="empty"] + .ghost-button {' in styles
    assert '.settings-status[data-state="empty"] + .ghost-button:hover {' in styles
