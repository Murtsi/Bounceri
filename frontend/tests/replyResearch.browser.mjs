import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { chromium } from "playwright";
import { createServer } from "vite";

test("reply research displays measured evidence, limitations and an explicit unavailable state", { timeout: 30_000 }, async (t) => {
  const report = JSON.parse(await readFile(new URL("../../models/evaluation.social_replies.json", import.meta.url), "utf8"));
  const server = await createServer({ logLevel: "error", server: { host: "127.0.0.1", port: 0, open: false } });
  await server.listen();
  t.after(() => server.close());
  const browser = await chromium.launch();
  t.after(() => browser.close());
  const page = await browser.newPage({ reducedMotion: "reduce" });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let unavailable = false;
  let researchRequests = 0;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/evaluation/social-replies") {
      researchRequests++;
      return route.fulfill({ status: unavailable ? 503 : 200, json: unavailable ? { detail: "Report unavailable" } : report });
    }
    if (path === "/api/summary") return route.fulfill({ json: { updated_at: null, synthetic: false, source: null, n_sessions: 0, by_label: {}, n_campaigns: 0, ingest: {} } });
    if (path === "/api/metrics") return route.fulfill({ json: { stub: true, synthetic_data: false, metrics: {}, known_weaknesses: ["Native quality remains unmeasured"], ingest: {} } });
    return route.fulfill({ status: 404, json: {} });
  });
  const url = `${server.resolvedUrls.local[0]}?tab=metrics`;
  await page.goto(url);
  const panel = page.getByRole("region", { name: "Reply attack research preview" });
  await panel.getByText("Independence unverified.", { exact: true }).waitFor();
  for (const metric of [report.splits.test.precision, report.splits.test.recall, report.splits.test.false_positive_rate]) {
    assert.equal(await panel.getByText(`${(metric.value * 100).toFixed(2)}%`, { exact: true }).count(), 1);
    assert.equal(await panel.getByText(`${metric.numerator.toLocaleString("en-GB")} / ${metric.denominator.toLocaleString("en-GB")} posts`, { exact: true }).count(), 1);
  }
  assert.match(await panel.innerText(), /Abstention: 0\.00% \(0 \/ 1,215 test posts\)/);
  assert.equal(await panel.getByRole("link", { name: report.source.title }).getAttribute("href"), "https://zenodo.org/records/13896309");
  assert.equal(await page.getByText(/models\/metrics.json is a stub/).count(), 1);
  await panel.getByText("Method, split counts and research limitations", { exact: true }).click();
  assert.match(await panel.innerText(), new RegExp(report.source.file_sha256));
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false, "mobile must not overflow horizontally");
  assert.equal(researchRequests, 1);
  unavailable = true;
  await page.reload();
  await panel.getByText("Research preview unavailable. No research result can be shown.", { exact: true }).waitFor();
  assert.equal(await panel.locator(".metric-value").count(), 0, "503 must not invent zero results");
  assert.deepEqual(errors, []);
});
