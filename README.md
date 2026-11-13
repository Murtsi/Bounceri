# Junction 2026 — Bouncer

> Bouncer kertoo sivuston omistajalle, kuka sivulla oikeasti käy — ihminen, hyvä botti vai hyökkääjä — ja **miksi**, ja näyttää rehellisesti, kuinka usein se on väärässä.

[![CI](https://github.com/Murtsi/Bounceri/actions/workflows/ci.yml/badge.svg)](https://github.com/Murtsi/Bounceri/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Haaste: **Hostinger — Decode the Noise**. Suunnitelma, kaistat ja tilanne: [`Challenges/Hostinger-Decode-the-Noise/`](Challenges/Hostinger-Decode-the-Noise/).

## Mistä aloittaa

| Tiedosto | Mitä |
|---|---|
| [AGENTS.md](AGENTS.md) | Säännöt kaikille (myös AI-agenteille): kaistat, työnkulku, changelog, rehellisyyssäännöt |
| [Challenges/Hostinger-Decode-the-Noise/README.md](Challenges/Hostinger-Decode-the-Noise/README.md) | Missä mennään |
| [TEAM.md](Challenges/Hostinger-Decode-the-Noise/TEAM.md) | Kuka tekee mitä, sopimukset S1–S11 |
| [TODO.md](Challenges/Hostinger-Decode-the-Noise/TODO.md) | Kortit kaistoittain |
| [IDEA.md](Challenges/Hostinger-Decode-the-Noise/IDEA.md) · [ARCHITECTURE.md](Challenges/Hostinger-Decode-the-Noise/ARCHITECTURE.md) | Idea ja rakenne |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Päätösloki |
| [CHANGELOG.md](CHANGELOG.md) | Jokainen muutos |
| [docs/PITCH.md](docs/PITCH.md) · [DEMO.md](docs/DEMO.md) · [JUDGING.md](docs/JUDGING.md) · [SUBMISSION.md](docs/SUBMISSION.md) | Pohjat loppuun (T+38 →) |

## Rakenne

```
src/bouncer/session/   B: session piirteet, säännöt, score()
src/bouncer/eval/      B: datasetti, arviointi, metrics.json
models/                B: metrics.json + mallit
tests/b/               B: testit
src/bouncer/network/   C: ip_intel, kampanjat (haara c/stubs-c1)
src/bouncer/explain/   C: LLM-selitykset + fallback (haara c/stubs-c1)
tests/c/               C: testit
deploy/, src/site/, src/bouncer/{ingest,db,api}/, frontend/, tools/sim/   A (tulossa)
scripts/               check.sh, check-changelog.sh, git-hook
```

## Komennot

```bash
make check                                                       # repon tarkistukset + changelog (myös CI)
uv run --no-project --python 3.12 --with pytest pytest tests/b   # kaistan B testit
uv run --no-project --python 3.12 --with pytest pytest tests/c   # kaistan C testit
make up                                                          # Postgres paikallisesti
```

`.env.example` → `.env`; `.env` ei koskaan mene gitiin.

## Lisenssi

MIT — ks. [LICENSE](LICENSE).
