import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const baseUrl = process.env.E2E_BASE_URL || "http://127.0.0.1:8765";
const runId =
  process.env.E2E_RUN_ID ||
  new Date().toISOString().replaceAll(":", "").replaceAll("-", "").replace(/\.\d+Z$/, "Z");
const runDir = process.env.E2E_RUN_DIR || path.join("docs", "e2e", runId);
const flow = "diligence-workflow";
const eventsPath = path.join(runDir, "events.jsonl");
const stepPauseMs = Number(process.env.E2E_STEP_PAUSE_MS || "700");
let eventIndex = 0;
let activeStep = "";
let activeProfile = "";
const cursorByProfile = new Map();

const dealFiles = [
  [
    "01-customer-contract-scan.txt",
    "Master services agreement for Northstar Managed Services.",
    "Change of control consent is required before assignment.",
    "Termination for convenience can be exercised on 30 days notice.",
  ],
  [
    "02-financial-pack-fy26.txt",
    "FY26 revenue is GBP 180m. Reported EBITDA is GBP 24m.",
    "Management normalisation adds GBP 5m for restructuring costs.",
    "Vendor response states recurring restructuring costs are GBP 4m.",
  ],
  [
    "03-operations-report.txt",
    "Operational report shows utilisation at 72 percent and SLA backlog at 19 days.",
    "Three offshore delivery leads own transition-critical workflows.",
  ],
  [
    "04-customer-data-export.txt",
    "Top customer represents 34 percent of revenue.",
    "Customer churn is 16 percent and renewal status is incomplete for two key accounts.",
  ],
  [
    "05-hr-records.txt",
    "HR records show 940 employees, regretted attrition of 18 percent,",
    "and 42 open vacancies in delivery roles.",
  ],
  [
    "06-qa-log-and-ir-list.txt",
    "Information request HR attrition schedule remains open and delayed by 12 days.",
    "Vendor response does not provide supporting payroll detail.",
  ],
].map(([filename, ...lines]) => ({ filename, text: lines.join(" ") }));

const dirs = {
  fixtures: path.join(runDir, "fixtures"),
  plans: path.join(runDir, "plans"),
  screenshots: path.join(runDir, "screenshots", flow),
  videos: path.join(runDir, "videos"),
  recaps: path.join(runDir, "recaps"),
  logs: path.join(runDir, "logs"),
};

await Promise.all(Object.values(dirs).map((dir) => fs.mkdir(dir, { recursive: true })));
await fs.writeFile(eventsPath, "");
const fixtureFiles = await writeFixtureFiles();
await writePlans();

const browser = await chromium.launch({ headless: true });
const allProfiles = [
  { name: "desktop", viewport: { width: 1050, height: 1044 }, isMobile: false },
  { name: "mobile", viewport: { width: 390, height: 844 }, isMobile: true },
];
const requestedProfiles = new Set(
  (process.env.E2E_PROFILES || "desktop,mobile")
    .split(",")
    .map((profile) => profile.trim())
    .filter(Boolean),
);
const profiles = allProfiles.filter((profile) => requestedProfiles.has(profile.name));
if (!profiles.length) throw new Error("No E2E profiles selected.");

const results = [];

try {
  for (const profile of profiles) {
    results.push(await runProfile(browser, profile));
  }
} finally {
  await browser.close();
}

await fs.writeFile(
  path.join(runDir, "state.json"),
  JSON.stringify(
    {
      runId,
      flow,
      baseUrl,
      driver: "standalone-playwright",
      dataMode: "uploaded-fixture-files",
      profiles: results,
      fixtureFiles: fixtureFiles.map((fixture) => path.relative(runDir, fixture.path)),
      riskLimits: ["local test data only", "no external sharing", "no destructive actions"],
    },
    null,
    2,
  ),
);
await fs.writeFile(path.join(runDir, "issues.md"), "# Issues\n\nNo unresolved issues.\n");
await fs.writeFile(
  path.join(runDir, "regression.md"),
  [
    "# Regression",
    "",
    "- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py tests/integration/test_diligence_api.py`",
    "- `node --check src/cite_or_die/ui/app.js src/cite_or_die/ui/diligence.js src/cite_or_die/ui/setup_progress.js`",
    "",
  ].join("\n"),
);
await fs.writeFile(
  path.join(runDir, "logs", `${flow}.log`),
  results.map((result) => `${result.profile}: ${result.status}`).join("\n") + "\n",
);
await writeReport(results);
console.log(JSON.stringify({ runId, runDir, results }, null, 2));

