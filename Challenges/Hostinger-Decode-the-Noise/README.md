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

*Päivitetty 2026-11-13 tarkistamalla `main` (PR #5 mergetty). A:n aloitusmuutokset ovat mainissa: kuuden rivin synteettinen Caddy-fixture, parseri/sessionointi ja ansalista. Julkista sovellusta ei ole vahvistettu toimivaksi.*

| Kaista | Kuka | `main`issa | Seuraava handoff | Odottaa |
|---|---|---|---|---|
| **A** alusta + hyökkääjä | Murtsi | A-1:n luonnokset: sopimustyypit, 6-rivin Caddy JSONL -fixture, parseri/sessionointi ja ansalista | S2/S10 ja login-event-muoto B/C:n kanssa; sitten S3: Postgres-ingest ja `load_sessions()`/`load_labels()` | Hostinger-live-deploy ja AI Router -avain vahvistamatta; S2 ID-ristiriita alla |
| **B** session tunnistus + arviointi | Niko | B-1…B-9; `lr-v1`, arviointiajo ja jäädytetyn mallin hidden-eval-työkalu | A:n Postgres-lataajat ja ei-synteettinen liikenne tarvitaan mallin opettamiseen ja oikeisiin mittareihin | S3; käyttökelpoinen live-data puuttuu |
| **C** verkosto + kampanjat + selitykset | Joonas | C-1…C-9, threat-feed ja campaign graph | Testaa login/campaign adapteri A:n vakaalla Session/ID/login-event-muodolla | A:n login-event/data-handoff; live AI Router -avain |

### Sopimukset S1–S11

| # | Sopimus | Tila |
|---|---|---|
| S1 | `samples/access.sample.jsonl` | ✅ 6-rivinen synteettinen Caddy-fixture; live-loki puuttuu |
| S2 | `src/bouncer/contracts.py` | ⚠️ Yhteinen päätös tarvitaan: sample-parseri tuottaa ajonaikaisia `int`-ID-arvoja vaikka annotaatiot ovat `str`; B:n datasetti käyttää string-avaimia ja C:n adapteri muuntaa ID:t `int`:ksi |
| S3 | `load_sessions(since)` + `load_labels()` | ❌ Postgres-toteutus puuttuu |
| S4 | `ip_intel()` | ✅ `verified_bot: bool \| None`; DNS-virhe → `None` (päätökset 020/027) |
| S5 | `find_campaigns()` | ✅ stuffing, behavior-klusterit ja shared-NAT-suodatus |
| S6 | `score()` | ✅ `rules-v1` + mallikäyttö, kun hyväksytty mallifile löytyy; todellinen opetus odottaa dataa |
| S7 | `explain()` | ✅ Router-polku + fallback; live-avainta ei ole vahvistettu |
| S8 | `metrics.json` | ⚠️ arviointityökalu on olemassa; repositoryssa oleva metrics-tiedosto on stub, ei mitattu suorituskyky |
| S9 | `campaign_metrics.json` | ✅ stub + evaluaattori |
| S10 | `X-Sim-Run` | ⚠️ `run-id:class[:campaign-id]` toimii fixture-parserissa; täydellinen luokkasanasto ja login-eventit vahvistettava B/C:n kanssa |
| S11 | `deploy/traps.txt` | ✅ lista ja B:n testikäyttö; reitit eivät ole vielä demo-sivustossa |

### Seuraavaksi

1. **A+B+C:** lukitkaa S2:n string/numeric ID-esitys, `Campaign.session_ids`, simulaattoriluokat sekä login-eventtien minimiskeema. B:n testissä ID-tyypin vaatimus on yhä tiukasti `xfail`; C:n adapteri muuntaa ID:t `int`:ksi ja fallbackaa ei-numeerisen ID:n indeksiksi.
2. **A:** rakenna paikallinen, idempotentti Caddy JSONL → Postgres ingest/sessionointi, migraatiot sekä `load_sessions(since)`/`load_labels()` ja worker. Synteettinen fixture riittää ohjelmistointegraatioon; älkää väittäkö siitä oikeita mittareita.
3. **A+B+C:** testatkaa loader B:n datasettiä ja C:n stuffing/campaign-funktioita vasten. Älkää kerätkö tai lokittako salasanoja tai raakaa kirjautumisrunkoa.
4. **A:** lisää demo-site/Caddy, simulaattoriliikenne ja tarkistettu redaktoitu dataesimerkki; tämän jälkeen live-deploy/dashboard.

- **A:** kaikki A-2…A-15 eivät ole valmiita. A-2:n julkinen deploy edellyttää vahvistettua pääsyä/domainin tilaa; A-3…A-6 ovat paikallisen päästä päähän -putken seuraava työ.
- **B:** voi jatkaa piirre-/sääntö-/mallityökaluja synteettisillä testidatoilla; mittarit ja mallin tallennus odottavat riittävää ei-synteettistä labeloitua aineistoa.
- **C:** voi ajaa nykyiset offline- ja synteettiset testit; A:n todellisia login-eventtejä vaativa C-4 odottaa sovittua skeemaa ja ingestia.
- **Kaikki:** pitäkää Googlebot/Bingbot-lista B:n ja C:n välillä synkassa (026).

## Avoimet kysymykset

- [x] Kuka on A, B, C? → Murtsi, Niko, Joonas (päätös 014)
- [x] Kieli ja stack? → Python + FastAPI, React, PostgreSQL + TimescaleDB (004–013)
- [x] S4 `verified_bot: bool \| None` + DNS-virhe → `None` (020 + 027)
- [ ] Virallinen palautusaika? (`DEADLINE` TODO.md:ssä)
- [x] PRE-1: VPS ja domain vahvistettu Hostinger Connectorilla
- [ ] PRE-1: AI Router -avain ja toimiva sovellusdeploy vahvistamatta
- [ ] Hostingerilta (PRE-4, Joonas): saako DB olla muualla? Onko Gemini AI Routerissa? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon?
