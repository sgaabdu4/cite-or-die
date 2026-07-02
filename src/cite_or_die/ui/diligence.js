import { updateSetupProgressDisclosure } from "./setup_progress.js?v=setup-progress-v3";

const SYNTHETIC_DEAL_ROOM = [
  {
    filename: "01-customer-contract-scan.txt",
    text:
      "Master services agreement for Northstar Managed Services. " +
      "Change of control consent is required before assignment. " +
      "Termination for convenience can be exercised on 30 days notice.",
  },
  {
    filename: "02-financial-pack-fy26.txt",
    text:
      "FY26 revenue is GBP 180m. Reported EBITDA is GBP 24m. " +
      "Management normalisation adds GBP 5m for restructuring costs. " +
      "Vendor response states recurring restructuring costs are GBP 4m.",
  },
  {
    filename: "03-operations-report.txt",
    text:
      "Operational report shows utilisation at 72 percent and SLA backlog at 19 days. " +
      "Three offshore delivery leads own transition-critical workflows.",
  },
  {
    filename: "04-customer-data-export.txt",
    text:
      "Top customer represents 34 percent of revenue. " +
      "Customer churn is 16 percent and renewal status is incomplete for two key accounts.",
  },
  {
    filename: "05-hr-records.txt",
    text:
      "HR records show 940 employees, regretted attrition of 18 percent, " +
      "and 42 open vacancies in delivery roles.",
  },
  {
    filename: "06-qa-log-and-ir-list.txt",
    text:
      "Information request HR attrition schedule remains open and delayed by 12 days. " +
      "Vendor response does not provide supporting payroll detail.",
  },
];

const state = {
  deal: null,
  sources: [],
  result: null,
  activeView: "sources",
  busy: false,
  selectedDocIds: () => [],
};

export function initDiligenceWorkspace({
  authHeaders,
  currentScope,
  refreshDocuments,
  selectedDocIds,
}) {
  const nodes = {
    workspace: document.getElementById("diligence-workspace"),
    loadDemo: document.getElementById("diligence-load-demo"),
    loadDemoInline: document.getElementById("diligence-load-demo-inline"),
    loadSelected: document.getElementById("diligence-load-selected"),
    loadSelectedInline: document.getElementById("diligence-load-selected-inline"),
    run: document.getElementById("diligence-run"),
    runInline: document.getElementById("diligence-run-inline"),
    assist: document.getElementById("diligence-assist"),
    setupDealTitle: document.getElementById("setup-deal-title"),
    setupRunTitle: document.getElementById("setup-run-title"),
    status: document.getElementById("diligence-status"),
    dealMeta: document.getElementById("diligence-deal-meta"),
    sourceCount: document.getElementById("diligence-source-count"),
    factCount: document.getElementById("diligence-fact-count"),
    riskCount: document.getElementById("diligence-risk-count"),
    reviewStatus: document.getElementById("diligence-review-status"),
    sourceLibrary: document.getElementById("diligence-source-library"),
    extractionTable: document.getElementById("diligence-extraction-table"),
    riskRegister: document.getElementById("diligence-risk-register"),
    insightList: document.getElementById("diligence-insight-list"),
    irTracker: document.getElementById("diligence-ir-tracker"),
    reportDrafts: document.getElementById("diligence-report-drafts"),
    tabs: [...document.querySelectorAll("[data-diligence-view-tab]")],
    views: [...document.querySelectorAll("[data-diligence-view]")],
  };
  if (!nodes.workspace) return;
  state.selectedDocIds = selectedDocIds || (() => []);

  nodes.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveView(nodes, tab.dataset.diligenceViewTab));
  });
  nodes.loadDemo.addEventListener("click", () =>
    loadSyntheticDealRoom(nodes, authHeaders, refreshDocuments),
  );
  nodes.loadDemoInline?.addEventListener("click", () =>
    loadSyntheticDealRoom(nodes, authHeaders, refreshDocuments),
  );
  nodes.loadSelected?.addEventListener("click", () => loadSelectedSources(nodes, authHeaders));
  nodes.loadSelectedInline?.addEventListener("click", () =>
    loadSelectedSources(nodes, authHeaders),
  );
  nodes.run.addEventListener("click", () => runAccelerator(nodes, authHeaders));
  nodes.runInline?.addEventListener("click", () => runAccelerator(nodes, authHeaders));
  nodes.assist?.addEventListener("click", () => runProviderAssistedReview(nodes, authHeaders));
  document.addEventListener("cod:workspace-changed", () => resetDiligence(nodes));
  document.addEventListener("cod:source-selection-changed", () => updateUi(nodes));
  updateUi(nodes);
}

