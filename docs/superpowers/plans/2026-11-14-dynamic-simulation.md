# Variable private traffic implementation plan

> For agentic workers: use the subagent-driven-development workflow for bounded,
> independently owned tasks; coordinate runtime and generator contracts before edits.

**Goal:** Replace repeated live waves with varied, replayable private HTTP episodes.

**Architecture:** A pure generator creates immutable episode plans using existing
`Actor`/`Step` contracts. A bounded player executes actual requests. The Hostinger
runtime supplies entropy, private replay persistence and continuous scheduling.

**Tech stack:** Existing Python standard library, Docker Compose, Caddy and pytest.
No new provider, package dependency, frontend redesign or paid inference is required.

## Task 1 — generator (isolated agent)

- [x] Write failing tests in `tests/a/test_dynamic_simulation.py` for deterministic
  replay, cross-seed diversity, caps, hard negatives and label isolation.
- [x] Implement pure `tools/sim/dynamic.py`: `Episode`, `generate_episode`, bounded
  behavior composition using existing `Actor`/`Step`, opaque identities and mixed UA pools.
- [x] Run focused tests/lint; return an isolated commit for coordinator integration.

## Task 2 — player and runtime (coordinator)

- [x] Write failing real-local-HTTP tests for pacing, no redirects, deadlines/stops
  and overload backoff in `tests/a/test_dynamic_player.py`.
- [x] Implement `tools/sim/player.py` with bounded concurrency, common rate limiter,
  explicit socket timeout and stop-aware waits. Target only the private gateway.
- [x] Update `tools/hostinger/runtime.py` to use fresh seeded episodes, continuously
  schedule them and rotate private replay metadata without resetting model budgets.
- [x] Add a simulator-only writable volume and explicit simulator environment settings
  in `tools/hostinger/package.py` and `.env.example`; keep detector data read-only there.

## Task 3 — review and live verification

- [x] Independently audit generator diversity, label leakage, target/rate bounds and
  shutdown behavior; fix grounded failures and retain regression tests.
- [x] Update changelog, decision log and deployment docs with actual limits/replay steps.
- [x] Run full Python/lint/hygiene and Compose checks; integrate current origin/main
  without replacing the owner's dashboard. Push the tested main revision first.
- [x] Preserve private keys/config, all named data volumes and current inference ledger.
  Deploy through existing authenticated Hostinger workflow; never reset data.
- [x] Observe two materially different completed VPS episodes, actual request counts,
  detector-store changes, successful public health and unchanged review spending limits.

## Observed verification

Code revision `511238f`: 464 Python tests passed; scoped lint, repository hygiene and Compose validation passed. Independent review exercised 1,400 generated plans and corrected cooldown, control-character and identity-history boundary bugs. Local Docker playback completed 111, 137 and 143 requests with zero network errors.

The live VPS completed 17 actors / 82 requests, then 19 actors / 49 requests, both with zero errors/drops. Private CLI replay rebuilt the first recorded plan with a matching fingerprint. Both public domains returned HTTP 200; all seven runtime services remained running. The inference ledger stayed at 56 executions / 88 requests / $0.063036 settled / $0.03 held, with no reset or budget increase.

The separate local `a/core-and-modules` branch and its work-in-progress files were left untouched. The updated simulator and all runtime changes were pushed to main before deployment. Procedural diversity is not a claim of improved detection accuracy.
