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
| **B** session tunnistus + arviointi | Niko | **B-1** stubit (S6, S8); **B-2** session piirteet; **B-4** varmat säännöt + `reasons` (`rules-v1`); **B-3/B-5** työkalut: datasetin kokoaminen + piirreraportti (112 testiä) | B-7:n arviointikoodi synteettisellä datalla | A: `contracts.py` (S2), lokinäyte (S1), `load_sessions()`/`load_labels()` (S3), `traps.txt` (S11), simulaattoriluokkien nimet (S10) |
| **C** verkosto + kampanjat + selitykset | Joonas | — | C-1…C-7 haarassa `c/stubs-c1` (ei vielä PR:ää) | — |

### Sopimukset S1–S11

| # | Sopimus | Tila |
|---|---|---|
| S1 | `samples/access.sample.jsonl` (A) | ❌ puuttuu |
| S2 | `contracts.py` (A) | ❌ puuttuu — B:n kenttäehdotus: `src/bouncer/session/_provisional_types.py` |
| S3 | `load_sessions()` + `load_labels()` (A) | ❌ puuttuu |
| S4 | `ip_intel()` (C) | ❌ puuttuu — B:n säännöt olettavat `verified_bot: bool \| None`, jossa `None` = ei tarkistettu (päätös 020). C:n haarassa `verified_bot: bool = False`, ja DNS-virhe palauttaa myös `False` → oikea Googlebot voi leimautua väärennökseksi, jos DNS-haku epäonnistuu — **sovittava ennen integraatiota** |
| S5 | `find_campaigns()` (C) | ❌ puuttuu |
| S6 | `score()` (B) | ✅ varmat säännöt (`rules-v1`): `good_bot` / `bad_bot` / `uncertain`, ei vielä `human` (malli B-6) |
| S7 | `explain()` (C) | ❌ puuttuu |
| S8 | `metrics.json` (B) | ✅ stub `models/metrics.json` — ei mitattuja lukuja |
| S9 | `campaign_metrics.json` (C) | ❌ puuttuu |
| S10 | `X-Sim-Run`-muoto (A) | sovittu TEAM.md:ssä; B:n datasetti olettaa luokat `human*`, `scraper`, `scanner`, `slow_scanner`, `credential_stuffing`, `brute_force`, `good_bot` — vahvista |
| S11 | `deploy/traps.txt` (A) | ❌ puuttuu — B:n ansasääntö aktivoituu, kun tiedosto on olemassa |

### Seuraavaksi

- **A:** S1–S3 ja S11 stubeina, jotta B ja C pääsevät ajamaan koodiaan oikeaa muotoa vasten (integraatio T+1).
- **B:** B-3 (piirreraportti oikeaa lokia vasten) ja B-5 (datasetti oikeilla labeleilla) heti kun S1 ja S3 ovat olemassa; siihen asti B-7:n arviointikoodi synteettisellä datalla.
- **C:** PR `c/stubs-c1` → `main`; sovi S4:n `verified_bot` B:n kanssa. B:n väärennössääntö tarkistaa vain Googlebotin ja Bingbotin, samat kuin C:n `bots.py` — pidetään listat samoina.
- **Kaikki:** päätä S4:n `verified_bot`-ehdotus (päätös 020).

## Avoimet kysymykset

- [x] Kuka on A, B, C? → Murtsi, Niko, Joonas (päätös 014)
- [x] Kieli ja stack? → Python + FastAPI, React, PostgreSQL + TimescaleDB (004–013)
- [ ] Virallinen palautusaika? (`DEADLINE` TODO.md:ssä)
- [ ] Hostingerilta (PRE-4, Joonas): saako DB olla muualla? Onko Gemini AI Routerissa? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon?
