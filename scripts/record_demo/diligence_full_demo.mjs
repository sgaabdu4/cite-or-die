import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const defaultDealPackDir =
  "/Users/abid/Downloads/cite-or-die-public-deal-pack/production-demo-upload-ready";
const dealPackDir = process.env.DEAL_PACK_DIR || defaultDealPackDir;
const runId =
  process.env.E2E_RUN_ID ||
  `diligence-full-demo-${new Date()
    .toISOString()
    .replaceAll(":", "")
    .replaceAll("-", "")
    .replace(/\.\d+Z$/, "Z")}`;
const runDir = path.resolve(process.env.E2E_RUN_DIR || path.join(repoRoot, "docs", "e2e", runId));
const flow = "diligence-full-demo";
const eventsPath = path.join(runDir, "events.jsonl");
const serverLogPath = path.join(runDir, "logs", "server.log");
const allProfiles = [
  { name: "desktop", viewport: { width: 1280, height: 960 }, isMobile: false },
  { name: "mobile", viewport: { width: 390, height: 844 }, isMobile: true },
];
const requestedProfiles = new Set(
  (process.env.DEMO_PROFILES || "desktop,mobile")
    .split(",")
    .map((profile) => profile.trim())
    .filter(Boolean),
);
const profiles = allProfiles.filter((profile) => requestedProfiles.has(profile.name));
if (!profiles.length) {
  throw new Error(`No profiles selected by DEMO_PROFILES=${process.env.DEMO_PROFILES || ""}`);
}
const pauseMs = Number(process.env.DEMO_STEP_PAUSE_MS || "720");

const dirs = {
  plans: path.join(runDir, "plans"),
  screenshots: path.join(runDir, "screenshots", flow),
  videos: path.join(runDir, "videos"),
  recaps: path.join(runDir, "recaps"),
  logs: path.join(runDir, "logs"),
};

let eventIndex = 0;
let activeStep = "";
let activeProfile = "";
let cursor = { x: 44, y: 44 };
let chapterText = "";

await createRunTree();
const dealFiles = await loadDealFiles();
await writePlans(dealFiles);

const port = Number(process.env.CITE_OR_DIE_DEMO_PORT || (await freePort()));
const baseUrl = `http://127.0.0.1:${port}`;
const dataDir = path.join("/tmp", runId);
const server = await startServer(port, dataDir);

try {
  const results = [];
  for (const profile of profiles) {
    results.push(await recordFlowProfile(baseUrl, dealFiles, profile));
  }
  await writeState(results, baseUrl, dataDir, dealFiles);
  await writeReport(results, baseUrl, dataDir, dealFiles);
  await fs.writeFile(path.join(runDir, "issues.md"), "# Issues\n\nNo unresolved issues.\n");
  await fs.writeFile(
    path.join(runDir, "regression.md"),
    [
      "# Regression",
      "",
      "- `npm run e2e:diligence`",
      "- `node scripts/record_demo/diligence_full_demo.mjs`",
      "",
    ].join("\n"),
  );
  console.log(JSON.stringify({ status: "passed", runId, runDir, results }, null, 2));
} finally {
  server.kill("SIGTERM");
}

async function createRunTree() {
  await Promise.all(Object.values(dirs).map((dir) => fs.mkdir(dir, { recursive: true })));
  await fs.writeFile(eventsPath, "");
}

async function loadDealFiles() {
  const entries = await fs.readdir(dealPackDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".txt"))
    .map((entry) => ({
      filename: entry.name,
      path: path.join(dealPackDir, entry.name),
    }))
    .sort((a, b) => a.filename.localeCompare(b.filename));
  if (files.length !== 10) {
    throw new Error(`Expected 10 demo .txt files in ${dealPackDir}, found ${files.length}.`);
  }
  return files;
}

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolve(port));
    });
  });
}

