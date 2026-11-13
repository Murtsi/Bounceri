# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- [A] CI now runs the complete Python test suite instead of leaving stack checks as a commented Node.js scaffold.
- [A] Public-release preparation: English setup/status README and private vulnerability-reporting guidance; preserve synthetic ingestion fixtures and tests in Git.
- [A] S2-datatyyppien alustava ehdotus, kuuden rivin Caddy JSONL -testifixture, fixture-parseri (sessiointi + `X-Sim-Run`) ja stub-ansalista; session/campaign ID-muodot vaativat B/C-hyväksynnän ja 50 rivin stub, Postgres-ingest, live-loki ja palvelu ovat vielä kesken (A-1, luonnos `a/person-a-integration`-haarassa)
- [A] `deploy/traps.txt` lisätty B:n sääntöjen kehitystestejä varten; polut eivät ole vielä demosivustossa (A-1)
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

### Changed
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
- [B] Väärennetyn hakukonebotin sääntö tarkistaa vain Googlebotin ja Bingbotin, eli samat kuin C:n `ip_intel()` varmistaa; aiemmin oikea Applebot/DuckDuckBot/YandexBot/Baiduspider olisi leimautunut `bad_bot`iksi integraatiossa (B-4)
- [X] Hostinger-haasteen README ajan tasalle: "Missä mennään" -osio (kaistojen tila, sopimukset S1–S11, seuraavat askeleet); roolit ja stack merkitty päätetyiksi
- [X] "Missä mennään" päivitetty PR:ien #2–#5 mergen jälkeen: B-4 ja B-3/B-5-työkalut `main`issa
- [B] "Missä mennään": B-7 (arviointi) ja B-8 (ablaatio) merkitty valmiiksi; `metrics.json` yhä stub, kunnes A:n data on olemassa