async function loadSyntheticDealRoom(nodes, authHeaders, refreshDocuments) {
  await withBusyStatus(nodes, "Loading sample deal pack...", "Sample load failed.", async () => {
    const sourceDocIds = await uploadSyntheticSources(authHeaders);
    await refreshDocumentList(refreshDocuments);
    await createAndClassifySyntheticDeal(nodes, authHeaders, sourceDocIds);
  });
}

async function runAccelerator(nodes, authHeaders) {
  if (!state.deal) {
    setStatus(nodes, "Add deal files first.");
    return;
  }
  await withBusyStatus(nodes, "Running accelerator...", "Diligence run failed.", async () => {
    state.result = await postJson(`/diligence/deals/${state.deal.deal_id}/run`, authHeaders);
    state.sources = state.result.knowledge_base.sources || state.sources;
    setActiveView(nodes, "risks");
    setStatus(nodes, "Accelerator run complete. Human sign-off required.");
    updateUi(nodes);
  });
}

async function runProviderAssistedReview(nodes, authHeaders) {
  if (!state.result) {
    setStatus(nodes, "Run the accelerator first.");
    return;
  }
  await withBusyStatus(
    nodes,
    "Running AI-assisted review...",
    "AI-assisted review failed.",
    async () => {
      const assisted = await postJson(
        `/diligence/deals/${state.deal.deal_id}/assist`,
        authHeaders,
      );
      const drafts = state.result.report_drafts || [];
      state.result.report_drafts = [
        ...drafts.filter((draft) => !draft.provider_assistance),
        assisted.report_draft,
      ];
      setActiveView(nodes, "reports");
      setStatus(nodes, "AI-assisted review added. Human sign-off required.");
      updateUi(nodes);
    },
  );
}

async function withBusyStatus(nodes, busyMessage, failureMessage, operation) {
  setBusy(nodes, true, busyMessage);
  try {
    await operation();
  } catch (error) {
    setStatus(nodes, error.message || failureMessage);
  } finally {
    setBusy(nodes, false);
  }
}

async function uploadSyntheticSources(authHeaders) {
  const sourceDocIds = [];
  for (const source of SYNTHETIC_DEAL_ROOM) {
    const docId = await uploadSyntheticSource(source, authHeaders);
    if (docId) sourceDocIds.push(docId);
  }
  return sourceDocIds;
}

async function uploadSyntheticSource(source, authHeaders) {
  const body = new FormData();
  body.set("file", new File([source.text], source.filename, { type: "text/plain" }));
  const upload = await fetch("/upload", {
    method: "POST",
    headers: await authHeaders(),
    body,
  });
  if (!upload.ok) throw new Error(await responseMessage(upload, "Upload failed"));
  const uploaded = await upload.json();
  return uploaded.document?.doc_id || null;
}

async function refreshDocumentList(refreshDocuments) {
  if (refreshDocuments) await refreshDocuments();
}

async function createAndClassifySyntheticDeal(nodes, authHeaders, sourceDocIds) {
  const deal = await createSyntheticDeal(authHeaders, sourceDocIds);
  await setDealAndClassify(nodes, authHeaders, deal, "Deal files loaded. Run the accelerator when ready.");
}

async function loadSelectedSources(nodes, authHeaders) {
  const sourceDocIds = selectedSourceIds();
  if (!sourceDocIds.length) {
    setStatus(nodes, "Select sources first.");
    return;
  }
  await withBusyStatus(
    nodes,
    "Creating review from selected sources...",
    "Selected-source review failed.",
    async () => {
      const deal = await createSelectedDeal(authHeaders, sourceDocIds);
      await setDealAndClassify(
        nodes,
        authHeaders,
        deal,
        "Selected files loaded. Run the accelerator when ready.",
      );
    },
  );
}

async function setDealAndClassify(nodes, authHeaders, deal, statusMessage) {
  state.deal = deal;
  state.sources = await postJson(`/diligence/deals/${deal.deal_id}/sources/classify`, authHeaders);
  state.result = null;
  setActiveView(nodes, "sources");
  setStatus(nodes, statusMessage);
  updateUi(nodes);
}

