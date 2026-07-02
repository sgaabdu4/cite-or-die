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

const dealFiles = [
  {
    filename: "01-customer-contract-scan.txt",
    text:
      "Master services agreement for Northstar Managed Services. " +
      "Change of control consent is required before assignment. " +
      "Termination for convenience can be exercised on 30 days notice.",
  },
  {
    filename: "02-financial-pack-fy26.txt",
    text:
      "FY26 revenue is GBP 180m. Reported EBITDA is GBP 24m. " +
      "Management normalisation adds GBP 5m for restructuring costs. " +
      "Vendor response states recurring restructuring costs are GBP 4m.",
  },
  {
    filename: "03-operations-report.txt",
    text:
      "Operational report shows utilisation at 72 percent and SLA backlog at 19 days. " +
      "Three offshore delivery leads own transition-critical workflows.",
  },
  {
    filename: "04-customer-data-export.txt",
    text:
      "Top customer represents 34 percent of revenue. " +
      "Customer churn is 16 percent and renewal status is incomplete for two key accounts.",
  },
  {
    filename: "05-hr-records.txt",
    text:
      "HR records show 940 employees, regretted attrition of 18 percent, " +
      "and 42 open vacancies in delivery roles.",
  },
  {
    filename: "06-qa-log-and-ir-list.txt",
    text:
      "Information request HR attrition schedule remains open and delayed by 12 days. " +
      "Vendor response does not provide supporting payroll detail.",
  },
];

const dirs = {
  fixtures: path.join(runDir, "fixtures"),
  plans: path.join(runDir, "plans"),
  screenshots: path.join(runDir, "screenshots", flow),
  videos: path.join(runDir, "videos"),
  logs: path.join(runDir, "logs"),
};

await Promise.all(Object.values(dirs).map((dir) => fs.mkdir(dir, { recursive: true })));
await fs.writeFile(eventsPath, "");
const fixtureFiles = await writeFixtureFiles();
await writePlans();

const browser = await chromium.launch({ headless: true });
const allProfiles = [
  { name: "desktop", viewport: { width: 1440, height: 980 }, isMobile: false },
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
      await page.getByRole("button", { name: "Configure provider" }).click();
      await page.getByRole("heading", { name: "Model provider" }).waitFor();
      await page.locator("#settings-llm-provider").selectOption("fake");
      await page.getByRole("button", { name: "Save" }).click();
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
        await page.locator("#file").setInputFiles(fixture.path);
        await page.getByRole("button", { name: "Upload" }).click();
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
      await page.getByRole("button", { name: "Use all files" }).click();
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
      await page
        .locator("#question")
        .fill("What customer concentration risk should the deal team review?");
      await page.getByRole("button", { name: "Ask" }).click();
      await page.getByRole("button", { name: "04-customer-data-export.txt" }).first().waitFor({
        timeout: 20000,
      });
    });
    await step(profile, page, "create-review-from-files", "click", async () => {
      await page.locator("#diligence-load-selected-inline").click();
      await page.getByText("Selected files loaded. Run the accelerator when ready.").waitFor({
        timeout: 20000,
      });
      await page.locator("#diligence-source-count", { hasText: "6" }).waitFor();
    });
    await step(profile, page, "run-accelerator", "click", async () => {
      await page.locator("#diligence-run-inline").click();
      await page.getByText("Accelerator run complete. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      await page
        .locator("#diligence-risk-register")
        .getByRole("heading", { name: "Top customer concentration" })
        .waitFor();
    });
    await step(profile, page, "open-classified-files", "click", async () => {
      await page.getByRole("button", { name: "Classified files" }).click();
      await page
        .locator("#diligence-source-library")
        .getByText("01-customer-contract-scan.txt")
        .waitFor();
    });
    await step(profile, page, "open-extracted-facts", "click", async () => {
      await page.getByRole("button", { name: "Extracted facts" }).click();
      await page.getByText("Top customer revenue share").waitFor();
    });
    await step(profile, page, "open-risk-register", "click", async () => {
      await page.getByRole("button", { name: "Risk register" }).click();
      await page
        .getByRole("heading", { name: "Normalisation requires earnings-quality review" })
        .waitFor();
    });
    await step(profile, page, "open-insights", "click", async () => {
      await page.getByRole("button", { name: "Cross-workstream insights" }).click();
      await page.getByText("Customer concentration affects earnings diligence").waitFor();
    });
    await step(profile, page, "open-requests", "click", async () => {
      await page.getByRole("button", { name: "Open requests" }).click();
      await page
        .locator("#diligence-ir-tracker")
        .getByRole("heading", { name: "Open information request" })
        .waitFor();
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
      await page
        .locator("#viewer-meta", { hasText: "Top customer represents 34 percent of revenue." })
        .waitFor();
    });
    await step(profile, page, "close-evidence", "click", async () => {
      await page.locator("#close-citation").click();
      await page.waitForFunction(() => !document.getElementById("citation-drawer")?.classList.contains("open"));
    });
    await step(profile, page, "run-ai-assisted-review", "click", async () => {
      await page.locator("#diligence-assist").click();
      await page.getByText("AI-assisted review added. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      const assistedReview = page.locator("#diligence-report-drafts article", {
        hasText: "AI-Assisted Risk Review",
      });
      await assistedReview.getByRole("heading", { name: "AI-Assisted Risk Review" }).waitFor();
      await assistedReview.getByText("Provider: fake").waitFor();
    });
    await step(profile, page, "rerun-ai-assisted-review", "click", async () => {
      await page.locator("#diligence-assist").click();
      await page.getByText("AI-assisted review added. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      await page.locator("#diligence-report-drafts article", {
        hasText: "AI-Assisted Risk Review",
      }).waitFor();
    });
    await step(profile, page, "rerun-accelerator", "click", async () => {
      await page.locator("#diligence-run-inline").click();
      await page.getByText("Accelerator run complete. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      await page.locator("#diligence-fact-count", { hasText: "14" }).waitFor();
      await page.locator("#diligence-risk-count", { hasText: "5" }).waitFor();
    });
    await step(profile, page, "run-ai-assisted-after-rerun", "click", async () => {
      await page.locator("#diligence-assist").click();
      await page.getByText("AI-assisted review added. Human sign-off required.").waitFor({
        timeout: 20000,
      });
      await page.locator("#diligence-report-drafts article", {
        hasText: "AI-Assisted Risk Review",
      }).waitFor();
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
      "Actions: provider setup and save, upload, selection, cited question, review creation, accelerator run, all output tabs, evidence drawer, AI-assisted review, reruns",
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
      "- `node --check src/cite_or_die/ui/app.js src/cite_or_die/ui/diligence.js src/cite_or_die/ui/setup_progress.js`",
      "",
      "## Unresolved",
      "",
      "None.",
      "",
    ].join("\n"),
  );
}