async function installCursorOverlay(context) {
  await context.addInitScript(() => {
    const initial = { x: 38, y: 38 };

    function ensureCursor() {
      if (document.getElementById("__e2e_cursor__")) return;

      const style = document.createElement("style");
      style.id = "__e2e_cursor_style__";
      style.textContent = `
        #__e2e_cursor__ {
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
        .__e2e_click_bloom__ {
          position: fixed;
          width: 14px;
          height: 14px;
          border: 3px solid rgb(14 97 77 / 88%);
          border-radius: 999px;
          pointer-events: none;
          z-index: 2147483646;
          transform: translate(-50%, -50%);
          animation: __e2e_click_bloom__ 520ms ease-out forwards;
        }
        @keyframes __e2e_click_bloom__ {
          from {
            opacity: 0.85;
            width: 14px;
            height: 14px;
          }
          to {
            opacity: 0;
            width: 46px;
            height: 46px;
          }
        }
      `;

      const cursor = document.createElement("div");
      cursor.id = "__e2e_cursor__";
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

      const root = document.documentElement;
      root.appendChild(style);
      root.appendChild(cursor);

      window.addEventListener("mousemove", (event) => {
        cursor.style.left = `${event.clientX}px`;
        cursor.style.top = `${event.clientY}px`;
      });

      window.addEventListener("mousedown", (event) => {
        const bloom = document.createElement("div");
        bloom.className = "__e2e_click_bloom__";
        bloom.style.left = `${event.clientX}px`;
        bloom.style.top = `${event.clientY}px`;
        root.appendChild(bloom);
        setTimeout(() => bloom.remove(), 620);
      });
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", ensureCursor, { once: true });
    } else {
      ensureCursor();
    }
  });
}