async function createSyntheticDeal(authHeaders, sourceDocIds) {
  return postJson("/diligence/deals", authHeaders, {
    name: "Project Northstar",
    target_business: "Northstar Managed Services",
    target_revenue_gbp_m: 180,
    horizon_weeks: 6,
    source_doc_ids: sourceDocIds,
  });
}

async function createSelectedDeal(authHeaders, sourceDocIds) {
  return postJson("/diligence/deals", authHeaders, {
    name: "Selected Source Review",
    target_business: "Selected source set",
    target_revenue_gbp_m: 150,
    horizon_weeks: 6,
    source_doc_ids: sourceDocIds,
  });
}

async function postJson(path, authHeaders, payload = null) {
  const options = {
    method: "POST",
    headers: await authHeaders({ "Content-Type": "application/json" }),
  };
  if (payload) options.body = JSON.stringify(payload);
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await responseMessage(response, `${path} failed`));
  return response.json();
}

async function responseMessage(response, fallback) {
  try {
    const body = await response.json();
    return body.detail || `${fallback}: ${response.status}`;
  } catch {
    return `${fallback}: ${response.status}`;
  }
}

function setActiveView(nodes, viewName) {
  state.activeView = viewName || "sources";
  nodes.tabs.forEach((tab) => {
    const active = tab.dataset.diligenceViewTab === state.activeView;
    tab.setAttribute("aria-selected", String(active));
  });
  nodes.views.forEach((view) => {
    view.hidden = view.dataset.diligenceView !== state.activeView;
  });
}

function setBusy(nodes, busy, message = "") {
  state.busy = busy;
  updateActionState(nodes);
  if (message) setStatus(nodes, message);
}

function setStatus(nodes, message) {
  nodes.status.textContent = message;
}

function resetDiligence(nodes) {
  state.deal = null;
  state.sources = [];
  state.result = null;
  setActiveView(nodes, "sources");
  setStatus(nodes, "Add deal files, then run the accelerator.");
  updateUi(nodes);
}

function updateUi(nodes) {
  const facts = currentFacts();
  const findings = currentFindings();
  updateSummary(nodes, facts, findings);
  renderDiligenceLists(nodes, facts, findings);
}

function currentFacts() {
  return state.result?.knowledge_base?.facts || [];
}

function currentFindings() {
  return state.result?.findings || [];
}

function currentInsights() {
  return state.result?.insights || [];
}

function currentRequests() {
  return state.result?.knowledge_base?.information_requests || [];
}

function currentReports() {
  return state.result?.report_drafts || [];
}

function updateSummary(nodes, facts, findings) {
  nodes.workspace.dataset.dealState = dealState();
  nodes.dealMeta.textContent = dealSummary();
  nodes.sourceCount.textContent = String(state.sources.length);
  nodes.factCount.textContent = String(facts.length);
  nodes.riskCount.textContent = String(findings.length);
  nodes.reviewStatus.textContent = reviewStatus();
  updateSetupState(nodes);
  updateActionState(nodes);
  updateSetupProgressDisclosure();
}

function updateActionState(nodes) {
  const selectedCount = selectedSourceIds().length;
  nodes.loadDemo.textContent = loadDemoLabel();
  updateLoadDemoAction(nodes.loadDemoInline);
  updateSelectedSourceAction(nodes.loadSelected, selectedCount);
  updateSelectedSourceAction(nodes.loadSelectedInline, selectedCount);
  updateRunAction(nodes.run);
  updateRunAction(nodes.runInline);
  updateProviderAssistAction(nodes.assist);
  nodes.loadDemo.disabled = state.busy;
}

function updateLoadDemoAction(button) {
  if (!button) return;
  button.textContent = loadDemoLabel();
  button.disabled = state.busy;
}

function updateRunAction(button) {
  if (!button) return;
  button.textContent = runReviewLabel();
  button.disabled = runReviewDisabled();
}

function updateProviderAssistAction(button) {
  if (!button) return;
  button.textContent = providerAssistLabel();
  button.disabled = providerAssistDisabled();
}

function providerAssistLabel() {
  if (hasProviderAssistedDraft()) return "Rerun AI-assisted review";
  return "Run AI-assisted review";
}

function providerAssistDisabled() {
  if (state.busy) return true;
  return !state.result;
}

function updateSetupState(nodes) {
  updateDealSetupState(nodes.setupDealTitle);
  updateRunSetupState(nodes.setupRunTitle);
}

