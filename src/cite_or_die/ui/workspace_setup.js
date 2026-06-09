const DEFAULT_TENANT = "dev";
const DEFAULT_MATTER = "m_default";

function normalizeScopeValue(value, fallback) {
  return value.trim() || fallback;
}

function openDialog(dialog) {
  if (typeof dialog.showModal === "function") {
    dialog.showModal();
  } else {
    dialog.setAttribute("open", "open");
  }
}

function closeDialog(dialog) {
  if (typeof dialog.close === "function") {
    dialog.close();
  } else {
    dialog.removeAttribute("open");
  }
}

export function initWorkspaceSetup({ nodes, currentScope, onScopeChange }) {
  let applyingSetup = false;

  function updateSummary() {
    const tenantId = normalizeScopeValue(nodes.tenant.value, DEFAULT_TENANT);
    const matterId = normalizeScopeValue(nodes.matter.value, DEFAULT_MATTER);
    nodes.workspaceSummary.textContent = `${tenantId} / ${matterId}`;
  }

  async function changeScope() {
    updateSummary();
    await onScopeChange();
  }

  function syncSetupInputs() {
    const { tenantId, matterId } = currentScope();
    nodes.setupTenant.value = tenantId;
    nodes.setupMatter.value = matterId;
  }

  function openSetup() {
    syncSetupInputs();
    updateSummary();
    openDialog(nodes.setupModal);
    nodes.setupTenant.focus();
  }

  function closeSetup() {
    closeDialog(nodes.setupModal);
  }

  async function submitSetup(event) {
    event.preventDefault();
    const nextTenant = normalizeScopeValue(nodes.setupTenant.value, DEFAULT_TENANT);
    const nextMatter = normalizeScopeValue(nodes.setupMatter.value, DEFAULT_MATTER);
    const changed = nodes.tenant.value !== nextTenant || nodes.matter.value !== nextMatter;
    nodes.tenant.value = nextTenant;
    nodes.matter.value = nextMatter;
    closeSetup();
    if (!changed) {
      updateSummary();
      return;
    }
    applyingSetup = true;
    nodes.tenant.dispatchEvent(new Event("change", { bubbles: true }));
    nodes.matter.dispatchEvent(new Event("change", { bubbles: true }));
    applyingSetup = false;
    await changeScope();
  }

  function handleInlineScopeChange() {
    if (!applyingSetup) void changeScope();
  }

  function openProviderSettings() {
    closeSetup();
    nodes.openSettings.click();
  }

  function focusSources() {
    closeSetup();
    nodes.sourcesPane.scrollIntoView({ block: "start" });
    nodes.file.focus();
  }

  nodes.setupButton.addEventListener("click", openSetup);
  nodes.setupClose.addEventListener("click", closeSetup);
  nodes.setupForm.addEventListener("submit", submitSetup);
  nodes.setupProvider.addEventListener("click", openProviderSettings);
  nodes.setupUpload.addEventListener("click", focusSources);
  nodes.tenant.addEventListener("input", updateSummary);
  nodes.matter.addEventListener("input", updateSummary);
  nodes.tenant.addEventListener("change", handleInlineScopeChange);
  nodes.matter.addEventListener("change", handleInlineScopeChange);

  updateSummary();
}