async function runProfile(browserInstance, profile) {
  const videoScratch = path.join(dirs.videos, `${profile.name}-raw`);
  await fs.mkdir(videoScratch, { recursive: true });
  const context = await browserInstance.newContext({
    viewport: profile.viewport,
    isMobile: profile.isMobile,
    recordVideo: { dir: videoScratch, size: profile.viewport },
  });
  await installCursorOverlay(context);
  cursorByProfile.set(profile.name, { x: 38, y: 38 });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      writeEvent({
        profile: profile.name,
        step: "console",
        action: message.type(),
        target: message.text(),
        status: "observed",
      });
    }
  });

  try {
    await step(profile, page, "open-app", "navigate", async () => {
      await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
      await page.getByRole("heading", { name: "Diligence Accelerator" }).waitFor();
      await page.getByRole("heading", { name: "Deal workflow" }).waitFor();
    });
    await step(profile, page, "set-empty-workspace", "scope", async () => {
      const scope = {
        tenant: `e2e-${runId.toLowerCase()}-${profile.name}`,
        matter: "m_diligence",
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
    await step(profile, page, "configure-offline-provider", "click", async () => {
      const setupProvider = page.locator("#setup-provider-action");
      if (await setupProvider.isVisible()) {
        await clickTarget(page, setupProvider, "Configure provider");
      } else {
        await clickTarget(page, page.locator("#open-settings"), "Model provider");
      }
      await page.getByRole("heading", { name: "Model provider" }).waitFor();
      await selectTarget(page, page.locator("#settings-llm-provider"), "fake", "Provider dropdown");
      await clickTarget(page, page.locator("#settings-save"), "Save provider settings");
      await page.getByText("Saved.").waitFor();
      await page.waitForFunction(() =>
        document.querySelector(".settings-status")?.textContent.includes("Offline demo"),
      );
      await page.waitForFunction(() => !document.getElementById("settings-modal")?.open, {
        timeout: 4000,
      });
    });
    await step(profile, page, "upload-deal-files", "upload", async () => {
      for (const fixture of fixtureFiles) {
        await chooseFile(page, fixture);
        await clickTarget(page, page.locator("#upload-form button[type='submit']"), "Upload file");
        await page.waitForFunction(
          (filename) => document.getElementById("upload-result")?.textContent.includes(filename),
          fixture.filename,
          { timeout: 20000 },
        );
        await page.locator("#document-list").getByText(fixture.filename).waitFor();
        await page.waitForTimeout(180);
      }
      await page.waitForFunction(
        (expectedCount) => document.querySelectorAll("#document-list li").length === expectedCount,
        fixtureFiles.length,
      );
    });
    await step(profile, page, "select-all-files", "click", async () => {
      await clickTarget(page, page.getByRole("button", { name: "Use all files" }), "Use all files");
      await page.waitForFunction(
        (expectedCount) =>
          document.querySelectorAll("#document-list input[type='checkbox']:checked").length ===
          expectedCount,
        fixtureFiles.length,
      );
      await page.waitForFunction(
        (expectedCount) =>
          document.getElementById("question")?.getAttribute("placeholder") ===
          `Ask ${expectedCount} selected files`,
        fixtureFiles.length,
      );
    });
    await step(profile, page, "ask-cited-question", "submit", async () => {
      await fillTarget(
        page,
        page.locator("#question"),
        "What customer concentration risk should the deal team review?",
        "Ask cited question",
      );
      await clickTarget(page, page.getByRole("button", { name: "Ask" }), "Ask");
      await page.getByRole("button", { name: "04-customer-data-export.txt" }).first().waitFor({
        timeout: 20000,
      });
    });
    await step(profile, page, "create-review-from-files", "click", async () => {
      await clickTarget(
        page,
        page.locator("#diligence-load-selected-inline"),
        "Create review from selected files",
      );
      await page.getByText("Selected files loaded. Run the accelerator when ready.").waitFor({
        timeout: 20000,
      });
      await page.locator("#diligence-source-count", { hasText: "6" }).waitFor();
    });
    await step(profile, page, "run-accelerator", "click", async () => {
      await clickTarget(page, page.locator("#diligence-run-inline"), "Run accelerator");
      await page.getByText("Accelerator run complete. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      await page
        .locator("#diligence-risk-register")
        .getByRole("heading", { name: "Top customer concentration" })
        .waitFor();
    });
    await step(profile, page, "open-classified-files", "click", async () => {
      await clickTarget(
        page,
        page.getByRole("button", { name: "Classified files" }),
        "Classified files tab",
      );
      await page
        .locator("#diligence-source-library")
        .getByText("01-customer-contract-scan.txt")
        .waitFor();
    });
    await step(profile, page, "open-extracted-facts", "click", async () => {
      await clickTarget(
        page,
        page.getByRole("button", { name: "Extracted facts" }),
        "Extracted facts tab",
      );
      await page.getByText("Top customer revenue share").waitFor();
    });
    await step(profile, page, "open-risk-register", "click", async () => {
      await clickTarget(
        page,
        page.getByRole("button", { name: "Risk register" }),
        "Risk register tab",
      );
      await page
        .getByRole("heading", { name: "Normalisation requires earnings-quality review" })
        .waitFor();
    });
    await step(profile, page, "open-insights", "click", async () => {
      await clickTarget(
        page,
        page.getByRole("button", { name: "Cross-workstream insights" }),
        "Cross-workstream insights tab",
      );
      await page.getByText("Customer concentration affects earnings diligence").waitFor();
    });
    await step(profile, page, "open-requests", "click", async () => {
      await clickTarget(
        page,
        page.getByRole("button", { name: "Open requests" }),
        "Open requests tab",
      );
      await page
        .locator("#diligence-ir-tracker")
        .getByRole("heading", { name: "Open information request" })
        .waitFor();
    });
    await step(profile, page, "open-report-drafts", "click", async () => {
      await clickTarget(
        page,
        page.getByRole("button", { name: "Report drafts" }),
        "Report drafts tab",
      );
      const executiveSummary = page.locator("#diligence-report-drafts article", {
        hasText: "Executive Risk Summary",
      });
      await executiveSummary.getByRole("heading", { name: "Executive Risk Summary" }).waitFor();
      await executiveSummary.getByText("Review status: needs review").waitFor();
    });
    await step(profile, page, "open-evidence", "click", async () => {
      const executiveSummary = page.locator("#diligence-report-drafts article", {
        hasText: "Executive Risk Summary",
      });
      await clickTarget(
        page,
        executiveSummary.getByRole("button", { name: "04-customer-data-export.txt" }),
        "Open cited evidence",
      );
      await page.locator("#citation-drawer.open").waitFor();
      await page.locator("#viewer-title", { hasText: "04-customer-data-export.txt" }).waitFor();
      await page
        .locator("#viewer-stage", { hasText: "Top customer represents 34 percent of revenue." })
        .waitFor();
    });
    await step(profile, page, "close-evidence", "click", async () => {
      await clickTarget(page, page.locator("#close-citation"), "Close evidence drawer");
      await page.waitForFunction(() => !document.getElementById("citation-drawer")?.classList.contains("open"));
    });
    await step(profile, page, "run-ai-assisted-review", "click", async () => {
      await clickTarget(page, page.locator("#diligence-assist"), "Run AI-assisted review");
      await page.getByText("AI-assisted review added. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      const assistedReview = assistedReviewCard(page);
      await assistedReview.getByRole("heading", { name: "AI-Assisted Risk Review" }).waitFor();
      await assistedReview.getByText("AI assisted").waitFor();
      await assistedReview.getByText("AI-assisted draft added from").waitFor();
      await assistedReview.getByText("Provider: fake").waitFor();
    });
    await step(profile, page, "rerun-ai-assisted-review", "click", async () => {
      await runAiAssistedReview(page);
    });
    await step(profile, page, "rerun-accelerator", "click", async () => {
      await clickTarget(page, page.locator("#diligence-run-inline"), "Rerun accelerator");
      await page.getByText("Accelerator run complete. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      await page.locator("#diligence-fact-count", { hasText: "14" }).waitFor();
      await page.locator("#diligence-risk-count", { hasText: "5" }).waitFor();
    });
    await step(profile, page, "run-ai-assisted-after-rerun", "click", async () => {
      await runAiAssistedReview(page);
    });
    const video = page.video();
    await context.close();
    const finalWebm = path.join(dirs.videos, `${flow}_${profile.name}.webm`);
    const finalMp4 = path.join(dirs.videos, `${flow}_${profile.name}.mp4`);
    const recap = path.join(dirs.recaps, `${flow}_${profile.name}_2x_cursor.mp4`);
    await fs.rename(await video.path(), finalWebm);
    await reencodeToMp4(finalWebm, finalMp4);
    await create2xRecap(finalMp4, recap);
    return {
      profile: profile.name,
      status: "passed",
      video: finalMp4,
      rawVideo: finalWebm,
      recap,
    };
  } catch (error) {
    const screenshotDir = path.join(dirs.screenshots, profile.name);
    await fs.mkdir(screenshotDir, { recursive: true });
    await page.screenshot({
      path: path.join(screenshotDir, "failure.png"),
      fullPage: true,
    });
    await context.close();
    throw error;
  }
}

async function runAiAssistedReview(page) {
  await clickTarget(page, page.locator("#diligence-assist"), "Run AI-assisted review");
  await page.getByText("AI-assisted review added. Human sign-off required.").waitFor({
    timeout: 20000,
  });
  await assistedReviewCard(page).waitFor();
  await assistedReviewCard(page).getByText("AI assisted").waitFor();
}

function assistedReviewCard(page) {
  return page.locator('#diligence-report-drafts [data-provider-assisted="true"]').first();
}

async function reencodeToMp4(input, output) {
  await new Promise((resolve, reject) => {
    const proc = spawn(
      "ffmpeg",
      [
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
      ],
      { stdio: ["ignore", "ignore", "inherit"] },
    );
    proc.on("error", reject);
    proc.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}`)),
    );
  });
}

async function create2xRecap(input, output) {
  await new Promise((resolve, reject) => {
    const proc = spawn(
      "ffmpeg",
      [
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
      ],
      { stdio: ["ignore", "ignore", "inherit"] },
    );
    proc.on("error", reject);
    proc.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`ffmpeg recap exited with ${code}`)),
    );
  });
}

async function clickTarget(page, locator, label) {
  const point = await moveToTarget(page, locator, label);
  await page.waitForTimeout(160);
  await page.mouse.down();
  await page.waitForTimeout(90);
  await page.mouse.up();
  await writeEvent({
    profile: activeProfile,
    step: activeStep,
    action: "click",
    target: label,
    x: Math.round(point.x),
    y: Math.round(point.y),
    assertion: "cursor clicked visible target",
    status: "acted",
  });
  await page.waitForTimeout(160);
}

async function chooseFile(page, fixture) {
  const chooserPromise = page.waitForEvent("filechooser");
  await clickTarget(page, page.locator(".file-picker"), `Choose ${fixture.filename}`);
  const chooser = await chooserPromise;
  await chooser.setFiles(fixture.path);
  await writeEvent({
    profile: activeProfile,
    step: activeStep,
    action: "file-selected",
    target: fixture.filename,
    assertion: "file chooser received fixture file",
    status: "acted",
  });
  await page.waitForTimeout(220);
}

async function fillTarget(page, locator, text, label) {
  await clickTarget(page, locator, label);
  await locator.fill("");
  await locator.pressSequentially(text, { delay: 22 });
  await writeEvent({
    profile: activeProfile,
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
    profile: activeProfile,
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
  const viewport = page.viewportSize();
  if (!box || !isBoxClickable(box, viewport)) {
    await locator.scrollIntoViewIfNeeded();
    await page.waitForTimeout(260);
    box = await locator.boundingBox();
  }
  if (!box) throw new Error(`Target is not visible: ${label}`);
  if (!isBoxClickable(box, viewport)) {
    throw new Error(`Target is outside the viewport after scrolling: ${label}`);
  }
  const point = {
    x: clamp(box.x + box.width / 2, 8, viewport.width - 8),
    y: clamp(box.y + box.height / 2, 8, viewport.height - 8),
  };
  await glideCursor(page, point.x, point.y);
  return point;
}

function isBoxClickable(box, viewport) {
  if (!viewport) return true;
  return (
    box.x < viewport.width - 4 &&
    box.x + box.width > 4 &&
    box.y < viewport.height - 4 &&
    box.y + box.height > 4
  );
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

async function scrollTargetIntoView(page, locator, label) {
  const handle = await locator.elementHandle();
  if (!handle) throw new Error(`Target not found: ${label}`);
  const before = await page.evaluate(() => window.scrollY);
  await page.evaluate(async (element) => {
    const rect = element.getBoundingClientRect();
    const targetTop = Math.max(0, rect.top + window.scrollY - 150);
    const startTop = window.scrollY;
    const distance = targetTop - startTop;
    if (Math.abs(distance) < 12) return;
    const duration = 620;
    const startedAt = performance.now();
    await new Promise((resolve) => {
      const animate = (now) => {
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - (1 - progress) ** 3;
        window.scrollTo(0, startTop + distance * eased);
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          resolve();
        }
      };
      requestAnimationFrame(animate);
    });
  }, handle);
  const after = await page.evaluate(() => window.scrollY);
  if (Math.abs(after - before) > 8) {
    const cursor = cursorByProfile.get(activeProfile) || { x: 38, y: 38 };
    await writeEvent({
      profile: activeProfile,
      step: activeStep,
      action: "scroll",
      target: label,
      x: Math.round(cursor.x),
      y: Math.round(cursor.y),
      assertion: "page scrolled to target instead of changing viewport",
      status: "acted",
    });
    await page.waitForTimeout(220);
  }
  await handle.dispose();
}

async function glideCursor(page, toX, toY) {
  const cursor = cursorByProfile.get(activeProfile) || { x: 38, y: 38 };
  const steps = 24;
  for (let i = 1; i <= steps; i += 1) {
    const x = cursor.x + ((toX - cursor.x) * i) / steps;
    const y = cursor.y + ((toY - cursor.y) * i) / steps;
    await page.mouse.move(x, y);
    await page.waitForTimeout(14);
  }
  cursorByProfile.set(activeProfile, { x: toX, y: toY });
}

async function step(profile, page, name, actionName, action) {
  activeProfile = profile.name;
  activeStep = name;
  await action();
  await page.waitForTimeout(stepPauseMs);
  const screenshotDir = path.join(dirs.screenshots, profile.name);
  await fs.mkdir(screenshotDir, { recursive: true });
  const screenshotRel = path.join("screenshots", flow, profile.name, `${name}_passed.png`);
  const screenshot = path.join(runDir, screenshotRel);
  await page.screenshot({ path: screenshot, fullPage: true });
  await writeEvent({
    profile: profile.name,
    step: name,
    action: actionName,
    target: page.url(),
    assertion: "visible state matched expected flow step",
    status: "passed",
    screenshot: screenshotRel,
  });
}

async function writeFixtureFiles() {
  const fixtures = [];
  for (const dealFile of dealFiles) {
    const fixturePath = path.resolve(dirs.fixtures, dealFile.filename);
    await fs.writeFile(fixturePath, dealFile.text, "utf8");
    fixtures.push({ filename: dealFile.filename, path: fixturePath });
  }
  return fixtures;
}

async function writeEvent(event) {
  const profileVideo = event.profile
    ? path.join("videos", `${flow}_${event.profile}.mp4`)
    : undefined;
  await fs.appendFile(
    eventsPath,
    `${JSON.stringify({
      runId,
      flow,
      eventId: `${flow}-${String((eventIndex += 1)).padStart(3, "0")}`,
      driver: "standalone-playwright",
      ts: new Date().toISOString(),
      ...(profileVideo ? { video: profileVideo } : {}),
      ...event,
    })}\n`,
  );
}

async function writePlans() {
  await fs.writeFile(
    path.join(dirs.plans, "INDEX.md"),
    "# Plans\n\n- [diligence-workflow](diligence-workflow.md)\n",
  );
  await fs.writeFile(
    path.join(dirs.plans, "diligence-workflow.md"),
    [
      "# Diligence Workflow",
      "",
      "- [x] Open app and verify the deal workflow is present.",
      "- [x] Use an isolated tenant and matter for the run.",
      "- [x] Configure the Offline demo provider through the setup flow.",
      "- [x] Upload six deal files through the UI.",
      "- [x] Select all uploaded files for cited questions and review creation.",
      "- [x] Ask a cited question over the selected files.",
      "- [x] Create the deal review from selected files.",
      "- [x] Run the accelerator.",
      "- [x] Inspect classified files, extracted facts, risk register, insights, open requests, and report drafts.",
      "- [x] Open cited evidence in the source drawer.",
      "- [x] Close the source drawer before continuing.",
      "- [x] Run and rerun the optional AI-assisted review.",
      "- [x] Rerun the accelerator and run the AI-assisted review again.",
      "",
    ].join("\n"),
  );
}

async function writeReport(results) {
  await fs.writeFile(
    path.join(runDir, "report.md"),
    [
      "# E2E Report",
      "",
      `Run: ${runId}`,
      `Target: ${baseUrl}`,
      "Driver: standalone Playwright after in-app browser capability check",
      "Data mode: uploaded-fixture-files",
      "Flow: diligence-workflow",
      `Profiles: ${results.map((result) => result.profile).join(", ")}`,
      "Capture: stable viewport, visible cursor, click bloom, and page scrolls instead of viewport changes",
      "Actions: provider setup and save, upload, selection, cited question, review creation, accelerator run, all output tabs, evidence drawer, AI-assisted review, reruns",
      "1x MP4 video paths:",
      ...results.map((result) => `- ${result.video}`),
      "Raw WebM paths:",
      ...results.map((result) => `- ${result.rawVideo}`),
      "2x cursor recap paths:",
      ...results.map((result) => `- ${result.recap}`),
      "",
      "## Results",
      "",
      ...results.map(
        (result) =>
          `- ${result.profile}: ${result.status}; 1x video ${result.video}; raw ${result.rawVideo}; 2x recap ${result.recap}`,
      ),
      "",
      "## Regression",
      "",
      "- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py tests/integration/test_diligence_api.py`",
      "- `node --check src/cite_or_die/ui/app.js src/cite_or_die/ui/diligence.js src/cite_or_die/ui/setup_progress.js`",
      "",
      "## Unresolved",
      "",
      "None.",
      "",
    ].join("\n"),
  );
}
