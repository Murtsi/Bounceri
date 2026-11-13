# Contributing

Optimized for a 48-hour event: fast merges, small diffs, no ceremony.

## Workflow

1. `git switch main && git pull --rebase`
2. `git switch -c feat/<short-name>` (or `fix/`, `docs/`, `chore/`)
3. Small commits, Conventional Commits: `feat(api): add claim endpoint`
4. `make check` before pushing
5. Open a PR, one reviewer, merge as soon as it is green

## Rules that keep `main` demo-safe

- `main` always boots. A broken `main` is a P0.
- No force-push to `main`, no direct commits to `main` after the first hour.
- Rebase on `main` before opening the PR to avoid merge spaghetti.
- Every PR: what it does, why, how it was tested, screenshot if UI.
- Feature flags for anything half-finished: ship behind `if (process.env.X)` rather than in a broken state.
- Delete dead branches; no "backup" branches.

## Definition of done

- [ ] Runs locally from a clean checkout (`make setup && make dev`)
- [ ] `make check` passes
- [ ] Happy path tested by hand; failure path at least observed once
- [ ] `.env.example` updated if a new variable was added
- [ ] No secrets, no debug leftovers, no commented-out blocks

## Commit types

`feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore` `revert`

## Review SLA

10 minutes. If nobody reviews, ping the channel; do not self-merge except trivial docs.
