export function renderDiligenceLists(nodes, { sources, facts, findings, insights, requests, reports }) {
  renderSources(nodes.sourceLibrary, sources);
  renderFacts(nodes.extractionTable, facts);
  renderFindings(nodes.riskRegister, findings);
  renderInsights(nodes.insightList, insights);
  renderRequests(nodes.irTracker, requests);
  renderReports(nodes.reportDrafts, reports);
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
  orderedReports(reports).forEach((report) => {
    const isProviderAssisted = Boolean(report.provider_assistance);
    const item = registerItem({
      title: report.title,
      tags: isProviderAssisted ? ["AI assisted"] : [],
      meta: [
        `Review status: ${formatValue(report.review_status)}`,
        report.workstream ? `Workstream: ${formatValue(report.workstream)}` : "Executive summary",
        report.provider_assistance ? providerAssistanceMeta(report.provider_assistance) : "",
      ].filter(Boolean),
      summary: isProviderAssisted
        ? providerAssistanceSummary(report.provider_assistance, report.claims.length)
        : `${report.claims.length} cited claim${report.claims.length === 1 ? "" : "s"}.`,
      evidence: report.claims.flatMap((claim) => claim.evidence || []).slice(0, 3),
    });
    if (isProviderAssisted) item.dataset.providerAssisted = "true";
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

function orderedReports(reports) {
  return [...reports].sort((left, right) => {
    if (left.provider_assistance && !right.provider_assistance) return -1;
    if (!left.provider_assistance && right.provider_assistance) return 1;
    return 0;
  });
}

function providerAssistanceMeta(metadata) {
  return `Provider: ${metadata.model_provider} (${metadata.model_version})`;
}

function providerAssistanceSummary(metadata, claimCount) {
  const claimLabel = `${claimCount} cited claim${claimCount === 1 ? "" : "s"}`;
  return [
    `AI-assisted draft added from ${metadata.evidence_chunk_count} cited evidence chunks.`,
    `${claimLabel} returned; analyst sign-off still required.`,
  ].join(" ");
}

function registerItem({ title, tags = [], meta, summary, evidence }) {
  const article = document.createElement("article");
  article.className = "diligence-register-item";
  const headingRow = document.createElement("div");
  headingRow.className = "diligence-register-heading";
  const heading = document.createElement("h3");
  heading.textContent = title;
  headingRow.append(heading);
  tags.forEach((tag) => headingRow.append(tagBadge(tag)));
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
  article.append(headingRow, metaList, body, evidenceWrap);
  return article;
}

function tagBadge(label) {
  const tag = document.createElement("span");
  tag.className = "diligence-tag";
  tag.textContent = label;
  return tag;
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
