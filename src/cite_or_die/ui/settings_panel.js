import { updateSetupProgressDisclosure } from "./setup_progress.js?v=setup-progress-v2";

const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai";

const PROVIDER_PRESETS = {
  fake: { label: "Offline demo", model: "", baseUrl: "" },
  gemini: { label: "Gemini", model: "gemini-3.5-flash", baseUrl: GEMINI_BASE_URL },
  openai: { label: "OpenAI", model: "gpt-5.5", baseUrl: "" },
  anthropic: { label: "Anthropic", model: "claude-sonnet-4-6", baseUrl: "" },
  "openai-compatible": { label: "OpenAI-compatible", model: "", baseUrl: "" },
  ollama: { label: "Ollama", model: "qwen3:8b", baseUrl: "http://localhost:11434" },
};

const PROVIDER_GUIDANCE = {
  fake: {
    provider: "Offline demo uses the local deterministic provider.",
    key: "No external API key, base URL, or hosted model call is needed.",
    test: "Save is available immediately; no provider connection test is required.",
  },
  gemini: {
    provider: "Gemini uses Google's official OpenAI-compatible endpoint.",
    key: "Use a Gemini API key from Google AI Studio.",
    test: "The connection test calls Gemini chat completions with a short setup check.",
  },
  openai: {
    provider: "OpenAI uses the default OpenAI API endpoint; no custom base URL is needed.",
    key: "Use an OpenAI API key. The server sends it as a bearer credential.",
    test: "The connection test calls the OpenAI Responses API with a short setup check.",
  },
  anthropic: {
    provider: "Anthropic uses the native Claude Messages API.",
    key: "Use an Anthropic API key from the Claude Console.",
    test: "The connection test calls the Claude Messages API with a short setup check.",
  },
  "openai-compatible": {
    provider: "Use this for a provider that exposes an OpenAI-compatible chat completions API.",
    key: "Use an API key only when that endpoint requires one.",
    test: "The connection test calls the configured chat completions endpoint.",
  },
  ollama: {
    provider: "Ollama runs locally against the configured local base URL.",
    key: "No API key is used for the local Ollama provider.",
    test: "The connection test calls the local Ollama generate endpoint.",
  },
};

