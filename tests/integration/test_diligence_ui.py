import json
import shutil
import subprocess
import textwrap
from pathlib import Path

from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.core.config import get_settings


def write_settings_panel_under_test(tmp_path: Path) -> Path:
    source = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")
    helpers = Path("src/cite_or_die/ui/settings_helpers.js").read_text(encoding="utf-8")
    setup_progress_import = (
        'import { updateSetupProgressDisclosure } from "./setup_progress.js?v=setup-progress-v3";'
    )
    (tmp_path / "settings_helpers.js").write_text(helpers, encoding="utf-8")
    module_path = tmp_path / "settings_panel_under_test.mjs"
    module_path.write_text(
        source.replace(
            setup_progress_import,
            "function updateSetupProgressDisclosure() {}",
        ),
        encoding="utf-8",
    )
    return module_path


def test_settings_reindex_banner_survives_modal_reopen(tmp_path) -> None:
    module_path = write_settings_panel_under_test(tmp_path)
    script_path = tmp_path / "settings_panel_reindex_test.mjs"
    script_path.write_text(
        textwrap.dedent(
            f"""
            import {{ pathToFileURL }} from "node:url";

            class Element {{
              constructor(id) {{
                this.id = id;
                this.dataset = {{}};
                this.listeners = {{}};
                this.hidden = false;
                this.value = "";
                this.textContent = "";
                this.innerHTML = "";
                this.placeholder = "";
                this.type = "";
                this.title = "";
                this.disabled = false;
                this.readOnly = false;
                this.attributes = {{}};
                this.parentElement = null;
              }}

              addEventListener(type, listener) {{
                if (!this.listeners[type]) this.listeners[type] = [];
                this.listeners[type].push(listener);
              }}

              click() {{
                for (const listener of this.listeners.click || []) {{
                  listener({{ preventDefault() {{}} }});
                }}
              }}

              focus() {{}}

              setAttribute(name, value) {{
                this.attributes[name] = value;
                if (name === "open") this.open = true;
              }}

              removeAttribute(name) {{
                delete this.attributes[name];
                if (name === "open") this.open = false;
              }}

              closest() {{
                return this.parentElement || this;
              }}
            }}

            const ids = [
              "settings-status",
              "setup-summary",
              "setup-provider-title",
              "setup-provider-action",
              "open-settings",
              "settings-modal",
              "settings-close",
              "settings-form",
              "settings-llm-provider",
              "settings-llm-model",
              "settings-llm-base-url",
              "settings-llm-api-key",
              "settings-key-toggle",
              "settings-key-clear",
              "settings-key-guidance",
              "settings-embedding-provider",
              "settings-reranker-provider",
              "settings-delete",
              "settings-test",
              "settings-save",
              "settings-result",
              "settings-save-guidance",
              "settings-reindex-banner",
              "settings-reindex",
              "settings-readiness-provider",
              "settings-readiness-key",
              "settings-readiness-test",
              "settings-guide-provider",
              "settings-guide-key",
              "settings-guide-test",
              "tenant"
            ];
            const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));

            for (const id of [
              "settings-readiness-provider",
              "settings-readiness-key",
              "settings-readiness-test"
            ]) {{
              const parent = new Element(`${{id}}-parent`);
              parent.dataset.readinessState = "needed";
              elements[id].parentElement = parent;
            }}
            const setupCard = new Element("setup-provider-card");
            setupCard.dataset.setupState = "needed";
            elements["setup-provider-title"].parentElement = setupCard;
            elements["settings-modal"].showModal = function () {{ this.open = true; }};
            elements["settings-modal"].close = function () {{ this.open = false; }};
            elements["settings-llm-provider"].value = "fake";
            elements["settings-llm-api-key"].type = "password";

            globalThis.document = {{
              getElementById(id) {{
                return elements[id] || null;
              }},
              querySelectorAll() {{
                return [];
              }}
            }};
            globalThis.confirm = () => false;
            let reindexCalled = false;
            globalThis.fetch = async (url, options = {{}}) => {{
              if (url === "/settings/provider/reindex" && options.method === "POST") {{
                reindexCalled = true;
                return {{
                  status: 200,
                  ok: true,
                  async json() {{
                    return {{
                      llm_provider: "fake",
                      llm_model: "",
                      llm_base_url: "",
                      llm_api_key_fingerprint: null,
                      embedding_provider: "bge-m3",
                      embedding_dim: 1024,
                      reranker_provider: "none",
                      requires_reindex: false
                    }};
                  }}
                }};
              }}
              if (url !== "/settings/provider") throw new Error(`Unexpected fetch ${{url}}`);
              return {{
                status: 200,
                ok: true,
                async json() {{
                  return {{
                    llm_provider: "fake",
                    llm_model: "",
                    llm_base_url: "",
                    llm_api_key_fingerprint: null,
                    embedding_provider: "bge-m3",
                    embedding_dim: 1024,
                    reranker_provider: "none",
                    requires_reindex: true
                  }};
                }}
              }};
            }};

            const moduleUrl = pathToFileURL({json.dumps(str(module_path))}).href;
            const {{ initSettingsPanel }} = await import(moduleUrl);
            initSettingsPanel({{
              authHeaders: async (headers = {{}}) => headers,
              currentScope: () => ({{ tenantId: "tenant-a" }}),
              tenantNode: elements.tenant
            }});

            const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
            await flush();
            await flush();
            elements["settings-reindex-banner"].hidden = true;
            elements["open-settings"].click();
            await flush();
            await flush();

            if (elements["settings-reindex-banner"].hidden) {{
              throw new Error("Expected reindex banner to be visible after reopening settings.");
            }}
            elements["settings-reindex"].click();
            await flush();
            await flush();

            if (!reindexCalled) {{
              throw new Error("Expected reindex request after clicking rebuild.");
            }}
            if (!elements["settings-reindex-banner"].hidden) {{
              throw new Error("Expected reindex banner to hide after rebuild.");
            }}
            """
        ),
        encoding="utf-8",
    )

    node = shutil.which("node")
    assert node is not None
    subprocess.run([node, str(script_path)], check=True)  # noqa: S603


