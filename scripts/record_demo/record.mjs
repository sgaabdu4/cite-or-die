// Records the full cite-or-die flow (settings wizard → ingest → chat → citation
// drawer → audit/persist) as a WebM in headless Chromium, then re-encodes it as
// `docs/site/demo.mp4`. The cursor is rendered as a fixed-position red dot
// injected via `page.addInitScript`, since Playwright's own pointer is invisible
// in recorded video (microsoft/playwright#1374).
//
// Run:
//   make demo-video
// or directly:
//   cd scripts/record_demo && npm install && npx playwright install chromium && node record.mjs
//
// The script boots its own server on $CITE_OR_DIE_DEMO_PORT (default 8765),
// drives the UI, then shuts the server down. The demo state lives under
// `data/demo-recording/` so it never pollutes a real install.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const videosDir = path.join(here, "videos");
const outputMp4 = path.join(repoRoot, "docs", "site", "demo.mp4");
const sampleDoc = path.join(repoRoot, "examples", "sample.txt");

const PORT = Number(process.env.CITE_OR_DIE_DEMO_PORT || 8765);
const BASE_URL = `http://127.0.0.1:${PORT}`;
const DEMO_DATA = path.join(repoRoot, "data", "demo-recording");

async function waitFor(url, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  let lastErr;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (error) {
      lastErr = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(`Server did not become ready at ${url}: ${lastErr?.message || ""}`);
}

async function startServer() {
  const proc = spawn(
    "uv",
    [
      "run",
      "cite-or-die",
      "serve",
      "--host",
      "127.0.0.1",
      "--port",
      String(PORT),
    ],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        CITE_OR_DIE_APP_ENV: "dev",
        CITE_OR_DIE_DATA_DIR: DEMO_DATA,
        CITE_OR_DIE_AUTH_SECRET: "demo-recording-secret-with-32-bytes!!",
        CITE_OR_DIE_VECTOR_BACKEND: "memory",
        CITE_OR_DIE_EMBEDDING_PROVIDER: "hash",
      },
      stdio: ["ignore", "inherit", "inherit"],
    },
  );
  await waitFor(`${BASE_URL}/healthz`, 60000);
  return proc;
}

