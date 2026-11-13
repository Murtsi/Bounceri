# Junction 2026 — <Project Name>

> One-sentence pitch: what it does, for whom, and why it matters.

[![CI](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Hackathon-ready repository scaffold, **deliberately stack-agnostic**: put your code in `src/`, wire the four commands at the top of the `Makefile`, and everything around it (CI, git hooks, containers, docs, demo and submission checklists) already works.

## Quickstart

Prereqs: Git, Docker Desktop/Engine, and on Linux/macOS/WSL `make`. On plain Windows (no `make`) use `scripts\win.ps1`, a thin wrapper around the same shell scripts and Compose commands:

```bash
# Linux / macOS / WSL / devcontainer
bash scripts/setup.sh     # creates .env from .env.example, inits git if needed
make hooks                # installs the pre-commit hook
make up                   # Postgres + Adminer in the background
make dev                  # starts your app (set DEV_CMD first)
```

```powershell
# Windows without make
powershell -ExecutionPolicy Bypass -File scripts\win.ps1 setup
powershell -ExecutionPolicy Bypass -File scripts\win.ps1 up
```

Either path calls the same scripts; CI runs `bash scripts/check.sh` directly.

App conventions live in [`CONTRIBUTING.md`](CONTRIBUTING.md); the demo-day plan in [`docs/DEMO.md`](docs/DEMO.md).

## Repository layout

```
.
├── .devcontainer/          # one-click dev environment (VS Code / Codespaces)
├── .github/                # CI, PR template, issue forms
├── .vscode/                # editor settings + recommended extensions
├── docs/                   # idea, architecture, API, pitch, demo, judging, submission
├── scripts/                # check.sh, setup.sh, install-hooks.sh, git hook
├── src/                    # YOUR CODE GOES HERE
├── tests/                  # YOUR TESTS GO HERE
├── .editorconfig
├── .env.example            # committed; .env never is
├── .gitattributes
├── .gitignore
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── docker-compose.yml      # Postgres + Adminer (Redis ready, commented out)
├── LICENSE
├── Makefile
└── README.md
```

## Commands

| Command | What it does |
|---|---|
| `make help` | List targets |
| `make setup` | Create `.env`, init git, print next steps |
| `make hooks` | Install the pre-commit hook |
| `make check` | Repo hygiene: conflicts, whitespace, JSON/YAML, secrets |
| `make dev` / `test` / `lint` / `build` | Your stack — set the `*_CMD` variables in the Makefile |
| `make up` / `down` / `logs` | docker-compose lifecycle |
| `make psql` | Shell into Postgres |
| `make reset-db` | Drop and recreate the database volume |
| `make clean` | Remove common build artifacts |

## Configuration

Copy `.env.example` → `.env` and fill in what you need. `.env` is git-ignored and the pre-commit hook refuses to commit it. Never put real keys in the repo; rotate anything you paste into a demo.

## Documentation

| File | Use it for |
|---|---|
| [docs/IDEA.md](docs/IDEA.md) | Problem, user, scope, non-goals, stretch goals |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data model, runtime diagram |
| [docs/API.md](docs/API.md) | Endpoint contract and error format |
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADR log: why we chose what we chose |
| [docs/TEAM.md](docs/TEAM.md) | Roles, comms, standup, demo owner |
| [docs/PITCH.md](docs/PITCH.md) | 3-minute pitch script and Q&A bank |
| [docs/DEMO.md](docs/DEMO.md) | Demo runbook and failure plan |
| [docs/JUDGING.md](docs/JUDGING.md) | Judging criteria mapped to evidence |
| [docs/SUBMISSION.md](docs/SUBMISSION.md) | Deadline checklist |

## Team norms

- Trunk-based: short-lived branches, PRs merged within the hour, one reviewer is enough.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
- The `main` branch always runs. If it doesn't, fixing it outranks your feature.
- Whoever breaks the demo build owns the fix — no blame, just a fast revert.

## License

MIT — see [LICENSE](LICENSE).
