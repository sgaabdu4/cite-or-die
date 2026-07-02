import { updateSetupProgressDisclosure } from "./setup_progress.js?v=setup-progress-v2";
import {
  BASE_URL_PROVIDERS,
  KEY_REUSE_BASE_URL_PROVIDERS,
  acceptsApiKey,
  apiKeyInputIssue,
  apiKeyPlaceholder,
  embeddingDimension,
  keyGuidanceMessage,
  keyInputType,
  normalizedUrl,
  providerFromStatus,
  providerGuidance,
  providerLabel,
  providerPayloadName,
  providerPreset,
  providerSetupView,
  reindexRequired,
  requiresApiKey,
  setOptionalDisabled,
  setOptionalText,
  setTesting,
  shouldApplyDefault,
  shouldHideKey,
  skipConnectionTest,
  updateKeyControl,
  updateKeyToggleState,
} from "./settings_helpers.js?v=provider-setup-v7";

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
    reindexButton: document.getElementById("settings-reindex"),
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
    const preset = providerPreset(provider);
    nodes.llmBaseUrl.readOnly = provider === "gemini";
    nodes.llmModel.placeholder = preset.model || "Model name";
    nodes.llmApiKey.placeholder = apiKeyPlaceholder(provider);
    updateProviderGuidance(provider);
    updateReadiness();
  }

  function updateProviderGuidance(provider) {
    const guidance = providerGuidance(provider);
    setOptionalText(nodes.guideProvider, guidance.provider);
    setOptionalText(nodes.guideKey, guidance.key);
    setOptionalText(nodes.guideTest, guidance.test);
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
    const required = Boolean(status?.requires_reindex);
    nodes.reindexBanner.hidden = !required;
    if (nodes.reindexButton) nodes.reindexButton.disabled = !required;
  }

  function renderSetupProvider(status) {
    if (!nodes.setupProviderTitle) return;
    const setup = providerSetupView(status);
    nodes.setupProviderTitle.textContent = setup.title;
    nodes.setupProviderTitle.closest(".setup-step-card").dataset.setupState = setup.state;
    setOptionalText(nodes.setupProviderAction, setup.action);
    setOptionalText(nodes.setupSummary, setup.summary);
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
      ? "Saved. Rebuild the source index."
      : "Saved.";
    renderStatus(status);
    if (!status.requires_reindex) setTimeout(closeModal, 1200);
  }

  async function reindexSources() {
    if (!reindexRequired(currentStatus)) return;
    nodes.resultLine.textContent = "Rebuilding source index...";
    setOptionalDisabled(nodes.reindexButton, true);
    const response = await fetch("/settings/provider/reindex", {
      method: "POST",
      headers: await authHeaders(),
    });
    if (!response.ok) {
      await renderReindexFailure(response);
      return;
    }
    const status = await response.json();
    nodes.resultLine.textContent = "Index rebuilt.";
    renderStatus(status);
  }

  async function testConnection() {
    const savedConfigSelected = usingSavedConfigForTest();
    const body = connectionTestBody(savedConfigSelected);
    if (skipConnectionTest(savedConfigSelected, body)) return;
    const testedSignature = formSignature(keyEntryVersion);
    const testedProvider = nodes.llmProvider.value;
    setTesting(true, "Testing connection...");
    try {
      const { response, result } = await fetchConnectionTest(body);
      applyConnectionTestResult(response, result, testedSignature, testedProvider);
    } catch {
      applyConnectionTestFailure(testedSignature);
    } finally {
      setTesting(false);
    }
  }

  function providerPayload() {
    applyProviderDefaults(false);
    const provider = nodes.llmProvider.value;
    const body = { llm_provider: providerPayloadName(provider) };
    applyModel(body);
    if (!applyBaseUrl(body, provider)) return null;
    if (!applyApiKey(body, provider)) return null;
    applyEmbedding(body);
    applyReranker(body);
    return body;
  }

  function applyProviderDefaults(overwrite) {
    const provider = nodes.llmProvider.value;
    const preset = providerPreset(provider);
    if (shouldApplyDefault(nodes.llmModel.value, overwrite)) {
      nodes.llmModel.value = preset.model;
    }
    if (shouldApplyBaseDefault(provider, overwrite)) {
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
    if (!savedKeyFingerprint()) return false;
    return savedKeyReusableForProvider(nodes.llmProvider.value);
  }

  function updateReadiness() {
    if (!nodes.readinessProvider) return;
    const readiness = readinessContext();
    updateKeyControls(readiness.provider);
    setKeyGuidance(
      keyGuidanceMessage(
        readiness.provider,
        readiness.keyValue,
        readiness.keyIssue,
        readiness.savedKeyAvailable,
      ),
    );
    updateProviderReadiness(readiness.provider);
    updateKeyReadiness(readiness);
    updateTestReadiness();
    updateSaveState();
  }

  async function renderReindexFailure(response) {
    const detail = await response.text();
    nodes.resultLine.textContent = `Rebuild failed: ${response.status} ${detail}`;
    renderReindexBanner(currentStatus);
  }

  function usingSavedConfigForTest() {
    if (!currentStatus) return false;
    if (nodes.llmApiKey.value) return false;
    return formMatchesStatus();
  }

  function connectionTestBody(savedConfigSelected) {
    if (savedConfigSelected) return null;
    return providerPayload();
  }

  async function fetchConnectionTest(body) {
    const response = await fetch("/settings/provider/test", {
      method: "POST",
      headers: await authHeaders(testHeaders(body)),
      body: testBody(body),
    });
    return { response, result: await response.json() };
  }

  function testHeaders(body) {
    if (body) return { "Content-Type": "application/json" };
    return {};
  }

  function testBody(body) {
    if (body) return JSON.stringify(body);
    return undefined;
  }

  function applyConnectionTestResult(response, result, signature, provider) {
    lastTestResult = { signature, ok: connectionTestPassed(response, result) };
    if (!response.ok) {
      nodes.resultLine.textContent = connectionHttpFailureMessage(response, result);
      updateReadiness();
      return;
    }
    nodes.resultLine.textContent = connectionResultMessage(provider, result);
    updateReadiness();
  }

  function connectionTestPassed(response, result) {
    if (!response.ok) return false;
    return Boolean(result.ok);
  }

  function connectionHttpFailureMessage(response, result) {
    if (result.detail) return result.detail;
    return `Test failed: ${response.status}`;
  }

  function connectionResultMessage(provider, result) {
    if (result.ok) return `Connection verified for ${providerLabel(provider)}.`;
    return `Connection failed: ${result.detail}`;
  }

  function applyConnectionTestFailure(signature) {
    lastTestResult = { signature, ok: false };
    nodes.resultLine.textContent = "Connection test failed.";
    updateReadiness();
  }

  function applyModel(body) {
    const model = nodes.llmModel.value.trim();
    if (model) body.llm_model = model;
  }

  function applyBaseUrl(body, provider) {
    if (!BASE_URL_PROVIDERS.has(provider)) return true;
    const baseUrl = nodes.llmBaseUrl.value.trim();
    if (!baseUrl) {
      nodes.resultLine.textContent = "Base URL required.";
      return false;
    }
    body.llm_base_url = baseUrl;
    return true;
  }

  function applyApiKey(body, provider) {
    if (!acceptsApiKey(provider)) return true;
    const value = nodes.llmApiKey.value;
    if (value) return applyNewApiKey(body, provider, value);
    if (missingRequiredApiKey(provider)) {
      nodes.resultLine.textContent = "API key required.";
      return false;
    }
    return true;
  }

  function applyNewApiKey(body, provider, value) {
    const issue = apiKeyInputIssue(provider, value);
    if (issue) {
      nodes.resultLine.textContent = issue.message;
      updateReadiness();
      return false;
    }
    body.llm_api_key = value;
    return true;
  }

  function missingRequiredApiKey(provider) {
    if (!requiresApiKey(provider)) return false;
    return !canReuseSavedKey();
  }

  function applyEmbedding(body) {
    const provider = nodes.embeddingProvider.value;
    if (!provider) return;
    body.embedding_provider = provider;
    body.embedding_dim = embeddingDimension(provider);
  }

  function applyReranker(body) {
    if (nodes.rerankerProvider.value) body.reranker_provider = nodes.rerankerProvider.value;
  }

  function shouldApplyBaseDefault(provider, overwrite) {
    if (provider === "gemini") return true;
    return shouldApplyDefault(nodes.llmBaseUrl.value, overwrite);
  }

  function savedKeyFingerprint() {
    if (!currentStatus) return "";
    return currentStatus.llm_api_key_fingerprint || "";
  }

  function savedKeyReusableForProvider(provider) {
    if (provider !== providerFromStatus(currentStatus)) return false;
    return savedKeyReusableForBase(provider);
  }

  function savedKeyReusableForBase(provider) {
    if (KEY_REUSE_BASE_URL_PROVIDERS.has(provider)) return baseUrlMatchesStatus();
    return true;
  }

  function baseUrlMatchesStatus() {
    return normalizedUrl(nodes.llmBaseUrl.value) === normalizedUrl(currentStatus.llm_base_url);
  }

  function readinessContext() {
    const provider = nodes.llmProvider.value;
    const keyValue = nodes.llmApiKey.value;
    return {
      provider,
      keyValue,
      keyIssue: apiKeyInputIssue(provider, keyValue),
      keyRequired: requiresApiKey(provider),
      keyAccepted: acceptsApiKey(provider),
      savedKeyAvailable: canReuseSavedKey(),
    };
  }

  function updateProviderReadiness(provider) {
    setReadiness(nodes.readinessProvider, "ready", `${providerLabel(provider)} selected`);
  }

  function updateKeyReadiness(readiness) {
    const key = keyReadiness(readiness);
    setReadiness(nodes.readinessKey, key.state, key.text);
  }

  function keyReadiness(readiness) {
    if (!readiness.keyAccepted) return { state: "ready", text: "No key required" };
    if (readiness.keyValue) return enteredKeyReadiness(readiness);
    return blankKeyReadiness(readiness);
  }

  function enteredKeyReadiness(readiness) {
    if (readiness.keyIssue) return { state: "needed", text: "Check key format" };
    return { state: "ready", text: "New write-only key entered" };
  }

  function blankKeyReadiness(readiness) {
    if (readiness.savedKeyAvailable) return savedKeyReadiness();
    if (readiness.keyRequired) return { state: "needed", text: "API key required" };
    return { state: "ready", text: "Key optional" };
  }

  function savedKeyReadiness() {
    return {
      state: "ready",
      text: `Saved key ${currentStatus.llm_api_key_fingerprint} will be reused`,
    };
  }

  function updateTestReadiness() {
    const test = testReadiness();
    setReadiness(nodes.readinessTest, test.state, test.text);
  }

  function testReadiness() {
    if (currentTestResultApplies()) return verifiedTestReadiness();
    if (lastTestResult) return { state: "needed", text: "Retest after changes" };
    return { state: "needed", text: "Not tested" };
  }

  function currentTestResultApplies() {
    if (!lastTestResult) return false;
    return lastTestResult.signature === formSignature(keyEntryVersion);
  }

  function verifiedTestReadiness() {
    if (lastTestResult.ok) return { state: "ready", text: "Connection verified" };
    return { state: "needed", text: "Connection not verified" };
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
    updateKeyControl(nodes.keyToggleButton, showControls);
    updateKeyControl(nodes.keyClearButton, showControls);
    if (shouldHideKey(showControls, nodes.llmApiKey.value)) {
      setKeyVisibility(false);
    }
  }

  function setKeyVisibility(visible) {
    if (!nodes.llmApiKey) return;
    nodes.llmApiKey.type = keyInputType(visible);
    updateKeyToggleState(nodes.keyToggleButton, visible);
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

  function canSaveWithoutConnectionTest(provider) {
    if (provider === "fake") return true;
    return savedConfigSelectedForSave();
  }

  function savedConfigSelectedForSave() {
    if (!currentStatus) return false;
    if (nodes.llmApiKey.value) return false;
    return formMatchesStatus();
  }

  function canSaveCurrentConfig() {
    if (canSaveWithoutConnectionTest(nodes.llmProvider.value)) return true;
    return currentConnectionVerified();
  }

  function updateSaveState() {
    if (!nodes.saveButton || !nodes.saveGuidance) return;
    const guidance = saveGuidance(canSaveCurrentConfig());
    nodes.saveButton.disabled = guidance.disabled;
    nodes.saveButton.title = guidance.title;
    nodes.saveGuidance.dataset.guidanceState = guidance.state;
    nodes.saveGuidance.textContent = guidance.text;
  }

  function saveGuidance(canSave) {
    if (canSave) return readySaveGuidance();
    return {
      disabled: true,
      title: "Test this provider before saving.",
      state: "needed",
      text: "Test this provider before saving.",
    };
  }

  function readySaveGuidance() {
    return {
      disabled: false,
      title: "",
      state: "ready",
      text: readySaveText(),
    };
  }

  function readySaveText() {
    if (currentConnectionVerified()) return "Connection verified. Ready to save.";
    return "Ready to save.";
  }

  nodes.openButton.addEventListener("click", openModal);
  if (nodes.setupProviderAction) nodes.setupProviderAction.addEventListener("click", openModal);
  nodes.closeButton.addEventListener("click", closeModal);
  nodes.form.addEventListener("submit", saveSettings);
  nodes.deleteButton.addEventListener("click", deleteSettings);
  nodes.testButton.addEventListener("click", testConnection);
  nodes.reindexButton?.addEventListener("click", reindexSources);
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

function setKeyGuidance(result) {
  const node = document.getElementById("settings-key-guidance");
  if (!node || !result) return;
  node.dataset.guidanceState = result.state;
  node.textContent = result.text;
}
