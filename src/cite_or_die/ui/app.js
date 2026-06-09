import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.mjs";
import { initSourcesResizer } from "./layout_resizer.js?v=source-resize-v2";
import { initSettingsPanel } from "./settings_panel.js?v=source-scope";
import { locateQuoteSegments, renderSourceExcerpt } from "./source_viewer.js?v=pdf-highlight-specific";
import { initWorkspaceSetup } from "./workspace_setup.js?v=workspace-setup-v1";

pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.mjs";

const state = {
  token: "",
  tokenScope: "",
  documents: [],
  activePdf: null,
  activePage: 1,
  activeDoc: null,
  activeQuote: "",
  selectedDocIds: new Set(),
};

const nodes = {
  workspace: document.getElementById("workspace"),
  tenant: document.getElementById("tenant"),
  matter: document.getElementById("matter"),
  workspaceSummary: document.getElementById("workspace-summary"),
  setupButton: document.getElementById("open-workspace-setup"),
  setupModal: document.getElementById("workspace-setup-modal"),
  setupForm: document.getElementById("workspace-setup-form"),
  setupTenant: document.getElementById("setup-tenant"),
  setupMatter: document.getElementById("setup-matter"),
  setupClose: document.getElementById("workspace-setup-close"),
  setupProvider: document.getElementById("setup-provider"),
  setupUpload: document.getElementById("setup-upload"),
  openSettings: document.getElementById("open-settings"),
  accessToken: document.getElementById("access-token"),
  file: document.getElementById("file"),
  fileName: document.getElementById("file-name"),
  uploadForm: document.getElementById("upload-form"),
  uploadResult: document.getElementById("upload-result"),
  documentList: document.getElementById("document-list"),
  sourcesPane: document.querySelector(".sources-pane"),
  sourcesResizer: document.getElementById("sources-resizer"),
  refreshDocs: document.getElementById("refresh-docs"),
  chatForm: document.getElementById("chat-form"),
  question: document.getElementById("question"),
  askButton: document.getElementById("ask-button"),
  transcript: document.getElementById("transcript"),
  citationDrawer: document.getElementById("citation-drawer"),
  closeCitation: document.getElementById("close-citation"),
  viewerTitle: document.getElementById("viewer-title"),
  viewerMeta: document.getElementById("viewer-meta"),
  viewerStage: document.getElementById("viewer-stage"),
  viewerEmpty: document.getElementById("viewer-empty"),
  pdfPage: document.getElementById("pdf-page"),
  pdfCanvas: document.getElementById("pdf-canvas"),
  pdfTextLayer: document.getElementById("pdf-text-layer"),
  prevPage: document.getElementById("prev-page"),
  nextPage: document.getElementById("next-page"),
  pageControls: document.querySelector(".page-controls"),
  pageIndicator: document.getElementById("page-indicator"),
};

function currentScope() {
  return {
    tenantId: nodes.tenant.value.trim() || "dev",
    matterId: nodes.matter.value.trim() || "m_default",
  };
}

async function getToken() {
  const manualToken = nodes.accessToken.value.trim();
  if (manualToken) {
    return manualToken;
  }

  const { tenantId, matterId } = currentScope();
  const scope = `${tenantId}:${matterId}`;
  if (state.token && state.tokenScope === scope) {
    return state.token;
  }
  const body = new FormData();
  body.set("tenant_id", tenantId);
  body.set("matter_id", matterId);
  const response = await fetch("/dev/token", { method: "POST", body });
  if (!response.ok) {
    throw new Error("A bearer token is required when the development token helper is disabled.");
  }
  const json = await response.json();
  state.token = json.access_token;
  state.tokenScope = scope;
  return state.token;
}

async function authHeaders(extra = {}) {
  return { Authorization: `Bearer ${await getToken()}`, ...extra };
}

function clearToken() {
  state.token = "";
  state.tokenScope = "";
  resetCitationViewer();
}

function setStatus(message) {
  nodes.uploadResult.textContent = message;
}

function makeMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Answer";
  const body = document.createElement("p");
  body.textContent = text;
  article.append(label, body);
  nodes.transcript.append(article);
  nodes.transcript.scrollTop = nodes.transcript.scrollHeight;
  return article;
}

function renderGuardrails(container, guardrails = []) {
  const list = document.createElement("ul");
  list.className = "guardrails";
  for (const guardrail of guardrails) {
    const item = document.createElement("li");
    item.textContent = `${guardrail.name}: ${guardrail.status}`;
    list.append(item);
  }
  container.append(list);
}

