import re
from pathlib import Path

from fastapi.testclient import TestClient


def test_phase3_ui_wires_streaming_and_pdfjs(api_client: TestClient) -> None:
    response = api_client.get("/")

    assert response.status_code == 200
    assert 'href="/static/tokens.css?v=ui-followups"' in response.text
    assert 'href="/static/workspace.css?v=ui-followups"' in response.text
    assert 'type="module" src="/static/app.js?v=scope-in-page"' in response.text
    assert "Provider settings" in response.text
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
    workspace_css = Path("src/cite_or_die/ui/workspace.css").read_text(encoding="utf-8")

    assert "/chat/stream" in app_js
    assert "layout_resizer.js" in app_js
    assert "settings_panel.js" in app_js
    assert "doc_ids" in app_js
    assert "selectedDocIds" in app_js
    assert "beginSourcesResize" in layout_resizer_js
    assert "handleSourcesResizeKey" in layout_resizer_js
    assert "initSettingsPanel" in settings_panel_js
    assert ".workspace-switcher" in workspace_css
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


def test_choosing_a_file_uploads_it_and_ask_stays_disabled_until_there_is_a_question(
    api_client: TestClient,
) -> None:
    html = api_client.get("/").text
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")

    assert "upload-button" not in html
    assert '<button id="ask-button" type="submit" disabled>' in html
    assert "nodes.uploadForm.requestSubmit();" in app_js
    assert "uploadButton" not in app_js
    assert "askButton.disabled = !nodes.question.value.trim();" in app_js
    assert "Choose a file first." not in app_js


def test_placeholder_text_uses_the_muted_colour_token() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")

    assert (
        "\ninput::placeholder,\ntextarea::placeholder {\n  color: var(--color-muted);\n}" in styles
    )


def test_empty_transcript_names_the_next_step_and_the_first_message_removes_it(
    api_client: TestClient,
) -> None:
    html = api_client.get("/").text
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")

    assert '<p id="transcript-empty" class="transcript-empty">' in html
    assert "Add a source, then ask a question.</p>" in html
    assert "nodes.transcriptEmpty.remove();" in app_js


def test_typing_a_follow_up_keeps_ask_disabled_while_an_answer_streams() -> None:
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")

    assert "state.asking = true;" in app_js
    assert "state.asking = false;" in app_js
    assert "askButton.disabled = state.asking || !nodes.question.value.trim();" in app_js


def test_disabled_buttons_drop_the_filled_green_for_a_quiet_neutral() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    disabled = styles[styles.index("\nbutton:disabled {") :].split("}", 1)[0]

    assert "background: var(--color-line);" in disabled
    assert "color: var(--color-muted);" in disabled


def test_provider_button_names_its_action(api_client: TestClient) -> None:
    html = api_client.get("/").text

    assert (
        '<button id="open-settings" type="button" class="ghost-button">Provider settings</button>'
        in html
    )


def test_empty_chat_line_lines_up_with_the_question_field_and_uses_the_body_size() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    transcript = styles[styles.index("\n.transcript {") :].split("}", 1)[0]
    empty = styles[styles.index("\n.transcript-empty {") :].split("}", 1)[0]

    assert "padding: var(--space-18) var(--space-14);" in transcript
    assert "font-size: var(--text-body);" in empty


def test_a_finished_answer_keeps_a_follow_up_typed_while_it_streamed() -> None:
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")

    assert 'if (nodes.question.value.trim() === question) nodes.question.value = "";' in app_js


def test_file_input_is_cleared_once_its_file_is_taken() -> None:
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")
    upload = app_js[app_js.index("async function uploadDocument") :].split("\n}\n", 1)[0]

    assert 'nodes.file.value = "";' in upload


