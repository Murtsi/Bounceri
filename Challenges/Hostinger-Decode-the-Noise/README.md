# Hostinger — Decode the Noise

> **Status: suunnittelu ja prototyypit käynnissä.** Roolit (päätös 014) ja stack (004–013) on päätetty, ks. [`docs/DECISIONS.md`](../../docs/DECISIONS.md). Hostinger Connectorilla on vahvistettu käynnissä oleva KVM 2 VPS ja bounceri.tech-domain. Sovelluksen live-deployta ja AI Router -avainta ei ole vahvistettu.

Työnimi **Bouncer**: kertoo sivuston omistajalle, onko kävijä ihminen, hyvä botti vai hyökkääjä, miksi, ja kuinka usein työkalu on väärässä.

| Tiedosto | Sisältö |
|---|---|
| [IDEA.md](IDEA.md) | Ongelma, ratkaisu, demo, rajaus, riskit, mittarit |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Rakenne, tunnistuslogiikka, arviointi, tietomalli, API |
| [TEAM.md](TEAM.md) | Kaistat A/B/C, omistajuus, sopimukset S1–S11, integraatiopisteet |
| [TODO.md](TODO.md) | Kortit kaistoittain T+0 → palautus; A:n avoimet ja estetyt työt on eritelty alla |

## Missä mennään

*Päivitetty 2026-11-13 tämän repon `main`-haaran ja saatavilla olevien etähaarojen perusteella. A-haaran muutokset eivät ole vielä `main`issa. PR:t #1–#4 on tarkistettu: kaikki mergetty. A-haaran luonnokset eivät vielä ole mainissa.*

| Kaista | Kuka | `main`issa | Työn alla | Odottaa |
|---|---|---|---|---|
| **A** alusta + hyökkääjä | Murtsi | Ei A:n toteutuksia | `a/person-a-integration`-haarassa A-1:n luonnokset: sopimustyypit, Caddy JSONL -fixture, `X-Sim-Run`-parseri ja ansalista; ei vielä `main`issa | Vahvista PRE-1 (VPS/domain/AI Router). A-1:n S2-ID-muoto hyväksytettävä C:n kanssa. A-2…A-15 ovat vielä tekemättä; tarkka lista alla/TODO:ssa |
| **B** session tunnistus + arviointi | Niko | **B-1** stubit (S6, S8); **B-2** session piirteet; **B-4** varmat säännöt + `reasons` (`rules-v1`); **B-3/B-5** datasetti + piirreraportti; fake-crawler = Googlebot+Bingbot (026); **B-7** arviointi: temporaalinen jako, kynnykset (ihmisten FPR ≤ 1 %), luvut + Wilson-yläraja, simuloitu/oikea/piilotettu erikseen; **B-8** ablaatio ilman C:n signaaleja (028–031) | B-6 mallikoodi (opetus vasta oikealla datalla) | A: `contracts.py` (S2), lokinäyte (S1), `load_sessions()`/`load_labels()` (S3), `traps.txt` (S11), simulaattoriluokkien nimet (S10) |
| **C** verkosto + kampanjat + selitykset | Joonas | C-1…C-9 + C-4 fixture/S2-align (`c/c4-s2-align`); threat-feed + campaign graph + `network_pass` | C-8 dashboard, C-10 piilotettu, live Router | A-8 stuffing-simu (metrics lock), A-11/A-12, PRE-1 avain |

### Sopimukset S1–S11

