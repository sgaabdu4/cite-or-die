import { initCitationViewer } from "./citation_viewer.js?v=citation-viewer-v1";
import { initDiligenceWorkspace } from "./diligence.js?v=diligence-workspace-v5";
import { initSourcesResizer } from "./layout_resizer.js?v=source-resize-v2";
import { initSettingsPanel } from "./settings_panel.js?v=provider-setup-v7";
import { initWorkspaceSetup } from "./workspace_setup.js?v=workspace-setup-v1";

const state = {
  token: "",
  tokenScope: "",
  documents: [],
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
  filePicker: document.querySelector(".file-picker"),
  fileName: document.getElementById("file-name"),
  uploadForm: document.getElementById("upload-form"),
  uploadButton: document.querySelector("#upload-form button[type='submit']"),
  uploadResult: document.getElementById("upload-result"),
  documentList: document.getElementById("document-list"),
  selectAllDocs: document.getElementById("select-all-docs"),
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

const citationViewer = initCitationViewer({
  nodes: {
    drawer: nodes.citationDrawer,
    close: nodes.closeCitation,
    title: nodes.viewerTitle,
    meta: nodes.viewerMeta,
    stage: nodes.viewerStage,
    empty: nodes.viewerEmpty,
    page: nodes.pdfPage,
    canvas: nodes.pdfCanvas,
    textLayer: nodes.pdfTextLayer,
    prevPage: nodes.prevPage,
    nextPage: nodes.nextPage,
    pageControls: nodes.pageControls,
    pageIndicator: nodes.pageIndicator,
  },
  getDocuments: () => state.documents,
  getToken,
});

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
  citationViewer.reset();
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

function openDocumentRecord(documentRecord) {
  if (!documentRecord?.doc_id) return;
  citationViewer.open({
    doc_id: documentRecord.doc_id,
    filename: documentRecord.filename,
    page: 1,
    quote: "",
  });
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
    button.addEventListener("click", () => citationViewer.open(citation));
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
    ? `Ask ${count} selected file${count === 1 ? "" : "s"}`
    : "Ask from this matter";
  if (nodes.selectAllDocs) {
    nodes.selectAllDocs.disabled = !state.documents.length;
  }
}

function toggleDocumentSelection(docId, selected) {
  if (selected) {
    state.selectedDocIds.add(docId);
  } else {
    state.selectedDocIds.delete(docId);
  }
  updateQuestionScope();
  document.dispatchEvent(new CustomEvent("cod:source-selection-changed", {
    detail: { count: selectedDocIds().length },
  }));
  renderDocuments();
}

function selectAllDocuments() {
  for (const documentRecord of state.documents) {
    state.selectedDocIds.add(documentRecord.doc_id);
  }
  updateQuestionScope();
  document.dispatchEvent(new CustomEvent("cod:source-selection-changed", {
    detail: { count: selectedDocIds().length },
  }));
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
    button.addEventListener("click", () => openDocumentRecord(documentRecord));
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
  document.dispatchEvent(new CustomEvent("cod:source-selection-changed", {
    detail: { count: selectedDocIds().length },
  }));
}

function fileList(files) {
  return Array.from(files || []).filter((file) => file?.name);
}

function fileSelectionLabel(files) {
  const selectedFiles = fileList(files);
  if (!selectedFiles.length) return "Drag files here or choose files";
  if (selectedFiles.length === 1) return selectedFiles[0].name;
  return `${selectedFiles.length} files selected`;
}

function updateFileSelectionLabel(files = nodes.file.files) {
  nodes.fileName.textContent = fileSelectionLabel(files);
}

async function uploadOneFile(file) {
  const { matterId } = currentScope();
  const body = new FormData();
  body.set("file", file);
  body.set("matter_id", matterId);
  const response = await fetch("/upload", {
    method: "POST",
    headers: await authHeaders(),
    body,
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(json.detail || "Upload failed.");
  }
  return json;
}

async function uploadFiles(files) {
  const selectedFiles = fileList(files);
  if (!selectedFiles.length) {
    setStatus("Choose files first.");
    return;
  }

  const uploaded = [];
  const failed = [];
  nodes.uploadButton.disabled = true;
  nodes.file.disabled = true;
  nodes.filePicker.dataset.dragState = "uploading";

  try {
    for (const [index, file] of selectedFiles.entries()) {
      setStatus(`Uploading ${index + 1}/${selectedFiles.length}: ${file.name}`);
      try {
        uploaded.push(await uploadOneFile(file));
      } catch (error) {
        failed.push(`${file.name}: ${error?.message || "Upload failed."}`);
      }
    }
  } finally {
    nodes.uploadButton.disabled = false;
    nodes.file.disabled = false;
    delete nodes.filePicker.dataset.dragState;
  }

  await refreshDocuments();
  nodes.file.value = "";
  updateFileSelectionLabel([]);

  if (failed.length) {
    const uploadedCount = uploaded.length;
    const prefix = uploadedCount
      ? `Uploaded ${uploadedCount}/${selectedFiles.length}.`
      : "No files uploaded.";
    setStatus(`${prefix} ${failed[0]}`);
    return;
  }

  if (uploaded.length === 1) {
    const uploadedFile = uploaded[0];
    setStatus(`${uploadedFile.document.filename}: ${uploadedFile.chunks} chunks`);
    return;
  }

  setStatus(`Uploaded ${uploaded.length} files.`);
}

async function uploadDocument(event) {
  event.preventDefault();
  await uploadFiles(nodes.file.files);
}

function dragEventHasFiles(event) {
  return Array.from(event.dataTransfer?.types || []).includes("Files");
}

function handleDragEnter(event) {
  if (!dragEventHasFiles(event)) return;
  event.preventDefault();
  nodes.filePicker.dataset.dragState = "over";
}

function handleDragOver(event) {
  if (!dragEventHasFiles(event)) return;
  event.preventDefault();
  nodes.filePicker.dataset.dragState = "over";
  event.dataTransfer.dropEffect = "copy";
}

function handleDragLeave(event) {
  if (event.relatedTarget && nodes.filePicker.contains(event.relatedTarget)) return;
  delete nodes.filePicker.dataset.dragState;
}

async function handleDrop(event) {
  if (!dragEventHasFiles(event)) return;
  event.preventDefault();
  const droppedFiles = fileList(event.dataTransfer.files);
  updateFileSelectionLabel(droppedFiles);
  setStatus(`Dropped ${droppedFiles.length} file${droppedFiles.length === 1 ? "" : "s"}.`);
  await uploadFiles(droppedFiles);
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
  citationViewer.reset();
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

nodes.file.addEventListener("change", () => updateFileSelectionLabel());
nodes.uploadForm.addEventListener("submit", uploadDocument);
nodes.filePicker.addEventListener("dragenter", handleDragEnter);
nodes.filePicker.addEventListener("dragover", handleDragOver);
nodes.filePicker.addEventListener("dragleave", handleDragLeave);
nodes.filePicker.addEventListener("drop", handleDrop);
nodes.selectAllDocs?.addEventListener("click", selectAllDocuments);
nodes.chatForm.addEventListener("submit", askQuestion);
nodes.refreshDocs.addEventListener("click", refreshDocuments);
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
    document.dispatchEvent(
      new CustomEvent("cod:workspace-changed", { detail: currentScope() }),
    );
    await refreshDocuments();
  },
});
initDiligenceWorkspace({ authHeaders, currentScope, refreshDocuments, selectedDocIds });
refreshDocuments();
