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
    complete: false,
    review_eligibility: { eligible: false, reason: "Fixture evidence exceeds bounded AI packet limits." },
    missing_information: ["Fixture missing source provenance"],
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
      limitations: ["Fixture local limitation"],
    },
    review: { status: "unavailable", job_id: null, result: null },
    future_optional_field: { harmless: true },
  };
  const real = {
    ...synthetic,
    id: "real-case",
    source: { kind: "monitored_traffic", synthetic: false },
    complete: true,
    local_assessment: { ...synthetic.local_assessment, label: "human" },
    review: { status: "not_requested" },
  };
  let mode = "empty";
  let reviewStatus = "unavailable";
  let enforcementStatus = "active";
  let affectedRequests = 3;
  let enforcementMode = "populated";
  const records = () => ({
    "/api/capabilities": {
      modules: {
        clean_traffic: { enabled: true, implemented: true },
        spot_the_swarm: { enabled: true, implemented: true },
      },
      providers: {
        decision_model: {
          provider: "featherless",
          model: "fixture/bounded-model",
          role: "bounded_decision",
          available: false,
        },
        reviewer: {
          provider: "featherless",
          model: "fixture/final-model",
          role: "final_advisory_reviewer",
          available: false,
        },
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
      execution_halted: true,
      halt_reason: "fixture_budget_halt",
    },
    "/api/investigations": mode === "empty" ? [] : [synthetic, real, { id: "unknown-origin", source: {} }],
    "/api/investigations/fixture-case": {
      ...synthetic,
      review: { status: reviewStatus, reason: "fixture_review_reason" },
    },
    "/api/investigations/real-case": real,
    "/api/investigations/real-case/assessments": [],
    "/api/investigations/real-case/enforcements": [],
    "/api/investigations/fixture-case/assessments": [
      {
        id: "local-revision",
        stage: "local",
        created_at: synthetic.created_at,
        payload: { label: "uncertain", evidence_ids: ["ev-1"] },
      },
      {
        id: "decision-revision",
        stage: "decision_model",
        created_at: synthetic.created_at,
        metadata: {
          provider: "featherless",
          model: "fixture/historical-model",
          returned_model: "fixture/returned-model",
          prompt_version: "prompt-fixture-v1",
          schema_version: "schema-fixture-v1",
        },
        payload: {
          outcome: "abstain",
          model: "mock-decision",
          evidence_ids: ["ev-1"],
        },
      },
    ],
    "/api/investigations/fixture-case/enforcements":
      enforcementMode === "empty"
        ? []
        : [
            {
              id: "policy-1",
              case_id: "fixture-case",
              actor_id: "attack",
              scope: "controlled_demo_actor",
              action: "rate_limit",
              approval_basis: "manual_demo_override",
              status: enforcementStatus,
              evidence_version: 1,
              evidence_hash: "a".repeat(64),
              created_at: 1794650400,
              expires_at: 1794650460,
              revoked_at: null,
              expired_at: null,
              affected_requests: affectedRequests,
              allowed_requests: 2,
              audit: [{ event: "approved", at: 1794650400, details: { ttl_seconds: 60 } }],
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
    "/api/sessions": [],
    "/api/campaigns": [],
    "/api/metrics": {
      stub: true,
      synthetic_data: true,
      metrics: { model_version: "stub-v0" },
      known_weaknesses: ["Fixture limitation"],
      ingest: {},
    },
  });
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = records();
    const unavailable =
      mode === "error" ||
      (mode === "history-error" && path.endsWith("/assessments")) ||
      (enforcementMode === "error" && path.endsWith("/enforcements"));
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
      await page.locator("header").getByRole("img", { name: "Bouncer", exact: true }).isVisible(),
      "Existing header changed",
    );
    check(
      (await page.getByRole("tab", { name: "Yleiskuva", exact: true }).getAttribute("aria-selected")) === "true",
      "Existing overview is no longer the default",
    );
    for (const name of ["Sessiot", "Kampanjat", "Mittarit"]) {
      check(await page.getByRole("tab", { name, exact: true }).isVisible(), "Existing navigation changed");
    }
    check(
      (await page.getByRole("button", { name: /Vaihda .* teemaan/ }).count()) === 0,
      "PR24 removed theme toggle was restored",
    );
    await page.getByRole("tab", { name: "Investigations", exact: true }).click();
    if (mode === "empty") await page.getByText("No investigations published yet", { exact: true }).waitFor();
    else if (mode === "error") await page.getByText("Investigations could not be loaded", { exact: true }).waitFor();
    else await page.getByRole("button", { name: /fixture-case/ }).waitFor();
    await page.waitForLoadState("networkidle");
  };
  await page.setViewportSize({ width: 1280, height: 900 });
  await reload();
  check(await page.getByText("No investigations published yet", { exact: true }).isVisible(), "Empty state missing");
  check((await page.getByText("Not implemented", { exact: true }).count()) === 3, "Future modules were enabled");
  check(
    await page.getByText("Model execution halted: fixture_budget_halt", { exact: true }).isVisible(),
    "Execution halt missing",
  );
  check(
    await page.evaluate(() => document.documentElement.classList.contains("dark")),
    "PR24 dark-only default changed",
  );
  check(
    await page
      .locator(".investigations-view section")
      .first()
      .evaluate(
        (node) =>
          node.classList.contains("glass") && getComputedStyle(node).backgroundColor === "rgba(255, 255, 255, 0.055)",
      ),
    "Investigation panels do not follow PR24 dark glass theme",
  );
  await page.getByRole("tab", { name: "Sessiot", exact: true }).click();
  await page.getByText("Ei sessioita tällä suodattimella.", { exact: true }).waitFor();
  await page.getByRole("tab", { name: "Kampanjat", exact: true }).click();
  await page.getByText("Ei kampanjoita:", { exact: false }).waitFor();
  await page.getByRole("tab", { name: "Mittarit", exact: true }).click();
  await page.getByText("models/metrics.json on stub:", { exact: false }).waitFor();
  await page.getByRole("tab", { name: "Yleiskuva", exact: true }).click();
  await page.getByText("Odotetaan liikennettä…", { exact: false }).waitFor();
  await page.getByRole("tab", { name: "Investigations", exact: true }).click();
  await page.getByText("No investigations published yet", { exact: true }).waitFor();

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
  check(
    await page
      .getByRole("button", { name: /fixture-case/ })
      .getByText("Bounded AI review ineligible", { exact: true })
      .isVisible(),
    "List hides AI review ineligibility",
  );
  check(await page.getByText("Origin unavailable", { exact: true }).isVisible(), "Unknown origin was concealed");
  await page.getByRole("combobox", { name: "Source" }).selectOption("real");
  check((await page.getByRole("button", { name: /real-case/ }).count()) === 1, "Real source filter missing real case");
  check(
    (await page.getByRole("button", { name: /fixture-case|unknown-origin/ }).count()) === 0,
    "Source filter misclassified evidence",
  );
  await page.getByRole("button", { name: /real-case/ }).click();
  await page.getByText("Bounded AI review ineligible", { exact: true }).waitFor();
  check(
    await page.getByText("Fixture evidence exceeds bounded AI packet limits.", { exact: true }).isVisible(),
    "Review eligibility reason missing",
  );
  check(
    (await page.getByText("Evidence snapshot is incomplete.", { exact: false }).count()) === 0,
    "AI ineligibility was confused with source completeness",
  );
  await page.getByRole("button", { name: "Back to investigations", exact: true }).click();
  await page.getByRole("combobox", { name: "Source" }).selectOption("synthetic");
  await page.getByRole("button", { name: /fixture-case/ }).click();
  await page.getByRole("heading", { name: "Evidence snapshot" }).waitFor();
  check(
    await page.getByText("Fixture missing source provenance", { exact: true }).isVisible(),
    "Missing evidence hidden",
  );
  check(await page.getByText("Fixture local limitation", { exact: true }).isVisible(), "Local limitation hidden");
  check(
    await page.getByText("Review reason: fixture_review_reason", { exact: true }).isVisible(),
    "Review reason hidden",
  );
  check(
    await page.getByText("Evidence snapshot is incomplete.", { exact: false }).isVisible(),
    "Incomplete evidence status hidden",
  );
  check(await page.getByText("Detector score: Not reported", { exact: true }).isVisible(), "Null score fabricated");
  check(await page.getByRole("heading", { name: "Bounded decision" }).isVisible(), "Decision stage missing");
  check(await page.getByRole("heading", { name: "Final advisory reviewer" }).isVisible(), "Reviewer stage missing");
  check(
    await page.getByText("fixture/bounded-model", { exact: true }).isVisible(),
    "Configured decision model missing",
  );
  check(await page.getByText("fixture/final-model", { exact: true }).isVisible(), "Configured reviewer model missing");
  check(
    await page.getByText("fixture/historical-model", { exact: true }).isVisible(),
    "Recorded model identity missing",
  );
  check(await page.getByText("fixture/returned-model", { exact: true }).isVisible(), "Returned model identity missing");
  check(await page.getByText("prompt-fixture-v1", { exact: true }).isVisible(), "Recorded prompt version missing");
  check(await page.getByText("schema-fixture-v1", { exact: true }).isVisible(), "Recorded schema version missing");
  check(
    !/Microsoft|Decision-1/.test(await page.locator(".investigations-view").innerText()),
    "Hardcoded provider/model claim remains",
  );
  check(
    await page
      .getByRole("heading", { name: "Local detector", exact: true })
      .locator("..")
      .getByText("local-revision", { exact: true })
      .isVisible(),
    "Actual stage-local assessment was misplaced",
  );
  check(
    await page
      .getByRole("heading", { name: "Bounded decision", exact: true })
      .locator("..")
      .getByText("decision-revision", { exact: true })
      .isVisible(),
    "Actual stage-decision assessment was misplaced",
  );
  check(
    (await page.getByText("Other assessment stages", { exact: false }).count()) === 0,
    "Known API stages were treated as unknown",
  );
  await page.getByText("Affected requests: 3", { exact: true }).waitFor();
  check(
    await page.getByText("Manually approved demo policy", { exact: true }).isVisible(),
    "Manual approval basis omitted",
  );
  check(await page.getByText("Active", { exact: true }).isVisible(), "Actual enforcement status missing");
  check(
    await page.getByText("Allowed requests: 2", { exact: true }).isVisible(),
    "Actual enforcement counters missing",
  );
  check(await page.getByText("Expires", { exact: true }).isVisible(), "Policy expiry missing");
  affectedRequests = 7;
  enforcementStatus = "revoked";
  await page.getByText("Affected requests: 7", { exact: true }).waitFor();
  await page.getByText("Revoked", { exact: true }).waitFor();
  enforcementStatus = "expired";
  await page.getByText("Expired", { exact: true }).waitFor();
  enforcementMode = "empty";
  await page.getByText("No enforcement policies recorded for this investigation.", { exact: true }).waitFor();
  enforcementMode = "error";
  await page.getByText("Enforcement status could not be loaded", { exact: true }).waitFor();
  check(
    (await page.getByText("No enforcement policies recorded for this investigation.", { exact: true }).count()) === 0,
    "Enforcement outage rendered as empty success",
  );
  enforcementMode = "populated";
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
    await page
      .getByRole("region", { name: "Model review", exact: true })
      .getByText(expected, { exact: true })
      .waitFor();
    await page.getByRole("button", { name: "Back to investigations" }).click();
    // Remounting must fetch the latest record rather than asserting stale cache.
    await page.waitForTimeout(1100);
  }

  mode = "history-error";
  await page.getByRole("button", { name: /fixture-case/ }).click();
  await page.getByText("History could not be loaded", { exact: true }).waitFor();
  check(await page.getByRole("heading", { name: "Evidence snapshot" }).isVisible(), "History failure hid evidence");
  await page.getByRole("button", { name: "Open current traffic overview →" }).click();
  await page.getByText("Odotetaan liikennettä…", { exact: false }).waitFor();
  check(writes.length === 0, `Public UI issued write requests: ${writes.join(", ")}`);
  check(errors.length === 0, `Browser errors: ${errors.join(", ")}`);
  return {
    passed: [
      "existing overview remains default",
      "existing header and navigation preserved",
      "PR24 sessions campaigns metrics and overview preserved",
      "PR24 dark-only glass theme preserved",
      "empty state",
      "outage distinction",
      "future modules disabled",
      "source filter",
      "bounded AI eligibility visible in list and detail",
      "AI eligibility distinct from source completeness",
      "null score",
      "separate history stages",
      "actual API stage grouping",
      "configured and recorded provider/model metadata",
      "manual demo approval basis",
      "incomplete evidence and limitations",
      "execution halt and review reason",
      "enforcement endpoint and polling",
      "enforcement counters and expiry",
      "enforcement empty versus error",
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
