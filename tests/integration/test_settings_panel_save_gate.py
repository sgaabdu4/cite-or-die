import json
import shutil
import subprocess
import textwrap
from pathlib import Path


def test_optional_key_providers_require_successful_connection_test(tmp_path) -> None:
    source = Path("src/cite_or_die/ui/settings_panel.js").read_text(encoding="utf-8")
    helpers = Path("src/cite_or_die/ui/settings_helpers.js").read_text(encoding="utf-8")
    setup_progress_import = (
        'import { updateSetupProgressDisclosure } from "./setup_progress.js?v=setup-progress-v3";'
    )
    (tmp_path / "settings_helpers.js").write_text(helpers, encoding="utf-8")
    module_path = tmp_path / "settings_panel_under_test.mjs"
    module_path.write_text(
        source.replace(setup_progress_import, "function updateSetupProgressDisclosure() {}"),
        encoding="utf-8",
    )
    script_path = tmp_path / "settings_panel_save_gate_test.mjs"
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
              setAttribute(name, value) {{ this.attributes[name] = value; }}
              removeAttribute(name) {{ delete this.attributes[name]; }}
              closest() {{ return this.parentElement || this; }}
            }}

            const ids = [
              "settings-status", "setup-summary", "setup-provider-title",
              "setup-provider-action", "open-settings", "settings-modal",
              "settings-close", "settings-form", "settings-llm-provider",
              "settings-llm-model", "settings-llm-base-url", "settings-llm-api-key",
              "settings-key-toggle", "settings-key-clear", "settings-key-guidance",
              "settings-embedding-provider", "settings-reranker-provider",
              "settings-delete", "settings-test", "settings-save", "settings-result",
              "settings-save-guidance", "settings-reindex-banner", "settings-reindex",
              "settings-readiness-provider", "settings-readiness-key",
              "settings-readiness-test", "settings-guide-provider", "settings-guide-key",
              "settings-guide-test", "tenant"
            ];
            const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));

            for (const id of [
              "settings-readiness-provider", "settings-readiness-key", "settings-readiness-test"
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
              getElementById(id) {{ return elements[id] || null; }},
              querySelectorAll() {{ return []; }}
            }};
            globalThis.confirm = () => false;
            globalThis.fetch = async (url, options = {{}}) => {{
              if (url === "/settings/provider") return {{ status: 404, ok: false }};
              if (url === "/settings/provider/test") {{
                const body = JSON.parse(options.body);
                return {{
                  status: 200,
                  ok: true,
                  async json() {{
                    return {{
                      ok: true,
                      detail: "Provider connection verified.",
                      llm_provider: body.llm_provider,
                      llm_model: body.llm_model,
                      llm_base_url: body.llm_base_url || null
                    }};
                  }}
                }};
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

            if (elements["settings-save"].disabled) {{
              throw new Error("Expected offline demo provider to be saveable without a test.");
            }}

            async function requireProbeBeforeSave(provider, model, baseUrl) {{
              elements["settings-llm-provider"].value = provider;
              elements["settings-llm-provider"].dispatch("change");
              elements["settings-llm-model"].value = model;
              elements["settings-llm-model"].dispatch("input");
              elements["settings-llm-base-url"].value = baseUrl;
              elements["settings-llm-base-url"].dispatch("input");

              if (!elements["settings-save"].disabled) {{
                throw new Error(`${{provider}} saved before connection test.`);
              }}
              elements["settings-test"].click();
              await flush();
              await flush();
              if (elements["settings-save"].disabled) {{
                throw new Error(`${{provider}} did not become saveable after test.`);
              }}
              elements["settings-llm-base-url"].value = `${{baseUrl}}/changed`;
              elements["settings-llm-base-url"].dispatch("input");
              if (!elements["settings-save"].disabled) {{
                throw new Error(`${{provider}} stayed saveable after changing base URL.`);
              }}
            }}

            await requireProbeBeforeSave("openai-compatible", "model-a", "http://localhost:8000/v1");
            await requireProbeBeforeSave("ollama", "qwen3:8b", "http://localhost:11434");
            """
        ),
        encoding="utf-8",
    )

    node = shutil.which("node")
    assert node is not None
    subprocess.run([node, str(script_path)], check=True)  # noqa: S603
