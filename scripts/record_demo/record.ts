import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { type Browser, chromium, type Locator } from "playwright";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const videosDir = process.env.CITE_OR_DIE_DEMO_VIDEOS || path.join(here, "videos");
const outputMp4 =
  process.env.CITE_OR_DIE_DEMO_OUTPUT || path.join(repoRoot, "docs", "site", "demo.mp4");
const sampleDoc = path.join(repoRoot, "examples", "sample.txt");

const PORT = Number(process.env.CITE_OR_DIE_DEMO_PORT || 8765);
const BASE_URL = `http://127.0.0.1:${PORT}`;
const DEMO_DATA =
  process.env.CITE_OR_DIE_DEMO_DATA || path.join(repoRoot, "data", "demo-recording");

export async function waitFor(url: string, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (error) {
      lastErr = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(
    `Server did not become ready at ${url}: ${lastErr instanceof Error ? lastErr.message : ""}`,
  );
}

async function startServer() {
  const proc = spawn(
    "uv",
    ["run", "cite-or-die", "serve", "--host", "127.0.0.1", "--port", String(PORT)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        CITE_OR_DIE_APP_ENV: "dev",
        CITE_OR_DIE_DATA_DIR: DEMO_DATA,
        CITE_OR_DIE_AUTH_SECRET: "demo-recording-secret-with-32-bytes!!",
        CITE_OR_DIE_VECTOR_BACKEND: "memory",
        CITE_OR_DIE_EMBEDDING_PROVIDER: "hash",
        CITE_OR_DIE_LLM_PROVIDER: "fake",
      },
      stdio: ["ignore", "inherit", "inherit"],
    },
  );
  try {
    await waitFor(`${BASE_URL}/healthz`, 60000);
  } catch (error) {
    proc.kill("SIGTERM");
    throw error;
  }
  return proc;
}

async function recordFlow() {
  await rm(videosDir, { recursive: true, force: true });
  await mkdir(videosDir, { recursive: true });
  await mkdir(path.dirname(outputMp4), { recursive: true });

  const browser = await chromium.launch({ headless: true });
  try {
    return await captureFlow(browser);
  } finally {
    await browser.close();
  }
}