export function initSettingsPanel({ authHeaders, currentScope, tenantNode }) {
  const nodes = {
    status: document.getElementById("settings-status"),
    setupSummary: document.getElementById("setup-summary"),
    setupProviderTitle: document.getElementById("setup-provider-title"),
    setupProviderAction: document.getElementById("setup-provider-action"),
    openButton: document.getElementById("open-settings"),
    modal: document.getElementById("settings-modal"),
    closeButton: document.getElementById("settings-close"),
    form: document.getElementById("settings-form"),
    llmProvider: document.getElementById("settings-llm-provider"),
    llmModel: document.getElementById("settings-llm-model"),
    llmBaseUrl: document.getElementById("settings-llm-base-url"),
    llmApiKey: document.getElementById("settings-llm-api-key"),
    keyToggleButton: document.getElementById("settings-key-toggle"),
    keyClearButton: document.getElementById("settings-key-clear"),
    keyGuidance: document.getElementById("settings-key-guidance"),
    embeddingProvider: document.getElementById("settings-embedding-provider"),
    rerankerProvider: document.getElementById("settings-reranker-provider"),
    deleteButton: document.getElementById("settings-delete"),
    testButton: document.getElementById("settings-test"),
    saveButton: document.getElementById("settings-save"),
    resultLine: document.getElementById("settings-result"),
    saveGuidance: document.getElementById("settings-save-guidance"),
    reindexBanner: document.getElementById("settings-reindex-banner"),
    readinessProvider: document.getElementById("settings-readiness-provider"),
    readinessKey: document.getElementById("settings-readiness-key"),
    readinessTest: document.getElementById("settings-readiness-test"),
    guideProvider: document.getElementById("settings-guide-provider"),
    guideKey: document.getElementById("settings-guide-key"),
    guideTest: document.getElementById("settings-guide-test"),
  };
  let lastFetchScope = "";
  let currentStatus = null;
  let lastTestResult = null;
  let keyEntryVersion = 0;

  function applyProviderUi() {
    const provider = nodes.llmProvider.value;
    for (const el of document.querySelectorAll(".settings-conditional")) {
      const matches = el.dataset.showFor.split(" ").includes(provider);
      el.hidden = !matches;
    }
    const preset = PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.fake;
    nodes.llmBaseUrl.readOnly = provider === "gemini";
    nodes.llmModel.placeholder = preset.model || "Model name";
    nodes.llmApiKey.placeholder = apiKeyPlaceholder(provider);
    updateProviderGuidance(provider);
    updateReadiness();
  }

  function updateProviderGuidance(provider) {
    const guidance = PROVIDER_GUIDANCE[provider] || PROVIDER_GUIDANCE.fake;
    if (nodes.guideProvider) nodes.guideProvider.textContent = guidance.provider;
    if (nodes.guideKey) nodes.guideKey.textContent = guidance.key;
    if (nodes.guideTest) nodes.guideTest.textContent = guidance.test;
  }

  function renderStatus(status) {
    currentStatus = status;
    renderReindexBanner(status);
    if (!status) {
      nodes.status.dataset.state = "empty";
      nodes.status.innerHTML =
        'Provider: <strong>not configured</strong> - <a href="#" id="settings-open-link">set up</a>';
      renderSetupProvider(null);
      updateSetupProgressDisclosure();
      updateReadiness();
      const link = document.getElementById("settings-open-link");
      if (link) link.addEventListener("click", openModal);
      return;
    }
    nodes.status.dataset.state = "set";
    const provider = providerFromStatus(status);
    const label = providerLabel(provider);
    const fp = status.llm_api_key_fingerprint
      ? ` - key ${status.llm_api_key_fingerprint}`
      : "";
    nodes.status.innerHTML = `Provider: <strong>${label}</strong>${fp}`;
    renderSetupProvider({ ...status, displayProvider: provider, displayLabel: label });
    updateSetupProgressDisclosure();
    updateReadiness();
  }

  function renderReindexBanner(status) {
    nodes.reindexBanner.hidden = !Boolean(status?.requires_reindex);
  }

  function renderSetupProvider(status) {
    if (!nodes.setupProviderTitle) return;
    if (!status) {
      nodes.setupProviderTitle.textContent = "Not configured";
      nodes.setupProviderTitle.closest(".setup-step-card").dataset.setupState = "needed";
      if (nodes.setupProviderAction) nodes.setupProviderAction.textContent = "Configure provider";
      if (nodes.setupSummary) {
        nodes.setupSummary.textContent =
          "Connect a model provider, load sources, then run the review.";
      }
      return;
    }
    nodes.setupProviderTitle.textContent = `${status.displayLabel} - ${status.llm_model}`;
    nodes.setupProviderTitle.closest(".setup-step-card").dataset.setupState = "ready";
    if (nodes.setupProviderAction) nodes.setupProviderAction.textContent = "Change provider";
    if (nodes.setupSummary) {
      nodes.setupSummary.textContent =
        "Provider ready. Load a deal room, then run the review.";
    }
  }

  async function fetchSettings() {
    const response = await fetch("/settings/provider", { headers: await authHeaders() });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`GET /settings/provider failed: ${response.status}`);
    return response.json();
  }

  function populateForm(status) {
    if (status) {
      nodes.llmProvider.value = providerFromStatus(status);
      nodes.llmModel.value = status.llm_model || "";
      nodes.llmBaseUrl.value = status.llm_base_url || "";
      nodes.embeddingProvider.value = status.embedding_provider || "";
      nodes.rerankerProvider.value = status.reranker_provider || "";
    } else {
      nodes.llmProvider.value = "fake";
      nodes.llmModel.value = "";
      nodes.llmBaseUrl.value = "";
      nodes.embeddingProvider.value = "";
      nodes.rerankerProvider.value = "";
    }
    clearUnsavedKey({ update: false });
    setKeyVisibility(false);
    lastTestResult = null;
    applyProviderDefaults(false);
    applyProviderUi();
  }

  async function refreshStatus() {
    const scope = currentScope().tenantId;
    lastFetchScope = scope;
    try {
      const status = await fetchSettings();
      if (lastFetchScope !== scope) return;
      renderStatus(status);
    } catch (error) {
      nodes.status.dataset.state = "error";
      nodes.status.textContent = `Provider: ${error.message}`;
    }
  }

  async function openModal(event) {
    if (event) event.preventDefault();
    nodes.resultLine.textContent = "";
    nodes.reindexBanner.hidden = true;
    try {
      const status = await fetchSettings();
      populateForm(status);
      renderStatus(status);
    } catch (error) {
      nodes.resultLine.textContent = error.message;
      nodes.status.dataset.state = "error";
      nodes.status.textContent = `Provider: ${error.message}`;
      populateForm(null);
    }
    if (typeof nodes.modal.showModal === "function") {
      nodes.modal.showModal();
    } else {
      nodes.modal.setAttribute("open", "open");
    }
  }

  function closeModal() {
    if (typeof nodes.modal.close === "function") {
      nodes.modal.close();
    } else {
      nodes.modal.removeAttribute("open");
    }
  }

  async function saveSettings(event) {
    event.preventDefault();
    if (!canSaveCurrentConfig()) {
      nodes.resultLine.textContent = "Test this provider before saving.";
      updateReadiness();
      return;
    }
    const body = providerPayload();
    if (!body) return;
    const response = await fetch("/settings/provider", {
      method: "PUT",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const detail = await response.text();
      nodes.resultLine.textContent = `Save failed: ${response.status} ${detail}`;
      return;
    }
    const status = await response.json();
    clearUnsavedKey({ update: false });
    setKeyVisibility(false);
    nodes.resultLine.textContent = status.requires_reindex
      ? "Saved. Re-upload sources to rebuild the index."
      : "Saved.";
    renderStatus(status);
    setTimeout(closeModal, 1200);
  }

  async function testConnection() {
    const savedConfigSelected = currentStatus && !nodes.llmApiKey.value && formMatchesStatus();
    const body = savedConfigSelected ? null : providerPayload();
    if (body === null && !savedConfigSelected) return;
    setTesting(true, "Testing connection...");
    try {
      const options = {
        method: "POST",
        headers: await authHeaders(
          body ? { "Content-Type": "application/json" } : {},
        ),
      };
      if (body) options.body = JSON.stringify(body);
      const response = await fetch("/settings/provider/test", options);
      const result = await response.json();
      lastTestResult = { signature: formSignature(keyEntryVersion), ok: response.ok && result.ok };
      if (!response.ok) {
        nodes.resultLine.textContent = result.detail || `Test failed: ${response.status}`;
        updateReadiness();
        return;
      }
      nodes.resultLine.textContent = result.ok
        ? `Connection verified for ${providerLabel(nodes.llmProvider.value)}.`
        : `Connection failed: ${result.detail}`;
      updateReadiness();
    } catch {
      lastTestResult = { signature: formSignature(keyEntryVersion), ok: false };
      nodes.resultLine.textContent = "Connection test failed.";
      updateReadiness();
    } finally {
      setTesting(false);
    }
  }

  function providerPayload() {
    applyProviderDefaults(false);
    const provider = nodes.llmProvider.value;
    const body = { llm_provider: provider === "gemini" ? "openai-compatible" : provider };
    if (nodes.llmModel.value.trim()) body.llm_model = nodes.llmModel.value.trim();
    if (["gemini", "openai-compatible", "ollama"].includes(provider)) {
      const baseUrl = nodes.llmBaseUrl.value.trim();
      if (!baseUrl) {
        nodes.resultLine.textContent = "Base URL required.";
        return null;
      }
      body.llm_base_url = baseUrl;
    }
    if (acceptsApiKey(provider)) {
      if (nodes.llmApiKey.value) {
        const issue = apiKeyInputIssue(provider, nodes.llmApiKey.value);
        if (issue) {
          nodes.resultLine.textContent = issue.message;
          updateReadiness();
          return null;
        }
        body.llm_api_key = nodes.llmApiKey.value;
      } else if (requiresApiKey(provider) && !canReuseSavedKey()) {
        nodes.resultLine.textContent = "API key required.";
        return null;
      }
    }
    if (nodes.embeddingProvider.value) {
      body.embedding_provider = nodes.embeddingProvider.value;
      body.embedding_dim = nodes.embeddingProvider.value === "bge-m3" ? 1024 : 384;
    }
    if (nodes.rerankerProvider.value) {
      body.reranker_provider = nodes.rerankerProvider.value;
    }
    return body;
  }

  function applyProviderDefaults(overwrite) {
    const provider = nodes.llmProvider.value;
    const preset = PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.fake;
    if (overwrite || !nodes.llmModel.value.trim()) {
      nodes.llmModel.value = preset.model;
    }
    if (overwrite || !nodes.llmBaseUrl.value.trim() || provider === "gemini") {
      nodes.llmBaseUrl.value = preset.baseUrl;
    }
    lastTestResult = null;
  }

  function formMatchesStatus() {
    const provider = providerFromStatus(currentStatus);
    return (
      nodes.llmProvider.value === provider &&
      nodes.llmModel.value.trim() === currentStatus.llm_model &&
      nodes.llmBaseUrl.value.trim().replace(/\/$/, "") ===
        (currentStatus.llm_base_url || "").replace(/\/$/, "")
    );
  }

  function canReuseSavedKey() {
    if (!currentStatus?.llm_api_key_fingerprint) return false;
    const provider = nodes.llmProvider.value;
    if (provider !== providerFromStatus(currentStatus)) return false;
    if (provider === "gemini" || provider === "openai-compatible") {
      return (
        nodes.llmBaseUrl.value.trim().replace(/\/$/, "") ===
        (currentStatus.llm_base_url || "").replace(/\/$/, "")
      );
    }
    return true;
  }

  function updateReadiness() {
    if (!nodes.readinessProvider) return;
    const provider = nodes.llmProvider.value;
    const keyIssue = apiKeyInputIssue(provider, nodes.llmApiKey.value);
    const savedKeyAvailable = canReuseSavedKey();
    const keyRequired = requiresApiKey(provider);
    const keyAccepted = acceptsApiKey(provider);
    updateKeyControls(provider);
    setKeyGuidance(
      keyGuidanceMessage(provider, nodes.llmApiKey.value, keyIssue, savedKeyAvailable),
    );
    setReadiness(
      nodes.readinessProvider,
      "ready",
      `${providerLabel(provider)} selected`,
    );
    if (!keyAccepted) {
      setReadiness(nodes.readinessKey, "ready", "No key required");
    } else if (nodes.llmApiKey.value && keyIssue) {
      setReadiness(nodes.readinessKey, "needed", "Check key format");
    } else if (nodes.llmApiKey.value) {
      setReadiness(nodes.readinessKey, "ready", "New write-only key entered");
    } else if (savedKeyAvailable) {
      setReadiness(
        nodes.readinessKey,
        "ready",
        `Saved key ${currentStatus.llm_api_key_fingerprint} will be reused`,
      );
    } else if (!keyRequired) {
      setReadiness(nodes.readinessKey, "ready", "Key optional");
    } else {
      setReadiness(nodes.readinessKey, "needed", "API key required");
    }

    if (lastTestResult?.signature === formSignature(keyEntryVersion)) {
      setReadiness(
        nodes.readinessTest,
        lastTestResult.ok ? "ready" : "needed",
        lastTestResult.ok ? "Connection verified" : "Connection not verified",
      );
    } else if (lastTestResult) {
      setReadiness(nodes.readinessTest, "needed", "Retest after changes");
    } else {
      setReadiness(nodes.readinessTest, "needed", "Not tested");
    }
    updateSaveState();
  }

  async function deleteSettings() {
    if (!confirm("Forget the provider config for this tenant?")) return;
    const response = await fetch("/settings/provider", {
      method: "DELETE",
      headers: await authHeaders(),
    });
    if (!response.ok && response.status !== 404) {
      nodes.resultLine.textContent = `Delete failed: ${response.status}`;
      return;
    }
    nodes.resultLine.textContent = "Forgotten.";
    populateForm(null);
    renderStatus(null);
    setTimeout(closeModal, 800);
  }

  function updateKeyControls(provider) {
    const showControls = acceptsApiKey(provider);
    if (nodes.keyToggleButton) {
      nodes.keyToggleButton.hidden = !showControls;
      nodes.keyToggleButton.disabled = !nodes.llmApiKey.value;
    }
    if (nodes.keyClearButton) {
      nodes.keyClearButton.hidden = !showControls;
      nodes.keyClearButton.disabled = !nodes.llmApiKey.value;
    }
    if (!showControls || !nodes.llmApiKey.value) {
      setKeyVisibility(false);
    }
  }

  function setKeyVisibility(visible) {
    if (!nodes.llmApiKey) return;
    nodes.llmApiKey.type = visible ? "text" : "password";
    if (!nodes.keyToggleButton) return;
    nodes.keyToggleButton.textContent = visible ? "Hide" : "Show";
    nodes.keyToggleButton.setAttribute("aria-pressed", visible ? "true" : "false");
  }

  function toggleKeyVisibility() {
    if (!nodes.llmApiKey.value) return;
    setKeyVisibility(nodes.llmApiKey.type === "password");
  }

  function clearKeyEntry() {
    clearUnsavedKey({ focus: true });
  }

  function clearUnsavedKey({ focus = false, update = true } = {}) {
    const hadValue = Boolean(nodes.llmApiKey.value);
    nodes.llmApiKey.value = "";
    nodes.resultLine.textContent = "";
    lastTestResult = null;
    if (hadValue) keyEntryVersion += 1;
    setKeyVisibility(false);
    if (!update) return;
    updateReadiness();
    if (focus) nodes.llmApiKey.focus();
  }

  function currentConnectionVerified() {
    return Boolean(
      lastTestResult?.signature === formSignature(keyEntryVersion) && lastTestResult.ok,
    );
  }

  function canSaveCurrentConfig() {
    const provider = nodes.llmProvider.value;
    if (!requiresApiKey(provider)) {
      return !nodes.llmApiKey.value || !apiKeyInputIssue(provider, nodes.llmApiKey.value);
    }
    if (!nodes.llmApiKey.value && currentStatus && formMatchesStatus()) return true;
    return currentConnectionVerified();
  }

  function updateSaveState() {
    if (!nodes.saveButton || !nodes.saveGuidance) return;
    const canSave = canSaveCurrentConfig();
    nodes.saveButton.disabled = !canSave;
    nodes.saveButton.title = canSave ? "" : "Test this provider before saving.";
    if (canSave) {
      nodes.saveGuidance.dataset.guidanceState = "ready";
      nodes.saveGuidance.textContent = currentConnectionVerified()
        ? "Connection verified. Ready to save."
        : "Ready to save.";
      return;
    }
    nodes.saveGuidance.dataset.guidanceState = "needed";
    nodes.saveGuidance.textContent = "Test this provider before saving.";
  }

  nodes.openButton.addEventListener("click", openModal);
  if (nodes.setupProviderAction) nodes.setupProviderAction.addEventListener("click", openModal);
  nodes.closeButton.addEventListener("click", closeModal);
  nodes.form.addEventListener("submit", saveSettings);
  nodes.deleteButton.addEventListener("click", deleteSettings);
  nodes.testButton.addEventListener("click", testConnection);
  nodes.keyToggleButton?.addEventListener("click", toggleKeyVisibility);
  nodes.keyClearButton?.addEventListener("click", clearKeyEntry);
  nodes.llmProvider.addEventListener("change", () => {
    nodes.resultLine.textContent = "";
    clearUnsavedKey({ update: false });
    applyProviderDefaults(true);
    applyProviderUi();
  });
  for (const node of [nodes.llmModel, nodes.llmBaseUrl, nodes.llmApiKey]) {
    node.addEventListener("input", () => {
      nodes.resultLine.textContent = "";
      if (node === nodes.llmApiKey) {
        keyEntryVersion += 1;
        lastTestResult = null;
      }
      updateReadiness();
    });
  }
  tenantNode.addEventListener("change", refreshStatus);

  applyProviderDefaults(false);
  applyProviderUi();
  refreshStatus();
}

