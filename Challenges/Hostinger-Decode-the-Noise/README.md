# Hostinger — Decode the Noise

> **Status: aktiivinen haaste.** Roolit (päätös 014) ja stack (004–013) on päätetty, ks. [`docs/DECISIONS.md`](../../docs/DECISIONS.md). Hack ei ole vielä virallisesti alkanut; VPS on haussa.

Työnimi **Bouncer**: kertoo sivuston omistajalle, onko kävijä ihminen, hyvä botti vai hyökkääjä, miksi, ja kuinka usein työkalu on väärässä.

| Tiedosto | Sisältö |
|---|---|
| [IDEA.md](IDEA.md) | Ongelma, ratkaisu, demo, rajaus, riskit, mittarit |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Rakenne, tunnistuslogiikka, arviointi, tietomalli, API |
| [TEAM.md](TEAM.md) | Kaistat A/B/C, omistajuus, sopimukset S1–S11, integraatiopisteet |
| [TODO.md](TODO.md) | Kortit kaistoittain T+0 → palautus |
| [MENTOR_QUESTIONS.md](MENTOR_QUESTIONS.md) | PRE-4 kysymykset Hostingerin mentoreille |

## Missä mennään

*Päivitetty 2026-11-13. Päivitä tämä osio, kun kortti valmistuu tai jumittuu.*

| Kaista | Kuka | `main`issa | Työn alla | Odottaa |
|---|---|---|---|---|
| **A** alusta + hyökkääjä | Murtsi | — | VPS:n hankinta (PRE-1) | — |
| **B** session tunnistus + arviointi | Niko | **B-1** stubit (S6, S8); **B-2** session piirteet; **B-4** varmat säännöt + `reasons` (`rules-v1`, PR #2 mergetty); **B-3/B-5** työkalut: datasetti + piirreraportti (PR #4 mergetty) | B-7 arviointi synteettisellä datalla; fake-crawler -lista rajattu Googlebot+Bingbot (päätös 026, haara `b/status-update`) | A: `contracts.py` (S2), lokinäyte (S1), `load_sessions()`/`load_labels()` (S3), `traps.txt` (S11), simulaattoriluokkien nimet (S10) |
| **C** verkosto + kampanjat + selitykset | Joonas | — | **C-1…C-7** haarassa [`c/stubs-c1`](https://github.com/Murtsi/Bounceri/tree/c/stubs-c1) (ei vielä PR:ää): `ip_intel`, stuffing, behavior-kampanjat, eval, `explain` | A: S1–S3; live AI Router -avain; C-4 oikea loki |

### Sopimukset S1–S11

| # | Sopimus | Tila |
|---|---|---|
| S1 | `samples/access.sample.jsonl` (A) | ❌ puuttuu |
| S2 | `contracts.py` (A) | ❌ puuttuu — B:n kenttäehdotus: `src/bouncer/session/_provisional_types.py` |
| S3 | `load_sessions()` + `load_labels()` (A) | ❌ puuttuu |
| S4 | `ip_intel()` (C) | ✅ koodi `c/stubs-c1` — **S4 sovittu (020+027):** `verified_bot: bool \| None`; `None` = ei tarkistettu / DNS epäonnistui; `False` = tarkistettu eikä ole (tai spoofattu PTR); lista = Googlebot + Bingbot (synkassa B:n kanssa, 026) |
| S5 | `find_campaigns()` (C) | ✅ koodi `c/stubs-c1` (stuffing + behavior); odottaa PR/mergeä |
| S6 | `score()` (B) | ✅ varmat säännöt (`rules-v1`) `main`issa: `good_bot` / `bad_bot` / `uncertain`, ei vielä `human` (malli B-6) |
| S7 | `explain()` (C) | ✅ koodi `c/stubs-c1` (Router + fallback); odottaa PR/mergeä |
| S8 | `metrics.json` (B) | ✅ stub `models/metrics.json` — ei mitattuja lukuja |
| S9 | `campaign_metrics.json` (C) | ✅ stub + evaluaattori `c/stubs-c1`; odottaa PR/mergeä |
| S10 | `X-Sim-Run`-muoto (A) | sovittu TEAM.md:ssä; B:n datasetti olettaa luokat `human*`, `scraper`, `scanner`, `slow_scanner`, `credential_stuffing`, `brute_force`, `good_bot` — vahvista |
| S11 | `deploy/traps.txt` (A) | ❌ puuttuu — B:n ansasääntö aktivoituu, kun tiedosto on olemassa |

### Seuraavaksi

- **A:** S1–S3 ja S11 stubeina, jotta B ja C pääsevät ajamaan koodiaan oikeaa muotoa vasten (integraatio T+1).
- **B:** B-3/B-5 oikealla datalla heti kun S1 ja S3 ovat olemassa; siihen asti B-7 synteettisellä datalla. Merge `b/status-update` (026).
- **C:** Avaa PR `c/stubs-c1` → `main` (S4-korjaus mukana). C-4 kun A:n loki on olemassa.
- **Kaikki:** S4 `verified_bot` on sovittu (C hyväksyi 020; DNS-virhe → `None`, päätös 027). Pidä crawler-listat samoina (`bots.py` ↔ `rules.VERIFIABLE_CRAWLER_TOKENS`).

## Avoimet kysymykset

- [x] Kuka on A, B, C? → Murtsi, Niko, Joonas (päätös 014)
- [x] Kieli ja stack? → Python + FastAPI, React, PostgreSQL + TimescaleDB (004–013)
- [x] S4 `verified_bot: bool \| None` + DNS-virhe → `None` (020 + 027)
- [ ] Virallinen palautusaika? (`DEADLINE` TODO.md:ssä)
- [ ] Hostingerilta (PRE-4, Joonas): ks. [`MENTOR_QUESTIONS.md`](MENTOR_QUESTIONS.md)