def test_provider_test_result_uses_signature_from_submitted_form(tmp_path) -> None:
    module_path = write_settings_panel_under_test(tmp_path)
    script_path = tmp_path / "settings_panel_signature_test.mjs"
    script_path.write_text(
        textwrap.dedent(
            f"""
            import {{ pathToFileURL }} from "node:url";

            class Element {{
              constructor(id) {{
                this.id = id;
                this.dataset = {{}};
                this.listeners = {{}};
                this.hidden = false;
                this.value = "";
                this.textContent = "";
                this.innerHTML = "";
                this.placeholder = "";
                this.type = "";
                this.title = "";
                this.disabled = false;
                this.readOnly = false;
                this.attributes = {{}};
                this.parentElement = null;
              }}

              addEventListener(type, listener) {{
                if (!this.listeners[type]) this.listeners[type] = [];
                this.listeners[type].push(listener);
              }}

              click() {{
                for (const listener of this.listeners.click || []) {{
                  listener({{ preventDefault() {{}} }});
                }}
              }}

              dispatch(type) {{
                for (const listener of this.listeners[type] || []) {{
                  listener({{ target: this }});
                }}
              }}

              focus() {{}}

              setAttribute(name, value) {{
                this.attributes[name] = value;
                if (name === "open") this.open = true;
              }}

              removeAttribute(name) {{
                delete this.attributes[name];
                if (name === "open") this.open = false;
              }}

              closest() {{
                return this.parentElement || this;
              }}
            }}

            const ids = [
              "settings-status",
              "setup-summary",
              "setup-provider-title",
              "setup-provider-action",
              "open-settings",
              "settings-modal",
              "settings-close",
              "settings-form",
              "settings-llm-provider",
              "settings-llm-model",
              "settings-llm-base-url",
              "settings-llm-api-key",
              "settings-key-toggle",
              "settings-key-clear",
              "settings-key-guidance",
              "settings-embedding-provider",
              "settings-reranker-provider",
              "settings-delete",
              "settings-test",
              "settings-save",
              "settings-result",
              "settings-save-guidance",
              "settings-reindex-banner",
              "settings-reindex",
              "settings-readiness-provider",
              "settings-readiness-key",
              "settings-readiness-test",
              "settings-guide-provider",
              "settings-guide-key",
              "settings-guide-test",
              "tenant"
            ];
            const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));

            for (const id of [
              "settings-readiness-provider",
              "settings-readiness-key",
              "settings-readiness-test"
            ]) {{
              const parent = new Element(`${{id}}-parent`);
              parent.dataset.readinessState = "needed";
              elements[id].parentElement = parent;
            }}
            const setupCard = new Element("setup-provider-card");
            setupCard.dataset.setupState = "needed";
            elements["setup-provider-title"].parentElement = setupCard;
            elements["settings-modal"].showModal = function () {{ this.open = true; }};
            elements["settings-modal"].close = function () {{ this.open = false; }};
            elements["settings-llm-provider"].value = "fake";
            elements["settings-llm-api-key"].type = "password";

            let completeProviderTest;
            globalThis.document = {{
              getElementById(id) {{
                return elements[id] || null;
              }},
              querySelectorAll() {{
                return [];
              }}
            }};
            globalThis.confirm = () => false;
            globalThis.fetch = async (url) => {{
              if (url === "/settings/provider") {{
                return {{ status: 404, ok: false }};
              }}
              if (url === "/settings/provider/test") {{
                return await new Promise((resolve) => {{
                  completeProviderTest = () => resolve({{
                    status: 200,
                    ok: true,
                    async json() {{
                      return {{ ok: true, detail: "Provider connection verified." }};
                    }}
                  }});
                }});
              }}
              throw new Error(`Unexpected fetch ${{url}}`);
            }};

            const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
            const moduleUrl = pathToFileURL({json.dumps(str(module_path))}).href;
            const {{ initSettingsPanel }} = await import(moduleUrl);
            initSettingsPanel({{
              authHeaders: async (headers = {{}}) => headers,
              currentScope: () => ({{ tenantId: "tenant-a" }}),
              tenantNode: elements.tenant
            }});
            await flush();
            await flush();

            elements["settings-llm-provider"].value = "openai";
            elements["settings-llm-provider"].dispatch("change");
            elements["settings-llm-api-key"].value = "sk-test-provider-key";
            elements["settings-llm-api-key"].dispatch("input");
            elements["settings-test"].click();
            while (!completeProviderTest) await flush();

            elements["settings-llm-model"].value = "gpt-untested";
            elements["settings-llm-model"].dispatch("input");
            completeProviderTest();
            await flush();
            await flush();

            if (!elements["settings-save"].disabled) {{
              throw new Error("Expected edited form to require another provider test.");
            }}
            const readinessText = elements["settings-readiness-test"].textContent;
            if (readinessText !== "Retest after changes") {{
              throw new Error(`Unexpected test readiness: ${{readinessText}}`);
            }}
            """
        ),
        encoding="utf-8",
    )

    node = shutil.which("node")
    assert node is not None
    subprocess.run([node, str(script_path)], check=True)  # noqa: S603