function loadDemoLabel() {
  if (state.deal) return "Reload sample deal pack";
  return "Load sample deal pack";
}

function runReviewLabel() {
  if (state.result) {
    return "Rerun accelerator";
  }
  return "Run accelerator";
}

function runReviewDisabled() {
  if (state.busy) return true;
  return !state.deal;
}

function updateSelectedSourceAction(button, selectedCount) {
  if (!button) return;
  button.textContent = selectedSourceActionLabel(selectedCount);
  button.disabled = selectedSourceActionDisabled(selectedCount);
}

function selectedSourceActionLabel(selectedCount) {
  if (!selectedCount) return "Create review from selected files";
  return `Create review from ${selectedCount} file${pluralSuffix(selectedCount)}`;
}

function pluralSuffix(count) {
  if (count === 1) return "";
  return "s";
}

function selectedSourceActionDisabled(selectedCount) {
  if (state.busy) return true;
  return !selectedCount;
}

function updateDealSetupState(title) {
  if (!title) return;
  const setup = dealSetupState();
  title.textContent = setup.text;
  title.closest(".setup-step-card").dataset.setupState = setup.state;
}

function dealSetupState() {
  if (state.deal) return { text: dealSummary(), state: "ready" };
  return emptyDealSetupState(selectedSourceIds().length);
}

function emptyDealSetupState(selectedCount) {
  if (selectedCount) {
    return { text: `${selectedCount} file${pluralSuffix(selectedCount)} selected`, state: "needed" };
  }
  return { text: "No deal loaded", state: "needed" };
}

function updateRunSetupState(title) {
  if (!title) return;
  const setup = runSetupState();
  title.textContent = setup.text;
  title.closest(".setup-step-card").dataset.setupState = setup.state;
}

function runSetupState() {
  if (state.result) return { text: "Review required", state: "ready" };
  if (state.deal) return { text: "Ready to run", state: "needed" };
  return { text: "Waiting for sources", state: "locked" };
}

function dealState() {
  if (state.result) return "complete";
  return state.deal ? "loaded" : "empty";
}

function dealSummary() {
  if (!state.deal) return "No deal loaded";
  return `${state.deal.name} - ${state.deal.target_business} - ${state.deal.horizon_weeks} weeks`;
}

function reviewStatus() {
  return state.result ? "Needs review" : "Needs setup";
}

function hasProviderAssistedDraft() {
  return currentReports().some((report) => report.provider_assistance);
}

function selectedSourceIds() {
  return state.selectedDocIds ? state.selectedDocIds() : [];
}

function renderDiligenceLists(nodes, facts, findings) {
  renderSources(nodes.sourceLibrary, state.sources);
  renderFacts(nodes.extractionTable, facts);
  renderFindings(nodes.riskRegister, findings);
  renderInsights(nodes.insightList, currentInsights());
  renderRequests(nodes.irTracker, currentRequests());
  renderReports(nodes.reportDrafts, currentReports());
}

function renderSources(tbody, sources) {
  tbody.replaceChildren();
  if (!sources.length) {
    appendEmptyRow(tbody, 4, "No classified sources.");
    return;
  }
  sources.forEach((source) => {
    const row = document.createElement("tr");
    row.append(
      cell(source.filename),
      cell(formatValue(source.document_type)),
      cell(formatValue(source.workstream)),
      cell(formatConfidence(source.confidence)),
    );
    tbody.append(row);
  });
}

function renderFacts(tbody, facts) {
  tbody.replaceChildren();
  if (!facts.length) {
    appendEmptyRow(tbody, 5, "No extracted facts.");
    return;
  }
  facts.forEach((fact) => {
    const row = document.createElement("tr");
    row.append(
      cell(fact.label),
      cell(formatFactValue(fact)),
      cell(formatValue(fact.workstream)),
      cell(formatConfidence(fact.confidence)),
      evidenceCell(fact.evidence),
    );
    tbody.append(row);
  });
}

function renderFindings(container, findings) {
  container.replaceChildren();
  if (!findings.length) {
    container.append(emptyBlock("No risk register entries."));
    return;
  }
  findings.forEach((finding) => {
    container.append(
      registerItem({
        title: finding.title,
        meta: [
          `Severity: ${formatValue(finding.severity)}`,
          `Materiality: ${formatValue(finding.materiality)}`,
          `Status: ${formatValue(finding.status)}`,
        ],
        summary: finding.summary,
        evidence: finding.evidence,
      }),
    );
  });
}

