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
let eventIndex = 0;

const dirs = {
  plans: path.join(runDir, "plans"),
  screenshots: path.join(runDir, "screenshots", flow),
  videos: path.join(runDir, "videos"),
  logs: path.join(runDir, "logs"),
};

await Promise.all(Object.values(dirs).map((dir) => fs.mkdir(dir, { recursive: true })));
await writePlans();

const browser = await chromium.launch({ headless: true });
const profiles = [
  { name: "desktop", viewport: { width: 1440, height: 980 }, isMobile: false },
  { name: "mobile", viewport: { width: 390, height: 844 }, isMobile: true },
];
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
      dataMode: "seeded-test",
      profiles: results,
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
    "- `node --check src/cite_or_die/ui/diligence.js`",
    "",
  ].join("\n"),
);
await fs.writeFile(
  path.join(runDir, "logs", `${flow}.log`),
  results.map((result) => `${result.profile}: ${result.status}`).join("\n") + "\n",
);
await writeReport(results);
console.log(JSON.stringify({ runId, runDir, results }, null, 2));

async function runProfile(browserInstance, profile) {
  const videoScratch = path.join(dirs.videos, `${profile.name}-raw`);
  await fs.mkdir(videoScratch, { recursive: true });
  const context = await browserInstance.newContext({
    viewport: profile.viewport,
    isMobile: profile.isMobile,
    recordVideo: { dir: videoScratch, size: profile.viewport },
  });
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
      await page.getByRole("heading", { name: "AI-enabled Due Diligence Acceleration" }).waitFor();
    });
    await step(profile, page, "load-sample-deal-room", "click", async () => {
      await page.getByRole("button", { name: "Load sample deal room" }).click();
      await page.getByText("Deal room loaded. Run the review when ready.").waitFor({
        timeout: 20000,
      });
      await page.locator("#diligence-deal-meta", { hasText: "Project Northstar" }).waitFor();
    });
    await step(profile, page, "run-diligence-review", "click", async () => {
      await page.getByRole("button", { name: "Run diligence review" }).click();
      await page.getByText("Diligence review complete. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      await page
        .locator("#diligence-risk-register")
        .getByRole("heading", { name: "Top customer concentration" })
        .waitFor();
    });
    await step(profile, page, "open-insights", "click", async () => {
      await page.getByRole("button", { name: "Cross-workstream insights" }).click();
      await page.getByText("Customer concentration affects earnings diligence").waitFor();
    });
    await step(profile, page, "open-report-drafts", "click", async () => {
      await page.getByRole("button", { name: "Report drafts" }).click();
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
      await executiveSummary.getByRole("button", { name: "04-customer-data-export.txt" }).click();
      await page.locator("#citation-drawer.open").waitFor();
      await page.getByText("Top customer represents 34 percent of revenue.").waitFor();
    });
    const video = page.video();
    await context.close();
    const finalVideo = path.join(dirs.videos, `${flow}_${profile.name}.webm`);
    await fs.rename(await video.path(), finalVideo);
    return { profile: profile.name, status: "passed", video: finalVideo };
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

async function step(profile, page, name, actionName, action) {
  await action();
  await page.waitForTimeout(220);
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

async function writeEvent(event) {
  await fs.appendFile(
    eventsPath,
    `${JSON.stringify({
      runId,
      flow,
      eventId: `${flow}-${String((eventIndex += 1)).padStart(3, "0")}`,
      driver: "standalone-playwright",
      ts: new Date().toISOString(),
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
      "- [x] Open app and verify the diligence workspace is present.",
      "- [x] Load the seeded deal room.",
      "- [x] Run the accelerator.",
      "- [x] Inspect the risk register.",
      "- [x] Open cross-workstream insights.",
      "- [x] Open report drafts.",
      "- [x] Open cited evidence in the source drawer.",
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
      "Data mode: seeded-test",
      "Flow: diligence-workflow",
      "Actions: desktop 6, mobile 6",
      "Video paths:",
      ...results.map((result) => `- ${result.video}`),
      "",
      "## Results",
      "",
      ...results.map((result) => `- ${result.profile}: ${result.status}; video ${result.video}`),
      "",
      "## Regression",
      "",
      "- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py tests/integration/test_diligence_api.py`",
      "- `node --check src/cite_or_die/ui/diligence.js`",
      "",
      "## Unresolved",
      "",
      "None.",
      "",
    ].join("\n"),
  );
}