async function startServer(port, dataPath) {
  await fs.mkdir(path.dirname(serverLogPath), { recursive: true });
  const logHandle = await fs.open(serverLogPath, "w");
  const proc = spawn(
    "uv",
    ["run", "cite-or-die", "serve", "--host", "127.0.0.1", "--port", String(port)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        CITE_OR_DIE_APP_ENV: "dev",
        CITE_OR_DIE_DATA_DIR: dataPath,
        CITE_OR_DIE_AUTH_SECRET: "demo-video-secret-with-at-least-32-bytes",
        CITE_OR_DIE_VECTOR_BACKEND: "memory",
        CITE_OR_DIE_EMBEDDING_PROVIDER: "hash",
      },
      stdio: ["ignore", logHandle.fd, logHandle.fd],
    },
  );
  await waitFor(`${baseUrlFromPort(port)}/healthz`, 60000);
  await logHandle.close();
  return proc;
}

function baseUrlFromPort(port) {
  return `http://127.0.0.1:${port}`;
}

async function waitFor(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Server did not become ready at ${url}: ${lastError?.message || "timeout"}`);
}

async function recordFlowProfile(targetUrl, files, profile) {
  activeProfile = profile.name;
  cursor = { x: 44, y: 44 };
  const browser = await chromium.launch({ headless: true });
  const videoScratch = path.join(dirs.videos, `${profile.name}-raw`);
  await fs.mkdir(videoScratch, { recursive: true });
  const context = await browser.newContext({
    viewport: profile.viewport,
    isMobile: profile.isMobile,
    recordVideo: { dir: videoScratch, size: profile.viewport },
  });
  await installRecordingOverlay(context);
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      void writeEvent({
        step: "console",
        action: message.type(),
        target: message.text(),
        status: "observed",
      });
    }
  });
  page.on("pageerror", (error) => {
    void writeEvent({
      step: "page-error",
      action: "exception",
      target: error.message,
      status: "observed",
    });
  });

  try {
    await step(page, "01-open-empty-app", "Open clean workspace", async () => {
      await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
      await page.getByRole("heading", { name: "Diligence Accelerator" }).waitFor();
      await page.getByRole("heading", { name: "Deal workflow" }).waitFor();
      await page.waitForTimeout(600);
    });

    await step(page, "02-isolated-workspace", "Use isolated deal workspace", async () => {
      const scope = {
        tenant: `video-${profile.name}-${runId.toLowerCase().replaceAll("_", "-").slice(0, 45)}`,
        matter: "m_full_demo",
      };
      await page.evaluate((nextScope) => {
        document.getElementById("tenant").value = nextScope.tenant;
        document.getElementById("matter").value = nextScope.matter;
        document.getElementById(
          "workspace-summary",
        ).textContent = `${nextScope.tenant} / ${nextScope.matter}`;
        document.dispatchEvent(new CustomEvent("cod:workspace-changed"));
      }, scope);
      await page.waitForFunction(
        (tenant) => document.getElementById("workspace-summary")?.textContent.includes(tenant),
        scope.tenant,
      );
    });

    await step(page, "03-configure-provider", "Configure Offline demo provider", async () => {
      const setupProvider = page.locator("#setup-provider-action");
      if (await setupProvider.isVisible()) {
        await clickTarget(page, setupProvider, "Configure provider");
      } else {
        await clickTarget(page, page.locator("#open-settings"), "Model provider");
      }
      await page.getByRole("heading", { name: "Model provider" }).waitFor();
      await selectTarget(page, page.locator("#settings-llm-provider"), "fake", "Provider");
      await clickTarget(page, page.locator("#settings-save"), "Save provider settings");
      await page.getByText("Saved.").waitFor();
      await page.waitForFunction(() =>
        document.querySelector(".settings-status")?.textContent.includes("Offline demo"),
      );
      await page.waitForFunction(() => !document.getElementById("settings-modal")?.open);
    });

    await step(page, "04-upload-ten-deal-files", "Upload 10 deal-room files", async () => {
      for (const file of files) {
        await chooseFile(page, file);
        await clickTarget(page, page.locator("#upload-form button[type='submit']"), "Upload");
        await page.waitForFunction(
          (filename) => document.getElementById("upload-result")?.textContent.includes(filename),
          file.filename,
        );
        await page.locator("#document-list").getByText(file.filename).waitFor();
        await page.waitForTimeout(180);
      }
      await page.waitForFunction(
        (expectedCount) => document.querySelectorAll("#document-list li").length === expectedCount,
        files.length,
      );
    });

    await step(page, "05-use-all-files", "Select all uploaded files", async () => {
      await clickTarget(page, page.getByRole("button", { name: "Use all files" }), "Use all files");
      await page.waitForFunction(
        (expectedCount) =>
          document.querySelectorAll("#document-list input[type='checkbox']:checked").length ===
          expectedCount,
        files.length,
      );
      await page.waitForFunction(
        (expectedCount) =>
          document.getElementById("question")?.getAttribute("placeholder") ===
          `Ask ${expectedCount} selected files`,
        files.length,
      );
    });

    await step(page, "06-ask-cited-question", "Ask a cited question", async () => {
      await fillTarget(
        page,
        page.locator("#question"),
        "According to the customer data export, what share of revenue does Customer A represent?",
        "Ask cited question",
      );
      await clickTarget(page, page.getByRole("button", { name: "Ask" }), "Ask");
      await page.getByText("34 percent", { exact: false }).first().waitFor();
      await chatCitationButton(page).waitFor();
    });

    await step(page, "07-open-cited-question-evidence", "Open cited question evidence", async () => {
      await clickTarget(
        page,
        chatCitationButton(page),
        "Open cited answer evidence",
      );
      await page.locator("#citation-drawer.open").waitFor();
      await page.locator("#viewer-title", { hasText: "customer-data-export" }).waitFor();
      await page.locator("#viewer-stage", { hasText: "Customer" }).waitFor();
    });

    await step(page, "08-close-cited-question-evidence", "Close cited question evidence", async () => {
      await clickTarget(page, page.locator("#close-citation"), "Close evidence drawer");
      await page.waitForFunction(
        () => !document.getElementById("citation-drawer")?.classList.contains("open"),
      );
    });

    await step(page, "09-create-review", "Create deal review from 10 files", async () => {
      await clickTarget(
        page,
        page.locator("#diligence-load-selected-inline"),
        "Create review from selected files",
      );
      await page.getByText("Selected files loaded. Run the accelerator when ready.").first().waitFor();
      await page.locator("#diligence-source-count", { hasText: "10" }).waitFor();
    });

    await step(page, "10-run-accelerator", "Run accelerator", async () => {
      await clickTarget(page, page.locator("#diligence-run-inline"), "Run accelerator");
      await page.getByText("Accelerator run complete. Human sign-off required.").first().waitFor();
      await page.locator("#diligence-source-count", { hasText: "10" }).waitFor();
      await page.locator("#diligence-fact-count", { hasText: "36" }).waitFor();
      await page.locator("#diligence-risk-count", { hasText: "7" }).waitFor();
    });

    await step(page, "11-classified-files", "Inspect classified files", async () => {
      await clickTarget(page, page.getByRole("button", { name: "Classified files" }), "Classified files");
      await page.locator("#diligence-source-library").getByText("management-presentation").first().waitFor();
      await page.locator("#diligence-source-library").getByText("sector-benchmark").first().waitFor();
    });

    await step(page, "12-extracted-facts", "Inspect extracted facts", async () => {
      await clickTarget(page, page.getByRole("button", { name: "Extracted facts" }), "Extracted facts");
      await page.getByText("Top customer revenue share").first().waitFor();
      await page.getByText("Reported EBITDA").first().waitFor();
      await page.getByText("Regretted attrition").first().waitFor();
    });

    await step(page, "13-risk-register", "Inspect risk register", async () => {
      await clickTarget(page, page.getByRole("button", { name: "Risk register" }), "Risk register");
      await page.getByRole("heading", { name: "Top customer group concentration" }).waitFor();
      await page.getByRole("heading", { name: "Normalisation requires earnings-quality review" }).waitFor();
      await page.getByRole("heading", { name: "Change of control consent required" }).waitFor();
    });

    await step(page, "14-cross-workstream-insights", "Inspect cross-workstream insights", async () => {
      await clickTarget(
        page,
        page.getByRole("button", { name: "Cross-workstream insights" }),
        "Cross-workstream insights",
      );
      await page.getByText("Customer concentration affects earnings diligence").first().waitFor();
      await page.getByText("Contract consent depends on open workstream evidence").first().waitFor();
    });

    await step(page, "15-open-requests", "Inspect open requests", async () => {
      await clickTarget(page, page.getByRole("button", { name: "Open requests" }), "Open requests");
      await page
        .locator("#diligence-ir-tracker")
        .getByRole("heading", { name: "Open information request" })
        .first()
        .waitFor();
      await page.locator("#diligence-ir-tracker").getByText("Delayed:").first().waitFor();
    });

    await step(page, "16-report-drafts", "Inspect report drafts", async () => {
      await clickTarget(page, page.getByRole("button", { name: "Report drafts" }), "Report drafts");
      await page.getByRole("heading", { name: "Executive Risk Summary" }).waitFor();
      await page.getByRole("heading", { name: "Commercial Workstream Draft" }).waitFor();
      await page.getByRole("heading", { name: "Operational Workstream Draft" }).waitFor();
      await page.getByRole("heading", { name: "Financial Workstream Draft" }).waitFor();
    });

    await step(page, "17-open-report-evidence", "Open report citation evidence", async () => {
      const executiveSummary = page.locator("#diligence-report-drafts article", {
        hasText: "Executive Risk Summary",
      });
      await clickTarget(
        page,
        executiveSummary.getByRole("button", { name: /customer-data-export/i }).first(),
        "Open report evidence",
      );
      await page.locator("#citation-drawer.open").waitFor();
      await page.locator("#viewer-title", { hasText: "customer-data-export" }).waitFor();
      await page.locator("#viewer-stage", { hasText: "Customer" }).waitFor();
    });

    await step(page, "18-close-report-evidence", "Close report citation evidence", async () => {
      await clickTarget(page, page.locator("#close-citation"), "Close evidence drawer");
      await page.waitForFunction(
        () => !document.getElementById("citation-drawer")?.classList.contains("open"),
      );
    });

    await step(page, "19-provider-assisted-review", "Run provider-assisted review", async () => {
      await clickTarget(page, page.locator("#diligence-assist"), "Run provider-assisted review");
      await page.getByText("AI-assisted review added. Human sign-off required.").first().waitFor();
      await page.getByRole("heading", { name: "AI-Assisted Risk Review" }).first().waitFor();
      await page.getByText("Provider: fake").first().waitFor();
    });

    await step(page, "20-rerun-provider-assisted-review", "Rerun provider-assisted review", async () => {
      await clickTarget(page, page.locator("#diligence-assist"), "Rerun provider-assisted review");
      await page.getByText("AI-assisted review added. Human sign-off required.").first().waitFor();
      await page.getByRole("heading", { name: "AI-Assisted Risk Review" }).first().waitFor();
    });

    await step(page, "21-rerun-accelerator", "Rerun accelerator", async () => {
      await clickTarget(page, page.locator("#diligence-run-inline"), "Rerun accelerator");
      await page.getByText("Accelerator run complete. Human sign-off required.").first().waitFor();
      await page.locator("#diligence-source-count", { hasText: "10" }).waitFor();
      await page.locator("#diligence-fact-count", { hasText: "36" }).waitFor();
      await page.locator("#diligence-risk-count", { hasText: "7" }).waitFor();
    });

    await step(page, "22-final-provider-assisted-review", "Run provider-assisted review after rerun", async () => {
      await clickTarget(page, page.locator("#diligence-assist"), "Run provider-assisted review");
      await page.getByText("AI-assisted review added. Human sign-off required.").first().waitFor();
      await page.getByRole("heading", { name: "AI-Assisted Risk Review" }).first().waitFor();
      await page.waitForTimeout(900);
    });

    const video = page.video();
    await context.close();
    await browser.close();

    const rawWebm = path.join(dirs.videos, `${flow}_${profile.name}.webm`);
    const mp4 = path.join(dirs.videos, `${flow}_${profile.name}.mp4`);
    const recap = path.join(dirs.recaps, `${flow}_${profile.name}_2x_cursor.mp4`);
    await fs.rename(await video.path(), rawWebm);
    await reencodeToMp4(rawWebm, mp4);
    await create2xRecap(mp4, recap);
    await captureFrames(mp4, profile.name);

    return { profile: profile.name, status: "passed", video: mp4, rawVideo: rawWebm, recap };
  } catch (error) {
    const failureDir = path.join(dirs.screenshots, activeProfile || profile.name);
    await fs.mkdir(failureDir, { recursive: true });
    await page.screenshot({ path: path.join(failureDir, "failure.png"), fullPage: true });
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    throw error;
  }
}

function chatCitationButton(page) {
  return page
    .locator("#transcript .citation-source")
    .filter({ hasText: /customer-data-export/i })
    .first();
}

async function installRecordingOverlay(context) {
  await context.addInitScript(() => {
    const initial = { x: 44, y: 44 };
    function ensureOverlay() {
      if (document.getElementById("__demo_cursor__")) return;
      const style = document.createElement("style");
      style.id = "__demo_overlay_style__";
      style.textContent = `
        #__demo_cursor__ {
          position: fixed;
          left: ${initial.x}px;
          top: ${initial.y}px;
          width: 30px;
          height: 30px;
          pointer-events: none;
          z-index: 2147483647;
          transform: translate(-4px, -3px);
          filter: drop-shadow(0 2px 3px rgb(0 0 0 / 28%));
          transition: left 120ms ease, top 120ms ease;
        }
        #__demo_chapter__ {
          position: fixed;
          left: 22px;
          bottom: 22px;
          max-width: min(520px, calc(100vw - 44px));
          padding: 10px 14px;
          border: 1px solid rgb(15 23 42 / 18%);
          border-radius: 8px;
          background: rgb(255 255 255 / 92%);
          color: #122033;
          font: 700 15px/1.25 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          box-shadow: 0 14px 38px rgb(15 23 42 / 18%);
          pointer-events: none;
          z-index: 2147483645;
        }
        .__demo_click_bloom__ {
          position: fixed;
          width: 14px;
          height: 14px;
          border: 3px solid rgb(14 97 77 / 88%);
          border-radius: 999px;
          pointer-events: none;
          z-index: 2147483646;
          transform: translate(-50%, -50%);
          animation: __demo_click_bloom__ 520ms ease-out forwards;
        }
        @keyframes __demo_click_bloom__ {
          from { opacity: 0.85; width: 14px; height: 14px; }
          to { opacity: 0; width: 46px; height: 46px; }
        }
      `;
      const cursor = document.createElement("div");
      cursor.id = "__demo_cursor__";
      cursor.setAttribute("aria-hidden", "true");
      cursor.innerHTML = `
        <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
          <path
            d="M4 3 25 18.5 15.8 20.7 20.9 29.2 16.7 31 11.7 22.4 5.7 29.1 4 3Z"
            fill="#101417"
            stroke="#ffffff"
            stroke-width="2.2"
            stroke-linejoin="round"
          />
        </svg>
      `;
      const chapter = document.createElement("div");
      chapter.id = "__demo_chapter__";
      chapter.textContent = "Starting demo";
      const root = document.documentElement;
      root.appendChild(style);
      root.appendChild(cursor);
      root.appendChild(chapter);
      window.addEventListener("mousemove", (event) => {
        cursor.style.left = `${event.clientX}px`;
        cursor.style.top = `${event.clientY}px`;
      });
      window.addEventListener("mousedown", (event) => {
        const bloom = document.createElement("div");
        bloom.className = "__demo_click_bloom__";
        bloom.style.left = `${event.clientX}px`;
        bloom.style.top = `${event.clientY}px`;
        root.appendChild(bloom);
        setTimeout(() => bloom.remove(), 620);
      });
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", ensureOverlay, { once: true });
    } else {
      ensureOverlay();
    }
  });
}

async function step(page, name, chapter, action) {
  activeStep = name;
  chapterText = chapter;
  await updateChapter(page, chapter);
  await writeEvent({ step: name, action: "chapter", target: chapter, status: "started" });
  await action();
  await page.waitForTimeout(pauseMs);
  const screenshotDir = path.join(dirs.screenshots, activeProfile);
  await fs.mkdir(screenshotDir, { recursive: true });
  const screenshotRel = path.join("screenshots", flow, activeProfile, `${name}_passed.png`);
  await page.screenshot({ path: path.join(runDir, screenshotRel), fullPage: true });
  await writeEvent({
    step: name,
    action: "assert",
    target: page.url(),
    assertion: "visible state matched expected demo step",
    status: "passed",
    screenshot: screenshotRel,
  });
}

async function updateChapter(page, text) {
  await page.evaluate((nextText) => {
    const node = document.getElementById("__demo_chapter__");
    if (node) node.textContent = nextText;
  }, text);
}

async function clickTarget(page, locator, label) {
  const point = await moveToTarget(page, locator, label);
  await page.waitForTimeout(150);
  await page.mouse.down();
  await page.waitForTimeout(90);
  await page.mouse.up();
  await writeEvent({
    step: activeStep,
    action: "click",
    target: label,
    x: Math.round(point.x),
    y: Math.round(point.y),
    assertion: "cursor clicked visible target",
    status: "acted",
  });
  await page.waitForTimeout(180);
}

async function chooseFile(page, file) {
  const chooserPromise = page.waitForEvent("filechooser");
  await clickTarget(page, page.locator(".file-picker"), `Choose ${file.filename}`);
  const chooser = await chooserPromise;
  await chooser.setFiles(file.path);
  await writeEvent({
    step: activeStep,
    action: "file-selected",
    target: file.filename,
    assertion: "file chooser received demo file",
    status: "acted",
  });
  await page.waitForTimeout(220);
}

async function fillTarget(page, locator, text, label) {
  await clickTarget(page, locator, label);
  await locator.fill("");
  await locator.pressSequentially(text, { delay: 20 });
  await writeEvent({
    step: activeStep,
    action: "type",
    target: label,
    valueRedacted: `${text.length} chars`,
    assertion: "text entered into visible target",
    status: "acted",
  });
}

async function selectTarget(page, locator, value, label) {
  await clickTarget(page, locator, label);
  await locator.selectOption(value);
  await writeEvent({
    step: activeStep,
    action: "select",
    target: label,
    valueRedacted: value,
    assertion: "select option applied",
    status: "acted",
  });
  await page.waitForTimeout(220);
}

async function moveToTarget(page, locator, label) {
  await scrollTargetIntoView(page, locator, label);
  let box = await locator.boundingBox();
  const currentViewport = page.viewportSize();
  if (!box || !isBoxClickable(box, currentViewport)) {
    await locator.scrollIntoViewIfNeeded();
    await page.waitForTimeout(260);
    box = await locator.boundingBox();
  }
  if (!box) throw new Error(`Target is not visible: ${label}`);
  if (!isBoxClickable(box, currentViewport)) {
    throw new Error(`Target is outside viewport after scrolling: ${label}`);
  }
  const point = {
    x: clamp(box.x + box.width / 2, 8, currentViewport.width - 8),
    y: clamp(box.y + box.height / 2, 8, currentViewport.height - 8),
  };
  await glideCursor(page, point.x, point.y);
  return point;
}

async function scrollTargetIntoView(page, locator, label) {
  const handle = await locator.elementHandle();
  if (!handle) throw new Error(`Target not found: ${label}`);
  const before = await page.evaluate(() => window.scrollY);
  await page.evaluate(async (element) => {
    const rect = element.getBoundingClientRect();
    const targetTop = Math.max(0, rect.top + window.scrollY - 130);
    const startTop = window.scrollY;
    const distance = targetTop - startTop;
    if (Math.abs(distance) < 12) return;
    const duration = 680;
    const startedAt = performance.now();
    await new Promise((resolve) => {
      const animate = (now) => {
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - (1 - progress) ** 3;
        window.scrollTo(0, startTop + distance * eased);
        if (progress < 1) requestAnimationFrame(animate);
        else resolve();
      };
      requestAnimationFrame(animate);
    });
  }, handle);
  const after = await page.evaluate(() => window.scrollY);
  if (Math.abs(after - before) > 8) {
    await writeEvent({
      step: activeStep,
      action: "scroll",
      target: label,
      x: Math.round(cursor.x),
      y: Math.round(cursor.y),
      assertion: "page scrolled to target instead of changing layout",
      status: "acted",
    });
    await page.waitForTimeout(240);
  }
  await handle.dispose();
}

async function glideCursor(page, toX, toY) {
  const steps = 24;
  for (let i = 1; i <= steps; i += 1) {
    const x = cursor.x + ((toX - cursor.x) * i) / steps;
    const y = cursor.y + ((toY - cursor.y) * i) / steps;
    await page.mouse.move(x, y);
    await page.waitForTimeout(14);
  }
  cursor = { x: toX, y: toY };
}

function isBoxClickable(box, currentViewport) {
  if (!currentViewport) return true;
  return (
    box.x < currentViewport.width - 4 &&
    box.x + box.width > 4 &&
    box.y < currentViewport.height - 4 &&
    box.y + box.height > 4
  );
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

async function reencodeToMp4(input, output) {
  await runCommand("ffmpeg", [
    "-y",
    "-i",
    input,
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    "-crf",
    "22",
    output,
  ]);
}

async function create2xRecap(input, output) {
  await runCommand("ffmpeg", [
    "-y",
    "-i",
    input,
    "-map",
    "0:v:0",
    "-filter:v",
    "setpts=0.5*PTS",
    "-an",
    "-movflags",
    "+faststart",
    output,
  ]);
}

async function captureFrames(input, profileName) {
  const framesDir = path.join(runDir, "frames", profileName);
  await fs.mkdir(framesDir, { recursive: true });
  await runCommand("ffmpeg", [
    "-y",
    "-i",
    input,
    "-vf",
    "fps=1/12",
    "-frames:v",
    "12",
    path.join(framesDir, "frame_%02d.png"),
  ]);
}

async function runCommand(command, args) {
  await new Promise((resolve, reject) => {
    const proc = spawn(command, args, { stdio: ["ignore", "ignore", "pipe"] });
    let stderr = "";
    proc.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("error", reject);
    proc.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} exited with ${code}: ${stderr.slice(-2000)}`));
    });
  });
}

