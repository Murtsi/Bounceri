# Decision log

Append-only, newest last. One entry per decision that someone might question on Sunday.

| # | Date | Decision | Why | Alternative rejected |
|---|---|---|---|---|
| 001 | | Stack-agnostic scaffold, code in `src/` | Fastest start, no lock-in before the idea is fixed | Pre-generated framework boilerplate |
| 002 | | Postgres in Docker, not SQLite | Seed/reset parity with demo env, real SQL | SQLite (faster start, weaker parity) |
| 003 | | Trunk-based with 1-reviewer PRs | Merge speed during the event | GitFlow |

## Template

```
### NNN — <decision>
Date: YYYY-MM-DD
Context: <constraint or force>
Decision: <what we did>
Consequences: <what gets easier, what gets harder>
Revisit if: <trigger>
```

---

## Stack (2026-11-13)

Päätetty ennen hackin alkua. Koskee kaikkia haasteita, joita repossa suunnitellaan; haastekohtaiset päätökset kirjataan haastekansioon.

| # | Date | Decision | Why | Alternative rejected |
|---|---|---|---|---|
| 004 | 2026-11-13 | **Backend: Python 3.12 + FastAPI + Pydantic v2**, paketinhallinta `uv`, lint/format `ruff`, testit `pytest` | Tunnistus ja ML ovat Pythonia (scikit-learn, LightGBM, polars) → yksi kieli koko backendille; FastAPI tuottaa OpenAPI-skeeman automaattisesti | Node/TypeScript-backend (ML-kirjastot heikompia), Go (hidas iteroida 48 h:ssa) |
| 005 | 2026-11-13 | **Frontend: TypeScript + React 19 + Vite + Tailwind CSS v4 + shadcn/ui + TanStack Query**, kaaviot Recharts, paketinhallinta `pnpm` | Moderni ja nopea kehittää; shadcn/ui antaa siistin dashboardin ilman designeria; käännetään staattisiksi tiedostoiksi, jotka Caddy tarjoilee → ei erillistä Node-palvelinta VPS:lle | Next.js (SSR:ää ei tarvita, raskaampi deploy), Jinja + HTMX (nopea mutta ei "trendikäs"), SvelteKit (pienempi ekosysteemi) |
| 006 | 2026-11-13 | **API-sopimus: FastAPI:n OpenAPI → `openapi-typescript` → frontendin tyypit** | Backendin ja frontendin välinen sopimus generoidaan, ei kirjoiteta käsin kahteen kertaan | Käsin ylläpidetyt tyypit |
| 007 | 2026-11-13 | **Tietokanta: PostgreSQL 16 + TimescaleDB-laajennus**, Docker-image `timescale/timescaledb` | Pyyntölokit ovat aikasarjaa: hypertable + continuous aggregates (dashboardin minuuttikäyrät) + pakkaus; silti tavallista Postgresia; mahdollinen MLH *Best Use of Tiger Data* -sivupalkinto (tarkistettava, kelpaako self-hosted) | Pelkkä Postgres (toimii, mutta aikasarjat käsin), ClickHouse (ylimitoitettu), SQLite (ei rinnakkaisia kirjoittajia) |
| 008 | 2026-11-13 | **DB-yhteys `psycopg` 3 ilman ORM:ää; migraatiot numeroituina SQL-tiedostoina** `src/bouncer/db/migrations/NNN_*.sql` | SQL on luettavaa ja katselmoitavaa; B ja C tekevät puhtaita funktioita eivätkä koske tietokantaan | SQLAlchemy + Alembic (enemmän ceremoniaa kuin hyötyä 48 h:ssa) |
| 009 | 2026-11-13 | **Taustatyöt: oma Python-worker-kontti silmukalla**, ei jonoa | Yksi kirjoittaja tietokantaan (kaista A), ei Redis/Celery-ylläpitoa | Celery + Redis |
| 010 | 2026-11-13 | **LLM: Hostinger AI Router OpenAI-yhteensopivalla SDK:lla**, malli ympäristömuuttujasta `LLM_MODEL` | Haaste tarjoaa krediitit (yksi avain, yksi yhteinen saldo, 150+ mallia; myös Anthropic-SDK-yhteensopiva) → malli vaihdettavissa koodia muuttamatta. Yhteinen saldo → selitykset välimuistiin, ei LLM-kutsua jokaisesta sessiosta | Suora yhteys yksittäiseen palveluntarjoajaan |
| 011 | 2026-11-13 | **Ajoympäristö: Docker Compose Hostinger-VPS:llä, Caddy 2 edessä** (automaattinen TLS, JSON-access-loki), deploy `make deploy` (ssh + `git pull` + `docker compose up -d --build`) | Haaste vaatii Hostingerin; yksi kone, yksi komento | Kubernetes, PaaS |
| 012 | 2026-11-13 | **Muutokset kirjataan aina `CHANGELOG.md`:hen ja päätökset tähän tiedostoon**; CI tarkistaa changelogin | Tiimi ja AI-agentit näkevät mitä on muuttunut ilman git-historian kaivamista; pitch ja palautus kirjoitetaan changelogista | Luotetaan commit-viesteihin |
| 013 | 2026-11-13 | **Hostingerin omat työkalut käyttöön:** VPS:n hallinta, deploy ja domain **Hostinger Connectorin / MCP-palvelimen** kautta (Claude Code, Cursor, VS Code); etusivu **Hostinger AI Builderilla** | Sponsorin työkalujen näkyvä käyttö = track fit; MCP:llä deploy suoraan editorista ilman käsin SSH-säätöä. VPS:n one-click-templateja (Ollama, n8n, Node.js, Python) ei käytetä — oma Docker Compose on toistettavampi | Pelkkä käsin SSH; dashboardin tekeminen AI Builderilla (tarvitsee live-dataa API:sta) |