function providerFromStatus(status) {
  if (
    status?.llm_provider === "openai-compatible" &&
    (status.llm_base_url || "").replace(/\/$/, "") === GEMINI_BASE_URL
  ) {
    return "gemini";
  }
  return status?.llm_provider || "fake";
}

function providerLabel(provider) {
  return PROVIDER_PRESETS[provider]?.label || provider;
}

function requiresApiKey(provider) {
  return ["gemini", "anthropic", "openai"].includes(provider);
}

function acceptsApiKey(provider) {
  return ["gemini", "anthropic", "openai", "openai-compatible"].includes(provider);
}

function formSignature(keyEntryVersion = 0) {
  const provider = document.getElementById("settings-llm-provider").value;
  const model = document.getElementById("settings-llm-model").value.trim();
  const baseUrl = document.getElementById("settings-llm-base-url").value.trim().replace(/\/$/, "");
  const hasNewKey = Boolean(document.getElementById("settings-llm-api-key").value);
  const newKeyVersion = hasNewKey ? keyEntryVersion : null;
  return JSON.stringify({ provider, model, baseUrl, hasNewKey, newKeyVersion });
}

function setReadiness(node, state, text) {
  if (!node) return;
  node.textContent = text;
  node.closest("[data-readiness-state]").dataset.readinessState = state;
}

