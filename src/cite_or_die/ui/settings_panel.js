export function initSettingsPanel({ authHeaders, currentScope, tenantNode }) {
  const nodes = {
    status: document.getElementById("settings-status"),
    openButton: document.getElementById("open-settings"),
    modal: document.getElementById("settings-modal"),
    closeButton: document.getElementById("settings-close"),
    form: document.getElementById("settings-form"),
    llmProvider: document.getElementById("settings-llm-provider"),
    llmModel: document.getElementById("settings-llm-model"),
    llmBaseUrl: document.getElementById("settings-llm-base-url"),
    llmApiKey: document.getElementById("settings-llm-api-key"),
    embeddingProvider: document.getElementById("settings-embedding-provider"),
    rerankerProvider: document.getElementById("settings-reranker-provider"),
    deleteButton: document.getElementById("settings-delete"),
    resultLine: document.getElementById("settings-result"),
    reindexBanner: document.getElementById("settings-reindex-banner"),
  };
  let lastFetchScope = "";

  function applyConditionalVisibility() {
    const provider = nodes.llmProvider.value;
    for (const el of document.querySelectorAll(".settings-conditional")) {
      const matches = el.dataset.showFor.split(" ").includes(provider);
      el.hidden = !matches;
    }
  }

  function renderStatus(status) {
    if (!status) {
      nodes.status.dataset.state = "empty";
      nodes.status.innerHTML =
        'Provider: <strong>not configured</strong> - <a href="#" id="settings-open-link">set up</a>';
      const link = document.getElementById("settings-open-link");
      if (link) link.addEventListener("click", openModal);
      return;
    }
    nodes.status.dataset.state = "set";
    const fp = status.llm_api_key_fingerprint
      ? ` - key ${status.llm_api_key_fingerprint}`
      : "";
    nodes.status.innerHTML = `Provider: <strong>${status.llm_provider}</strong> (${status.llm_model})${fp}`;
  }

  async function fetchSettings() {
    const response = await fetch("/settings/provider", { headers: await authHeaders() });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`GET /settings/provider failed: ${response.status}`);
    return response.json();
  }

  function populateForm(status) {
    if (status) {
      nodes.llmProvider.value = status.llm_provider;
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
    nodes.llmApiKey.value = "";
    applyConditionalVisibility();
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
    const provider = nodes.llmProvider.value;
    const body = { llm_provider: provider };
    if (nodes.llmModel.value.trim()) body.llm_model = nodes.llmModel.value.trim();
    if (["openai-compatible", "ollama"].includes(provider) && nodes.llmBaseUrl.value.trim()) {
      body.llm_base_url = nodes.llmBaseUrl.value.trim();
    }
    if (["anthropic", "openai", "openai-compatible"].includes(provider) && nodes.llmApiKey.value) {
      body.llm_api_key = nodes.llmApiKey.value;
    }
    if (nodes.embeddingProvider.value) {
      body.embedding_provider = nodes.embeddingProvider.value;
      body.embedding_dim = nodes.embeddingProvider.value === "bge-m3" ? 1024 : 384;
    }
    if (nodes.rerankerProvider.value) {
      body.reranker_provider = nodes.rerankerProvider.value;
    }
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
    nodes.llmApiKey.value = "";
    nodes.reindexBanner.hidden = !status.requires_reindex;
    nodes.resultLine.textContent = status.requires_reindex
      ? "Saved. Re-upload sources to rebuild the index."
      : "Saved.";
    renderStatus(status);
    setTimeout(closeModal, 1200);
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

  nodes.openButton.addEventListener("click", openModal);
  nodes.closeButton.addEventListener("click", closeModal);
  nodes.form.addEventListener("submit", saveSettings);
  nodes.deleteButton.addEventListener("click", deleteSettings);
  nodes.llmProvider.addEventListener("change", applyConditionalVisibility);
  tenantNode.addEventListener("change", refreshStatus);

  applyConditionalVisibility();
  refreshStatus();
}