function citationLocation(citation) {
  const parts = [];
  if (citation.page) parts.push(`page ${citation.page}`);
  const lineStart = citation.line_start || citation.lineStart || citation.line;
  const lineEnd = citation.line_end || citation.lineEnd;
  if (lineStart && lineEnd && lineEnd !== lineStart) {
    parts.push(`lines ${lineStart}-${lineEnd}`);
  } else if (lineStart) {
    parts.push(`line ${lineStart}`);
  }
  return parts.length ? parts.join(" - ") : "retrieved passage";
}

function citationQuote(citation) {
  return citation.quote || citation.text_excerpt || "No source quote was returned.";
}

function renderCitations(container, citations = []) {
  if (!citations.length) return;
  const list = document.createElement("section");
  list.className = "citation-list";
  list.setAttribute("aria-label", "Citations");
  const title = document.createElement("p");
  title.className = "citation-list-title";
  title.textContent = citations.length === 1 ? "Citation" : "Citations";
  list.append(title);
  for (const citation of citations) {
    const item = document.createElement("article");
    item.className = "citation-item";
    const meta = document.createElement("div");
    meta.className = "citation-meta";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "citation-source";
    button.textContent = citation.filename;
    button.setAttribute("aria-label", `Open source ${citation.filename}`);
    button.addEventListener("click", () => openCitation(citation));
    const location = document.createElement("span");
    location.className = "citation-location";
    location.textContent = citationLocation(citation);
    meta.append(button, location);
    const quote = document.createElement("blockquote");
    quote.className = "citation-quote";
    quote.textContent = citationQuote(citation);
    item.append(meta, quote);
    list.append(item);
  }
  container.append(list);
}

function renderAnswer(response) {
  const article = makeMessage("assistant", response.answer || "");
  renderCitations(article, response.citations || []);
  renderGuardrails(article, response.guardrails || []);
}

function selectedDocIds() {
  return [...state.selectedDocIds].filter((docId) =>
    state.documents.some((documentRecord) => documentRecord.doc_id === docId),
  );
}

function updateQuestionScope() {
  const count = selectedDocIds().length;
  nodes.question.placeholder = count
    ? `Ask ${count} selected source${count === 1 ? "" : "s"}`
    : "Ask from this matter";
}

function toggleDocumentSelection(docId, selected) {
  if (selected) {
    state.selectedDocIds.add(docId);
  } else {
    state.selectedDocIds.delete(docId);
  }
  updateQuestionScope();
  renderDocuments();
}

function pruneSelectedDocuments() {
  const available = new Set(state.documents.map((documentRecord) => documentRecord.doc_id));
  for (const docId of state.selectedDocIds) {
    if (!available.has(docId)) state.selectedDocIds.delete(docId);
  }
}

function renderDocuments() {
  nodes.documentList.replaceChildren();
  for (const documentRecord of state.documents) {
    const item = document.createElement("li");
    if (state.selectedDocIds.has(documentRecord.doc_id)) {
      item.dataset.selected = "true";
    }
    const row = document.createElement("div");
    row.className = "document-row";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "document-button";
    button.textContent = documentRecord.filename;
    button.addEventListener("click", () => openDocument(documentRecord));
    const scopeLabel = document.createElement("label");
    scopeLabel.className = "document-scope";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedDocIds.has(documentRecord.doc_id);
    checkbox.setAttribute("aria-label", `Use ${documentRecord.filename} for answers`);
    checkbox.addEventListener("change", () =>
      toggleDocumentSelection(documentRecord.doc_id, checkbox.checked),
    );
    const scopeText = document.createElement("span");
    scopeText.textContent = "Use";
    scopeLabel.append(checkbox, scopeText);
    row.append(button, scopeLabel);
    const meta = document.createElement("span");
    meta.textContent = documentRecord.page_count
      ? `${documentRecord.page_count} pages`
      : documentRecord.content_type;
    item.append(row, meta);
    nodes.documentList.append(item);
  }
  updateQuestionScope();
}

async function refreshDocuments() {
  const response = await fetch("/docs/list", {
    headers: await authHeaders(),
  });
  state.documents = response.ok ? await response.json() : [];
  pruneSelectedDocuments();
  renderDocuments();
}