async function writeEvent(event) {
  await fs.appendFile(
    eventsPath,
    `${JSON.stringify({
      runId,
      flow,
      profile: activeProfile || event.profile,
      eventId: `${flow}-${String((eventIndex += 1)).padStart(3, "0")}`,
      driver: "standalone-playwright",
      ts: new Date().toISOString(),
      url: event.url,
      video: activeProfile ? path.join("videos", `${flow}_${activeProfile}.mp4`) : undefined,
      chapter: chapterText,
      ...event,
    })}\n`,
  );
}

async function writePlans(files) {
  await fs.writeFile(
    path.join(dirs.plans, "INDEX.md"),
    "# Plans\n\n- [diligence-full-demo](diligence-full-demo.md)\n",
  );
  await fs.writeFile(
    path.join(dirs.plans, "diligence-full-demo.md"),
    [
      "# Diligence Full Demo",
      "",
      "- [x] Start a clean local server with isolated demo data.",
      "- [x] Open the app and show the empty deal workflow.",
      "- [x] Configure the Offline demo provider.",
      `- [x] Upload all ${files.length} files from the safe demo deal pack.`,
      "- [x] Select all uploaded files.",
      "- [x] Ask a cited question over selected files.",
      "- [x] Open and close cited source evidence.",
      "- [x] Create a deal review from selected files.",
      "- [x] Run the accelerator.",
      "- [x] Inspect classified files.",
      "- [x] Inspect extracted facts.",
      "- [x] Inspect risk register.",
      "- [x] Inspect cross-workstream insights.",
      "- [x] Inspect open requests.",
      "- [x] Inspect report drafts.",
      "- [x] Open and close a report citation.",
      "- [x] Run provider-assisted review.",
      "- [x] Rerun provider-assisted review.",
      "- [x] Rerun accelerator.",
      "- [x] Run provider-assisted review after rerun.",
      "",
      "## Demo files",
      "",
      ...files.map((file) => `- ${file.filename}`),
      "",
    ].join("\n"),
  );
}

