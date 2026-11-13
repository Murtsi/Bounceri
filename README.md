# Bounceri

Your website has visitors. Bounceri helps you spot trouble.

[![CI](https://github.com/Murtsi/Bounceri/actions/workflows/ci.yml/badge.svg)](https://github.com/Murtsi/Bounceri/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Bounceri is a Junction 2026 prototype for **Hostinger — Decode the Noise**. It analyses web traffic at session level and returns a verdict with the evidence behind it. When the scoring rules cannot decide, they return `uncertain`.

## Current state

The repository contains session features and detection rules, temporal evaluation and threshold selection, IP intelligence, campaign detection, and optional explanations through Hostinger AI Router. Rule-based explanations work without an API key. The A-lane integration draft adds shared type proposals, a sample-log parser, synthetic traffic fixtures and a trap-path list.

The complete application is still under development. A live ingestion pipeline, database loaders, API and dashboard are not implemented here. The scoring rules do not yet classify visitors as human. The committed metrics files are stubs, not measured accuracy results. Shared contract types still need team agreement before application integration.

Hostinger infrastructure exists for `bounceri.tech`, but this repository does not establish a working public application there. The local Compose file starts development database tools only.

## Run the tests

Install Git and [uv](https://docs.astral.sh/uv/), then run:

```sh
git clone https://github.com/Murtsi/Bounceri.git
cd Bounceri
uv run --no-project --python 3.12 --with pytest pytest tests -q
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

PostgreSQL listens on `127.0.0.1:5432`; Adminer is at `http://127.0.0.1:8080`. The example credentials are public development defaults. Set unique credentials before deployment. This setup uses PostgreSQL 16; TimescaleDB is planned in the architecture.

Keep credentials in the ignored `.env` file. Never commit raw visitor logs, database exports, or real request headers. The log fixture in `samples/` is synthetic and uses documentation IP addresses.

## Repository map

| Path | Contents |
|---|---|
| `src/bouncer/session/` | Session features and scoring rules |
| `src/bouncer/eval/` | Dataset assembly, evaluation and metrics |
| `src/bouncer/network/` | IP intelligence, campaigns and graph export |
| `src/bouncer/explain/` | Grounded explanations and fallback text |
| `src/bouncer/ingest/`, `samples/` | Sample-log parsing and synthetic fixtures |
| `deploy/traps.txt` | Proposed trap paths; no deployed routes yet |
| `tests/` | Tests for each team lane |
| `models/metrics.json` | Metrics schema placeholder |

See the [project status](Challenges/Hostinger-Decode-the-Noise/README.md), [architecture](Challenges/Hostinger-Decode-the-Noise/ARCHITECTURE.md), and [decision log](docs/DECISIONS.md). Some planning documents are in Finnish.

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before changing the project. Team ownership and contract changes follow the rules there. Record changes in [CHANGELOG.md](CHANGELOG.md).

For vulnerability reports, see [SECURITY.md](SECURITY.md). Bounceri is an advisory prototype; automatic production blocking is outside its scope.

## License

[MIT](LICENSE).
