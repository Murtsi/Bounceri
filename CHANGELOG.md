# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Hackathon scaffold: docs, CI, docker-compose, pre-commit hook, devcontainer.
- [X] `Challenges/`-kansio: idea-tason suunnitelmat Hostinger (Decode the Noise) ja Valio Aimo (Trusted Trade Agents) -haasteille.
- [X] Hostinger-suunnitelma: kolme kaistaa ilman päällekkäisyyksiä — A alusta + hyökkääjä, B session tunnistus + arviointi, C verkosto- ja kampanjatunnistus + selitykset; sopimukset S1–S11.
- [X] Stack-päätökset 004–013 (`docs/DECISIONS.md`): Python + FastAPI, React + Vite + Tailwind + shadcn/ui, PostgreSQL + TimescaleDB, Hostinger AI Router, Docker Compose + Caddy, Hostinger Connector / MCP.
- [X] `AGENTS.md` (+ `CLAUDE.md`, joka viittaa siihen): yhteiset säännöt tiimille ja AI-agenteille; jokainen muutos kirjataan `CHANGELOG.md`:hen.
- [X] CI-tarkistus `scripts/check-changelog.sh`: push tai PR ilman `CHANGELOG.md`-merkintää hylätään (poikkeus: `[skip changelog]`); ajetaan myös `make check`:ssa.

### Changed
- [X] Hostinger-suunnitelman frontend Jinja + HTMX → React (`frontend/`), tietokanta → PostgreSQL + TimescaleDB.

### Fixed