async function captureFlow(browser: Browser) {
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
  async function glide(toX: number, toY: number, steps = 22, delay = 18) {
    for (let i = 1; i <= steps; i++) {
      const x = cursor.x + ((toX - cursor.x) * i) / steps;
      const y = cursor.y + ((toY - cursor.y) * i) / steps;
      await page.mouse.move(x, y);
      await page.waitForTimeout(delay);
    }
    cursor = { x: toX, y: toY };
  }

  async function moveTo(locator: Locator) {
    const box = await locator.boundingBox();
    if (!box) throw new Error("element not visible");
    await glide(box.x + box.width / 2, box.y + box.height / 2);
    return box;
  }

  async function typeInto(locator: Locator, text: string, { clear = true } = {}) {
    await moveTo(locator);
    await locator.click();
    if (clear) await locator.fill("");
    await locator.pressSequentially(text, { delay: 35 });
  }

  const step = (n: number, label: string) => console.log(`[demo] step ${n}: ${label}`);

  step(1, "pan across workspace");
  await glide(640, 380, 38);
  await page.waitForTimeout(700);

  step(2, "open settings");
  await moveTo(page.locator("#open-settings"));
  await page.locator("#open-settings").click();
  await page.waitForSelector("#settings-modal[open]", { timeout: 10000 });
  await page.waitForTimeout(500);

  await page.selectOption("#settings-llm-provider", "openai-compatible");
  await page.waitForTimeout(300);
  await typeInto(page.locator("#settings-llm-model"), "qwen3-8b");
  await typeInto(page.locator("#settings-llm-base-url"), "http://localhost:11434/v1");
  await typeInto(page.locator("#settings-llm-api-key"), "sk-demo-redacted-XXXX1234");
  await page.waitForTimeout(350);

  await page.selectOption("#settings-embedding-provider", "bge-m3");
  await page.waitForTimeout(300);

  await moveTo(page.locator("#settings-save"));
  await page.locator("#settings-save").click();
  await page.waitForTimeout(2000);

  await page.locator("#open-settings").click();
  await page.waitForSelector("#settings-modal[open]", { timeout: 10000 });
  await page.waitForTimeout(400);
  await moveTo(page.locator("#settings-delete"));
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#settings-delete").click();
  await page.waitForTimeout(1500);

  step(3, "upload sample document");
  const fileInput = page.locator("#file");
  await fileInput.setInputFiles(sampleDoc);
  await page.waitForTimeout(300);
  await moveTo(page.locator("#upload-form button[type=submit]"));
  await page.locator("#upload-form button[type=submit]").click();
  await page.waitForSelector("#upload-result:not(:empty)", { timeout: 20000 });
  await page.waitForTimeout(900);

  await moveTo(page.locator("#refresh-docs"));
  await page.locator("#refresh-docs").click();
  await page.waitForTimeout(700);

  step(4, "ask question");
  await typeInto(page.locator("#question"), "What does the sample document say?");
  await page.waitForTimeout(300);
  await moveTo(page.locator("#ask-button"));
  await page.locator("#ask-button").click();
  await page.waitForSelector(".transcript .citation-source", {
    state: "visible",
    timeout: 30000,
  });
  await page.waitForTimeout(4000);

  step(5, "hover citation source");
  const sourceButton = page.locator(".transcript .citation-source").first();
  await sourceButton.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  await moveTo(sourceButton);
  await page.waitForTimeout(900);
  const sourceBox = await sourceButton.boundingBox();
  if (sourceBox) {
    await glide(sourceBox.x + sourceBox.width / 2 - 14, sourceBox.y + sourceBox.height / 2, 12, 22);
    await page.waitForTimeout(250);
    await glide(sourceBox.x + sourceBox.width / 2 + 14, sourceBox.y + sourceBox.height / 2, 12, 22);
    await page.waitForTimeout(250);
    await glide(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2, 8, 22);
  }
  await page.waitForTimeout(900);

  step(5, "open citation drawer");
  await sourceButton.click();
  await page.waitForSelector("#citation-drawer.open, .citation-drawer.open", {
    timeout: 10000,
  });
  await page.waitForTimeout(4500);
  if (await page.locator("#close-citation").count()) {
    await moveTo(page.locator("#close-citation"));
    await page.waitForTimeout(400);
    await page.locator("#close-citation").click();
    await page.waitForTimeout(1200);
  }
  await moveTo(sourceButton);
  await page.waitForTimeout(1200);

  step(6, "show persisted fingerprint");
  await page.locator("#open-settings").click();
  await page.waitForSelector("#settings-modal[open]", { timeout: 10000 });
  await page.waitForTimeout(1600);
  await page.keyboard.press("Escape").catch(() => null);
  await page.waitForTimeout(800);

  const video = page.video();
  if (!video) throw new Error("Browser recording was not created");
  const videoPath = await video.path();
  await context.close();
  return videoPath;
}

async function reencodeToMp4(webmPath: string) {
  await new Promise<void>((resolve, reject) => {
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

export async function main() {
  if (!existsSync(sampleDoc)) {
    await writeFile(
      sampleDoc,
      "Cite-or-die demo: this sample document is small but cited verbatim.\n",
    );
  }
  await rm(DEMO_DATA, { recursive: true, force: true });

  const server = await startServer();
  let webmPath: string;
  try {
    webmPath = await recordFlow();
  } finally {
    server.kill("SIGINT");
    await new Promise<void>((resolve) => server.on("exit", () => resolve()));
  }
  await reencodeToMp4(webmPath);
  const info = await stat(outputMp4);
  console.log(`Wrote ${outputMp4} (${info.size} bytes).`);
}

if (import.meta.main) {
  main().catch((error: unknown) => {
    console.error(error);
    process.exitCode = 1;
  });
}
