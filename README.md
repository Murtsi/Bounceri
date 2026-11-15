# Bounceri

Your website has visitors. Bounceri helps you spot trouble.

[![CI](https://github.com/Murtsi/Bounceri/actions/workflows/ci.yml/badge.svg)](https://github.com/Murtsi/Bounceri/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Bounceri is a Junction 2026 prototype for **Hostinger — Decode the Noise**. It analyses web traffic at session level and returns a verdict with the evidence behind it. When the scoring rules cannot decide, they return `uncertain`.

Live dashboard: **[bounceri.tech](https://bounceri.tech)**. The traffic demo is explicitly synthetic; its Docker simulator, detector, database and dashboard run on Hostinger.

## Current state

The repository contains session features and detection rules, temporal evaluation, IP intelligence, campaign detection, persistent investigations and a two-role Featherless review pipeline. Local detection works without an API key. Model review requires explicit verified settings and a shared spending reservation; it records advisory assessments separately from evidence.

**The MVP runs end to end locally** ([docs/MVP.md](docs/MVP.md)): a demo shop behind real Caddy, signed traffic simulators, a live worker (Caddy log → sessions → IP intelligence and campaigns → verdict → explanation), a read-only API and a React dashboard. `make demo` starts it and checks all six acceptance criteria automatically. All demo traffic is synthetic, so `models/metrics.json` remains a stub: no measured numbers are claimed until labelled non-synthetic traffic exists.

The Hostinger stack adds PostgreSQL-backed investigations, immutable redacted evidence, a review-job/budget ledger and reversible actor-scoped enforcement. The session worker retains its JSON compatibility store. The existing dashboard remains the default; Investigations is an added tab. See [Hostinger deployment, cost controls and overnight evaluation](docs/HOSTINGER_LIVE.md). Social swarms, text techniques and provenance are clearly labelled future modules. Session/campaign IDs remain strings at the Python boundary.

## Run the MVP demo

Needs Docker (running), [uv](https://docs.astral.sh/uv/) and Make:

```sh
make demo        # build, start Caddy + site + worker + API, run simulators, check criteria 1–6
make demo-logs   # follow worker and API
make demo-down   # stop
```

Dashboard: http://127.0.0.1:8001 · demo shop (monitored through Caddy): http://127.0.0.1:8080. The dashboard is served outside Caddy on purpose, so its own traffic never enters the analysed log. Ports can be changed with `API_PORT` and `DEMO_PORT`.

The local Caddyfile trusts `X-Forwarded-For` from private networks so the simulators can present many client IPs from one machine (decision 050). Production uses `deploy/Caddyfile`, which trusts no proxies. Set a real `SIM_RUN_SECRET` on any shared deployment (decision 046).

## Run the tests

Install Git and [uv](https://docs.astral.sh/uv/), then run:

```sh
git clone https://github.com/Murtsi/Bounceri.git
cd Bounceri
uv run pytest -q      # or: make test
```

The test command works in PowerShell as well as a Unix shell. It does not require database containers or an AI Router key.

With Bash installed, run repository checks with:

```sh
bash scripts/check.sh
bash scripts/check-changelog.sh
```

`make check` runs both checks when Make is available. These are repository checks; run pytest separately.

## Optional local database

Copy `.env.example` to `.env` and run:

```sh
docker compose up -d --wait
```

PostgreSQL listens on `127.0.0.1:5432`; Adminer is at `http://127.0.0.1:8080` (the same port as the demo's Caddy: run one at a time or set `DEMO_PORT`). The example credentials are public development defaults. Set unique credentials before deployment. This setup uses PostgreSQL 16; TimescaleDB is planned in the architecture.

Keep credentials in the ignored `.env` file. Never commit raw visitor logs, database exports, or real request headers. The log fixture in `samples/` is synthetic and uses documentation IP addresses.

## Repository map

| Path | Contents |
|---|---|
| `src/bouncer/session/` | Session features and scoring rules |
| `src/bouncer/eval/` | Dataset assembly, evaluation and metrics |
| `src/bouncer/network/` | IP intelligence, campaigns and graph export |
| `src/bouncer/explain/` | Grounded explanations and fallback text |
| `src/bouncer/ingest/`, `samples/` | Caddy log parsing, signed simulator labels, live worker, synthetic fixtures |
| `src/bouncer/site/` | Demo shop (pages, login, hidden trap link) |
| `src/bouncer/api/`, `frontend/` | Read-only API and React dashboard |
| `tools/sim/` | Traffic simulators and the MVP acceptance check |
| `deploy/` | Docker Compose, Caddyfiles, trap paths |
| `tests/` | Tests for each team lane |
| `models/metrics.json` | Metrics schema placeholder |

See the [project status](Challenges/Hostinger-Decode-the-Noise/README.md), [architecture](Challenges/Hostinger-Decode-the-Noise/ARCHITECTURE.md), and [decision log](docs/DECISIONS.md). Some planning documents are in Finnish.

The [implemented runtime](docs/RUNTIME-PLAN.md) uses Featherless for both bounded evidence questions and final advisory review. The asynchronous orchestrator and persistent shared budget ledger are implemented; paid review remains disabled unless its model, provider, pricing and limit checks pass. Native Microsoft Decision is unavailable until separately verified. The [recorded live synthetic validation](docs/LIVE_AI_VALIDATION.md) established contract compatibility, with every accepted final review returning `uncertain`; it did not establish better detection quality.

See the [module evidence matrix](docs/MODULES.md) for supported inputs, labels, limitations and capability states. Core hardening comes before the three planned modules: Trust the Source, Spot the Swarm (social coordination), and Name the Technique (text). Existing HTTP campaigns belong to Clean the Traffic. The [synthetic benchmark](docs/EVALUATION.md) is separate from production metrics; consented real-human evaluation and a genuinely withheld attack remain unavailable.

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before changing the project. Team ownership and contract changes follow the rules there. Record changes in [CHANGELOG.md](CHANGELOG.md).

For vulnerability reports, see [SECURITY.md](SECURITY.md). Bounceri is an advisory prototype; automatic production blocking is outside its scope.

## License

[MIT](LICENSE).

## Durable traffic cutover

The SQL traffic path now stores normalized events, sessions and labels with atomic source checkpoints. It is selected explicitly; the JSON compatibility path remains the default until its stopped writer is archived and verified. See [traffic storage, cutover, retention and fresh rollback](docs/TRAFFIC_STORAGE.md). Local PostgreSQL and packaged-runtime checks establish storage behavior, not real-world detector accuracy or live Hostinger deployment.


Private native log uploads are now available through the authenticated [traffic import API](docs/TRAFFIC_IMPORTS.md). They preserve missing-data/source context, keep archives and cases private by default, and never create gold labels or queue paid reviews automatically.

See [core operations](docs/OPERATIONS.md) for read-only health probes, private backup/restore, explicit source deletion, log rotation and measured worker bounds.

Private [consented collection and session-review records](docs/HUMAN_STUDY.md) keep participant consent separate from observed manual/automated behavior and simulator labels. Enrollment alone does not supply human ground truth. The [frozen native evaluation workflow](docs/FROZEN_EVALUATION.md) reserves complete groups, freezes separate fit/calibration/test contexts, and records one-shot private reports. Actual independent evidence and production publication remain separate gates.
