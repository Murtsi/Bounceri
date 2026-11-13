# Hostinger — Decode the Noise

> **Status: aktiivinen haaste.** Roolit (päätös 014) ja stack (004–013) on päätetty, ks. [`docs/DECISIONS.md`](../../docs/DECISIONS.md). Hack ei ole vielä virallisesti alkanut; VPS on haussa.

Työnimi **Bouncer**: kertoo sivuston omistajalle, onko kävijä ihminen, hyvä botti vai hyökkääjä, miksi, ja kuinka usein työkalu on väärässä.

| Tiedosto | Sisältö |
|---|---|
| [IDEA.md](IDEA.md) | Ongelma, ratkaisu, demo, rajaus, riskit, mittarit |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Rakenne, tunnistuslogiikka, arviointi, tietomalli, API |
| [TEAM.md](TEAM.md) | Kaistat A/B/C, omistajuus, sopimukset S1–S11, integraatiopisteet |
| [TODO.md](TODO.md) | Kortit kaistoittain T+0 → palautus |

## Missä mennään

*Päivitetty 2026-11-13. Päivitä tämä osio, kun kortti valmistuu tai jumittuu.*

| Kaista | Kuka | `main`issa | Työn alla | Odottaa |
|---|---|---|---|---|
| **A** alusta + hyökkääjä | Murtsi | — | VPS:n hankinta (PRE-1) | — |
| **B** session tunnistus + arviointi | Niko | **B-1** `score()`-stub (S6) + `metrics.json`-stub (S8); **B-2** session piirteet + testit | **B-4** varmat säännöt → [PR #2](https://github.com/Murtsi/JunctionHackathon/pull/2); **B-3/B-5** datasetti + piirreraportti, koodi valmis haarassa `b/dataset` | A: `contracts.py` (S2), lokinäyte (S1), `load_sessions()`/`load_labels()` (S3), `traps.txt` (S11) |
| **C** verkosto + kampanjat + selitykset | Joonas | — | — | — |

### Sopimukset S1–S11

| # | Sopimus | Tila |
|---|---|---|
| S1 | `samples/access.sample.jsonl` (A) | ❌ puuttuu |
| S2 | `contracts.py` (A) | ❌ puuttuu — B:n kenttäehdotus: `src/bouncer/session/_provisional_types.py` |
| S3 | `load_sessions()` + `load_labels()` (A) | ❌ puuttuu |
| S4 | `ip_intel()` (C) | ❌ puuttuu — B ehdottaa `verified_bot: bool \| None` ([PR #2](https://github.com/Murtsi/JunctionHackathon/pull/2), päätös 020) |
| S5 | `find_campaigns()` (C) | ❌ puuttuu |
| S6 | `score()` (B) | ✅ stub `main`issa; säännöt (`rules-v1`) PR #2:ssa |
| S7 | `explain()` (C) | ❌ puuttuu |
| S8 | `metrics.json` (B) | ✅ stub `models/metrics.json` — ei mitattuja lukuja |
| S9 | `campaign_metrics.json` (C) | ❌ puuttuu |
| S10 | `X-Sim-Run`-muoto (A) | sovittu TEAM.md:ssä; B:n datasetti olettaa luokat `human*`, `scraper`, `scanner`, `slow_scanner`, `credential_stuffing` — vahvista |
| S11 | `deploy/traps.txt` (A) | ❌ puuttuu — B:n ansasääntö aktivoituu, kun tiedosto on olemassa |

### Seuraavaksi

- **A:** S1–S3 ja S11 stubeina, jotta B ja C pääsevät ajamaan koodiaan oikeaa muotoa vasten (integraatio T+1).
- **B:** B-3 (piirteet oikeaa lokia vasten) heti kun S1 on olemassa; siihen asti B-7:n arviointikoodi synteettisellä datalla.
- **C:** C-1-stubit (S4, S5, S7, S9).
- **Kaikki:** päätä S4:n `verified_bot`-ehdotus (PR #2).

## Avoimet kysymykset

- [x] Kuka on A, B, C? → Murtsi, Niko, Joonas (päätös 014)
- [x] Kieli ja stack? → Python + FastAPI, React, PostgreSQL + TimescaleDB (004–013)
- [ ] Virallinen palautusaika? (`DEADLINE` TODO.md:ssä)
- [ ] Hostingerilta (PRE-4, Joonas): saako DB olla muualla? Onko Gemini AI Routerissa? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon?