async function uploadDocument(event) {
  event.preventDefault();
  const file = nodes.file.files[0];
  if (!file) {
    setStatus("Choose a file first.");
    return;
  }
  const { matterId } = currentScope();
  const body = new FormData();
  body.set("file", file);
  body.set("matter_id", matterId);
  setStatus("Uploading...");
  const response = await fetch("/upload", {
    method: "POST",
    headers: await authHeaders(),
    body,
  });
  const json = await response.json();
  if (!response.ok) {
    setStatus(json.detail || "Upload failed.");
    return;
  }
  setStatus(`${json.document.filename}: ${json.chunks} chunks`);
  await refreshDocuments();
}

function parseSseBlock(block) {
  const event = { type: "message", data: "" };
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event.type = line.slice(6).trim();
    }
    if (line.startsWith("data:")) {
      event.data += line.slice(5).trim();
    }
  }
  return event;
}

function renderStreamBlock(block, pending) {
  const sse = parseSseBlock(block);
  if (!sse.data) {
    return false;
  }
  if (sse.type === "error") {
    const error = JSON.parse(sse.data);
    pending.querySelector("p").textContent = error.message || "Chat request failed.";
    return true;
  }
  if (sse.type !== "answer") {
    return false;
  }
  try {
    const response = JSON.parse(sse.data);
    pending.remove();
    renderAnswer(response);
  } catch {
    pending.querySelector("p").textContent = "Chat response was not valid JSON.";
  }
  return true;
}

async function responseErrorMessage(response) {
  let detail = "";
  try {
    const text = await response.text();
    if (text) {
      const parsed = JSON.parse(text);
      detail = parsed.detail || parsed.message || text;
    }
  } catch {
    detail = "";
  }
  return detail
    ? `Chat stream failed: ${response.status} ${detail}`
    : `Chat stream failed: ${response.status}`;
}

function chatErrorMessage(error) {
  if (error instanceof TypeError) {
    return "Chat API is offline or unreachable. Restart the local server and try again.";
  }
  return error?.message || "Chat request failed.";
}

