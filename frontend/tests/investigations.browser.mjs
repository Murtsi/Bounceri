// Inject a Playwright Page into this dependency-free browser regression suite.
// All API responses are intercepted; no provider, token or real budget is used.
export default async function checkInvestigations(page, baseURL = "http://127.0.0.1:5178") {
  const check = (condition, message) => {
    if (!condition) throw new Error(message);
  };
  const writes = [];
  const errors = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") writes.push(`${request.method()} ${request.url()}`);
  });
  page.on("pageerror", (error) => errors.push(error.message));
  const synthetic = {
    id: "fixture-case",
    module: "clean_the_traffic",
    source: { kind: "fixture", synthetic: true },
    created_at: "2026-11-14T10:00:00Z",
    evidence_version: 1,
    evidence_hash: "a".repeat(64),
    evidence: [
      {
        id: "ev-1",
        kind: "traffic_summary",
        data: {
          session_count: 3,
          request_count: 17,
          missing_information: ["No independent human labels"],
        },
      },
    ],
    local_assessment: {
      id: "local-1",
      kind: "local",
      label: "uncertain",
      score: null,
      model_version: "rules-v1",
      reasons: ["Insufficient evidence to classify"],
      evidence_ids: ["ev-1"],
    },
    review: { status: "unavailable", job_id: null, result: null },
    future_optional_field: { harmless: true },
  };
  const real = {
    ...synthetic,
    id: "real-case",
    source: { kind: "monitored_traffic", synthetic: false },
    local_assessment: { ...synthetic.local_assessment, label: "human" },
    review: { status: "not_requested" },
  };
  let mode = "empty";
  let reviewStatus = "unavailable";
  const records = () => ({
    "/api/capabilities": {
      modules: {
        clean_traffic: { enabled: true, implemented: true },
        spot_the_swarm: { enabled: true, implemented: true },
      },
    },
    "/api/usage": {
      limit_usd: 5,
      spent_usd: 0,
      reserved_usd: 0,
      available_usd: 5,
      executions: 0,
      requests: 0,
      max_executions: 100,
      max_requests: 200,
      paid_review_enabled: false,
    },
    "/api/investigations": mode === "empty" ? [] : [synthetic, real, { id: "unknown-origin", source: {} }],
    "/api/investigations/fixture-case": {
      ...synthetic,
      review: { status: reviewStatus },
    },
    "/api/investigations/fixture-case/assessments": [
      {
        id: "local-revision",
        kind: "local",
        created_at: synthetic.created_at,
        payload: { label: "uncertain", evidence_ids: ["ev-1"] },
      },
      {
        id: "decision-revision",
        kind: "decision_model",
        created_at: synthetic.created_at,
        payload: {
          outcome: "abstain",
          model: "mock-decision",
          evidence_ids: ["ev-1"],
        },
      },
    ],
    "/api/summary": {
      updated_at: null,
      synthetic: true,
      n_sessions: 0,
      by_label: {},
      n_campaigns: 0,
      ingest: {},
    },
    "/api/overview": { n_sessions: 0 },
  });
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = records();
    const unavailable = mode === "error" || (mode === "history-error" && path.endsWith("/assessments"));
    return route.fulfill({
      status: unavailable || !(path in data) ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(unavailable ? { detail: "Mock unavailable" } : (data[path] ?? {})),
    });
  });
  const reload = async () => {
    await page.goto(baseURL);
    await page.waitForLoadState("networkidle");
    check(
      await page.getByRole("heading", { name: "Kuka sivulla oikeasti käy" }).isVisible(),
      "Existing header changed",
    );
    check(
      (await page.getByRole("button", { name: "Yleiskuva", exact: true }).getAttribute("aria-current")) === "page",
      "Existing overview is no longer the default",
    );
    for (const name of ["Sessiot", "Kampanjat", "Mittarit"]) {
      check(await page.getByRole("button", { name, exact: true }).isVisible(), "Existing navigation changed");
    }
    await page.getByRole("button", { name: "Investigations", exact: true }).click();
    await page.waitForLoadState("networkidle");
  };
  await page.setViewportSize({ width: 1280, height: 900 });
  await reload();
  check(await page.getByText("No investigations published yet", { exact: true }).isVisible(), "Empty state missing");
  check((await page.getByText("Not implemented", { exact: true }).count()) === 3, "Future modules were enabled");

  mode = "error";
  await reload();
  await page.getByText("Investigations could not be loaded", { exact: true }).waitFor();
  check(
    (await page.getByText("No investigations published yet", { exact: true }).count()) === 0,
    "Outage rendered as empty success",
  );
  check((await page.getByRole("alert").count()) === 3, "Capabilities, usage and list errors must stay visible");

  mode = "populated";
  await reload();
  await page.getByRole("button", { name: /fixture-case/ }).waitFor();
  check(await page.getByText("Origin unavailable", { exact: true }).isVisible(), "Unknown origin was concealed");
  await page.getByRole("combobox", { name: "Source" }).selectOption("real");
  check((await page.getByRole("button", { name: /real-case/ }).count()) === 1, "Real source filter missing real case");
  check(
    (await page.getByRole("button", { name: /fixture-case|unknown-origin/ }).count()) === 0,
    "Source filter misclassified evidence",
  );
  await page.getByRole("combobox", { name: "Source" }).selectOption("synthetic");
  await page.getByRole("button", { name: /fixture-case/ }).click();
  await page.getByRole("heading", { name: "Evidence snapshot" }).waitFor();
  check(await page.getByText("Detector score: Not reported", { exact: true }).isVisible(), "Null score fabricated");
  check(await page.getByRole("heading", { name: "Microsoft Decision-1" }).isVisible(), "Decision stage missing");
  check(await page.getByRole("heading", { name: "Featherless reviewer" }).isVisible(), "Reviewer stage missing");
  check(
    (await page.getByText("No recorded assessment.", { exact: true }).count()) === 1,
    "Missing reviewer assessment was fabricated",
  );
  await page.getByRole("link", { name: "ev-1", exact: true }).first().click();
  check(
    (await page.locator("#evidence-ev-1").getAttribute("open")) !== null,
    "Evidence reference did not open evidence",
  );
  await page.locator("#evidence-ev-1 > summary").click();
  await page.getByRole("link", { name: "ev-1", exact: true }).first().click();
  check(
    (await page.locator("#evidence-ev-1").getAttribute("open")) !== null,
    "Evidence reference did not reopen closed evidence",
  );

  await page.setViewportSize({ width: 375, height: 812 });
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Mobile page overflow");
  check(
    await page.getByRole("button", { name: "Back to investigations" }).isVisible(),
    "Mobile return control inaccessible",
  );
  await page.getByRole("button", { name: "Back to investigations" }).click();
  for (const status of [
    "not_requested",
    "queued",
    "running",
    "completed",
    "failed",
    "unavailable",
    "deferred_budget",
  ]) {
    reviewStatus = status;
    await page.getByRole("button", { name: /fixture-case/ }).click();
    await page.getByRole("heading", { name: "Model review", exact: true }).waitFor();
    const expected = {
      not_requested: "Not requested",
      queued: "Queued",
      running: "Running",
      completed: "Completed",
      failed: "Failed",
      unavailable: "Unavailable",
      deferred_budget: "Deferred · budget",
    }[status];
    await page.getByText(expected, { exact: true }).waitFor();
    await page.getByRole("button", { name: "Back to investigations" }).click();
    // Remounting must fetch the latest record rather than asserting stale cache.
    await page.waitForTimeout(1100);
  }

  mode = "history-error";
  await page.getByRole("button", { name: /fixture-case/ }).click();
  await page.getByText("History could not be loaded", { exact: true }).waitFor();
  check(await page.getByRole("heading", { name: "Evidence snapshot" }).isVisible(), "History failure hid evidence");
  await page.getByRole("button", { name: "Open current traffic overview →" }).click();
  await page.getByText("Ei vielä liikennettä.", { exact: false }).waitFor();
  check(writes.length === 0, `Public UI issued write requests: ${writes.join(", ")}`);
  check(errors.length === 0, `Browser errors: ${errors.join(", ")}`);
  return {
    passed: [
      "existing overview remains default",
      "existing header and navigation preserved",
      "empty state",
      "outage distinction",
      "future modules disabled",
      "source filter",
      "null score",
      "separate history stages",
      "evidence references",
      "mobile width",
      "seven review states",
      "history outage",
      "legacy navigation",
      "GET only",
      "no browser errors",
    ],
    writes,
    errors,
  };
}
