import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.mjs";

const state = {
  token: "",
  tokenScope: "",
  documents: [],
  activePdf: null,
  activePage: 1,
  activeDoc: null,
};

const nodes = {
  tenant: document.getElementById("tenant"),
  matter: document.getElementById("matter"),
  file: document.getElementById("file"),
  fileName: document.getElementById("file-name"),
  uploadForm: document.getElementById("upload-form"),
  uploadResult: document.getElementById("upload-result"),
  documentList: document.getElementById("document-list"),
  refreshDocs: document.getElementById("refresh-docs"),
  chatForm: document.getElementById("chat-form"),
  question: document.getElementById("question"),
  askButton: document.getElementById("ask-button"),
  transcript: document.getElementById("transcript"),
  viewerTitle: document.getElementById("viewer-title"),
  viewerMeta: document.getElementById("viewer-meta"),
  viewerStage: document.getElementById("viewer-stage"),
  viewerEmpty: document.getElementById("viewer-empty"),
  pdfCanvas: document.getElementById("pdf-canvas"),
  prevPage: document.getElementById("prev-page"),
  nextPage: document.getElementById("next-page"),
  pageIndicator: document.getElementById("page-indicator"),
};

function currentScope() {
  return {
    tenantId: nodes.tenant.value.trim() || "dev",
    matterId: nodes.matter.value.trim() || "m_default",
  };
}

async function getToken() {
  const { tenantId, matterId } = currentScope();
  const scope = `${tenantId}:${matterId}`;
  if (state.token && state.tokenScope === scope) {
    return state.token;
  }
  const body = new FormData();
  body.set("tenant_id", tenantId);
  body.set("matter_id", matterId);
  const response = await fetch("/dev/token", { method: "POST", body });
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

function renderCitations(container, citations = []) {
  const rail = document.createElement("div");
  rail.className = "citation-rail";
  for (const citation of citations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "citation-chip";
    button.textContent = `${citation.filename}${citation.page ? ` p.${citation.page}` : ""}`;
    button.addEventListener("click", () => openCitation(citation));
    rail.append(button);
  }
  container.append(rail);
}

function renderAnswer(response) {
  const article = makeMessage("assistant", response.answer || "");
  renderCitations(article, response.citations || []);
  renderGuardrails(article, response.guardrails || []);
}

function renderDocuments() {
  nodes.documentList.replaceChildren();
  for (const documentRecord of state.documents) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "document-button";
    button.textContent = documentRecord.filename;
    button.addEventListener("click", () => openDocument(documentRecord));
    const meta = document.createElement("span");
    meta.textContent = documentRecord.page_count
      ? `${documentRecord.page_count} pages`
      : documentRecord.content_type;
    item.append(button, meta);
    nodes.documentList.append(item);
  }
}

async function refreshDocuments() {
  const response = await fetch("/docs/list", {
    headers: await authHeaders(),
  });
  state.documents = response.ok ? await response.json() : [];
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

async function askQuestion(event) {
  event.preventDefault();
  const question = nodes.question.value.trim();
  if (!question) {
    return;
  }
  const { tenantId, matterId } = currentScope();
  makeMessage("user", question);
  const pending = makeMessage("assistant", "Streaming...");
  nodes.askButton.disabled = true;
  const response = await fetch("/chat/stream", {
    method: "POST",
    headers: await authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      question,
      tenant_id: tenantId,
      matter_id: matterId,
      stream: true,
    }),
  });
  if (!response.ok || !response.body) {
    pending.querySelector("p").textContent = "Request failed.";
    nodes.askButton.disabled = false;
    return;
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
      const sse = parseSseBlock(block);
      if (sse.type === "answer" && sse.data) {
        pending.remove();
        renderAnswer(JSON.parse(sse.data));
      }
    }
  }
  nodes.question.value = "";
  nodes.askButton.disabled = false;
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
  state.activeDoc = documentRecord;
  nodes.viewerTitle.textContent = documentRecord.filename;
  nodes.viewerMeta.textContent = quote || documentRecord.content_type;
  if (!isPdf(documentRecord)) {
    showViewerText(quote || "PDF preview is available for PDF sources.");
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

function showViewerText(text) {
  state.activePdf = null;
  nodes.pdfCanvas.hidden = true;
  nodes.viewerEmpty.hidden = false;
  nodes.viewerEmpty.textContent = text;
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
  nodes.pdfCanvas.width = Math.floor(scaled.width);
  nodes.pdfCanvas.height = Math.floor(scaled.height);
  nodes.pdfCanvas.hidden = false;
  nodes.viewerEmpty.hidden = true;
  await pdfPage.render({ canvasContext: context, viewport: scaled }).promise;
  nodes.pageIndicator.textContent = `${page} / ${state.activePdf.numPages}`;
}

nodes.file.addEventListener("change", () => {
  nodes.fileName.textContent = nodes.file.files[0]?.name || "Select PDF, TXT, DOCX, or MD";
});
nodes.uploadForm.addEventListener("submit", uploadDocument);
nodes.chatForm.addEventListener("submit", askQuestion);
nodes.refreshDocs.addEventListener("click", refreshDocuments);
nodes.prevPage.addEventListener("click", () => renderPage(state.activePage - 1));
nodes.nextPage.addEventListener("click", () => renderPage(state.activePage + 1));
nodes.tenant.addEventListener("input", clearToken);
nodes.matter.addEventListener("input", clearToken);

refreshDocuments();
