import assert from "node:assert/strict";
import test from "node:test";
import { chromium } from "playwright";
import { createServer } from "vite";
import checkInvestigations from "./investigations.browser.mjs";

test("dashboard browser regressions", { timeout: 120_000 }, async (t) => {
  const server = await createServer({
    logLevel: "error",
    server: { host: "127.0.0.1", port: 0, open: false },
  });
  t.after(async () => {
    await server.close();
    assert.equal(server.httpServer.listening, false, "Vite server must stop");
  });
  await server.listen();

  const browser = await chromium.launch();
  t.after(async () => {
    await browser.close();
    assert.equal(browser.isConnected(), false, "Browser must stop");
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(10_000);
  const result = await checkInvestigations(page, server.resolvedUrls.local[0]);
  assert.ok(result.passed.length > 0, "Browser suite must execute checks");
  t.diagnostic(`${result.passed.length} browser checks passed: ${result.passed.join(", ")}`);
});
