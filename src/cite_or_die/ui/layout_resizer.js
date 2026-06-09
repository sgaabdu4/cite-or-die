const SOURCES_WIDTH_KEY = "cite-or-die:sources-width";
const SOURCES_WIDTH_DEFAULT = 286;
const SOURCES_WIDTH_MIN = 220;
const SOURCES_WIDTH_MAX = 560;
const CHAT_WIDTH_MIN = 420;
const MOBILE_QUERY = "(max-width: 860px)";

export function initSourcesResizer({ workspace, sourcesPane, resizer }) {
  function sourcesWidthLimit() {
    const workspaceWidth = workspace.getBoundingClientRect().width;
    if (!workspaceWidth) return SOURCES_WIDTH_MAX;
    return Math.max(
      SOURCES_WIDTH_MIN,
      Math.min(SOURCES_WIDTH_MAX, workspaceWidth - CHAT_WIDTH_MIN),
    );
  }

  function clampSourcesWidth(width) {
    return Math.max(SOURCES_WIDTH_MIN, Math.min(sourcesWidthLimit(), Math.round(width)));
  }

  function setSourcesWidth(width, persist = false) {
    const clamped = clampSourcesWidth(width);
    workspace.style.setProperty("--sources-width", `${clamped}px`);
    resizer.setAttribute("aria-valuenow", String(clamped));
    resizer.setAttribute("aria-valuemax", String(sourcesWidthLimit()));
    if (persist) {
      localStorage.setItem(SOURCES_WIDTH_KEY, String(clamped));
    }
  }

  function savedSourcesWidth() {
    const saved = Number.parseInt(localStorage.getItem(SOURCES_WIDTH_KEY) || "", 10);
    return Number.isFinite(saved) ? saved : SOURCES_WIDTH_DEFAULT;
  }

  function resizeSourcesBy(delta) {
    setSourcesWidth(sourcesPane.getBoundingClientRect().width + delta, true);
  }

  function beginSourcesResize(event) {
    if (window.matchMedia(MOBILE_QUERY).matches) return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = sourcesPane.getBoundingClientRect().width;
    const isMouseEvent = event.type === "mousedown";
    const moveEvent = isMouseEvent ? "mousemove" : "pointermove";
    const endEvent = isMouseEvent ? "mouseup" : "pointerup";
    const cancelEvent = isMouseEvent ? "mouseleave" : "pointercancel";
    document.body.classList.add("sources-resizing");
    if (!isMouseEvent) {
      resizer.setPointerCapture?.(event.pointerId);
    }

    function move(moveEventPayload) {
      setSourcesWidth(startWidth + moveEventPayload.clientX - startX);
    }

    function finish() {
      document.body.classList.remove("sources-resizing");
      localStorage.setItem(
        SOURCES_WIDTH_KEY,
        String(Math.round(sourcesPane.getBoundingClientRect().width)),
      );
      window.removeEventListener(moveEvent, move);
      window.removeEventListener(endEvent, finish);
      window.removeEventListener(cancelEvent, finish);
    }

    window.addEventListener(moveEvent, move);
    window.addEventListener(endEvent, finish);
    window.addEventListener(cancelEvent, finish);
  }

  function handleSourcesResizeKey(event) {
    const step = event.shiftKey ? 32 : 16;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      resizeSourcesBy(-step);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      resizeSourcesBy(step);
    } else if (event.key === "Home") {
      event.preventDefault();
      setSourcesWidth(SOURCES_WIDTH_MIN, true);
    } else if (event.key === "End") {
      event.preventDefault();
      setSourcesWidth(sourcesWidthLimit(), true);
    }
  }

  resizer.addEventListener("pointerdown", beginSourcesResize);
  resizer.addEventListener("mousedown", beginSourcesResize);
  resizer.addEventListener("keydown", handleSourcesResizeKey);
  window.addEventListener("resize", () =>
    setSourcesWidth(sourcesPane.getBoundingClientRect().width),
  );
  setSourcesWidth(savedSourcesWidth());
}
