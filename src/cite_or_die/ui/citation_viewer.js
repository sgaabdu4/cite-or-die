import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.mjs";
import { locateQuoteSegments, renderSourceExcerpt } from "./source_viewer.js?v=pdf-highlight-specific";

pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.mjs";

export function initCitationViewer({ nodes, getDocuments, getToken }) {
  const state = {
    activePdf: null,
    activePage: 1,
    activeDoc: null,
    activeQuote: "",
  };

  async function open(citation) {
    const documentRecord = getDocuments().find((item) => item.doc_id === citation.doc_id);
    if (!documentRecord) {
      nodes.title.textContent = citation.filename;
      nodes.meta.textContent = "Source is not in the current matter list.";
      return;
    }
    await openDocument(documentRecord, citation.page || 1, citation.quote);
  }

  async function openDocument(documentRecord, page = 1, quote = "") {
    openDrawer();
    setActiveDocument(documentRecord, quote);
    if (shouldShowTextSource(documentRecord, quote)) {
      await showTextSource(documentRecord, quote);
      return;
    }
    await showPdfSource(documentRecord, page);
  }

  function setActiveDocument(documentRecord, quote) {
    state.activeDoc = documentRecord;
    state.activeQuote = quote || "";
    nodes.title.textContent = documentRecord.filename;
    nodes.meta.textContent = viewerMeta(documentRecord, quote);
  }

  async function showPdfSource(documentRecord, page) {
    const token = await getToken();
    const task = pdfjsLib.getDocument({
      url: `/docs/${documentRecord.doc_id}/raw`,
      httpHeaders: { Authorization: `Bearer ${token}` },
    });
    state.activePdf = await task.promise;
    await renderPage(page);
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
        nodes.meta.textContent = `${documentRecord.content_type} - ${label}`;
      } else {
        nodes.meta.textContent = documentRecord.content_type;
      }
      showContent(figure);
    } catch (error) {
      showContent(quote || error.message || "Source preview failed.");
    }
  }

  function showContent(...children) {
    openDrawer();
    state.activePdf = null;
    state.activeQuote = "";
    nodes.page.hidden = true;
    nodes.canvas.hidden = true;
    nodes.textLayer.replaceChildren();
    nodes.empty.hidden = false;
    nodes.empty.replaceChildren(...children);
    nodes.pageControls.hidden = true;
    nodes.pageIndicator.textContent = "-";
  }

  function openDrawer() {
    nodes.drawer.classList.add("open");
    nodes.drawer.setAttribute("aria-hidden", "false");
    document.body.classList.add("citation-open");
  }

  function closeDrawer() {
    nodes.drawer.classList.remove("open");
    nodes.drawer.setAttribute("aria-hidden", "true");
    document.body.classList.remove("citation-open");
  }

  function reset() {
    closeDrawer();
    state.activePdf = null;
    state.activeDoc = null;
    state.activeQuote = "";
    nodes.title.textContent = "Citation";
    nodes.meta.textContent = "No source selected";
    nodes.page.hidden = true;
    nodes.canvas.hidden = true;
    nodes.textLayer.replaceChildren();
    nodes.empty.hidden = false;
    nodes.empty.textContent = "No citation selected";
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
    const width = Math.max(nodes.stage.clientWidth - 32, 320);
    const scale = width / viewport.width;
    const scaled = pdfPage.getViewport({ scale });
    const context = nodes.canvas.getContext("2d");
    nodes.page.style.setProperty("--scale-factor", String(scale));
    nodes.page.style.width = `${Math.floor(scaled.width)}px`;
    nodes.page.style.height = `${Math.floor(scaled.height)}px`;
    nodes.textLayer.style.setProperty("--scale-factor", String(scale));
    nodes.textLayer.replaceChildren();
    nodes.textLayer.classList.remove("has-cited-text");
    nodes.canvas.width = Math.floor(scaled.width);
    nodes.canvas.height = Math.floor(scaled.height);
    nodes.canvas.style.width = `${Math.floor(scaled.width)}px`;
    nodes.canvas.style.height = `${Math.floor(scaled.height)}px`;
    nodes.page.hidden = false;
    nodes.canvas.hidden = false;
    nodes.empty.hidden = true;
    nodes.pageControls.hidden = false;
    nodes.pageIndicator.textContent = `${page} / ${state.activePdf.numPages}`;
    pdfPage.render({ canvasContext: context, viewport: scaled }).promise.catch((error) => {
      console.error("PDF render failed", error);
    });
    const highlighted = await renderPdfTextLayer(pdfPage, scaled, state.activeQuote);
    const metaParts = [state.activeDoc?.content_type || "application/pdf", `page ${page}`];
    if (highlighted) metaParts.push("highlighted");
    nodes.meta.textContent = metaParts.join(" - ");
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
      nodes.textLayer.append(textSpan);
    }
    const firstHighlighted = nodes.textLayer.querySelector(".is-cited");
    if (!firstHighlighted) return false;
    nodes.textLayer.classList.add("has-cited-text");
    firstHighlighted.scrollIntoView({ block: "center", inline: "center" });
    return true;
  }

  nodes.prevPage.addEventListener("click", () => renderPage(state.activePage - 1));
  nodes.nextPage.addEventListener("click", () => renderPage(state.activePage + 1));
  nodes.close.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer();
    }
  });
  document.addEventListener("cod:open-citation", (event) => {
    if (event.detail) open(event.detail);
  });

  return { open, reset };
}

function viewerMeta(documentRecord, quote) {
  if (quote) return quote;
  return documentRecord.content_type;
}

function shouldShowTextSource(documentRecord, quote) {
  if (quote) return true;
  return !isPdf(documentRecord);
}

function isPdf(documentRecord) {
  return (
    documentRecord.content_type === "application/pdf" ||
    documentRecord.filename.toLowerCase().endsWith(".pdf")
  );
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
