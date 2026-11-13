# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
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

### Changed
- [X] Repo siirretty: `Murtsi/JunctionHackathon` → `Murtsi/Bounceri`, koko historia mukana (yhdistetty uuden repon alkucommitin kanssa; `LICENSE` uuden repon versio). Vanhojen PR:ien #1–#6 linkit osoittavat yhä vanhaan repoon
- [B] Ehdotus `IpIntel.verified_bot` → `bool | None` (`None` = ei tarkistettu), ettei C:n stub leimaa oikeita Googlebotteja väärennöksiksi; vaatii S4-sopimuksen hyväksynnän (B-4, päätös 020)
- [B] `models/metrics.json` on edelleen stub, mutta `model_version` on nyt `rules-v1`; lukuja ei ole vielä mitattu (B-4)
- [X] Hostinger-suunnitelman frontend Jinja + HTMX → React (`frontend/`), tietokanta → PostgreSQL + TimescaleDB.
- [X] Juuren `README.md` kirjoitettu uusiksi projektin (Bouncer) oikealla sisällöllä; `CONTRIBUTING.md` viittaa nyt `AGENTS.md`:hen (vanha ohje oli ristiriidassa kaistahaarojen kanssa).

### Removed
- [X] Scaffoldin käyttämättömät pohjat: `docs/IDEA.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/TEAM.md`, juuren `TODO.md` (korvattu `Challenges/Hostinger-Decode-the-Noise/`-tiedostoilla), `src/README.md`, `tests/README.md`, issue-pohjat ja tyhjä `Challenges/Challenges.MD`. Lisäksi valitsematta jääneen Valio Aimo -haasteen suunnitelma ja `j26.html`. Kaikki löytyvät git-historiasta.

### Fixed
- [X] Hostinger-haasteen README ajan tasalle: "Missä mennään" -osio (kaistojen tila, sopimukset S1–S11, seuraavat askeleet); roolit ja stack merkitty päätetyiksi
