# Core hardening and modules implementation plan

Goal: fix the mandatory audit findings and complete every requirement in modules plan.md, without claiming unavailable evaluation or deployment evidence.
Architecture: retain current FastAPI/React investigation platform; repair core contracts, establish versioned durable storage, then add independent provenance/social/text vertical slices. Paid inference and enforcement remain separately gated.
Tech stack: existing Python/SQLAlchemy/PostgreSQL and React, pinned C2PA SDK for media verification.

The owner approved execution of modules plan.md and the audit fixes. Work is on a/core-and-modules in the existing checkout; preserve the owner's untracked plan. Use Ponytail and regression tests. Do not push or deploy implicitly.

- [x] Critical fixes: tolerant parsing, JSON-compatible serialization, DNS unknown/IPv6, stable session identity through retention/restart, bounded and Unicode-safe login.
- [ ] Remaining reliability: bounded case list, interrupted review reconciliation without inference retry, browser suite in CI.
- [ ] Phase 0: baseline verification, reconcile runtime/challenge docs, docs/MODULES.md.
- [ ] Phase 1.1: additive migrations for existing/new tables, populated upgrade and fresh/restart/concurrent tests.
- [ ] Phase 1.2: SQL request/session/label repository, atomic source checkpoints/event identity, readers/cutover/backfill/rollback and retention.
- [ ] Phase 1.3–4: bounded cached live network evidence and complete scoped campaign/rule provenance.
- [ ] Phase 1.5: authenticated private log import with redaction/limits/reports.
- [ ] Phase 1.6: detailed health, pagination, backup/restore, measured resources, deployment smoke.
- [ ] Phase 1.7–8: consent records, real data collection, whole-actor/run/time holdouts, independent hidden attack and separate evaluation artifacts. External participants/independent author remain required; never fabricate their evidence.
- [ ] Phase 2: private bounded media import/storage, locked offline/network-restricted C2PA verification and reproducible trust context, licensed fixtures/evaluator, authenticated case creation and result UI.
- [ ] Phase 3: private SocialEvent import, bounded windowed features/null comparison, typed coordination findings, permitted data/holdout evaluator, API and graph/table UI.
- [ ] Phase 4: private text import, explicit Unicode span convention/taxonomy/languages, deterministic baseline, permitted SemEval adapters/scorers/holdouts, API and highlighted UI. Dataset-use clarification remains an external gate.
- [ ] Phase 5: independent capability prerequisites, gated supported review packets, CI/resource/migration checks, docs and final clean-checkout/demo/deployment verification.

For each checkbox: add a focused regression/acceptance test, observe failure, implement minimum complete behavior, run relevant tests/lint, record decisions/changelog and evidence here. Mark items only when their full requirement is proven. Run full backend/frontend/repository/Compose checks after each phase. Existing baseline at23e6c7a:430pytest, Ruff,6frontend tests/build and Compose configuration passed during audit; revalidate before edits.

## Evidence: critical fixes

All new regression tests were observed failing before the corresponding implementation. Backend suite increased from 430 to 456 tests, verified passing with Ruff before commit. The independent review found quiet-window and visible-old-session identity loss; both now have regression tests and independent persisted identity state. DNS and login changes were independently implemented and reviewed; no paid calls or deployment occurred. Production Docker build, six frontend tests, TypeScript and Vite build passed; full demo acceptance remains required. Existing user modules plan is untracked and unchanged.

Isolated Docker/Caddy smoke: production image builds; 139 signed synthetic requests; scanner, stuffing campaign, human false-alarm, evidence and dashboard/metrics gates passed. Fake-crawler gate remained uncertain because DNS verification was unavailable. This is an outstanding live DNS acceptance gate, not a passing six-gate demo. Containers/network used isolated scratch data and were removed. Repository hygiene passed; shellcheck unavailable.

Case-list pagination is in progress (test first, bounded limit/offset and 3 SQL queries). UI navigation and API pagination regressions remain to finish before marking that task done. Versioned schema runner is in progress independently. Phase 0 docs are reconciled but the full demo/DNS gate is still open.
