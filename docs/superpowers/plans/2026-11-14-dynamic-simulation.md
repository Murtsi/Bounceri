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

- [ ] Write failing tests in `tests/a/test_dynamic_simulation.py` for deterministic
  replay, cross-seed diversity, caps, hard negatives and label isolation.
- [ ] Implement pure `tools/sim/dynamic.py`: `Episode`, `generate_episode`, bounded
  behavior composition using existing `Actor`/`Step`, opaque identities and mixed UA pools.
- [ ] Run focused tests/lint; return an isolated commit for coordinator integration.

## Task 2 — player and runtime (coordinator)

- [ ] Write failing real-local-HTTP tests for pacing, no redirects, deadlines/stops
  and overload backoff in `tests/a/test_dynamic_player.py`.
- [ ] Implement `tools/sim/player.py` with bounded concurrency, common rate limiter,
  explicit socket timeout and stop-aware waits. Target only the private gateway.
- [ ] Update `tools/hostinger/runtime.py` to use fresh seeded episodes, continuously
  schedule them and rotate private replay metadata without resetting model budgets.
- [ ] Add a simulator-only writable volume and explicit simulator environment settings
  in `tools/hostinger/package.py` and `.env.example`; keep detector data read-only there.

## Task 3 — review and live verification

- [ ] Independently audit generator diversity, label leakage, target/rate bounds and
  shutdown behavior; fix grounded failures and retain regression tests.
- [ ] Update changelog, decision log and deployment docs with actual limits/replay steps.
- [ ] Run full Python/lint/hygiene and Compose checks; integrate current origin/main
  without replacing the owner's dashboard. Push the tested main revision first.
- [ ] Preserve private keys/config, all named data volumes and current inference ledger.
  Deploy through existing authenticated Hostinger workflow; never reset data.
- [ ] Observe two materially different completed VPS episodes, actual request counts,
  detector-store changes, successful public health and unchanged review spending limits.