function apiKeyPlaceholder(provider) {
  const labels = {
    gemini: "Gemini API key from AI Studio",
    openai: "OpenAI API key",
    anthropic: "Anthropic API key",
    "openai-compatible": "Optional provider API key",
  };
  return labels[provider] || "Write-only server secret";
}

function apiKeyInputIssue(provider, value) {
  if (!value) return null;
  if (value.trim().startsWith("{") || value.includes("\n") || value.includes("\r")) {
    return {
      state: "warning",
      message:
        "This looks like JSON or a multi-line credential. Paste a single provider API key instead.",
    };
  }
  if (/\s/.test(value)) {
    return {
      state: "warning",
      message:
        provider === "gemini"
          ? "Gemini expects a single API key from AI Studio; remove spaces or line breaks."
          : "Remove spaces or line breaks before testing the key.",
    };
  }
  if (provider === "gemini" && (value.startsWith("ya29.") || value.startsWith("1//"))) {
    return {
      state: "warning",
      message: "This looks like an OAuth token. Use a Gemini API key from AI Studio.",
    };
  }
  return null;
}

function keyGuidanceMessage(provider, value, issue, savedKeyAvailable) {
  if (!acceptsApiKey(provider)) {
    return { state: "ready", text: "No API key is needed for the offline demo." };
  }
  if (issue) return { state: issue.state, text: issue.message };
  if (!value) {
    if (savedKeyAvailable) {
      return {
        state: "ready",
        text: "Saved write-only key will be reused for this provider and base URL.",
      };
    }
    if (!requiresApiKey(provider)) {
      return {
        state: "ready",
        text: "API key optional. Leave blank for a local no-auth endpoint.",
      };
    }
    return {
      state: "needed",
      text: "Paste a provider API key. It is encrypted after saving and never shown again.",
    };
  }
  return {
    state: "ready",
    text: "New write-only key entered. Test connection before saving.",
  };
}

function setKeyGuidance(result) {
  const node = document.getElementById("settings-key-guidance");
  if (!node || !result) return;
  node.dataset.guidanceState = result.state;
  node.textContent = result.text;
}

function setTesting(testing, message = "") {
  const button = document.getElementById("settings-test");
  if (!button) return;
  button.disabled = testing;
  const saveButton = document.getElementById("settings-save");
  if (saveButton) saveButton.disabled = testing || saveButton.disabled;
  if (message) document.getElementById("settings-result").textContent = message;
}
