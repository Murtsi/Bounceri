# Person A: local data pipeline handoff

## Status discovered

`a/person-a-integration` is already an ancestor of `main` through PR #5. The checked-in `contracts.py`, six-row synthetic Caddy JSONL fixture, parser/sessionizer, trap list, and seven `tests/a` tests are present. `python -m pytest tests/a -q` passes (7 passed). The challenge README and TODO still say those changes are unmerged; correct those status claims before assigning more work.

The remaining integration gap is concrete: the shared `Session.id` and B's dataset keys are strings, but A's sample parser returns integers. C's `SessionView` and login-event adapter force IDs to integers, using a fallback ID for strings it cannot parse. C's duplicate `network/types.py` also uses `list[int]` for campaign member IDs while `contracts.Campaign` uses `tuple[str, ...]`. B's fixture integration test still expects string IDs and is currently strict-xfail. No database package, schema/migrations, Postgres reader/writer, continuous access-log ingest, demo site, API, frontend, or live traffic sample is present. The root README correctly warns that the application and public deployment are not yet verified.

## Goal

Make the next A-owned increment unblock B's real-data evaluation and C's login/campaign validation without making live Hostinger credentials or deployment a prerequisite.

## Proposed design

### 1. Resolve the shared contract before editing it

Request explicit B/C agreement on one shared contract change; do not silently change another lane's adapter. Preferred outcome, subject to approval by all three owners:

- Keep all Python-boundary session and campaign identifiers as `str`; serialize database numeric primary keys with `str(id)` at the boundary. This matches B's `DatasetRow.session_id` and metrics maps and avoids PostgreSQL implementation details leaking into lane contracts.
- Use immutable `tuple[str, ...]` campaign members consistently with `contracts.Campaign`.
- Keep existing simulator labels that B recognizes: `human`, `human_playwright`, `human_real`, `scraper`, `scanner`, `slow_scanner`, `credential_stuffing`, `brute_force`, and `good_bot`. Add a canonical list and review additions with B/C before they are emitted.
- Include structured login-attempt events in the contract or session view: timestamp, submitted username (not password), success/status, and path. Define whether this is a `Session` field or a derived view, with C, because current session request contracts omit request-body fields while C's stuffing detector expects login events.
- Never persist or log login passwords, request bodies, or arbitrary raw authentication headers. Preserve the existing rule that client IP is the origin address, not untrusted `X-Forwarded-For`.

No contract/interface edits should merge until A, B, and C agree. Record approved interface changes as `BREAKING:` in `CHANGELOG.md` and in `docs/DECISIONS.md` as required by `AGENTS.md`.

### 2. Build a local ingestion vertical slice (A-5/A-6, S3)

Keep the existing deterministic JSONL fixture parser for tests. Add a separate Postgres-backed A-owned module and numbered SQL migrations using the selected `psycopg` 3 stack:

1. Create request, session, and trusted simulator-label tables. Add unique/idempotency constraints and indexes needed for time-window reads. Keep credentials/environment settings out of code and fixtures.
2. Implement Caddy JSON access-log normalization and bounded sessionization with the agreed five-minute idle window. A replayed log line must not duplicate a request or duplicate a label. Preserve `X-Sim-Run` only as internal simulator truth; strip it from normalized public request headers.
3. Ensure a session crossing a batch boundary is not prematurely closed: either retain/update the open session in storage or use an explicit late-arrival/look-back policy that gives B/C stable IDs. Document the boundary for `load_sessions(since)`.
4. Implement `load_sessions(since)` and `load_labels()` with values constructed from `bouncer.contracts`; string IDs must be stable and labels must reference the same IDs. A fresh empty database returns empty lists.
5. Add a worker/CLI entry point that reads new JSONL records, persists them transactionally, handles malformed lines without discarding later valid lines, and can be stopped cleanly. Keep B/C computation as pure function calls and keep DB writes in A's lane.

### 3. Fixtures and acceptance proof

Do not commit real visitor logs. Add a deterministic synthetic integration fixture with browser, scanner, and login-attempt cases and explicit `synthetic` provenance. Add isolated database tests for schema creation, session split at five minutes, boundary-crossing sessions, internal label handling, duplicate replay, `since` filtering, and empty database behavior. Tests must use a local disposable Postgres service or a test-specific isolated database and never use the Hostinger endpoint or paid AI Router.

Run in order: `python -m pytest tests/a -q`, focused Postgres integration tests, B's integration test, C's real-session login/campaign test, then `python -m pytest tests -q`. Do not publish model metrics from the synthetic fixture.

## Work sequence and lane handoffs

| Order | Owner | Deliverable | Unblocks |
|---|---|---|---|
| 0 | A+B+C | Approve ID, campaign member, label-name, and login-event contract | Prevents type churn and fallback-ID corruption |
| 1 | A | Correct README/TODO: A starter is merged; list actual local blockers; move A-1 to review/accepted only where accurate | Team starts from one source of truth |
| 2 | A | Stable string-ID parser/contract after approval; remove or make passing B's strict-xfail integration test with B's owner | B dataset consumes labels; C consumes same session IDs |
| 3 | A | Migrations + idempotent JSONL ingest + Postgres session/label loaders + worker | B can run `bouncer.eval.run --source db`; C can evaluate login/campaign features against real requests |
| 4 | A+B+C | Execute lane-owned integration tests on the synthetic DB fixture | Confirms S3/S10 handoff without claiming measured accuracy |
| 5 | A | Demo site/Caddy logging/simulator traffic and a privacy-reviewed redacted sample | Replaces synthetic-only integration for B-3/B-7 and C-4 |
| 6 | A | API/dashboard and public deploy after local end-to-end path works | C-8 and demo integration |

## Alternatives considered

1. **Deploy-first:** start public Hostinger/Caddy immediately. Not recommended because deployment is currently unverified and does not itself resolve contract IDs or create the local S3 loader needed by B/C.
2. **Generate more fixtures only:** increases example volume but still leaves B/C blocked on database access and real-login data.
3. **Contract plus local ingestion first (recommended):** ships a verifiable, credential-free dependency for both lanes; public hosting can proceed separately after access is confirmed.

## Out of scope for this first slice

Public VPS/domain changes, Router-key setup, React dashboard, full production API, hidden attack, and real visitor-data retention. The deployment blocker should be updated only from actual operator confirmation; do not claim the domain is live just because infrastructure exists.

## Open review questions for B/C

1. Confirm `Session.id`, `SessionLabel.session_id`, and `Campaign.session_ids` are strings at shared Python boundaries, with database integer keys stringified by A.
2. Confirm the canonical simulator label spellings listed above (or propose exact alternatives).
3. Decide a minimal structured login-event representation that lets C count failed/low-and-slow attempts but stores no password or body.
4. Confirm how A's worker finalizes/updates five-minute sessions while keeping IDs stable for repeated loads.

Implementation is intentionally gated on these contract answers. This document is a proposal, not an approved S2/S10 contract.