def test_file_input_stays_disabled_while_an_upload_is_pending() -> None:
    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")
    upload = app_js[app_js.index("async function uploadDocument") :].split("\n}\n", 1)[0]

    assert upload.index("nodes.file.disabled = true;") < upload.index("await ")
    assert upload.index("} finally {") < upload.index("nodes.file.disabled = false;")
    assert upload.count("nodes.file.disabled") == 2


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = (
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_field_outline_meets_three_to_one_on_every_surface_a_field_sits_on() -> None:
    tokens = Path("src/cite_or_die/ui/tokens.css").read_text(encoding="utf-8")
    colour = dict(re.findall(r"--color-([a-z-]+): (#[0-9a-f]{6});", tokens))
    surfaces = ("white", "paper", "composer-surface", "switcher-surface", "upload-surface")

    assert min(_contrast(colour["field-line"], colour[name]) for name in surfaces) >= 3


def test_every_field_outline_uses_the_one_field_line_token() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    plain = styles[styles.index("\ninput,\ntextarea {\n  width:") :].split("}", 1)[0]
    dialog = styles[styles.index("\n.settings-modal input,") :].split("}", 1)[0]

    assert "border: var(--size-rule) solid var(--color-field-line);" in plain
    assert "border: var(--size-rule) solid var(--color-field-line);" in dialog
    assert "settings-field-line" not in styles
    assert "field-line" in Path("DESIGN.md").read_text(encoding="utf-8")


def test_dialog_forms_shrink_to_the_dialog_and_footer_buttons_start_at_the_text_edge() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    provider = styles[styles.index("\n.settings-modal form {") :].split("}", 1)[0]
    provider_foot = styles[styles.index("\n.settings-modal-foot {") :].split("}", 1)[0]

    assert "grid-template-columns: minmax(0, var(--size-track));" in provider
    assert "justify-content: flex-start;" in provider_foot
    assert "settings-hint" not in styles


def test_reindex_notice_is_one_alert_and_the_save_line_does_not_repeat_it() -> None:
    dialog = Path("src/cite_or_die/ui/library/provider_dialog.html").read_text(encoding="utf-8")
    panel = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")

    assert 'id="settings-reindex-banner" class="settings-banner" role="alert"' in dialog
    assert 'id="settings-result" class="status-line" role="status" aria-live="polite"' in dialog
    assert 'nodes.resultLine.textContent = "Saved.";' in panel
    assert "Re-upload sources to rebuild" not in panel


def test_dialog_fields_fill_their_row_use_the_ink_colour_and_the_model_hint_fits() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    dialog = Path("src/cite_or_die/ui/library/provider_dialog.html").read_text(encoding="utf-8")
    fields = styles[styles.index("\n.settings-modal input,") :].split("}", 1)[0]

    assert "width: var(--size-full);" in fields
    assert "color: var(--color-ink);" in fields
    assert 'placeholder="e.g. gpt-5.5 or qwen3:8b"' in dialog


def test_buttons_summaries_and_selects_show_the_green_focus_outline_not_the_browser_blue() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    focus = styles[styles.index("\nbutton:focus-visible,") :].split("}", 1)[0]

    assert "summary:focus-visible {" in focus
    assert "select:focus-visible" not in focus
    assert "outline: var(--size-3) solid var(--color-green);" in focus
    assert "outline-offset: var(--size-3);" in focus


def test_headings_use_the_ink_and_heading_stack() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    h3 = styles[styles.index("\nh3 {\n  font-family") :].split("}", 1)[0]
    ink = styles[styles.index("\nh1,\nh2,\nh3 {\n  color") :].split("}", 1)[0]

    assert "font-family: var(--font-family-heading);" in h3
    assert "color: var(--color-ink);" in ink


def test_forget_settings_is_off_until_a_provider_config_is_stored() -> None:
    panel = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")
    populate = panel[panel.index("  function populateForm") :].split("\n  }\n", 1)[0]
    save = panel[panel.index("  async function saveSettings") :].split("\n  }\n", 1)[0]

    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    off = styles[styles.index("\n.settings-modal-foot .danger-button:disabled") :].split("}", 1)[0]

    assert "nodes.deleteButton.disabled = !status;" in populate
    assert "nodes.deleteButton.disabled = false;" in save
    assert "color: var(--color-muted);" in off


def test_sources_resize_handle_uses_the_field_line_colour_for_3_to_1_contrast() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    tokens = Path("src/cite_or_die/ui/tokens.css").read_text(encoding="utf-8")
    handle = styles[styles.index("\n.sources-resizer::before {") :].split("}", 1)[0]

    assert "background: var(--color-field-line);" in handle
    assert "color-resizer" not in styles + tokens


def test_choose_file_drop_zone_outline_uses_the_field_line_colour() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    tokens = Path("src/cite_or_die/ui/tokens.css").read_text(encoding="utf-8")
    picker = styles[styles.index("\n.file-picker {") :].split("}", 1)[0]

    assert "border: var(--size-rule) dashed var(--color-field-line);" in picker
    assert "upload-line" not in styles + tokens


def test_provider_dialog_closes_with_the_same_text_button_as_the_citation_drawer() -> None:
    library = Path("src/cite_or_die/ui/library")
    dialog = (library / "provider_dialog.html").read_text(encoding="utf-8")
    drawer = (library / "citation_viewer.html").read_text(encoding="utf-8")

    assert '<button type="button" id="settings-close" class="ghost-button">Close</button>' in dialog
    assert '<button id="close-citation" class="ghost-button" type="button">Close</button>' in drawer


def test_workspace_card_pads_its_content_like_the_sources_card() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    workspace = Path("src/cite_or_die/ui/workspace.css").read_text(encoding="utf-8")
    switcher = workspace[workspace.index("\n.workspace-switcher {") :].split("}", 1)[0]
    sources = styles[styles.index("\n.sources-pane {") :].split("}", 1)[0]

    assert "padding: var(--space-15);" in switcher
    assert "padding: var(--space-15);" in sources


def test_the_scope_fields_are_the_one_place_to_set_tenant_and_matter() -> None:
    ui = Path("src/cite_or_die/ui")
    page = "".join(path.read_text(encoding="utf-8") for path in ui.rglob("*") if path.is_file())
    app = (ui / "app.js").read_text(encoding="utf-8")
    api = Path("src/cite_or_die/api/app.py").read_text(encoding="utf-8")

    assert not (ui / "workspace_setup.js").exists()
    assert not (ui / "library/workspace_dialog.html").exists()
    assert "workspace_dialog" not in api
    for gone in ("workspace-summary", "open-workspace-setup", "setup-modal", "Use workspace"):
        assert gone not in page
    assert "nodes.tenant.value = tenantId;" in app
    assert "nodes.matter.value = matterId;" in app
    assert 'nodes.tenant.addEventListener("change", applyScope);' in app
    assert 'nodes.matter.addEventListener("change", applyScope);' in app


def test_pane_height_comes_from_the_shell_grid_not_a_guessed_header_height() -> None:
    ui = Path("src/cite_or_die/ui")
    styles = (ui / "styles.css").read_text(encoding="utf-8")
    tokens = (ui / "tokens.css").read_text(encoding="utf-8")
    shell = styles[styles.index("\n.app-shell {") :].split("}", 1)[0]
    workspace = styles[styles.index("\n.workspace {\n  display: grid;") :].split("}", 1)[0]
    wide = styles[styles.index("@media (min-width: 861px)") :].split("\n}\n", 1)[0]

    assert "size-112" not in styles + tokens
    assert "grid-template-rows: auto minmax(0, var(--size-track));" in shell
    assert "grid-template-rows: minmax(0, var(--size-track));" in workspace
    assert "height: var(--size-viewport-height);" in wide


def test_one_field_text_style_and_one_label_style_serve_the_page_and_the_dialog() -> None:
    ui = Path("src/cite_or_die/ui")
    styles = (ui / "styles.css").read_text(encoding="utf-8")
    tokens = (ui / "tokens.css").read_text(encoding="utf-8")
    base = styles[styles.index("\nbutton,\ninput,") :].split("}", 1)[0]
    field = styles[styles.index("\n}\n\ninput,\nselect,\ntextarea {") + 3 :].split("}", 1)[0]
    modal_label = styles[styles.index("\n.settings-modal label {") :].split("}", 1)[0]
    modal_field = styles[styles.index("\n.settings-modal input,") :].split("}", 1)[0]

    assert "select," in base
    assert "font-size: var(--text-body);" in field
    assert "font-weight: var(--weight-400);" in field
    assert "font-size" not in modal_label
    assert "font:" not in modal_field
    assert "text-settings-field" not in styles + tokens


def test_provider_dialog_opens_with_focus_on_its_first_field_not_on_close() -> None:
    dialog = Path("src/cite_or_die/ui/library/provider_dialog.html").read_text(encoding="utf-8")
    first = dialog[dialog.index('<select id="settings-llm-provider"') :].split(">", 1)[0]

    assert "autofocus" in first


def test_auth_toggle_reads_like_the_other_outlined_buttons() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    summary = styles[styles.index("\n.token-details summary {") :].split("}", 1)[0]
    ghost = styles[styles.index("\n.ghost-button {") :].split("}", 1)[0]

    assert "color: var(--color-ink);" in summary
    assert "color: var(--color-ink);" in ghost


def test_provider_status_names_the_server_default_when_no_config_is_saved() -> None:
    panel = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")
    empty = panel[panel.index("    if (!status) {") :].split("      return;", 1)[0]

    assert "not configured" not in panel
    assert "Provider: <strong>server default</strong>" in empty
    assert "offline demo" not in empty


def test_the_token_toggle_names_what_it_opens() -> None:
    controls = Path("src/cite_or_die/ui/library/workspace_controls.html").read_text(
        encoding="utf-8"
    )

    assert "<summary>Access token</summary>" in controls
    assert "<summary>Auth</summary>" not in controls


def test_selects_show_the_field_focus_border_and_halo_like_text_fields() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    focus = styles[styles.index("\ninput:focus,") :].split("}", 1)[0]

    assert "select:focus" in focus
    assert ".settings-modal input:focus," in focus
    assert ".settings-modal select:focus" in focus
    assert "border-color: var(--color-green);" in focus
    assert "box-shadow: var(--shadow-focus);" in focus


def test_dialog_footer_buttons_use_the_one_button_text_style() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    foot = styles[styles.index("\n.settings-modal-foot button {") :].split("}", 1)[0]

    assert "font: inherit;" not in foot
    assert "font-size: var(--text-small);" in foot


def test_provider_status_text_meets_4_5_to_1_on_each_status_surface() -> None:
    tokens = Path("src/cite_or_die/ui/tokens.css").read_text(encoding="utf-8")
    colour = dict(re.findall(r"--color-([a-z-]+): (#[0-9a-f]{6});", tokens))
    pairs = (
        ("provider-empty-text", "warning-surface"),
        ("provider-ready-text", "provider-ready-surface"),
        ("provider-error-text", "provider-error-surface"),
    )

    assert min(_contrast(colour[text], colour[surface]) for text, surface in pairs) >= 4.5


def test_stacked_cards_keep_their_own_height_on_narrow_screens() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    narrow = styles[styles.index("@media (max-width: 860px)") :].split("\n}\n", 1)[0]
    workspace = narrow[narrow.index("  .workspace {\n    grid-template-rows: none;") :].split(
        "}", 1
    )[0]

    assert "align-content: start;" in workspace


def test_empty_source_rows_take_no_space_in_the_stacked_sources_card() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    narrow = styles[styles.index("@media (max-width: 860px)") :].split("\n}\n", 1)[0]
    card = narrow[narrow.index("  .sources-pane {\n    grid-template-rows") :].split("}", 1)[0]

    assert "grid-template-rows: none;" in card
    assert ".sources-pane .status-line:empty," in narrow
    assert ".sources-pane .document-list:empty {" in narrow
    assert "display: none;" in narrow[narrow.index(".sources-pane .document-list:empty {") :]


def test_changed_assets_carry_a_new_cache_key() -> None:
    ui = Path("src/cite_or_die/ui")
    page = (ui / "index.html").read_text(encoding="utf-8")
    app = (ui / "app.js").read_text(encoding="utf-8")

    assert "ui-tokens" not in page
    assert "shared-controls" not in page
    assert "settings_panel.js?v=provider-status" in app
    assert "workspace_setup" not in app


def test_provider_select_starts_empty_so_saving_needs_a_chosen_provider() -> None:
    ui = Path("src/cite_or_die/ui")
    dialog = (ui / "library/provider_dialog.html").read_text(encoding="utf-8")
    panel = (ui / "settings_panel.js").read_text(encoding="utf-8")
    select = dialog[dialog.index('<select id="settings-llm-provider"') :].split("</select>", 1)[0]
    populate = panel[panel.index("  function populateForm") :].split("\n  }\n", 1)[0]
    empty = populate[populate.index("    } else {") :]

    assert "required" in select.split(">", 1)[0]
    assert '<option value="">Choose a provider</option>' in select
    assert 'nodes.llmProvider.value = "";' in empty
    assert "fake" not in empty


def test_stacked_chat_card_sizes_its_rows_by_content_so_the_composer_stays_inside() -> None:
    styles = Path("src/cite_or_die/ui/styles.css").read_text(encoding="utf-8")
    narrow = styles[styles.index("@media (max-width: 860px)") :].split("\n}\n", 1)[0]
    chat = narrow[narrow.index("  .chat-pane {\n    grid-template-rows") :].split("}", 1)[0]

    assert "grid-template-rows: auto auto;" in chat