| # | Sopimus | Tila |
|---|---|---|
| S1 | `samples/access.sample.jsonl` (A) | A-haaran haarassa: 6 synteettistä Caddy JSON -riviä; ei vielä live-loki |
| S2 | `src/bouncer/contracts.py` (A) | Session ID on A/B:n luonnoksessa `str` ja C:n adapterissa numeerinen; kampanja-ID ja kokoelmat eroavat myös. S2:n yhteinen muoto vaatii B:n/C:n hyväksynnän ennen mergeä |
| S3 | `load_sessions()` + `load_labels()` Postgresista (A) | ❌ puuttuu; JSONL-fixture-parseri ei ole tietokantalataaja |
| S4 | `ip_intel()` (C) | ✅ koodi [PR #2](https://github.com/Murtsi/Bounceri/pull/2) — **S4 sovittu (020+027):** `verified_bot: bool \| None`; DNS-virhe → `None`; lista = Googlebot + Bingbot (026) |
| S5 | `find_campaigns()` (C) | ✅ koodi [PR #2](https://github.com/Murtsi/Bounceri/pull/2) (stuffing + behavior + NAT-suodatin) |
| S6 | `score()` (B) | ✅ `main`issa: säännöt (`rules-v1`), ei vielä mallia/`human`-päätöstä |
| S7 | `explain()` (C) | ✅ koodi [PR #2](https://github.com/Murtsi/Bounceri/pull/2) (Router + fallback) |
| S8 | `metrics.json` (B) | ✅ arviointikoodi valmis (B-7/B-8); `models/metrics.json` on yhä stub — oikeat luvut lasketaan vasta A:n datalla |
| S9 | `campaign_metrics.json` (C) | ✅ stub + evaluaattori [PR #2](https://github.com/Murtsi/Bounceri/pull/2) |
| S10 | `X-Sim-Run`-muoto (A) | A-haaran fixture käyttää `run-id:class:campaign-id`-arvoa `X-Sim-Run`-pyyntöotsakkeessa; luokkien täydellinen lista sovittava C/B-simulaattorien kanssa |
| S11 | `deploy/traps.txt` (A) | A-haaran luonnos; ansapolut eivät ole vielä demosivustossa |

### Seuraavaksi

- **A (Murtsi), jäljellä olevat tehtävät:** PRE-1 (VPS/domain/Router-avaimen tila, ulkoinen vahvistus); A-1 (S1:n 50 rivin sopimusfixture, S2/S10 ID- ja simuluokkien sopimus B/C:n kanssa, S11:n reitit myös demosivustoon); A-2 VPS/Caddy/TLS; A-3 demosivusto ja login/ansat; A-4 simulaattorit + oikea lokinäyte; A-5 ingest/sessionointi/labelien tallennus; A-6 Postgres-lukijat ja worker; A-7 deploy; A-8 täyssimulaattorit; A-9 ihmissimulaattori/QR; A-10 piilotettu hyökkäys; A-11 API; A-12 dashboard; A-13 AI Builder -etusivu; A-14 operointi/varmistukset/rate limit; A-15 paljastus ja integraatio. Toteutusjärjestys ja hyväksymiskriteerit ovat `TODO.md`:ssä. Sovi ensin S2:n ID-tyyppi: A/B käyttävät `str`, C:n nykyinen adapteri olettaa numeeriset ID:t. A-2 edellyttää PRE-1:n vahvistamista; A-3 tarvitsee toimivan demo-hostin. A-4:n oikea loki ja A-5/A-6:n tietokantaputki estävät B:n/C:n oikean datan integraatiota.
- **B:** käytä nykyistä fixtureä yksikkötesteissä; B-3/B-5 tarvitsee live-lokin sekä A:n Postgres-lataajat (S3). Varmista A:n lopulliset simulaattoriluokat ennen labeloitua ajoa.
- **C:** S2 merkkijono-id:t hyväksytty (päätös 032); C-4 stuffing-fixture + A ingest-smoke valmis. Seuraavaksi A-8 stuffing-simu → metrics lock; C-8 kun dashboard.
- **Kaikki:** S4 on sovittu (020 + 027); pidä Googlebot/Bingbot-listat samoina B:n ja C:n koodissa.

## Avoimet kysymykset

- [x] Kuka on A, B, C? → Murtsi, Niko, Joonas (päätös 014)
- [x] Kieli ja stack? → Python + FastAPI, React, PostgreSQL + TimescaleDB (004–013)
- [x] S4 `verified_bot: bool \| None` + DNS-virhe → `None` (020 + 027)
- [ ] Virallinen palautusaika? (`DEADLINE` TODO.md:ssä)
- [x] PRE-1: VPS ja domain vahvistettu Hostinger Connectorilla
- [ ] PRE-1: AI Router -avain ja toimiva sovellusdeploy vahvistamatta
- [ ] Hostingerilta (PRE-4, Joonas): saako DB olla muualla? Onko Gemini AI Routerissa? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon?