function renderInsights(container, insights) {
  container.replaceChildren();
  if (!insights.length) {
    container.append(emptyBlock("No cross-workstream insights."));
    return;
  }
  insights.forEach((insight) => {
    container.append(
      registerItem({
        title: insight.title,
        meta: [
          insight.workstreams.map(formatValue).join(" + "),
          `Review status: ${formatValue(insight.review_status)}`,
        ],
        summary: insight.summary,
        evidence: insight.evidence,
      }),
    );
  });
}

function renderRequests(container, requests) {
  container.replaceChildren();
  if (!requests.length) {
    container.append(emptyBlock("No open information requests."));
    return;
  }
  requests.forEach((request) => {
    container.append(
      registerItem({
        title: request.title,
        meta: [
          `Status: ${formatValue(request.status)}`,
          `Delayed: ${request.delayed_days} days`,
        ],
        summary: "Manual owner follow-up required before workstream sign-off.",
        evidence: request.evidence,
      }),
    );
  });
}

function renderReports(container, reports) {
  container.replaceChildren();
  if (!reports.length) {
    container.append(emptyBlock("No report drafts."));
    return;
  }
  reports.forEach((report) => {
    const item = registerItem({
      title: report.title,
      meta: [
        `Review status: ${formatValue(report.review_status)}`,
        report.workstream ? `Workstream: ${formatValue(report.workstream)}` : "Executive summary",
        report.provider_assistance ? providerAssistanceMeta(report.provider_assistance) : "",
      ].filter(Boolean),
      summary: `${report.claims.length} cited claim${report.claims.length === 1 ? "" : "s"}.`,
      evidence: report.claims.flatMap((claim) => claim.evidence || []).slice(0, 3),
    });
    const list = document.createElement("ol");
    list.className = "diligence-claims";
    report.claims.forEach((claim) => {
      const claimItem = document.createElement("li");
      claimItem.textContent = claim.text;
      list.append(claimItem);
    });
    item.append(list);
    container.append(item);
  });
}

function providerAssistanceMeta(metadata) {
  return `Provider: ${metadata.model_provider} (${metadata.model_version})`;
}

function registerItem({ title, meta, summary, evidence }) {
  const article = document.createElement("article");
  article.className = "diligence-register-item";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const metaList = document.createElement("ul");
  metaList.className = "diligence-meta";
  meta.forEach((item) => {
    const entry = document.createElement("li");
    entry.textContent = item;
    metaList.append(entry);
  });
  const body = document.createElement("p");
  body.textContent = summary;
  const evidenceWrap = document.createElement("div");
  evidenceWrap.className = "diligence-evidence";
  (evidence || []).slice(0, 3).forEach((link) => evidenceWrap.append(evidenceButton(link)));
  article.append(heading, metaList, body, evidenceWrap);
  return article;
}

function evidenceCell(evidence) {
  const td = document.createElement("td");
  const link = evidence?.[0];
  td.append(link ? evidenceButton(link) : document.createTextNode("-"));
  return td;
}

function evidenceButton(link) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "diligence-evidence-link";
  button.textContent = link.filename;
  button.addEventListener("click", () => openEvidence(link));
  return button;
}

function openEvidence(link) {
  document.dispatchEvent(new CustomEvent("cod:open-citation", { detail: link }));
}

function appendEmptyRow(tbody, colspan, message) {
  const row = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = colspan;
  td.className = "diligence-empty-cell";
  td.textContent = message;
  row.append(td);
  tbody.append(row);
}

function emptyBlock(message) {
  const block = document.createElement("p");
  block.className = "diligence-empty";
  block.textContent = message;
  return block;
}

function cell(value) {
  const td = document.createElement("td");
  td.textContent = value || "-";
  return td;
}

function formatValue(value) {
  return String(value || "-").replaceAll("_", " ");
}

function formatFactValue(fact) {
  const value = fact?.value;
  if (!value) return "-";
  return factParts(fact, value).join(" ");
}

function factParts(fact, value) {
  return [String(value), formattedFactUnit(fact), formattedFactPeriod(fact)].filter(Boolean);
}

function formattedFactUnit(fact) {
  return fact.unit ? formatValue(fact.unit) : "";
}

function formattedFactPeriod(fact) {
  return fact.period ? `(${fact.period})` : "";
}

function formatConfidence(value) {
  if (typeof value === "number") return `${Math.round(value * 100)}%`;
  return formatValue(value);
}