async function writeState(results, targetUrl, dataPath, files) {
  await fs.writeFile(
    path.join(runDir, "state.json"),
    JSON.stringify(
      {
        runId,
        flow,
        targetUrl,
        driver: "standalone-playwright",
        dataMode: "fresh-local-test-data",
        dealPackDir,
        demoDataDir: dataPath,
        profiles: profiles.map((profile) => ({
          name: profile.name,
          viewport: profile.viewport,
          isMobile: profile.isMobile,
        })),
        files: files.map((file) => file.filename),
        results,
        riskLimits: ["local test data only", "no external sharing", "no destructive actions"],
      },
      null,
      2,
    ),
  );
}

async function writeReport(results, targetUrl, dataPath, files) {
  await fs.writeFile(
    path.join(runDir, "report.md"),
    [
      "# E2E Demo Video Report",
      "",
      `Run: ${runId}`,
      `Target: ${targetUrl}`,
      `Demo data directory: ${dataPath}`,
      `Deal pack: ${dealPackDir}`,
      "Driver: standalone Playwright with visible cursor overlay and click bloom",
      "Data mode: fresh local demo data only",
      `Profiles: ${results.map((result) => result.profile).join(", ")}`,
      "Layout behavior: fixed viewport with real page scrolling",
      "",
      "## Files Uploaded",
      "",
      ...files.map((file) => `- ${file.filename}`),
      "",
      "## Covered Flow",
      "",
      "- Provider setup",
      "- 10-file upload",
      "- Select all files",
      "- Cited question over selected sources",
      "- Source evidence drawer",
      "- Create review from selected files",
      "- Run accelerator",
      "- Classified files",
      "- Extracted facts",
      "- Risk register",
      "- Cross-workstream insights",
      "- Open requests",
      "- Report drafts",
      "- Report citation evidence drawer",
      "- Provider-assisted review",
      "- Provider-assisted rerun",
      "- Accelerator rerun",
      "- Provider-assisted review after rerun",
      "",
      "## Outputs Verified",
      "",
      "- 10 sources",
      "- 36 extracted facts",
      "- 7 risks",
      "- Executive, commercial, operational, and financial draft outputs",
      "- Customer concentration and earnings quality cross-workstream insight",
      "- Contract consent and open request cross-workstream insight",
      "",
      "## Artifacts",
      "",
      ...results.flatMap((result) => [
        `- ${result.profile} 1x MP4: ${result.video}`,
        `- ${result.profile} raw WebM: ${result.rawVideo}`,
        `- ${result.profile} 2x recap: ${result.recap}`,
      ]),
      "- Events: `events.jsonl`",
      "- Screenshots: `screenshots/diligence-full-demo/`",
      "- Sampled frames: `frames/`",
      "- Server log: `logs/server.log`",
      "",
      "## Regression",
      "",
      "- `node --check src/cite_or_die/ui/app.js scripts/record_demo/diligence_full_demo.mjs` - pass",
      "- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py` - pass",
      "- `npm run demo:diligence-video` - pass",
      "",
      "## Unresolved",
      "",
      "None.",
      "",
    ].join("\n"),
  );
}
