import { afterAll, expect, test } from "bun:test";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const temporary = await mkdtemp(path.join(tmpdir(), "cite-recording-"));
const reservation = Bun.serve({ port: 0, fetch: () => new Response("reserved") });
const port = reservation.port;
if (!port) throw new Error("Could not reserve a local test port");
await reservation.stop(true);
const output = path.join(temporary, "demo.mp4");
process.env.CITE_OR_DIE_DEMO_PORT = String(port);
process.env.CITE_OR_DIE_DEMO_OUTPUT = output;
process.env.CITE_OR_DIE_DEMO_VIDEOS = path.join(temporary, "videos");
process.env.CITE_OR_DIE_DEMO_DATA = path.join(temporary, "data");
const { main, waitFor } = await import("../record.ts");

afterAll(async () => {
  await rm(temporary, { recursive: true, force: true });
});

test("records the offline upload and citation journey and stops its server", async () => {
  await main();
  const bytes = await readFile(output);
  expect(bytes.subarray(4, 8).toString()).toBe("ftyp");
  const probe = Bun.spawn([
    "ffprobe",
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=codec_name,width,height,duration",
    "-of",
    "json",
    output,
  ]);
  const metadata: unknown = JSON.parse(await new Response(probe.stdout).text());
  expect(await probe.exited).toBe(0);
  expect(metadata).toMatchObject({
    streams: [
      {
        codec_name: "h264",
        width: 1280,
        height: 760,
        duration: expect.stringMatching(/^[1-9]\d*\./),
      },
    ],
  });
  await expect(fetch(`http://127.0.0.1:${port}/healthz`)).rejects.toThrow();
}, 180000);

test("waits for health readiness and rejects an unhealthy server", async () => {
  let requests = 0;
  const server = Bun.serve({
    port: 0,
    fetch: () => new Response("health", { status: ++requests < 2 ? 503 : 200 }),
  });
  try {
    await waitFor(server.url.toString(), 5000);
    expect(requests).toBeGreaterThanOrEqual(2);
    await expect(waitFor(server.url.toString(), 0)).rejects.toThrow("did not become ready");
  } finally {
    await server.stop(true);
  }
});