async function recordFlow() {
  await rm(videosDir, { recursive: true, force: true });
  await mkdir(videosDir, { recursive: true });
  await mkdir(path.dirname(outputMp4), { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 760 },
    recordVideo: { dir: videosDir, size: { width: 1280, height: 760 } },
  });

  await context.addInitScript(() => {
    const dot = document.createElement("div");
    dot.id = "__demo_cursor__";
    Object.assign(dot.style, {
      position: "fixed",
      width: "20px",
      height: "20px",
      borderRadius: "50%",
      background: "rgba(220, 38, 38, 0.55)",
      border: "2px solid rgba(220, 38, 38, 0.95)",
      boxShadow: "0 0 18px rgba(220, 38, 38, 0.6)",
      pointerEvents: "none",
      zIndex: 2147483647,
      transform: "translate(-50%, -50%)",
      transition: "left 0.12s ease, top 0.12s ease",
      left: "0px",
      top: "0px",
    });
    const inject = () => {
      if (!document.documentElement) return;
      if (!document.getElementById("__demo_cursor__")) {
        document.documentElement.appendChild(dot);
      }
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", inject, { once: true });
    } else {
      inject();
    }
    window.addEventListener("mousemove", (event) => {
      dot.style.left = `${event.clientX}px`;
      dot.style.top = `${event.clientY}px`;
    });
  });

  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on("console", (msg) => {
    if (msg.type() === "error") console.warn(`[page error] ${msg.text()}`);
  });
  page.on("pageerror", (err) => console.warn(`[page exception] ${err.message}`));
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#open-settings", { timeout: 15000 });

  let cursor = { x: 100, y: 100 };
  async function glide(toX, toY, steps = 22, delay = 18) {
    for (let i = 1; i <= steps; i++) {
      const x = cursor.x + ((toX - cursor.x) * i) / steps;
      const y = cursor.y + ((toY - cursor.y) * i) / steps;
      await page.mouse.move(x, y);
      await page.waitForTimeout(delay);
    }
    cursor = { x: toX, y: toY };
  }

  async function moveTo(locator) {
    const box = await locator.boundingBox();
    if (!box) throw new Error("element not visible");
    await glide(box.x + box.width / 2, box.y + box.height / 2);
    return box;
  }

  async function typeInto(locator, text, { clear = true } = {}) {
    await moveTo(locator);
    await locator.click();
    if (clear) await locator.fill("");
    await locator.pressSequentially(text, { delay: 35 });
  }

  const step = (n, label) => console.log(`[demo] step ${n}: ${label}`);

  // ── 1. Pan across the empty workspace ──────────────────────────────────────
  step(1, "pan across workspace");
  await glide(640, 380, 38);
  await page.waitForTimeout(700);

  // ── 2. Open Settings (first-run wizard) ───────────────────────────────────
  step(2, "open settings");
  await moveTo(page.locator("#open-settings"));
  await page.locator("#open-settings").click();
  await page.waitForSelector("#settings-modal[open]", { timeout: 10000 });
  await page.waitForTimeout(500);

  // Pick a hosted-style provider to show the API-key field, but stay on
  // the offline `fake` provider so the demo doesn't need a real key.
  await page.selectOption("#settings-llm-provider", "openai-compatible");
  await page.waitForTimeout(300);
  await typeInto(page.locator("#settings-llm-model"), "qwen3-8b");
  await typeInto(page.locator("#settings-llm-base-url"), "http://localhost:11434/v1");
  await typeInto(page.locator("#settings-llm-api-key"), "sk-demo-redacted-XXXX1234");
  await page.waitForTimeout(350);

  // Switch embedder to BGE-M3 to trigger the re-index banner.
  await page.selectOption("#settings-embedding-provider", "bge-m3");
  await page.waitForTimeout(300);

  await moveTo(page.locator("#settings-save"));
  await page.locator("#settings-save").click();
  // Wait for the toast "Saved. Re-upload sources..." then auto-close.
  await page.waitForTimeout(2000);

  // Reset to defaults so the rest of the flow uses the bundled fake provider
  // and hash embeddings (no network, no model downloads).
  await page.locator("#open-settings").click();
  await page.waitForSelector("#settings-modal[open]", { timeout: 10000 });
  await page.waitForTimeout(400);
  await moveTo(page.locator("#settings-delete"));
  // Suppress the confirm() dialog so the recorder doesn't stall.
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#settings-delete").click();
  await page.waitForTimeout(1500);

  // ── 3. Upload a sample document ───────────────────────────────────────────
  step(3, "upload sample document");
  const fileInput = page.locator("#file");
  await fileInput.setInputFiles(sampleDoc);
  await page.waitForTimeout(300);
  await moveTo(page.locator("#upload-form button[type=submit]"));
  await page.locator("#upload-form button[type=submit]").click();
  await page.waitForSelector("#upload-result:not(:empty)", { timeout: 20000 });
  await page.waitForTimeout(900);

  // Refresh the document list so the new doc renders in the sidebar.
  await moveTo(page.locator("#refresh-docs"));
  await page.locator("#refresh-docs").click();
  await page.waitForTimeout(700);

  // ── 4. Ask a question ─────────────────────────────────────────────────────
  step(4, "ask question");
  await typeInto(
    page.locator("#question"),
    "What does the sample document say?",
  );
  await page.waitForTimeout(300);
  await moveTo(page.locator("#ask-button"));
  await page.locator("#ask-button").click();
  await page.waitForSelector(".transcript .citation-chip", {
    state: "visible",
    timeout: 30000,
  });
  // Hold the answer + citation chip on screen long enough for a viewer to
  // read both before anything else happens.
  await page.waitForTimeout(4000);

  // ── 5. Hover the citation chip, then open the drawer ──────────────────────
  step(5, "hover citation chip");
  const chip = page.locator(".transcript .citation-chip").first();
  await chip.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  // Park the cursor on the chip for two full seconds so the hover-state colour
  // change is obvious in the recording. Add a little side-to-side wiggle so the
  // viewer's eye is drawn to it instead of staring at a static frame.
  await moveTo(chip);
  await page.waitForTimeout(900);
  const chipBox = await chip.boundingBox();
  if (chipBox) {
    await glide(chipBox.x + chipBox.width / 2 - 14, chipBox.y + chipBox.height / 2, 12, 22);
    await page.waitForTimeout(250);
    await glide(chipBox.x + chipBox.width / 2 + 14, chipBox.y + chipBox.height / 2, 12, 22);
    await page.waitForTimeout(250);
    await glide(chipBox.x + chipBox.width / 2, chipBox.y + chipBox.height / 2, 8, 22);
  }
  await page.waitForTimeout(900);

  step(5, "open citation drawer");
  await chip.click();
  await page.waitForSelector("#citation-drawer.open, .citation-drawer.open", {
    timeout: 10000,
  });
  // Hold the drawer open so the verbatim quote is readable.
  await page.waitForTimeout(4500);
  if (await page.locator("#close-citation").count()) {
    await moveTo(page.locator("#close-citation"));
    await page.waitForTimeout(400);
    await page.locator("#close-citation").click();
    await page.waitForTimeout(1200);
  }
  // After close, briefly highlight the chip again so the viewer connects the
  // drawer they just saw back to the chip on the answer.
  await moveTo(chip);
  await page.waitForTimeout(1200);

  // ── 6. Re-open Settings to show the persisted fingerprint state ───────────
  step(6, "show persisted fingerprint");
  await page.locator("#open-settings").click();
  await page.waitForSelector("#settings-modal[open]", { timeout: 10000 });
  await page.waitForTimeout(1600);
  await page.keyboard.press("Escape").catch(() => null);
  await page.waitForTimeout(800);

  const videoPath = await page.video().path();
  await context.close();
  await browser.close();
  return videoPath;
}

async function reencodeToMp4(webmPath) {
  await new Promise((resolve, reject) => {
    const proc = spawn(
      "ffmpeg",
      [
        "-y",
        "-i",
        webmPath,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-crf",
        "23",
        outputMp4,
      ],
      { stdio: "inherit" },
    );
    proc.on("error", reject);
    proc.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}`)),
    );
  });
}

async function main() {
  if (!existsSync(sampleDoc)) {
    await writeFile(
      sampleDoc,
      "Cite-or-die demo: this sample document is small but cited verbatim.\n",
    );
  }
  await rm(DEMO_DATA, { recursive: true, force: true });

  const server = await startServer();
  let webmPath;
  try {
    webmPath = await recordFlow();
  } finally {
    server.kill("SIGINT");
    await new Promise((resolve) => server.on("exit", () => resolve()));
  }
  await reencodeToMp4(webmPath);
  const info = await stat(outputMp4);
  console.log(`Wrote ${outputMp4} (${info.size} bytes).`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
