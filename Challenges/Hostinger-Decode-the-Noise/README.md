# Hostinger — Decode the Noise

> **Status: suunnittelu ja prototyypit käynnissä.** Roolit (päätös 014) ja stack (004–013) on päätetty, ks. [`docs/DECISIONS.md`](../../docs/DECISIONS.md). VPS:n, domainin ja AI Router -avaimen hankintaa ei ole vahvistettu tässä repossa; älä merkitse niitä tehdyiksi ilman omistajan vahvistusta.

Työnimi **Bouncer**: kertoo sivuston omistajalle, onko kävijä ihminen, hyvä botti vai hyökkääjä, miksi, ja kuinka usein työkalu on väärässä.

| Tiedosto | Sisältö |
|---|---|
| [IDEA.md](IDEA.md) | Ongelma, ratkaisu, demo, rajaus, riskit, mittarit |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Rakenne, tunnistuslogiikka, arviointi, tietomalli, API |
| [TEAM.md](TEAM.md) | Kaistat A/B/C, omistajuus, sopimukset S1–S11, integraatiopisteet |
| [TODO.md](TODO.md) | Kortit kaistoittain T+0 → palautus; A:n avoimet ja estetyt työt on eritelty alla |

## Missä mennään

*Päivitetty 2026-11-13 tämän repon `main`-haaran ja saatavilla olevien etähaarojen perusteella. Työpuun A-muutokset eivät ole vielä `main`issa. GitHubin avointen PR:ien tilaa ei voitu varmistaa.*

| Kaista | Kuka | `main`issa | Työn alla | Odottaa |
|---|---|---|---|---|
| **A** alusta + hyökkääjä | Murtsi | Ei A:n toteutuksia | `a/person-a-integration`-työpuussa A-1:n luonnokset: sopimustyypit, Caddy JSONL -fixture, `X-Sim-Run`-parseri ja ansalista; ei vielä `main`issa | Vahvista PRE-1 (VPS/domain/AI Router). A-1:n S2-ID-muoto hyväksytettävä C:n kanssa. A-2…A-15 ovat vielä tekemättä; tarkka lista alla/TODO:ssa |
| **B** session tunnistus + arviointi | Niko | B-1…B-5: stubit, piirteet, säännöt, datasetti ja piirreraportti | Ei vahvistettua uutta B-työtä `main`issa | A:n Postgres `load_sessions()`/`load_labels()` (S3), oikea loki ja vahvistettu A:n simulaattoriluokkien lista (B-3/B-5) |
| **C** verkosto + kampanjat + selitykset | Joonas | Ei C-toteutuksia | C-1…C-7-koodi löytyy `origin/c/stubs-c1`-haarasta (ei `main`issa) | PR/integrointi, yhteensopivuus A:n S2-tyyppien kanssa, A:n S1/S3, C-4:n oikea liikenne ja live AI Router -avain |

### Sopimukset S1–S11

| # | Sopimus | Tila |
|---|---|---|
| S1 | `samples/access.sample.jsonl` (A) | A-haaran työpuussa: 6 synteettistä Caddy JSON -riviä; ei vielä live-loki |
| S2 | `src/bouncer/contracts.py` (A) | Session ID on A/B:n luonnoksessa `str` ja C:n adapterissa numeerinen; kampanja-ID ja kokoelmat eroavat myös. S2:n yhteinen muoto vaatii B:n/C:n hyväksynnän ennen mergeä |
| S3 | `load_sessions()` + `load_labels()` Postgresista (A) | ❌ puuttuu; JSONL-fixture-parseri ei ole tietokantalataaja |
| S4 | `ip_intel()` (C) | koodi `origin/c/stubs-c1`-haarassa; ei `main`issa |
| S5 | `find_campaigns()` (C) | koodi `origin/c/stubs-c1`-haarassa; ei `main`issa |
| S6 | `score()` (B) | ✅ `main`issa: säännöt (`rules-v1`), ei vielä mallia/`human`-päätöstä |
| S7 | `explain()` (C) | koodi `origin/c/stubs-c1`-haarassa; ei `main`issa |
| S8 | `metrics.json` (B) | ✅ stub `models/metrics.json` — ei mitattuja lukuja |
| S9 | `campaign_metrics.json` (C) | stub ja evaluaattori `origin/c/stubs-c1`-haarassa; ei `main`issa |
| S10 | `X-Sim-Run`-muoto (A) | A-haaran fixture käyttää `run-id:class:campaign-id`-arvoa `X-Sim-Run`-pyyntöotsakkeessa; luokkien täydellinen lista sovittava C/B-simulaattorien kanssa |
| S11 | `deploy/traps.txt` (A) | A-haaran luonnos; ansapolut eivät ole vielä demosivustossa |

### Seuraavaksi

- **A (Murtsi), jäljellä olevat tehtävät:** PRE-1 (VPS/domain/Router-avaimen tila, ulkoinen vahvistus); A-1 (S1:n 50 rivin sopimusfixture, S2/S10 ID- ja simuluokkien sopimus B/C:n kanssa, S11:n reitit myös demosivustoon); A-2 VPS/Caddy/TLS; A-3 demosivusto ja login/ansat; A-4 simulaattorit + oikea lokinäyte; A-5 ingest/sessionointi/labelien tallennus; A-6 Postgres-lukijat ja worker; A-7 deploy; A-8 täyssimulaattorit; A-9 ihmissimulaattori/QR; A-10 piilotettu hyökkäys; A-11 API; A-12 dashboard; A-13 AI Builder -etusivu; A-14 operointi/varmistukset/rate limit; A-15 paljastus ja integraatio. Toteutusjärjestys ja hyväksymiskriteerit ovat `TODO.md`:ssä. Sovi ensin S2:n ID-tyyppi: A/B käyttävät `str`, C:n nykyinen adapteri olettaa numeeriset ID:t. A-2 edellyttää PRE-1:n vahvistamista; A-3 tarvitsee toimivan demo-hostin. A-4:n oikea loki ja A-5/A-6:n tietokantaputki estävät B:n/C:n oikean datan integraatiota.
- **B:** käytä nykyistä fixtureä yksikkötesteissä; B-3/B-5 tarvitsee live-lokin sekä A:n Postgres-lataajat (S3). Varmista A:n lopulliset simulaattoriluokat ennen labeloitua ajoa.
- **C:** avaa PR `origin/c/stubs-c1`-työlle ja sovi S2:n session/campaign ID-esitys A:n kanssa ennen mergeä. C-4 tarvitsee oikean lokin.
- **Kaikki:** tarkista crawler- ja S4-sopimus C-haaran integroinnissa; kyseistä branch-only päätöstä ei ole vielä kirjattu tähän `main`-haaraan.

## Avoimet kysymykset

- [x] Kuka on A, B, C? → Murtsi, Niko, Joonas (päätös 014)
- [x] Kieli ja stack? → Python + FastAPI, React, PostgreSQL + TimescaleDB (004–013)
- [ ] Virallinen palautusaika? (`DEADLINE` TODO.md:ssä)
- [ ] PRE-1: VPS, domain ja AI Router -avain — ulkoinen vahvistus tarvitaan
- [ ] Hostingerilta (PRE-4, Joonas): saako DB olla muualla? Onko Gemini AI Routerissa? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon?