async function askQuestion(event) {
  event.preventDefault();
  const question = nodes.question.value.trim();
  if (!question) {
    return;
  }
  const { tenantId, matterId } = currentScope();
  resetCitationViewer();
  makeMessage("user", question);
  const pending = makeMessage("assistant", "Streaming...");
  nodes.askButton.disabled = true;
  let receivedAnswer = false;
  try {
    const body = {
      question,
      tenant_id: tenantId,
      matter_id: matterId,
      stream: true,
    };
    const scopedDocIds = selectedDocIds();
    if (scopedDocIds.length) {
      body.doc_ids = scopedDocIds;
    }
    const response = await fetch("/chat/stream", {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    if (!response.ok || !response.body) {
      throw new Error(await responseErrorMessage(response));
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        receivedAnswer = renderStreamBlock(block, pending) || receivedAnswer;
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) {
      receivedAnswer = renderStreamBlock(buffer, pending) || receivedAnswer;
    }
    if (!receivedAnswer) {
      pending.querySelector("p").textContent = "No answer returned.";
      return;
    }
    nodes.question.value = "";
  } catch (error) {
    console.error("Chat stream failed", error);
    pending.querySelector("p").textContent = chatErrorMessage(error);
  } finally {
    nodes.askButton.disabled = false;
  }
}

async function openCitation(citation) {
  const documentRecord = state.documents.find((item) => item.doc_id === citation.doc_id);
  if (!documentRecord) {
    nodes.viewerTitle.textContent = citation.filename;
    nodes.viewerMeta.textContent = "Source is not in the current matter list.";
    return;
  }
  await openDocument(documentRecord, citation.page || 1, citation.quote);
}

async function openDocument(documentRecord, page = 1, quote = "") {
  openCitationDrawer();
  state.activeDoc = documentRecord;
  state.activeQuote = quote || "";
  nodes.viewerTitle.textContent = documentRecord.filename;
  nodes.viewerMeta.textContent = quote || documentRecord.content_type;
  if (!isPdf(documentRecord)) {
    await showTextSource(documentRecord, quote);
    return;
  }
  const token = await getToken();
  const url = `/docs/${documentRecord.doc_id}/file`;
  const task = pdfjsLib.getDocument({
    url,
    httpHeaders: { Authorization: `Bearer ${token}` },
  });
  state.activePdf = await task.promise;
  await renderPage(page);
}

function isPdf(documentRecord) {
  return (
    documentRecord.content_type === "application/pdf" ||
    documentRecord.filename.toLowerCase().endsWith(".pdf")
  );
}

async function showTextSource(documentRecord, quote = "") {
  try {
    const token = await getToken();
    const response = await fetch(`/docs/${documentRecord.doc_id}/file`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new Error(`GET source failed: ${response.status}`);
    }
    const text = await response.text();
    const { figure, match } = renderSourceExcerpt(text, quote);
    if (match) {
      const label =
        match.lineStart === match.lineEnd
          ? `line ${match.lineStart}`
          : `lines ${match.lineStart}-${match.lineEnd}`;
      nodes.viewerMeta.textContent = `${documentRecord.content_type} - ${label}`;
    } else {
      nodes.viewerMeta.textContent = documentRecord.content_type;
    }
    showViewerNode(figure);
  } catch (error) {
    showViewerText(quote || error.message || "Source preview failed.");
  }
}

function showViewerNode(node) {
  openCitationDrawer();
  state.activePdf = null;
  state.activeQuote = "";
  nodes.pdfPage.hidden = true;
  nodes.pdfCanvas.hidden = true;
  nodes.pdfTextLayer.replaceChildren();
  nodes.viewerEmpty.hidden = false;
  nodes.viewerEmpty.replaceChildren(node);
  nodes.pageControls.hidden = true;
  nodes.pageIndicator.textContent = "-";
}

function showViewerText(text) {
  openCitationDrawer();
  state.activePdf = null;
  state.activeQuote = "";
  nodes.pdfPage.hidden = true;
  nodes.pdfCanvas.hidden = true;
  nodes.pdfTextLayer.replaceChildren();
  nodes.viewerEmpty.hidden = false;
  nodes.viewerEmpty.replaceChildren();
  nodes.viewerEmpty.textContent = text;
  nodes.pageControls.hidden = true;
  nodes.pageIndicator.textContent = "-";
}

function openCitationDrawer() {
  nodes.citationDrawer.classList.add("open");
  nodes.citationDrawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("citation-open");
}

function closeCitationDrawer() {
  nodes.citationDrawer.classList.remove("open");
  nodes.citationDrawer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("citation-open");
}

function resetCitationViewer() {
  closeCitationDrawer();
  state.activePdf = null;
  state.activeDoc = null;
  state.activeQuote = "";
  nodes.viewerTitle.textContent = "Citation";
  nodes.viewerMeta.textContent = "No source selected";
  nodes.pdfPage.hidden = true;
  nodes.pdfCanvas.hidden = true;
  nodes.pdfTextLayer.replaceChildren();
  nodes.viewerEmpty.hidden = false;
  nodes.viewerEmpty.textContent = "No citation selected";
  nodes.pageControls.hidden = true;
  nodes.pageIndicator.textContent = "-";
}

async function renderPage(pageNumber) {
  if (!state.activePdf) {
    return;
  }
  const page = Math.min(Math.max(pageNumber, 1), state.activePdf.numPages);
  state.activePage = page;
  const pdfPage = await state.activePdf.getPage(page);
  const viewport = pdfPage.getViewport({ scale: 1 });
  const width = Math.max(nodes.viewerStage.clientWidth - 32, 320);
  const scale = width / viewport.width;
  const scaled = pdfPage.getViewport({ scale });
  const context = nodes.pdfCanvas.getContext("2d");
  nodes.pdfPage.style.setProperty("--scale-factor", String(scale));
  nodes.pdfPage.style.width = `${Math.floor(scaled.width)}px`;
  nodes.pdfPage.style.height = `${Math.floor(scaled.height)}px`;
  nodes.pdfTextLayer.style.setProperty("--scale-factor", String(scale));
  nodes.pdfTextLayer.replaceChildren();
  nodes.pdfTextLayer.classList.remove("has-cited-text");
  nodes.pdfCanvas.width = Math.floor(scaled.width);
  nodes.pdfCanvas.height = Math.floor(scaled.height);
  nodes.pdfCanvas.style.width = `${Math.floor(scaled.width)}px`;
  nodes.pdfCanvas.style.height = `${Math.floor(scaled.height)}px`;
  nodes.pdfPage.hidden = false;
  nodes.pdfCanvas.hidden = false;
  nodes.viewerEmpty.hidden = true;
  nodes.pageControls.hidden = false;
  nodes.pageIndicator.textContent = `${page} / ${state.activePdf.numPages}`;
  pdfPage.render({ canvasContext: context, viewport: scaled }).promise.catch((error) => {
    console.error("PDF render failed", error);
  });
  const highlighted = await renderPdfTextLayer(pdfPage, scaled, state.activeQuote);
  const metaParts = [state.activeDoc?.content_type || "application/pdf", `page ${page}`];
  if (highlighted) metaParts.push("highlighted");
  nodes.viewerMeta.textContent = metaParts.join(" - ");
}

async function renderPdfTextLayer(pdfPage, viewport, quote) {
  const textContent = await pdfPage.getTextContent();
  const textItems = textContent.items.filter((item) => typeof item.str === "string");
  const { segmentRanges } = locateQuoteSegments(
    textItems.map((item) => item.str),
    quote,
  );
  const highlightedRanges = new Map(
    segmentRanges.map(({ index, start, end }) => [index, { start, end }]),
  );
  for (let index = 0; index < textItems.length; index += 1) {
    const item = textItems[index];
    if (!item.str.trim()) continue;
    const textSpan = renderPdfTextSpan(
      item,
      textContent.styles[item.fontName],
      viewport,
      highlightedRanges.get(index),
    );
    nodes.pdfTextLayer.append(textSpan);
  }
  const firstHighlighted = nodes.pdfTextLayer.querySelector(".is-cited");
  if (!firstHighlighted) return false;
  nodes.pdfTextLayer.classList.add("has-cited-text");
  firstHighlighted.scrollIntoView({ block: "center", inline: "center" });
  return true;
}

function renderPdfTextSpan(item, style, viewport, highlightRange) {
  const transform = pdfjsLib.Util.transform(viewport.transform, item.transform);
  const fontHeight = Math.hypot(transform[2], transform[3]);
  const textSpan = document.createElement("span");
  appendPdfTextWithHighlight(textSpan, item.str, highlightRange);
  textSpan.style.left = `${transform[4]}px`;
  textSpan.style.top = `${transform[5] - fontHeight}px`;
  textSpan.style.fontSize = `${fontHeight}px`;
  textSpan.style.fontFamily = style?.fontFamily || "sans-serif";
  if (item.width) {
    textSpan.style.minWidth = `${item.width * viewport.scale}px`;
  }
  return textSpan;
}

function appendPdfTextWithHighlight(textSpan, text, highlightRange) {
  const range = trimHighlightRange(text, highlightRange);
  if (!range) {
    textSpan.textContent = text;
    return;
  }
  if (range.start > 0) {
    textSpan.append(document.createTextNode(text.slice(0, range.start)));
  }
  const mark = document.createElement("mark");
  mark.className = "is-cited";
  mark.textContent = text.slice(range.start, range.end);
  textSpan.append(mark);
  if (range.end < text.length) {
    textSpan.append(document.createTextNode(text.slice(range.end)));
  }
}

function trimHighlightRange(text, highlightRange) {
  if (!highlightRange) return null;
  let start = Math.max(0, Math.min(text.length, highlightRange.start));
  let end = Math.max(0, Math.min(text.length, highlightRange.end));
  while (start < end && /\s/.test(text[start])) start += 1;
  while (end > start && /\s/.test(text[end - 1])) end -= 1;
  return start < end ? { start, end } : null;
}

nodes.file.addEventListener("change", () => {
  nodes.fileName.textContent = nodes.file.files[0]?.name || "Select PDF, TXT, DOCX, or MD";
});
nodes.uploadForm.addEventListener("submit", uploadDocument);
nodes.chatForm.addEventListener("submit", askQuestion);
nodes.refreshDocs.addEventListener("click", refreshDocuments);
nodes.prevPage.addEventListener("click", () => renderPage(state.activePage - 1));
nodes.nextPage.addEventListener("click", () => renderPage(state.activePage + 1));
nodes.closeCitation.addEventListener("click", closeCitationDrawer);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeCitationDrawer();
  }
});
nodes.tenant.addEventListener("input", clearToken);
nodes.matter.addEventListener("input", clearToken);
nodes.accessToken.addEventListener("input", clearToken);

initSourcesResizer({
  workspace: nodes.workspace,
  sourcesPane: nodes.sourcesPane,
  resizer: nodes.sourcesResizer,
});
initSettingsPanel({ authHeaders, currentScope, tenantNode: nodes.tenant });
initWorkspaceSetup({
  nodes,
  currentScope,
  onScopeChange: async () => {
    clearToken();
    await refreshDocuments();
  },
});
refreshDocuments();
