# Core hardening and modules implementation plan

Goal: fix the mandatory audit findings and complete every requirement in modules plan.md, without claiming unavailable evaluation or deployment evidence.
Architecture: retain current FastAPI/React investigation platform; repair core contracts, establish versioned durable storage, then add independent provenance/social/text vertical slices. Paid inference and enforcement remain separately gated.
Tech stack: existing Python/SQLAlchemy/PostgreSQL and React, pinned C2PA SDK for media verification.

The owner approved execution of modules plan.md and the audit fixes. Work is on a/core-and-modules in the existing checkout; preserve the owner's untracked plan. Use Ponytail and regression tests. Do not push or deploy implicitly.

- [x] Critical fixes: tolerant parsing, JSON-compatible serialization, DNS unknown/IPv6, stable session identity through retention/restart, bounded and Unicode-safe login.
- [x] Remaining reliability: bounded case list, interrupted review reconciliation without inference retry, browser suite in CI.
- [ ] Phase 0: baseline verification, reconcile runtime/challenge docs, docs/MODULES.md.
- [x] Phase 1.1: additive migrations for existing/new tables, populated upgrade and fresh/restart/concurrent tests.
- [x] Phase 1.2: SQL request/session/label repository, atomic source checkpoints/event identity, readers/cutover/backfill/rollback and retention.
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

Historical note, superseded by the verified increments below: case-list pagination was in progress (test first, bounded limit/offset and 3 SQL queries). UI navigation and API pagination regressions remain to finish before marking that task done. Versioned schema runner is in progress independently. Phase 0 docs are reconciled but the full demo/DNS gate is still open.

## Evidence: Phase 1.1 and reliability increment

Twenty isolated real PostgreSQL migration tests pass: fresh/adopted populated stores, concurrent startup/writers, transactional rollback, version/checksum/schema drift, line-ending portability, future additive-column upgrade, production create_all exclusion and PostgreSQL origin-query privacy. SQL002 is included in wheels and Hostinger capsules; existing001 is unchanged. Independent read-only review found no further defect. SQLite remains explicitly local/test only.

Case paging and interrupted-review recovery are implemented with test-first evidence. Integrated verification: 492 Python tests passed with PostgreSQL enabled; Ruff, 7 frontend tests, TypeScript/Vite build, repository hygiene, root/demo Compose configuration passed. Independent final review approved recovery ownership/accounting and pagination privacy. Browser agent verified36 checks including desktop/mobile paging, held fetches, source reset, empty final page, no writes/page errors. Main traffic SQL writer/checkpoints/cutover, core import/operations/evaluation and all3 new modules remain incomplete. Browser suite still needs a repeatable CI runner; migration tests are wired into CI.

## Evidence: repeatable browser CI

Pinned dev-only Playwright with native Node test/Vite API runner. Root reran7 unit tests, TypeScript/Vite build and36Chromiumchecks; exactNode22.18.0 was independently verified. Failure probes exitnonzero and closebrowser/server. CI frontendjob nowinstallsexplicitChromiumdeps andrunssuite; actualGitHubjobnotyetexecuted. Phase 1.2SQL/history/checkpointintegration remainsinprogress andisnotmarkedcomplete.

## Evidence: Phase 1.2 locally verified

Normalized traffic, exact source-byte identities, revision CAS, full fresh history before read-window eviction, atomic age retention, immutable origins/archives, private checkpoint/session/truth state, and consistent multi-query reads are implemented. Runtime/API SQL selection is explicit; JSON stays the compatibility default. Backfill verifies opaque IDs/native data and freezes an archive, and rollback exports current source state without overwriting the original. The SQL startup guard also protects empty visible JSON windows that still own source coordinates.

Review reproduced and fixed late/bridging ownership, stale gold labels, origin flips, dropped overflow history, stat/open/copytruncate/gzip/retained-rotation races, archive inode reuse and mixed-batch read snapshots. Final full checks:616 Python tests with PostgreSQL enabled and Ruff passed;7frontendunit+build+36 browserchecks passed. Packaged SQL Docker stack:21 sessions/235 synthetic requests, checkpoint revision 8, no primaryJSON, no paidrequests; resources cleaned. Wheels and SQL assets build; repository hygiene and both Compose configs pass. Independent final review approved after focused regressions.

Next:Phase 1.3–4 bounded live network provenance and complete scoped evidence, followed by imports, remaining operations/study/evaluation and the three modules. Live Hostinger cutover is NOT performed. Archive/backup deletion lifecycle, external real-human/hidden evidence and liveDNS/final release gates remain open in their corresponding later tasks. Do not mark the overall goal complete from this storage increment.
