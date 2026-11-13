# Todo — Junction kanban

**WIP limit: 2 cards in *In Progress*.** More than that at a hackathon means nothing is demoable.
Sizes: S ≈ 15 min, M ≈ 1 h, L ≈ half a day. `P0` = demo dies without it, `P1` = judges notice, `P2` = only if idle.

Move cards by moving the row. Keep the *Blocked* reason on the card, not in chat.

---

## Pre-event (T-7 → T-0)

Do these before the clock starts; they cost ~3 h and buy back a full day.

| ID | Card | Size | Owner | Notes |
|---|---|---|---|---|
| PRE-1 | Fill `README.md` pitch + real project name | S | | One-liner first, then the rest |
| PRE-2 | Fill `docs/IDEA.md`: problem, user, non-goals | M | | Non-goals are what stops scope creep |
| PRE-3 | Pick stack, set `DEV_CMD/TEST_CMD/LINT_CMD/BUILD_CMD` in `Makefile` | S | | Do not scaffold app code yet |
| PRE-4 | `make setup && make hooks && make up` on every teammate's machine | S | | Fix laptop issues now, not at 02:00 |
| PRE-5 | Enable the commented `stack` job in `.github/workflows/ci.yml` | S | | Needs PRE-3 |
| PRE-6 | Create GitHub repo, push `main`, confirm CI badge is green | S | | Public + MIT license |
| PRE-7 | Fill `docs/TEAM.md` roles and post the chat channel | S | | Every file gets an owner |
| PRE-8 | Read the track briefs, pick 2 tracks, write them in `docs/JUDGING.md` | M | | Track fit is free points |
| PRE-9 | Draft 6-slide skeleton in `docs/PITCH.md` | M | | Empty slides are fine |
| PRE-10 | Prepare demo hardware: laptop, phone hotspot, chargers, adapters | S | | Shared checklist exists in `docs/DEMO.md` |

---

## Backlog

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| T-01 | Write the demo-path user story ("as a user I open X and see Y") | P0 | S | | Becomes the E2E test |
| T-02 | Database schema v1 + migration | P0 | M | | 3–5 tables max |
| T-03 | Seed script producing the exact demo state | P0 | M | | Idempotent: safe to re-run |
| T-04 | API contract in `docs/API.md` for the 3 endpoints the demo touches | P0 | S | | Contract before code |
| T-05 | Happy path end-to-end: UI → API → DB → UI | P0 | L | | This is the demo |
| T-06 | Auth (or a hard-coded demo session, flagged as such) | P1 | M | | Skip real auth if it eats a day |
| T-07 | Error + empty states on the demo screens | P1 | M | | Judges click empty inputs |
| T-08 | External API integration behind one provider module | P1 | L | | Mock the boundary first |
| T-09 | Loading states / skeletons on slow calls | P2 | S | | Perceived speed is design points |
| T-10 | Landing page with one-liner + screenshot | P2 | S | | Source for the pitch's first slide |
| T-11 | Deploy to a public URL (Vercel/Fly/Render) | P1 | M | | Judges may try it later |
| T-12 | Health endpoint + request logging with ids | P2 | S | | Debugging aid on demo day |
| T-13 | Record 90-second backup demo video | P0 | S | | Do it while the flow works, not at 04:00 |
| T-14 | Screenshots for submission (hero, flow, result) | P1 | S | | 3–5 images |
| T-15 | Update `CHANGELOG.md` and tag `demo` | P1 | S | | Submission checklist item |
| T-16 | Write Q&A answers in `docs/PITCH.md` from a hostile-judge angle | P1 | M | | "How is this not a wrapper?" |

---

## Ready (groomed, start within the next 24 h)

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| T-04 | API contract in `docs/API.md` for the 3 demo endpoints | P0 | S | | Unblocks T-02/T-05 |
| T-02 | Database schema v1 + migration | P0 | M | | Blocks T-03 |
| T-01 | Demo-path user story | P0 | S | | Blocks T-05 acceptance |

---

## In Progress (max 2)

| ID | Card | Pri | Owner | Started | Blocker |
|---|---|---|---|---|---|
| T-05 | Happy path end-to-end | P0 | | | |

---

## Review / Verify

Definition of done for any card: runs from a clean checkout, `make check` passes, happy path observed by hand,
`.env.example` updated if a variable was added.

| ID | Card | Reviewer | Evidence |
|---|---|---|---|
| | | | |

---

## Done

| ID | Card | When | Commit |
|---|---|---|---|
| PRE-0 | Hackathon scaffold: docs, CI, compose, hooks, devcontainer | 2026-11-13 | `c8a7ed8` |

---

## Cut line

If Sunday morning arrives, ship in this order and stop:

1. T-05 demo path + T-03 seed data + T-08 integration
2. T-13 backup video + T-14 screenshots + T-15 tag
3. T-07 error states + T-11 deploy
4. Everything else is a stretch goal; say so in the pitch.

## Blocked

| ID | Card | Blocked on | Since | Owner |
|---|---|---|---|---|
| | | | | |
