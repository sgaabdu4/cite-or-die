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
};

export function initDiligenceWorkspace({ authHeaders, currentScope, refreshDocuments }) {
  const nodes = {
    workspace: document.getElementById("diligence-workspace"),
    loadDemo: document.getElementById("diligence-load-demo"),
    run: document.getElementById("diligence-run"),
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

  nodes.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveView(nodes, tab.dataset.diligenceViewTab));
  });
  nodes.loadDemo.addEventListener("click", () =>
    loadSyntheticDealRoom(nodes, authHeaders, refreshDocuments),
  );
  nodes.run.addEventListener("click", () => runAccelerator(nodes, authHeaders));
  document.addEventListener("cod:workspace-changed", () => resetDiligence(nodes));
  updateUi(nodes);
}

async function loadSyntheticDealRoom(nodes, authHeaders, refreshDocuments) {
  setBusy(nodes, true, "Loading synthetic deal room...");
  try {
    const sourceDocIds = [];
    for (const source of SYNTHETIC_DEAL_ROOM) {
      const body = new FormData();
      body.set("file", new File([source.text], source.filename, { type: "text/plain" }));
      const upload = await fetch("/upload", {
        method: "POST",
        headers: await authHeaders(),
        body,
      });
      if (!upload.ok) throw new Error(await responseMessage(upload, "Upload failed"));
      const uploaded = await upload.json();
      if (uploaded.document?.doc_id) sourceDocIds.push(uploaded.document.doc_id);
    }
    if (refreshDocuments) await refreshDocuments();
    const deal = await postJson("/diligence/deals", authHeaders, {
      name: "Project Northstar",
      target_business: "Northstar Managed Services",
      target_revenue_gbp_m: 180,
      horizon_weeks: 6,
      source_doc_ids: sourceDocIds,
    });
    state.deal = deal;
    state.sources = await postJson(
      `/diligence/deals/${deal.deal_id}/sources/classify`,
      authHeaders,
    );
    state.result = null;
    setActiveView(nodes, "sources");
    setStatus(nodes, "Deal room loaded. Run accelerator when ready.");
    updateUi(nodes);
  } catch (error) {
    setStatus(nodes, error.message || "Diligence load failed.");
  } finally {
    setBusy(nodes, false);
  }
}

async function runAccelerator(nodes, authHeaders) {
  if (!state.deal) {
    setStatus(nodes, "Load a deal room first.");
    return;
  }
  setBusy(nodes, true, "Running accelerator...");
  try {
    state.result = await postJson(
      `/diligence/deals/${state.deal.deal_id}/run`,
      authHeaders,
    );
    state.sources = state.result.knowledge_base.sources || state.sources;
    setActiveView(nodes, "risks");
    setStatus(nodes, "Accelerator run complete. Analyst review required.");
    updateUi(nodes);
  } catch (error) {
    setStatus(nodes, error.message || "Diligence run failed.");
  } finally {
    setBusy(nodes, false);
  }
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
  nodes.loadDemo.disabled = busy;
  nodes.run.disabled = busy;
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
  setStatus(nodes, "Ready");
  updateUi(nodes);
}

function updateUi(nodes) {
  const facts = state.result?.knowledge_base?.facts || [];
  const findings = state.result?.findings || [];
  nodes.dealMeta.textContent = state.deal
    ? `${state.deal.name} - ${state.deal.target_business} - ${state.deal.horizon_weeks} weeks`
    : "No deal loaded";
  nodes.sourceCount.textContent = String(state.sources.length);
  nodes.factCount.textContent = String(facts.length);
  nodes.riskCount.textContent = String(findings.length);
  nodes.reviewStatus.textContent = state.result ? "Needs review" : "Needs setup";
  renderSources(nodes.sourceLibrary, state.sources);
  renderFacts(nodes.extractionTable, facts);
  renderFindings(nodes.riskRegister, findings);
  renderInsights(nodes.insightList, state.result?.insights || []);
  renderRequests(nodes.irTracker, state.result?.knowledge_base?.information_requests || []);
  renderReports(nodes.reportDrafts, state.result?.report_drafts || []);
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
      ],
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
  if (!fact?.value) return "-";
  const parts = [String(fact.value)];
  if (fact.unit) parts.push(formatValue(fact.unit));
  if (fact.period) parts.push(`(${fact.period})`);
  return parts.join(" ");
}

function formatConfidence(value) {
  if (typeof value === "number") return `${Math.round(value * 100)}%`;
  return formatValue(value);
}