Revisit if: tiimissä ei ole ketään, joka osaa Reactia → vaihdetaan frontend Jinja + HTMX:ään (päätös 005), backend ei muutu.

## Roolit (2026-11-13)

| # | Date | Decision | Why | Alternative rejected |
|---|---|---|---|---|
| 014 | 2026-11-13 | **Hostinger-roolit: A (alusta + hyökkääjä) = Murtsi, B (session tunnistus + arviointi) = Niko, C (verkosto, kampanjat, selitykset) = Joonas**; omistajuus pakotetaan `.github/CODEOWNERS`-tiedostolla | Tiimin oma valinta; jokaisella kaistalla yksi omistaja ja yksi katselmoija | — |

## Kaista B — session tunnistus (2026-11-13)

| # | Date | Decision | Why | Alternative rejected |
|---|---|---|---|---|
| 015 | 2026-11-13 | **`metrics.json` (S8) asuu `models/metrics.json`:ssä**; stubissa kaikki luvut `null` ja `"stub": true`, `model_version="stub-v0"` | Luvut kuuluvat mallin versioon (`models/`); `null` ei voi sekoittua mitattuun lukuun, toisin kuin 0 tai TEAM.md:n esimerkkiarvot | Esimerkkiluvut stubissa (näyttäisivät oikeilta dashboardissa), `src/bouncer/eval/`-kansio (koodia, ei artefakteja) |
| 016 | 2026-11-13 | **B:n väliaikaiset tyypit `src/bouncer/session/_provisional_types.py`:ssä** kunnes A:n `contracts.py` (S2) on `main`-haarassa; juuren `pyproject.toml` puuttuu, joten B:n testit ajetaan `uv run --no-project --python 3.12 --with pytest pytest tests/b` ja `tests/b/conftest.py` lisää `src/`:n polulle. B ei tarvitse ajonaikaisia riippuvuuksia (pelkkä stdlib) | B pääsee aloittamaan odottamatta A:ta eikä koske A:n tiedostoihin; `src/bouncer/` jätetään namespace-paketiksi ilman `__init__.py`:tä | B kirjoittaa `contracts.py`:n tai `pyproject.toml`:n itse (A:n / yhteisiä tiedostoja) |
| 017 | 2026-11-13 | **Tahtipiirteet:** `requests_per_min = 60·(n−1) / max(kesto, 1 s)` (alle 2 pyyntöä → 0); `peak_requests_per_min` = suurin pyyntömäärä liukuvassa 60 s ikkunassa; `interarrival_cv` vaatii ≥ 3 pyyntöä, muuten `None` (= ei dataa, ei nolla) | (n−1) väliä on oikea tahti; 1 s minimikesto estää nollalla jakamisen samalla aikaleimalla; huippuikkuna löytää purskeen pitkän session sisältä, jonka keskiarvo piilottaisi | Jakaja n / kesto (yliarvioi lyhyet sessiot), kiinteät minuuttilokerot (purske voi jakautua kahteen) |
| 018 | 2026-11-13 | **Haavoittuvuuspolut ja otsakkeet:** `VULN_PATH_PATTERNS` (`features.py`) on *piirre*, ei ansa — ansat tulevat A:n `traps.txt`:stä (S11) ja ovat eri asia, koska niitä käytetään labeleina. Otsakkeiden johdonmukaisuus tarkistetaan vain HTML-pyynnöistä selaimeksi esittäytyvältä UA:lta: `Accept` + `Accept-Language` aina, `Sec-Fetch-Mode` Chrome/Edge ≥ 76, Firefox ≥ 90, Safari ≥ 17, `Sec-CH-UA` Chromium ≥ 89 | Resurssipyynnöissä selaimet lähettävät eri otsakkeet → väärät positiiviset; versiokynnykset seuraavat sitä, milloin selaimet alkoivat lähettää otsakkeita; ansat erillään, jotta ne voidaan poistaa mallin syötteistä arvioinnissa | Kaikkien pyyntöjen tarkistus, UA-kirjaston käyttö (riippuvuus, ei tarvita) |
| 019 | 2026-11-13 | **Haavoittuvuuspoluista varma `bad_bot` vasta ≥ 2 eri polusta**; yksi osuma on vain havainto | Ihmisten FPR < 1 % on tärkein luku: yksittäinen `/wp-login.php` voi tulla ihmiseltä (vanha kirjanmerkki, väärä sivusto), kaksi eri skannauspolkua ei käytännössä koskaan | Yksi osuma riittää (enemmän väärät positiiviset), ≥ 3 (päästää lyhyet skannerit) |
| 020 | 2026-11-13 | **S4: `IpIntel.verified_bot: bool \| None`**, jossa `None` = ei tarkistettu; väärennetyn hakukonebotin sääntö laukeaa vain arvolla `False` | Pelkkä `bool` ei erota "ei botti" ja "ei tarkistettu" -tapauksia. **Hyväksytty** B:n ehdotuksena + C:n toteutuksena (ks. 027) | `bool` + erillinen `checked`-kenttä (kaksi kenttää yhden asian kuvaamiseen) |
| 021 | 2026-11-13 | **Sääntöjen järjestys: varmistettu crawler > ansa > väärennetty crawler > haavoittuvuuspolut**; ansat luetaan A:n `deploy/traps.txt`:stä (polku per rivi, `#` = kommentti, kirjainkoko ja lopun `/` normalisoidaan), puuttuva tiedosto = ei ansoja | DNS-varmistusta ei voi väärentää, mutta oikea crawler voi seurata piilolinkkiä ansaan → A:n kannattaa kieltää ansat `robots.txt`:ssä. Ristiriita näkyy syissä | Ansa aina ensin (oikea Googlebot voisi päätyä `bad_bot`iksi) |
| 022 | 2026-11-13 | **Säännöt eivät koskaan päätä `human`**; ilman sääntöosumaa tulos on `uncertain` (score 0.5) ja enintään 3 pehmeää havaintoa syinä | Ihmiseksi luokittelu vaatii kalibroidun kynnyksen (B-7); havainnot antavat `explain()`:lle sisältöä jo ennen mallia | Ihmiseksi oletuksena (FPR-luku olisi merkityksetön) |
| 023 | 2026-11-13 | **Simulaattoriluokat → label eksplisiittisellä listalla** (`SIM_CLASS_TO_LABEL`; `human*` → `human`); tuntematonta luokkaa ei arvata, vaan se jää pois datasetistä ja näkyy `unmapped_classes`-laskurissa | Väärin arvattu label vääristäisi FPR:n huomaamatta; laskuri paljastaa heti, jos A lisää uuden simulaattorin | Tuntematon → `bad_bot` (ihmissimulaattori uudella nimellä nostaisi FPR:ää) |
| 024 | 2026-11-13 | **Oikean vastauksen etusija: `X-Sim-Run` > DNS-varmistus > ansa**; ristiriitaa ei ratkaista ylikirjoittamalla, vaan se listataan `conflicts`-kenttään | Simulaattorin label on tunnettu totuus; jos simuloitu ihminen osuu ansaan, vika on ansassa tai simulaattorissa, ja se pitää korjata eikä piilottaa | Ansa aina voittaa (piilottaisi näkyvän ansan bugin) |
| 025 | 2026-11-13 | **Piilotetun hyökkäyksen ajot (`exclude_run_ids`) jätetään datasetistä kokonaan pois**, myös labeloimattomista; labeloimaton oikea liikenne pidetään mukana vain jakaumia varten (ei opetukseen eikä testiin) | Piilotettu hyökkäys ei saa vuotaa opetukseen (AGENTS.md §7); labeloimattomasta liikenteestä näkee, miltä oikea maailma näyttää | Labeloimattomat oletuksena ihmisiksi (osa on botteja → FPR-luku valehtelisi) |
| 026 | 2026-11-13 | **Väärennetyn crawlerin sääntö koskee vain crawlereita, jotka C:n `ip_intel()` oikeasti varmistaa** (nyt Googlebot, Bingbot); lista pidetään samana kuin C:n `network/bots.py` (`VERIFIABLE_CRAWLER_TOKENS`) | `verified_bot=False` tarkoittaa väärennöstä vain, jos C on tarkistanut juuri sen crawlerin; muuten oikea Applebot ym. leimautuisi `bad_bot`iksi | Kaikki tunnetut crawlerit (väärät positiiviset integraatiossa) |
| 027 | 2026-11-13 | **S4 lukittu: DNS-virhe (timeout/herror/gaierror) → `verified_bot=None`**; `False` vain kun PTR saatiin ja forward-confirm epäonnistui spoofina, tai PTR ei ole Googlebot/Bingbot. C hyväksyy 020. | Oikea Googlebot + hetkellinen DNS-virhe ei saa laukaista B:n fake-crawler -sääntöä | DNS-virhe → `False` (väärät positiiviset) |
| 028 | 2026-11-13 | **Temporaalinen jako `started_at`-ajan mukaan**, oletuksena myöhäisin 30 % testiin; ajot, joilla on sessioita rajan molemmin puolin, raportoidaan (`straddling_runs`) | Satunnainen jako vuotaisi saman hyökkäysajon molemmille puolille; rajan yli jatkuva ajo tekee testistä helpomman kuin täysin uusi hyökkäys, joten se näytetään | Satunnainen / ajoittain ositettu jako |
| 029 | 2026-11-13 | **Kynnykset vain opetusjoukolla:** botti-kynnys = pienin pistemäärä, jolla ihmisten FPR ≤ 1 %; ihminen-kynnys = suurin pistemäärä (< botti-kynnys), jonka alle jää ≤ 5 % boteista; välissä `uncertain`. Ilman ihmisiä opetusjoukossa kynnyksiä ei kalibroida | IDEA.md:n FPR-tavoite on pääluku; ohi menevä botti on halvempi virhe kuin estetty ihminen, siksi löysempi 5 % | Kynnykset testijoukolla (vuotaa), yksi kynnys ilman epävarma-vyöhykettä |
| 030 | 2026-11-13 | **Arvioinnissa pisteyttäjä ajetaan ilman ansoja, ja DNS-labeloidut rivit jätetään luvuista pois** (määrä raportoidaan `data.excluded_dns_labelled`) | Ansat ja DNS-varmistus ovat sekä labeli että varma sääntö → kehämäinen, luvut olisivat automaattisesti 100 % | Ansapiirre mukana (ARCHITECTURE.md §5 kieltää) |
| 031 | 2026-11-13 | **`metrics.json`:iin lisätään `human_fpr_ci95_upper` (Wilson), `confusion_axes` ja `data` (otoskoot, raja, `synthetic`, poistetut rivit)**; `write_metrics()` kieltäytyy synteettisestä datasta ja kalibroimattomista kynnyksistä | 0/40 ihmistä on 0 % mutta yläraja ~9 % → väite "FPR < 1 %" vaatii n ≳ 300 ihmissessiota; synteettinen tulos ei saa päätyä dashboardiin oikeana lukuna. Kentät ovat lisäyksiä, eivät muuta S8:n olemassa olevia kenttiä | Pelkkä pisteestimaatti |

Huom: numerot 015–031 voivat törmätä muiden kaistojen samanaikaisiin merkintöihin; numeroidaan uudelleen mergessä tarvittaessa.


## Public release preparation (2026-11-13)

- Local PostgreSQL and Adminer host ports bind to `127.0.0.1`. The public example credentials are suitable only for local development; exposing these tools requires a separate deployment decision.
- Keep raw visitor traffic, database exports and credentials outside Git and Docker build contexts. Commit synthetic fixtures for reproducibility.
- Preserve Git history: the release audit found a historical Stripe publishable browser key in a deleted event-page snapshot, not a private API credential. No history rewrite is required for that finding. This audit is not a guarantee that every form of sensitive data has been detected.