def test_diligence_workspace_is_wired_to_app_shell(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/")

    app_js = Path("src/cite_or_die/ui/app.js").read_text(encoding="utf-8")
    citation_viewer_js = Path("src/cite_or_die/ui/citation_viewer.js").read_text(encoding="utf-8")
    diligence_js = Path("src/cite_or_die/ui/diligence.js").read_text(encoding="utf-8")
    diligence_renderer_js = Path("src/cite_or_die/ui/diligence_renderers.js").read_text(
        encoding="utf-8"
    )
    diligence_ui_js = diligence_js + diligence_renderer_js
    diligence_css = Path("src/cite_or_die/ui/diligence.css").read_text(encoding="utf-8")
    settings_panel_js = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")
    settings_provider_js = settings_panel_js + Path(
        "src/cite_or_die/ui/settings_helpers.js"
    ).read_text(encoding="utf-8")
    workbench_css = Path("src/cite_or_die/ui/workbench.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'href="/static/diligence.css?v=diligence-workspace-v1"' in response.text
    assert 'href="/static/workbench.css?v=deal-command-v12"' in response.text
    assert 'id="setup-strip" class="setup-strip"' in response.text
    assert 'id="setup-heading"' in response.text
    assert 'class="setup-step-copy"' in response.text
    assert 'id="setup-provider-action"' in response.text
    assert 'id="setup-deal-title"' in response.text
    assert 'id="setup-run-title"' in response.text
    assert 'id="diligence-load-selected"' in response.text
    assert 'id="diligence-load-selected-inline"' in response.text
    assert 'id="diligence-load-demo-inline"' in response.text
    assert 'id="diligence-run-inline"' in response.text
    assert 'id="select-all-docs"' in response.text
    assert 'class="setup-step-actions"' in response.text
    assert 'class="workbench-grid"' in response.text
    assert 'id="diligence-workspace"' in response.text
    assert "Diligence Accelerator" in response.text
    assert "Deal command center" in response.text
    assert "AI-enabled Due Diligence Acceleration" in response.text
    assert "Deal workflow" in response.text
    assert "Upload and ask questions" in response.text
    assert "Ask cited questions" in response.text
    assert 'aria-label="Model provider"' in response.text
    assert 'class="settings-setup-list"' in response.text
    assert 'id="settings-guide-provider"' in response.text
    assert 'id="settings-guide-key"' in response.text
    assert 'id="settings-guide-test"' in response.text
    assert '<details class="settings-advanced-section">' in response.text
    assert "Advanced retrieval settings" in response.text
    assert "Server defaults are usually right" in response.text
    assert "Load sample deal pack" in response.text
    assert "Run accelerator" in response.text
    assert "Run AI-assisted review" in response.text
    assert "Use all files" in response.text
    assert "Drag files here or choose files" in response.text
    assert "Bulk upload PDF, TXT, DOCX, or MD files." in response.text
    assert 'type="file"' in response.text
    assert "multiple" in response.text
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
    assert "initCitationViewer" in app_js
    assert "refreshDocuments" in app_js
    assert "uploadFiles" in app_js
    assert "handleDrop" in app_js
    assert 'dataset.dragState = "over"' in app_js
    assert "cod:open-citation" in citation_viewer_js
    assert "diligence_renderers.js" in diligence_js
    assert "/diligence/deals" in diligence_js
    assert "/sources/classify" in diligence_js
    assert "/run" in diligence_js
    assert "/assist" in diligence_js
    assert "refreshDocuments" in diligence_js
    assert "knowledge_base" in diligence_js
    assert "source_doc_ids" in diligence_js
    assert "information_requests" in diligence_js
    assert "report_drafts" in diligence_js
    assert "review_status" in diligence_ui_js
    assert "evidence" in diligence_ui_js
    assert "updateSetupState" in diligence_js
    assert "updateSetupProgressDisclosure" in diligence_js
    assert "setup-progress-v3" in diligence_js
    assert 'state: "locked"' in diligence_js
    assert "dataset.setupState = setup.state" in diligence_js
    assert "formatFactValue(fact)" in diligence_renderer_js
    assert "fact.unit" in diligence_renderer_js
    assert "fact.period" in diligence_renderer_js
    assert "nodes.runInline" in diligence_js
    assert "nodes.loadDemoInline" in diligence_js
    assert "updateLoadDemoAction(nodes.loadDemoInline)" in diligence_js
    assert "updateRunAction(nodes.run)" in diligence_js
    assert "updateRunAction(nodes.runInline)" in diligence_js
    assert "nodes.assist" in diligence_js
    assert "function providerAssistDisabled()" in diligence_js
    assert "provider_assistance" in diligence_js
    assert "function runReviewDisabled()" in diligence_js
    assert "loadSelectedSources" in diligence_js
    assert "createSelectedDeal" in diligence_js
    assert "Selected Source Review" in diligence_js
    assert "selectedSourceIds()" in diligence_js
    assert 'new CustomEvent("cod:open-citation"' in diligence_renderer_js
    assert "cod:workspace-changed" in app_js
    assert "cod:source-selection-changed" in app_js
    assert "selectedDocIds" in app_js
    assert "selectAllDocuments" in app_js
    assert "function openDocumentRecord(documentRecord)" in app_js
    assert "button.addEventListener(\"click\", () => openDocumentRecord(documentRecord))" in app_js
    assert "openDocument(documentRecord)" not in app_js
    assert "nodes.selectAllDocs" in app_js
    assert "diligence-workspace-v5" in app_js
    assert "cfo-flow-v2" in response.text
    assert "provider-setup-v7" in app_js
    assert "Northstar Managed Services" in diligence_js
    assert "GEMINI_BASE_URL" in settings_provider_js
    assert "/settings/provider/test" in settings_provider_js
    assert "PROVIDER_GUIDANCE" in settings_provider_js
    assert "OpenAI uses the default OpenAI API endpoint" in settings_provider_js
    assert "OpenAI Responses API" in settings_provider_js
    assert "Use a Gemini API key from Google AI Studio." in settings_provider_js
    assert "Use an API key only when that endpoint requires one." in settings_provider_js
    assert "Optional provider API key" in settings_provider_js
    assert "API key optional. Leave blank for a local no-auth endpoint." in settings_provider_js
    assert "function acceptsApiKey(provider)" in settings_provider_js
    assert "Anthropic uses the native Claude Messages API." in settings_provider_js
    assert "Ollama runs locally" in settings_provider_js
    assert "updateProviderGuidance(provider)" in settings_provider_js
    assert "Connection verified" in settings_provider_js
    assert "canReuseSavedKey" in settings_provider_js
    assert "apiKeyInputIssue" in settings_provider_js
    assert "setKeyVisibility" in settings_provider_js
    assert "keyEntryVersion" in settings_provider_js
    assert "clearUnsavedKey" in settings_provider_js
    assert "clearKeyEntry" in settings_provider_js
    assert "canSaveCurrentConfig" in settings_provider_js
    assert "Test this provider before saving." in settings_provider_js
    assert "This looks like JSON or a multi-line credential" in settings_provider_js
    assert "This looks like an OAuth token" in settings_provider_js
    assert "Test connection before saving" in settings_provider_js
    assert "New write-only key entered" in settings_provider_js
    assert "Retest after changes" in settings_provider_js
    assert "Change provider" in settings_provider_js
    assert "updateSetupProgressDisclosure" in settings_provider_js
    assert "setup-progress-v3" in settings_provider_js
    assert ".advanced-controls" in workbench_css
    assert '.workbench-grid:has(.diligence-workspace[data-deal-state="empty"])' in workbench_css
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
    assert '.setup-step-card[data-setup-state="ready"] > button' in workbench_css
    assert ".setup-strip-head::-webkit-details-marker" in workbench_css
    assert '[data-setup-complete="true"]:not([open])' in workbench_css
    assert '[data-setup-complete="true"] .setup-steps' in workbench_css
    assert "repeat(auto-fit, minmax(250px, 1fr))" in workbench_css
    assert '.setup-step-card[data-setup-state="locked"]' in workbench_css
    assert "display: none" in workbench_css
    assert "grid-template-columns: 1fr" in workbench_css
    assert "text-overflow: ellipsis" in workbench_css
    assert "align-items: start" in workbench_css
    assert '.setup-step-card[data-setup-state="ready"] button' in workbench_css
    assert "Reload sample deal pack" in diligence_js
    assert "Rerun accelerator" in diligence_js
    assert "Rerun AI-assisted review" in diligence_js
    assert "Accelerator run complete. Human sign-off required." in diligence_js
    assert "AI-assisted review added. Human sign-off required." in diligence_js
    assert "var(--green)" in diligence_css
    assert "@media (max-width: 880px)" in diligence_css
