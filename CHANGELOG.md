# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- [A] Explicit validated dashboard hostname aliases allow the owner-approved bounceri.tech and www.bounceri.tech HTTPS routes alongside the VPS preview URL.
- [A] Reproducible Hostinger Docker deployment with private source capsule, PostgreSQL, bounded HTTP simulation, ingest/detection, dashboard/API and asynchronous review worker; operator smoke test verifies actual 429/403, benign isolation, expiry and revoke without paid inference.
- [A] Add an opt-in investigation workspace with source provenance, evidence snapshots, separate assessment history and capability/budget status; preserve the existing dashboard default and navigation.
- [A] Administrator-approved synthetic demo actor rate-limit/temporary-block policies, HMAC actor authentication, durable expiry/revoke/history and actual HTTP 403/429 counters; normal site/admin routes remain accessible.
- [C] Asynchronous two-stage review transport, strict evidence validation and capability gates; no paid retries, automatic model substitution or enforcement authority.
- [A] Persistent, immutable investigations with redacted evidence, separate assessment history and transactional whole-review cost reservations; unknown provider charges remain reserved (decision 062).
- [X] Runtime dependencies for transactional investigation storage and bounded provider HTTP transport; existing local demo remains unchanged.
- [A] CI now runs the complete Python test suite instead of leaving stack checks as a commented Node.js scaffold.
- [A] Public-release preparation: English setup/status README and private vulnerability-reporting guidance; preserve synthetic ingestion fixtures and tests in Git.
- [A] S2-tyyppien ehdotus, kuuden rivin synteettinen Caddy JSONL -fixture ja parseri/sessionointi sekä `traps.txt` ovat mainissa (PR #5); yhteinen S2/S10-hyväksyntä, 50-rivin sopimusfixture, Postgres-ingest, live-loki ja sovelluspalvelu puuttuvat vielä (A-1).
- [C] Stubit S4/S5/S7/S9: `ip_intel` → `asn_type=unknown`, `find_campaigns` → `[]`, `explain` reasons-tekstinä, `campaign_metrics.json` stub (C-1).
- [C] `ip_intel` C-2: Googlebot/Bingbot käänteinen+forward DNS -varmistus; offline CIDR→ASN-tyyppi (datacenter/residential/mobile).
- [C] `find_campaigns` C-3: credential stuffing / distributed spray / low-and-slow sessioiden yli (C-3).
- [C] `find_campaigns` C-5: behavior-klusterointi (header FP + path Jaccard/MinHash + union-find).
- [C] `evaluate_campaigns` C-6: purity/coverage truth-kampanja-id:itä vasten.
- [C] `explain` C-7: AI Router -polku + groundedness-guardrail + fallback ilman avainta.
- [C] PRE-4 mentori­kysymykset: `Challenges/Hostinger-Decode-the-Noise/MENTOR_QUESTIONS.md`.
- Hackathon scaffold: docs, CI, docker-compose, pre-commit hook, devcontainer.
- [X] `Challenges/`-kansio: idea-tason suunnitelmat Hostinger (Decode the Noise) ja Valio Aimo (Trusted Trade Agents) -haasteille.
- [X] Hostinger-suunnitelma: kolme kaistaa ilman päällekkäisyyksiä — A alusta + hyökkääjä, B session tunnistus + arviointi, C verkosto- ja kampanjatunnistus + selitykset; sopimukset S1–S11.
- [X] Stack-päätökset 004–013 (`docs/DECISIONS.md`): Python + FastAPI, React + Vite + Tailwind + shadcn/ui, PostgreSQL + TimescaleDB, Hostinger AI Router, Docker Compose + Caddy, Hostinger Connector / MCP.
- [X] `AGENTS.md` (+ `CLAUDE.md`, joka viittaa siihen): yhteiset säännöt tiimille ja AI-agenteille; jokainen muutos kirjataan `CHANGELOG.md`:hen.
- [X] Roolit päätetty (014): A = Murtsi, B = Niko, C = Joonas; nimet `TEAM.md`:hen, `TODO.md`:hen ja `AGENTS.md`:hen.
- [X] `.github/CODEOWNERS`: kaistan polkujen PR:t pyytävät katselmoinnin automaattisesti omistajalta; yhteiset säännöt ja sopimukset kaikilta kolmelta.
- [X] CI-tarkistus `scripts/check-changelog.sh`: push tai PR ilman `CHANGELOG.md`-merkintää hylätään (poikkeus: `[skip changelog]`); ajetaan myös `make check`:ssa.
- [B] `score(session, intel, campaign) -> Verdict` -stub (S6), joka palauttaa aina `uncertain` (`model_version="stub-v0"`), ja `models/metrics.json`-stub (S8): skeeman kentät, kaikki luvut `null`, `"stub": true`. Väliaikaiset tyypit `src/bouncer/session/_provisional_types.py`:ssä, kunnes A:n `contracts.py` on olemassa (B-1, päätökset 015–016)
- [B] Session piirteet puhtaina funktioina (`bouncer.session.features.compute_features`): pyyntöä/min ja huipputahti 60 s ikkunassa, aikavälien variaatiokerroin, kesto, staattisten resurssien ja HTML:n osuus, polkujen monipuolisuus, `robots.txt`, 4xx/404-osuus, haavoittuvuuspolkujen osumat, selain-UA:n otsakkeiden johdonmukaisuus, puuttuva Referer, työkalu- ja botti-UA; testit synteettisillä sessioilla `tests/b/`:ssä (B-2, päätökset 017–018)
- [B] Varmat säännöt `score()`:ssa (`model_version="rules-v1"`): varmistettu hakukonebotti → `good_bot`; ansaosuma (`deploy/traps.txt`), väärennetty hakukone-UA ja ≥ 2 eri haavoittuvuuspolkua → `bad_bot`; muuten `uncertain`, ja havainnot syinä (enintään 3). Säännöt eivät koskaan päätä `human` (B-4, päätökset 019–022)
- [B] Labeloidun datasetin kokoaminen `bouncer.eval.dataset.build_dataset`: oikeat vastaukset A:n `X-Sim-Run`-labeleista, C:n DNS-varmistuksesta ja ansaosumista (tässä etusijajärjestyksessä); ristiriidat ja tuntemattomat simulaattoriluokat listataan eikä niitä arvata; piilotetun hyökkäyksen ajot voi jättää kokonaan pois. Valmis ajettavaksi heti, kun A:n `load_sessions()`/`load_labels()` on olemassa (B-5, päätökset 023–025)
- [B] Piirreraportti `bouncer.eval.feature_report`: piirteiden jakaumat (p10/mediaani/p90, True-osuus) erikseen simuloidulle ja oikealle liikenteelle luokittain, sekä lista ihmisiksi labeloiduista sessioista, joista löytyy bottihavaintoja (väärien positiivisten ehdokkaat). B-3:n työkalu; ajetaan oikeaa lokinäytettä vasten, kun se on olemassa (B-3)
- [B] Arviointi (`bouncer.eval.evaluate.run_evaluation`): temporaalinen train/test-jako, kynnykset vain opetusjoukolla (ihmisten FPR ≤ 1 %), luvut testijoukolla S8-muodossa: ihmisten FPR + 95 %:n Wilson-yläraja, luokka- ja alaluokkakohtaiset luvut, sekaannusmatriisi, simuloitu/oikea/piilotettu hyökkäys erikseen ja ablaatio ilman C:n verkostosignaaleja. Ansat pois päältä arvioinnissa; synteettisen datan lukuja ei voi kirjoittaa `metrics.json`:iin. `metrics.json` on yhä stub, koska oikeaa dataa ei ole (B-7, B-8, päätökset 028–031)

- [B] B käyttää nyt A:n `bouncer.contracts`-tyyppejä (S2); integraatiotesti ajaa A:n lokinäytteen, lukijan ja `traps.txt`:n B:n putken läpi (datasetti, `score()`, piirreraportti). Havainto A:lle: lukija antaa `Session.id`:n int-arvona, vaikka S2 sanoo str (strict-xfail-testi) (päätös 032)
- [B] Tunnetut heikkoudet (`bouncer.eval.weaknesses`): 9 kohtaa, jotka arviointi kirjoittaa oletuksena `metrics.json`:n `known_weaknesses`-kenttään (B-9, päätös 033)
- [B] Malli `lr-v1` (`bouncer.session.model`): logistinen regressio puhtaalla Pythonilla 20 piirteen päällä, 3 syytä jokaiselle päätökselle kertoimista. `score()` ajaa varmat säännöt ensin ja sitten mallin, jos `models/model.json` on olemassa; muuten käytös on ennallaan (`rules-v1`). `bouncer.eval.train.train_and_evaluate`: opetus, kalibrointi ja testi ajan mukaan, ablaatio uudelleenopetuksella. Synteettisellä datalla malli tunnistaa scraperit, jotka säännöiltä jäävät ohi; mallia ei ole tallennettu eikä `metrics.json`:ia päivitetty, koska oikeaa dataa ei ole (B-6, päätökset 034–036)
- [B] Ajoskripti `python -m bouncer.eval.run`: yksi komento lataa sessiot ja labelit (A:n näyte nyt, A:n tietokanta myöhemmin), hakee C:n IP-tiedot ja kampanjat, kokoaa datasetin, kirjoittaa piirreraportin ja opettaa ja arvioi mallin; `--write` tallentaa `metrics.json`:n ja mallin vain oikealla datalla. A:n näytteellä se kertoo, että labeloitua dataa on liian vähän (B-7, päätös 037)
- [B] Piilotettu hyökkäys (`python -m bouncer.eval.hidden --run <ajo-id>`): jäädytetty malli ja kynnykset, ei uudelleenopetusta; tunnistusosuus ansat päällä ja ilman ansoja; `--write` lisää tuloksen `metrics.json`:n `split.hidden_attack`-kenttään muuttamatta muita lukuja eikä ylikirjoita aiempaa tulosta. Valmis T+34:ää varten (B-11, päätös 038)
- [B] Proof of concept `notebooks/b/poc.py`: A:n parseri → C:n IP-tiedot ja kampanjat → B:n säännöt ja malli → C:n selitys ilman LLM:ää, A:n näytteellä ja C:n tunnusten kokeilun fixturella (synteettinen data, ei tietokantaa). B:n ja C:n integraatiotesti `tests/b/test_integration_c.py` (DNS mockattuna) (päätökset 042–043)
- [A] Kirjautumistunnus lokista: demosivun `X-Login-User`-vastausotsake `POST /login` -pyynnöstä tallentuu kenttään `Request.username`, jolloin C:n tunnusten kokeilun tunnistus toimii oikeasta Caddy-lokista (A-3/A-5, päätös 047)
- [A] `bouncer.ingest.simrun`: `X-Sim-Run`-merkinnän allekirjoitus (`sign`/`verify`) ja `IngestStats`-laskurit hylätyille merkinnöille (A-5, päätös 046)
- [X] MVP-määrittely `docs/MVP.md`: hyväksymiskriteerit, rakenne ja vaiheet paikalliselle demolle (päätökset 057–051)
- [X] Yhteinen `pyproject.toml` + `uv.lock`; `make test` ajaa kaikkien kaistojen testit, `make lint` / `make fmt` käyttävät ruffia (päätös 057)
- [A] MVP vaihe 1: demosivu `bouncer.site` (FastAPI; sivut, CSS/JS/kuva, `POST /login` → 401 + `X-Login-User`, piilotettu ansalinkki, `robots.txt` kieltää ansat) ja Caddy Docker Composella (`deploy/`: tuotanto- ja paikallinen Caddyfile). Parseri käyttää Caddyn laskemaa `client_ip`:tä (A-3, päätökset 049–050, 052)
- [A] MVP vaihe 2: simulaattorit `tools/sim/run.py` (ihmistä matkiva selaus, scraper, skanneri, tunnusten kokeilu kuudesta IP:stä, väärennetty Googlebot), allekirjoitetut merkinnät, `--dry-run`. Tarkistettu oikeaa Caddyä vasten: skanneri ja väärennetty Googlebot → `bad_bot`, ihmiset eivät koskaan `bad_bot`; tunnusten kokeilu löytyy kampanjana mutta B:n päätös puuttuu vielä (vaihe 3) (A-4/A-8)
- [B] Tunnettu heikkous: C:n käyttäytymisklusterointi niputti MVP:ssä simuloidut ihmiset kampanjaksi
- [B] Varma sääntö kirjautumishyökkäyksille: session kuuluminen C:n `credential_stuffing`- tai `distributed_login_spray`-kampanjaan (≥ 3 sessiota) → `bad_bot`, syynä kampanjan kuvaus. MVP:n Caddy-lokilla kaikki 6 tunnusten kokeilu -sessiota tunnistuvat (aiemmin `uncertain`) (päätös 053)
- [A] MVP vaihe 3: live-worker `python -m bouncer.ingest.worker` seuraa Caddy-lokia (sietää rikkinäiset rivit, katkaisun ja rotaation), sessioi allekirjoitetuilla merkinnöillä, hakee C:n IP-tiedot kerran per IP ja kampanjat, pisteyttää B:n `score()`:lla ja selittää C:n `explain()`:lla ilman LLM:ää, ja kirjoittaa päätökset storeen. Session ID on vakaa (`ip|ua|alkuaika`). MVP:n Caddy-lokilla kriteerit 1–4 täyttyvät (A-5/A-6)
- [A] MVP vaihe 4a: ohut API `bouncer.api` (`/api/summary`, `/api/sessions`, `/api/sessions/{id}`, `/api/campaigns`, `/api/metrics`) lukee workerin storea; `/api/metrics` kertoo stub- ja synteettinen-tilan sekä tunnetut heikkoudet. Tarjoilee myös `frontend/dist`:in, jos se on käännetty (A-11)
- [A] MVP vaihe 4b: React-dashboard `frontend/` (sessiolista suodattimella, session kortti: päätös, P(botti), syyt, kampanja, pyynnöt, selitys; kampanjat; mittarisivu, joka näyttää stub- ja synteettinen-tilan sekä tunnetut heikkoudet). Tarkistettu selaimessa oikealla Caddy → worker → API -datalla: MVP-kriteerit 1–6 täyttyvät (A-12, päätös 054)
- [X] MVP vaihe 5: `make demo` rakentaa ja käynnistää Caddyn, demosivun, workerin ja API:n Docker Composella (yksi image, dashboard käännetään buildissa), ajaa simulaattorit ja tarkistaa kriteerit 1–6 automaattisesti (`python -m tools.sim.check`); `make demo-down`, `make demo-logs`. Tarkistettu puhtaalta pöydältä: 6/6. README päivitetty (docs/MVP.md)
- [X] Dashboardin uusi oletusnäkymä **Yleiskuva** sivuston omistajalle: käynnissä oleva koordinoitu kirjautumishyökkäys kärjessä selkokielisenä ("tunnusta ”admin” yritettiin 6 eri IP-osoitteesta") toimenpidesuosituksineen, liikenne aikaväleittäin (Recharts), jakauma, haitalliset toimijat (Rajoita / Estä / Haaste) ja "kuinka usein olemme väärässä" simuloidulle ajolle 95 % ylärajoineen. Uusi `/api/overview`; kampanjat saavat alkuajan, kesto, IP-määrän ja otsikon (päätökset 055–056)
- [B] Suositeltu toimenpide jokaiselle päätökselle (`bouncer.session.actions`): kirjautumishyökkäys → rajoita, varma hyökkäys → estä, mallin botti → haaste, epävarma → seuraa; worker tallentaa `rule_id`:n ja `action`:in (päätös 055)
- [X] Dashboardin ammattitason UI: kaikki näkymät (yleiskuva, sessiot, kampanjat, mittarit) shadcn/ui-komponenteilla, dataviz-skillin validoima paletti (ihminen → hyvä botti → haitallinen → epävarma, CVD ΔE ≥ 9,2) vaaleaan ja tummaan tilaan, vaalea/tumma-kytkin (oletus käyttöjärjestelmän mukaan), liikennekaavio ja segmentoitu jakaumapalkki taulukkonäkymineen, toimenpidemerkit tilaväreillä + kuvakkeilla, sessiosuodatin määrineen, ja Bouncer-logoanimaatio ("ouncer" pomppaa B:stä) otsikkoon ja latausnäyttöön (pois päältä, jos käyttäjä on pyytänyt vähemmän liikettä) (päätös 057)

### Changed
- [X] Integrate the owner's latest dark glass dashboard from PR #24 with Investigations as an additional tab; preserve its default overview and components. Renumber investigation decisions to 062–063 alongside the existing UI history.
- [X] CI installs locked runtime/test dependencies, checks Python lint, and builds/tests the frontend; clean legacy lint findings without changing detection behavior.
- [A] Overnight simulation uses independent signed rounds, bounded retained evidence, full traffic snapshots plus scoped session investigations, and an opt-in 20-execution review experiment under the shared cap; deployment and evaluation instructions document measured versus unmeasured claims.
- [C] Owner-selected Featherless now supports both a bounded evidence-only decision role and a separate final advisory reviewer; actual provider/model identities are retained and native Microsoft Decision remains an explicit unavailable option until verified (decision 063).
- [A] BREAKING: Public investigation and legacy traffic APIs expose only explicitly published synthetic demonstrations; monitored visitor data requires an administrator bearer token.
- [X] Dashboard on nyt vain tumma: syvänvihreä sumea tausta, lasikortit, limenvihreä korostus (aktiivinen välilehti, pääpainikkeet) ja pilleripainikkeet; vaalea/tumma-kytkin poistettu. Kaaviovärit validoitu uudelleen vihreää lasipintaa vasten, ja "Epävarma" piirretään harmaana vinoviivoituksella. Punainen hälytyskehys ja -merkki korvattu lasikortilla ja sykkivällä lime-"Käynnissä"-merkillä; Estä-kuvakkeen sävy lämpimämpi koralli (päätös 058)
- [X] Liikennekaavio widget-tyyliin: ohuet pinotut pylväät himmeiden raitojen päällä, ei y-akselia, kokonaismäärä ja huippu otsikossa, vihje hiirellä; Recharts poistettu riippuvuuksista (JS-paketti 632 → 298 kB) (päätös 059)
- [X] Viimeistely: taulukko/kaavio-vaihto kuvakepainikkeena kortin kulmassa, pylväät leveämmät (max 24 px), jakaumapalkki pillerinä, välilehtipalkin vierityspalkki piilotettu mobiilissa
- [X] Liikennekaavio tiheämmäksi ja yhtenäisemmäksi: aikavälit 1, 2 ja 5 s mukaan ja enintään 40 palkkia (lyhyt demoajo = 1 s palkit), palkkien väli 3 px. Korjattu: välin pituus mitataan ikkunan loppuun ("nyt"), ei viimeiseen pyyntöön, jottei pyyntöjä jää ikkunan ulkopuolelle (päätös 056 täydennetty)
- [X] Värit vihreään teemaan: haitallinen botti kullanruskea (ei punainen/koralli), ihminen sininen, hyvä botti turkoosi; toimenpidemerkit erotetaan kuvakkeella + tekstillä ilman värejä. Lataus: avausruutu (pomppiva logo + lime-edistymisviiva, häivytys), näkymien muotoiset lasiskeletonit välähdyksellä; liike: kortit nousevat porrastetusti, pylväät kasvavat pohjasta, jakaumapalkki täyttyy, luvut liukuvat uuteen arvoon. Kaikki liike pois, jos käyttäjä on pyytänyt vähemmän liikettä (päätös 060)
- [X] Featherless replaces Gemini as the selected reviewer provider; S7 requires an explicit model, separates provider/model cache entries and avoids automatic retries or paid-provider fallback. Final Decision-1 orchestration remains planned, and no live key or inference request is included (decision 061, renumbered from 048).
- [X] Päätösnumerot: Featherless-arvioijan päätös numeroitu 048 → 061 (048 oli jo MVP:n `pyproject`-päätös); viittaukset päivitetty
- [A] BREAKING: S10 — kun `SIM_RUN_SECRET` on asetettu, `X-Sim-Run` hyväksytään vain oikealla `X-Sim-Sig`-allekirjoituksella; muuten kuka tahansa voisi labeloida bottinsa ihmiseksi (päätös 046, needs-ack)
- [A] BREAKING: S2 — `Request`-sopimukseen uusi valinnainen kenttä `username` (oletus `None`); vanha koodi toimii ennallaan (päätös 047, needs-ack)
- [B] Ajoskripti ja piilotetun hyökkäyksen komento käyttävät C:n virallista `ip_intel_contract()`-funktiota; sessio, joka kuuluu moneen kampanjaan, saa tunnusten kokeilu -kampanjan (päätös 042)
- [X] `AGENTS.md`: kaistarajat eivät enää estä toisen polun muokkausta; CODEOWNERS on review-apuri (päätös 044).
- [A] BREAKING S2: sample-ingest/`SessionLabel` käyttävät `str`-session-id:itä; B:n strict-xfail poistettu (A-1/S2).
- [A] S3: `bouncer.db.load_sessions` / `load_labels` + paikallinen JSON-store + `python -m bouncer.db seed` (Postgres-migraatio 001 valmis; live-writer myöhemmin) (A-5/A-6, päätös 045).
- [C] BREAKING S2: `Campaign.session_ids` ja session-id:t C:ssä ovat `str` (A:n contracts); `make_campaign()` normalisoi; duck-type lukee `user_agent` + `X-Login-User` (C-4, päätös 039).
- [C] C-4: stuffing-fixture + testi A:n `load_sample_data`-ingestiä vasten; A:n `access.sample.jsonl` smoke (ei stuffingia) (C-4).
- [C] `network_pass()` / `intel_for_sessions()`: yksi kutsu A:n workerille (S4+S5+graafi).
- [C] C-8 prep: `campaign_by_session`, `intel_by_ip_contract`, `campaign_to_api` B:n evaluateen ja A:n dashboardiin; C-11 pitch tiivistetty.
- [C] `IpIntel.country` curated ASN-prefixeistä (FI); `ip_intel_contract()` B:n eval.runille (päätös 040).
- [C] C-10 prep: `python -m bouncer.network.hidden --run <id>` — piilotetun ajon kampanja-arvio ilman uudelleensäätöä.
- [C] `ExplainCache` A:n API:lle (S7); synteettinen `campaign_metrics.fixture.json` C-4-fixtuurista; DEMO C-beat.
- [A] Local PostgreSQL/Adminer ports bind to loopback; ignore private traffic, database exports and credential files in Git and Docker build contexts. Public example credentials are explicitly marked for local development.
- [A] Hostinger-haasteen tila ja A:n kortit dokumentoitu `main`-haaran/etähaarojen todisteiden mukaan; PRE-1/A-2 merkitty vahvistusta odottavaksi eikä synteettistä fixtureä väitetä oikeaksi liikenteeksi
- [X] Repo siirretty: `Murtsi/JunctionHackathon` → `Murtsi/Bounceri`, koko historia mukana (yhdistetty uuden repon alkucommitin kanssa; `LICENSE` uuden repon versio). Vanhojen PR:ien #1–#6 linkit osoittavat yhä vanhaan repoon
- [C] Origin → `Murtsi/Bounceri`; `c/stubs-c1` rebasoitu uuden mainin päälle; juuren README listaa C:n polut + `tests/c`
- [C] C-9: shared NAT / venue-WiFi -suodatin behavior-kampanjoille; `known_weaknesses` päivitetty.
- [C] AI Router -oletus → `https://router.hostinger.com/v1`, malli `gemini-2.0-flash`; hyväksyy myös `HOSTINGER_ROUTER_API_KEY`.
- [C] Threat-feed (offline CIDR → `IpIntel.threat_label`) + `campaign_graph()` dashboardille; C-pitch-luonnos `docs/PITCH.md`.
- [C] BREAKING S4: `IpIntel.verified_bot: bool | None`; DNS-virhe → `None` (ei `False`); spoofattu PTR → `False`; lista Googlebot+Bingbot synkassa B:n kanssa (`VERIFIABLE_CRAWLER_TOKENS`, päätökset 020/026/027).
- [X] Hostinger README "Missä mennään": B-4 ja B-3/B-5 mergetty mainiin; C C-1…C-7 haarassa `c/stubs-c1`; S4 merkitty sovituksi.
- [B] Ehdotus `IpIntel.verified_bot` → `bool | None` (`None` = ei tarkistettu), ettei C:n stub leimaa oikeita Googlebotteja väärennöksiksi; vaatii S4-sopimuksen hyväksynnän (B-4, päätös 020)
- [B] `models/metrics.json` on edelleen stub, mutta `model_version` on nyt `rules-v1`; lukuja ei ole vielä mitattu (B-4)
- [X] Hostinger-suunnitelman frontend Jinja + HTMX → React (`frontend/`), tietokanta → PostgreSQL + TimescaleDB.
- [X] Juuren `README.md` kirjoitettu uusiksi projektin (Bouncer) oikealla sisällöllä; `CONTRIBUTING.md` viittaa nyt `AGENTS.md`:hen (vanha ohje oli ristiriidassa kaistahaarojen kanssa).

### Removed
- [X] Scaffoldin käyttämättömät pohjat: `docs/IDEA.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/TEAM.md`, juuren `TODO.md` (korvattu `Challenges/Hostinger-Decode-the-Noise/`-tiedostoilla), `src/README.md`, `tests/README.md`, issue-pohjat ja tyhjä `Challenges/Challenges.MD`. Lisäksi valitsematta jääneen Valio Aimo -haasteen suunnitelma ja `j26.html`. Kaikki löytyvät git-historiasta.

### Fixed
- [A] Live enforcement verification waits the server-issued TTL rather than assuming the operator machine and VPS wall clocks are synchronized.
- [C] Account model discovery preserves verified access/pricing when an output ceiling is absent, reports it as unknown, and rejects invalid supplied limits without activating inference.
- [A] Synthetic traffic refuses redirects so signed labels cannot escape the owned target; deployment excludes private JSON/TXT exports, correctly routes custom demo subdomains and recreates all processes for each checksummed release.
- [A] Investigation UI distinguishes bounded-AI eligibility from source completeness and provider availability, retaining evidence inspection for oversized snapshots.
- [C] Both model decision routes validate attack/coordination prerequisites; malformed or unrepresentable billing values remain reserved and visibly stop review without retry.
- [A] Validate complete immutable model packets before queueing paid review; oversized/incomplete cases remain inspectable and return explicit review_ineligible without reserving funds or counting execution.
- [A] Investigation details show actual model provenance, evidence gaps, review failure reasons, manual approval basis and durable spending halts without changing the existing dashboard default.
- [A] Investigation history reads the API's actual stage field; controlled enforcement status polls its dedicated endpoint and shows real effects, expiry and revocation.
- [A] Provider billing-ceiling breaches halt all further paid dispatch, including reserved queued jobs, across restarts; public campaign references redact account-bearing IDs; enforcement authenticates before bounded body parsing and records manual demo approval honestly.
- [A] Fresh restart/rotation log batches are bounded before detection; quiet cycles expire retained data and cached source metadata.
- [X] Testit eivät enää riipu kehittäjän ympäristön `SIM_RUN_SECRET`-arvosta (yhteinen `tests/conftest.py`); PoC lukee repon fixturet ilman allekirjoitusvaatimusta. Löytyi, kun Makefile vei avaimen myös `make test` -ajoon
- [B] Tunnettu heikkous päivitetty: kirjautumishyökkäykset tunnistetaan nyt C:n kampanjan kautta (053); vanha teksti väitti B:n jättävän ne epävarmoiksi
- [A] JSON-store kirjoitetaan atomisesti (väliaikainen tiedosto + `os.replace`), joten API ei koskaan lue puolikasta tiedostoa workerin kirjoittaessa
- [A] Parseri lukee Caddyn oikean aikaleiman (Unix-aika liukulukuna); aiemmin vain käsin kirjoitettujen fixturejen ISO-muoto toimi, joten yhtään oikeaa Caddy-riviä ei olisi luettu. Löytyi MVP:n vaiheen 1 tarkistuksessa oikealla Caddyllä
- [A] Virheellinen tai ristiriitainen `X-Sim-Run`-merkintä ei enää kaada lukemista: sessio jää ilman labelia ja ohitus lasketaan (päätös 046)
- [B] `python -m bouncer.eval.run --source db` lukee A:n storesta tiedon, onko data synteettistä (`bouncer.db seed` näytteestä → synteettinen), joten `--write` ei tallenna näytteen lukuja oikeiksi
- [B] Mallin syistä jätetään pois piirteet, joita sessiosta ei voi mitata (esim. tahti yhdestä pyynnöstä, otsakkeet työkalu-UA:lta) (päätös 043)
- [X] `docs/DECISIONS.md`: kaistan C päätökset 032–034 numeroitu uudelleen 039–041:ksi, koska samat numerot olivat jo kaistan B käytössä; viittaukset korjattu (README, TEAM.md, C:n kommentit, CHANGELOG)
- [B] Väärennetyn hakukonebotin sääntö tarkistaa vain Googlebotin ja Bingbotin, eli samat kuin C:n `ip_intel()` varmistaa; aiemmin oikea Applebot/DuckDuckBot/YandexBot/Baiduspider olisi leimautunut `bad_bot`iksi integraatiossa (B-4)
- [X] Hostinger-haasteen README ajan tasalle: "Missä mennään" -osio (kaistojen tila, sopimukset S1–S11, seuraavat askeleet); roolit ja stack merkitty päätetyiksi
- [X] "Missä mennään" päivitetty PR:ien #2–#5 mergen jälkeen: B-4 ja B-3/B-5-työkalut `main`issa
- [B] "Missä mennään": B-7 (arviointi) ja B-8 (ablaatio) merkitty valmiiksi; `metrics.json` yhä stub, kunnes A:n data on olemassa
