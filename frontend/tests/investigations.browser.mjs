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
  let releasePage;
  let holdNextPage = false;
  const caseRequests = [];
  let evaluationMode = "published";
  let runtimeMetricsUnavailable = false;
  const publishedEvaluation = {
    available: true,
    dataset: {
      id: "native-7",
      n_known: 24,
      n_runs: 2,
      n_sessions: 28,
      n_unknown: 4,
      split: "reserved_known_templates",
    },
    detector: {
      freeze_commit: "b92b333b41857695bcace285fe6ae1b9bcf95488",
      model_version: "rules-v2",
      source_code_sha256: {
        "src/bouncer/session/rules.py": "96d2478035ef7d15882a1d3524d5154c9b4c6644c0888224c6a46700098ef50c",
        "src/bouncer/session/score.py": "21a87b40e3b975960474951378ba39aba1baa5d3a44a08e2fd905d813400772a",
      },
    },
    limitations: [
      "Synthetic generator reference intent, not independently verified human identity or real-world maliciousness.",
      "The reserved partition uses known public templates; it is not a genuinely hidden attack.",
      "The rule fix was frozen before this once-only reserved evaluation; viewed candidate validation is development data.",
      "Precision is conditional on the 24 known-reference sessions; 4 unknown-intent sessions are excluded from that denominator.",
      "All 28 sessions contribute to uncertainty. More abstention accounts for the two corrected development false positives.",
      "Zero false positives among 14 simulated human sessions does not demonstrate real-human FPR below 1%.",
      "95% Wilson intervals are descriptive and do not account for dependence within the two generated runs.",
      "Familiar scanner and same-target authentication fixtures do not establish novel-attack generalization.",
      "No DNS verification, coefficient training, paid model calls or automatic model promotion occurred.",
      "S8 models/metrics.json remains an unmeasured stub with null outcomes.",
    ],
    metrics: {
      bad_bot_precision: {
        ci95_lower: 0.7224671969739422,
        ci95_upper: 0.9999999999999999,
        denominator: 10,
        numerator: 10,
        value: 1.0,
      },
      human_false_positive_rate: {
        ci95_lower: 2.220446049250313e-16,
        ci95_upper: 0.21531080540298045,
        denominator: 14,
        numerator: 0,
        value: 0.0,
      },
      uncertain_share: {
        ci95_lower: 0.4583030637323058,
        ci95_upper: 0.7929417058564169,
        denominator: 28,
        numerator: 18,
        value: 0.6428571428571429,
      },
    },
    schema_version: 1,
    synthetic: true,
    unavailable: ["independent_real_humans", "genuinely_hidden_attack"],
  };
  let reviewStatus = "unavailable";
  let enforcementStatus = "active";
  let affectedRequests = 3;
  let enforcementMode = "populated";
  let populatedSessions = false;
  const publicReason = "Local cross-session relationship; attribution remains uncertain.";
  const publicSession = {
    id: "public-session",
    ip: "client-c055e25963",
    user_agent: "Redacted demo client",
    started_at: "2026-11-14T18:13:53Z",
    ended_at: "2026-11-14T18:16:33Z",
    n_requests: 2,
    label: "bad_bot",
    score: 1,
    reason: "Local detector label: bad_bot.",
    action: "rate_limit",
    sim_class: null,
    campaign_id: "campaign-1",
  };
  const records = () => ({
    "/api/evaluation":
      evaluationMode === "unavailable"
        ? { available: false, synthetic: true, reason: "Fixture evaluation withheld" }
        : publishedEvaluation,
    "/api/capabilities": {
      modules: {
        clean_traffic: { enabled: true, implemented: true },
        spot_the_swarm: { enabled: true, implemented: true },
      },
      providers: {
        mode: "experimental",
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
    "/api/overview": {
      n_sessions: 0,
      alerts: [],
      actors: [],
      distribution: { human: 0, good_bot: 0, bad_bot: 0, uncertain: 0 },
      timeline: { step_s: 60, points: [] },
      honesty: { synthetic: true, n_humans: 0, false_alarms: 0, fpr: null, fpr_ci95_upper: null },
    },
    "/api/sessions": populatedSessions ? [publicSession] : [],
    "/api/sessions/public-session": {
      ...publicSession,
      verdict: {
        label: "bad_bot",
        score: 1,
        model_version: "local-detector",
        reasons: ["Local detector label: bad_bot."],
        verified_bot: null,
      },
      campaign: {
        id: "campaign-1",
        kind: "credential_stuffing",
        size: 24,
        session_ids: ["public-session"],
        reasons: [publicReason],
      },
      requests: [{ ts: "2026-11-14T18:13:53Z", method: "POST", path: "/login", status: 401, username: null }],
    },
    "/api/campaigns": [],
    "/api/metrics": {
      stub: true,
      synthetic_data: true,
      metrics: { model_version: "stub-v0" },
      known_weaknesses: ["Fixture limitation"],
      ingest: {},
    },
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const data = records();
    if (path === "/api/investigations") {
      const origin = url.searchParams.get("origin") ?? "all";
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const limit = Number(url.searchParams.get("limit") ?? 100);
      caseRequests.push({ origin, offset, limit });
      const cases = mode === "paginated"
        ? [synthetic, ...Array.from({ length: 99 }, (_, index) => ({ ...synthetic, id: `fixture-${index}` })), real]
        : data[path];
      data[path] = cases.filter((item) => origin === "all" || (origin === "synthetic"
        ? item.source?.synthetic === true
        : item.source?.synthetic === false && item.source.kind === "monitored_traffic")).slice(offset, offset + limit);
      if (holdNextPage && offset === 100) await new Promise((resolve) => { releasePage = resolve; });
    }
    if (path === "/api/evaluation" && evaluationMode === "404")
      return route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
    const unavailable =
      mode === "error" ||
      (runtimeMetricsUnavailable && path === "/api/metrics") ||
      (mode === "history-error" && path.endsWith("/assessments")) ||
      (enforcementMode === "error" && path.endsWith("/enforcements"));
    return route.fulfill({
      status: unavailable || !(path in data) ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(unavailable ? { detail: "Mock unavailable" } : (data[path] ?? {})),
    });
  });
  const nav = (label) =>
    page
      .locator('nav[aria-label="Views"]:visible')
      .getByRole("button", { name: new RegExp(`^${label}(?:\\s*\\d+)?$`) });
  const reload = async () => {
    const dashboardURL = new URL(baseURL);
    dashboardURL.searchParams.set("tab", "overview");
    await page.goto(dashboardURL.href);
    await page.waitForLoadState("networkidle");
    await page.getByText("Analysing traffic\u2026", { exact: true }).waitFor({ state: "hidden" });
    check(await page.getByRole("button", { name: "Bounceri home", exact: true }).filter({ visible: true }).isVisible(), "Dashboard home logo missing");
    check(
      (await nav("Overview").getAttribute("aria-current")) === "page",
      "Explicit dashboard route did not open overview",
    );
    for (const name of ["Sessions", "Campaigns", "Metrics"]) {
      check(await nav(name).isVisible(), "Existing navigation changed");
    }
    check(
      (await page.getByRole("button", { name: /Vaihda .* teemaan/ }).count()) === 0,
      "PR25 removed theme toggle was restored",
    );
    await nav("Investigations").click();
    if (mode === "empty") await page.getByText("No investigations published yet", { exact: true }).waitFor();
    else if (mode === "error") await page.getByText("Investigations could not be loaded", { exact: true }).waitFor();
    else await page.getByRole("button", { name: /fixture-case/ }).waitFor();
    await page.waitForLoadState("networkidle");
  };
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(baseURL);
  await page.waitForLoadState("networkidle");
  await page.getByText("Analysing traffic\u2026", { exact: true }).waitFor({ state: "hidden" });
  const landingTitle = page.getByRole("heading", { name: /Every session meets/ });
  await landingTitle.waitFor();
  check((await page.getByRole("navigation", { name: "Views", exact: true }).count()) === 0,
    "Default landing unexpectedly includes dashboard navigation");
  check(await page.getByRole("img", { name: /^Animated illustration: a doorman/ }).isVisible(),
    "Landing gatehouse illustration missing");
  check(await page.getByRole("status").filter({ hasText: "synthetic traffic" }).isVisible(),
    "Landing hides API synthetic provenance");
  await page.getByRole("button", { name: "Open the live dashboard", exact: true }).first().click();
  await nav("Overview").waitFor();
  check(new URL(page.url()).searchParams.get("tab") === "overview"
    && await nav("Overview").getAttribute("aria-current") === "page", "Landing CTA did not open dashboard overview");
  await page.getByRole("button", { name: "Bounceri home", exact: true }).filter({ visible: true }).click();
  await landingTitle.waitFor();
  check(new URL(page.url()).search === "", "Sidebar logo did not restore landing route");
  await page.getByRole("button", { name: "Open dashboard", exact: true }).click();
  await nav("Overview").waitFor();
  check(await nav("Overview").getAttribute("aria-current") === "page", "Landing header CTA did not open overview");
  await reload();
  check(await page.getByText("No investigations published yet", { exact: true }).isVisible(), "Empty state missing");
  check((await page.getByText("Not implemented", { exact: true }).count()) === 3, "Future modules were enabled");
  check(
    await page.getByText("Model execution halted: fixture_budget_halt", { exact: true }).isVisible(),
    "Execution halt missing",
  );
  const evaluation = page.getByRole("region", { name: "Detector evaluation", exact: true });
  await evaluation.getByText("Synthetic benchmark", { exact: true }).waitFor();
  check(
    await evaluation.getByText("Reserved known-template runs", { exact: true }).isVisible(),
    "Evaluation split hidden",
  );
  check(
    await evaluation.getByText("28 sessions · 2 runs · 24 known · 4 unknown", { exact: true }).isVisible(),
    "Evaluation support counts missing",
  );
  check(await evaluation.getByText("10 / 10", { exact: true }).isVisible(), "Published precision support missing");
  check(
    await evaluation.getByText("0 / 14", { exact: true }).isVisible(),
    "Published human false positive support missing",
  );
  check(await evaluation.getByText("18 / 28", { exact: true }).isVisible(), "Published uncertain denominator missing");
  check(
    await evaluation.getByText("0.00% · 95% interval: 0.00%–21.53%", { exact: true }).isVisible(),
    "Small-sample human interval hidden",
  );
  check(
    await evaluation
      .getByText("Unavailable: independent real humans; genuinely hidden attack.", { exact: true })
      .isVisible(),
    "Missing independent evaluation concealed",
  );
  check(
    await evaluation
      .getByText(
        "Zero false positives among 14 simulated human sessions does not demonstrate real-human FPR below 1%.",
        { exact: true },
      )
      .isVisible(),
    "Synthetic limitation hidden",
  );
  await evaluation.getByText("Dataset and detector provenance", { exact: true }).click();
  check(await evaluation.getByText("rules-v2", { exact: true }).isVisible(), "Evaluation detector version missing");
  check(
    await evaluation.getByText(publishedEvaluation.detector.freeze_commit, { exact: true }).isVisible(),
    "Detector freeze commit missing",
  );
  evaluationMode = "404";
  await evaluation.getByRole("button", { name: "Refresh evaluation", exact: true }).click();
  await evaluation.getByText("Evaluation has not been published.", { exact: false }).waitFor();
  check(
    (await evaluation.getByText("0 / 14", { exact: true }).count()) === 0,
    "404 evaluation retained a measured result",
  );
  evaluationMode = "unavailable";
  await evaluation.getByRole("button", { name: "Refresh evaluation", exact: true }).click();
  await evaluation.getByText("Fixture evaluation withheld", { exact: false }).waitFor();
  evaluationMode = "published";
  await evaluation.getByRole("button", { name: "Refresh evaluation", exact: true }).click();
  await evaluation.getByText("Synthetic benchmark", { exact: true }).waitFor();
  check(
    await page.evaluate(() => document.documentElement.classList.contains("dark")),
    "PR25 dark-only default changed",
  );
  check(
    await page
      .locator(".investigations-view section")
      .first()
      .evaluate(
        (node) =>
          node.classList.contains("glass") && getComputedStyle(node).backgroundColor === "rgba(255, 255, 255, 0.055)",
      ),
    "Investigation panels do not follow PR25 dark glass theme",
  );
  await nav("Sessions").click();
  await page.getByText("No sessions match this filter.", { exact: true }).waitFor();
  await nav("Campaigns").click();
  await page.getByText("No campaigns:", { exact: false }).waitFor();
  await page.getByRole("button", { name: "Bounceri home", exact: true }).filter({ visible: true }).click();
  await page.getByRole("button", { name: "See benchmark results and limitations", exact: true }).click();
  check(new URL(page.url()).search === "?tab=metrics", "Landing benchmark link did not open Metrics");
  await page.getByText("models/metrics.json is a stub:", { exact: false }).waitFor();
  await evaluation.getByText("Synthetic benchmark", { exact: true }).waitFor();
  check(await evaluation.getByText("18 / 28", { exact: true }).isVisible(), "Metrics omitted the published benchmark");
  check(
    await evaluation.getByRole("link", { name: "Read the benchmark method" }).getAttribute("href") ===
      "https://github.com/Murtsi/Bounceri/blob/main/docs/EVALUATION.md",
    "Benchmark method link missing",
  );
  await evaluation.getByText("Dataset and detector provenance", { exact: true }).click();
  check(
    await evaluation.getByRole("link", { name: publishedEvaluation.detector.freeze_commit }).getAttribute("href") ===
      `https://github.com/Murtsi/Bounceri/commit/${publishedEvaluation.detector.freeze_commit}`,
    "Benchmark does not link to the frozen commit",
  );
  await page.setViewportSize({ width: 375, height: 812 });
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    "Expanded benchmark provenance overflows on mobile",
  );
  runtimeMetricsUnavailable = true;
  await page.reload();
  await page.getByText("API not responding: Error: /api/metrics: 503", { exact: true }).waitFor();
  await evaluation.getByText("18 / 28", { exact: true }).waitFor();
  runtimeMetricsUnavailable = false;
  await nav("Overview").click();
  await page.getByText("Waiting for traffic…", { exact: false }).waitFor();
  populatedSessions = true;
  await page.setViewportSize({ width: 375, height: 812 });
  await nav("Sessions").click();
  await page.getByRole("button", { name: "Open session public-session", exact: true }).click();
  await page.getByRole("complementary", { name: "Session public-session", exact: true }).waitFor();
  await page.waitForTimeout(650);
  check(
    await page
      .getByRole("complementary", { name: "Session public-session", exact: true })
      .getByText(publicReason, { exact: true })
      .isVisible(),
    "Actual public campaign reason missing",
  );
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    "375px session detail overflows with actual public campaign reason",
  );
  const favicon = await page.locator('link[rel="icon"]').getAttribute("href");
  check(favicon === "/favicon.svg", "Bouncer favicon link missing");
  const icon = await page.request.get(new URL(favicon, baseURL).href);
  check(icon.status() === 200 && (await icon.text()).includes("<svg"), "Bouncer favicon unavailable");
  await nav("Investigations").click();
  await page.getByText("No investigations published yet", { exact: true }).waitFor();

  mode = "error";
  await reload();
  await page.getByText("Investigations could not be loaded", { exact: true }).waitFor();
  check(
    (await page.getByText("No investigations published yet", { exact: true }).count()) === 0,
    "Outage rendered as empty success",
  );
  check(
    (await page.getByRole("alert").count()) === 4,
    "Capabilities, usage, evaluation and list errors must stay visible",
  );

  mode = "paginated";
  await reload();
  const pagination = page.getByRole("navigation", { name: "Investigation pages", exact: true });
  const previous = pagination.getByRole("button", { name: "Previous", exact: true });
  const next = pagination.getByRole("button", { name: "Next", exact: true });
  check(await previous.isDisabled(), "First page allows a previous page");
  check(await next.isEnabled(), "Older cases are inaccessible after the first 100");
  holdNextPage = true;
  await next.click();
  await page.getByText("Loading investigations…", { exact: true }).waitFor();
  check(await previous.isDisabled() && await next.isDisabled(), "Page controls allow overlapping fetches");
  holdNextPage = false;
  releasePage();
  await page.getByRole("button", { name: /real-case/ }).waitFor();
  check(await next.isDisabled(), "Short final page allows another page");
  check(await previous.isEnabled(), "Older page cannot return to newer cases");
  await previous.click();
  await page.getByRole("button", { name: /fixture-case/ }).waitFor();
  await next.click();
  await page.getByRole("button", { name: /real-case/ }).waitFor();
  await page.getByRole("combobox", { name: "Source" }).selectOption("real");
  await page.getByText("Page 1", { exact: true }).waitFor();
  await page.getByRole("button", { name: /real-case/ }).waitFor();
  check(await previous.isDisabled() && await next.isDisabled(), "Source change did not reset pagination");
  check(caseRequests.some(({ origin, offset, limit }) => origin === "real" && offset === 0 && limit === 100),
    "Source filter did not query older real cases independently of the current page");
  await page.getByRole("combobox", { name: "Source" }).selectOption("synthetic");
  await page.getByRole("button", { name: /fixture-case/ }).waitFor();
  await next.click();
  await page.getByText("No more investigations", { exact: true }).waitFor();
  check(await previous.isEnabled() && await next.isDisabled(), "Empty final page traps navigation");
  check((await page.getByText("No investigations published yet", { exact: true }).count()) === 0,
    "Empty final page was confused with an unpublished workspace");

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
  await page.getByRole("button", { name: /real-case/ }).waitFor();
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
    (await page
      .getByRole("region", { name: "Assessment history", exact: true })
      .getByText("Experimental", { exact: true })
      .count()) === 2,
    "Experimental provider mode hidden",
  );
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
  await page.getByText("Waiting for traffic…", { exact: false }).waitFor();
  check(writes.length === 0, `Public UI issued write requests: ${writes.join(", ")}`);
  check(errors.length === 0, `Browser errors: ${errors.join(", ")}`);
  return {
    passed: [
      "landing is default with gatehouse and synthetic provenance",
      "landing dashboard CTAs and sidebar logo home routing",
      "explicit dashboard overview route and navigation",
      "PR25 sessions campaigns metrics and overview preserved",
      "PR25 dark-only glass theme preserved",
      "empty state",
      "outage distinction",
      "future modules disabled",
      "source filter",
      "100-case pagination and final page",
      "pagination disabled during fetch",
      "server origin filter resets pagination",
      "empty final page preserves previous navigation",
      "API-backed synthetic benchmark support counts",
      "evaluation confidence intervals and provenance",
      "landing link opens the benchmark and its sources in Metrics",
      "unpublished evaluation distinct from service error",
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
      "375px session detail with actual public campaign reason",
      "Bouncer SVG favicon",
      "GET only",
      "no browser errors",
    ],
    writes,
    errors,
  };
}
