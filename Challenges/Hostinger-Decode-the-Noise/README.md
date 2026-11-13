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

*Päivitetty 2026-11-13: `main` sisältää A starterin (PR #5/#11), B-6…B-11 (PR #6–#10/#12), C-1…C-9 + S2/C-4/C-10-prep (PR #8).*

| Kaista | Kuka | `main`issa | Seuraava handoff | Odottaa |
|---|---|---|---|---|
| **A** alusta + hyökkääjä | Murtsi | sopimustyypit, 6-rivin Caddy JSONL -fixture, parseri/sessionointi, ansalista, ingest-suunnitelma | S3 Postgres-ingest + `load_sessions()`/`load_labels()`; sitten simut/dashboard | Hostinger-live-deploy ja AI Router -avain; 50 rivin S1-fixture |
| **B** session tunnistus + arviointi | Niko | B-1…B-8 ja B-11: piirteet, säännöt, malli `lr-v1`, datasetti, arviointi + ablaatio, `bouncer.eval.run`, `bouncer.eval.hidden` | A:n Postgres-lataajat (S3) → `bouncer.eval.run --source db` | S3 ja labeloitu ei-synteettinen liikenne (≥ 300 ihmissessiota FPR-väitteeseen) |
| **C** verkosto + kampanjat + selitykset | Joonas | C-1…C-9 + S2 `str`-ID:t + C-4 fixture + `network_pass` + hidden prep (PR #8); ExplainCache / fixture-metrics follow-up | C-8 dashboard UI, live Router | A-8 stuffing-simu (S9 lock), A-11/A-12, A-15, PRE-1 avain |

### Sopimukset S1–S11

| # | Sopimus | Tila |
|---|---|---|
| S1 | `samples/access.sample.jsonl` | ✅ 6-rivinen synteettinen Caddy-fixture; live-loki puuttuu |
| S2 | `src/bouncer/contracts.py` | ✅ **Lukittu `str` (039)** B+C; A:n sample-parseri voi vielä syöttää int-id:itä runtimeen — C stringifioi |
| S3 | `load_sessions(since)` + `load_labels()` | ❌ Postgres-toteutus puuttuu |
| S4 | `ip_intel()` | ✅ `verified_bot: bool \| None`; DNS-virhe → `None` (020/027); `country` curated FI-prefixeistä (040) |
| S5 | `find_campaigns()` | ✅ stuffing, behavior-klusterit ja shared-NAT-suodatus |
| S6 | `score()` | ✅ `rules-v1` + mallikäyttö, kun hyväksytty mallifile löytyy; todellinen opetus odottaa dataa |
| S7 | `explain()` | ✅ Router-polku + fallback + `ExplainCache`; live-avainta ei ole vahvistettu |
| S8 | `metrics.json` | ⚠️ arviointityökalu on olemassa; repositoryssa oleva metrics-tiedosto on stub |
| S9 | `campaign_metrics.json` | ✅ stub + evaluaattori; synteettinen `campaign_metrics.fixture.json` erillään |
| S10 | `X-Sim-Run` | ⚠️ `run-id:class[:campaign-id]` toimii fixture-parserissa; täydellinen luokkasanasto vahvistettava |
| S11 | `deploy/traps.txt` | ✅ lista ja B:n testikäyttö; reitit eivät ole vielä demo-sivustossa |

### Seuraavaksi

1. **A:** paikallinen Caddy JSONL → Postgres ingest + `load_sessions`/`load_labels` + worker (S3).
2. **A+B+C:** testatkaa loader B:n datasettiä ja C:n stuffing/campaign-funktioita vasten. Älkää kerätkö salasanoja.
3. **A:** demo-site, simulaattorit (sis. stuffing A-8), live-deploy/dashboard.
4. **B:** `eval.run --source db` → lukitse `metrics.json`.
5. **C:** S9 lock stuffing-simulla; C-8 UI; C-10 A-15:n jälkeen.

- **A:** A-2…A-15 eivät ole valmiita; A-3…A-6 ovat paikallisen E2E-putken seuraava työ.
- **B:** voi jatkaa synteettisillä testeillä; mittarit odottavat ei-synteettistä dataa.
- **C:** PR #8 mergetty; odottaa A:n stuffing-simua / dashboardia / Router-avainta.
- **Kaikki:** S4 sovittu (020 + 027); pidä Googlebot/Bingbot-listat samoina B:n ja C:n koodissa.

## Avoimet kysymykset

- [x] Kuka on A, B, C? → Murtsi, Niko, Joonas (päätös 014)
- [x] Kieli ja stack? → Python + FastAPI, React, PostgreSQL + TimescaleDB (004–013)
- [x] S4 `verified_bot: bool \| None` + DNS-virhe → `None` (020 + 027)
- [x] S2 ID:t `str` (039)
- [ ] Virallinen palautusaika? (`DEADLINE` TODO.md:ssä)
- [x] PRE-1: VPS ja domain vahvistettu Hostinger Connectorilla
- [ ] PRE-1: AI Router -avain ja toimiva sovellusdeploy vahvistamatta
- [ ] Hostingerilta (PRE-4, Joonas): saako DB olla muualla? Onko Gemini AI Routerissa? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon?
