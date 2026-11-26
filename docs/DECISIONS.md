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
| 032 | 2026-11-13 | **B käyttää A:n `bouncer.contracts`-tyyppejä (S2)**; `_provisional_types.py` jää pelkäksi uudelleenvienniksi, kunnes `tests/a/test_sample_ingest.py` tuo tyypit suoraan `contracts.py`:stä. Ristiriita `Session.id: str` vs. A:n lukijan `int` kirjataan strict-`xfail`-testinä | Kentät ovat samat kuin B:n ehdotuksessa, joten vaihto ei muuta käytöstä; B ei muokkaa A:n testiä; `xfail` hälyttää heti, kun A korjaa ID:t | Väliaikaisen tiedoston poisto (rikkoisi A:n testin), A:n testin muokkaus (A:n kaista) |
| 033 | 2026-11-13 | **Tunnetut heikkoudet listana `bouncer.eval.weaknesses.KNOWN_WEAKNESSES`**, jonka arviointi kirjoittaa oletuksena `known_weaknesses`-kenttään | AGENTS.md §7: heikkoudet raportoidaan, ei piiloteta; yksi paikka, jota B-9:n virheanalyysi täydentää | Käsin kirjoitettu lista `metrics.json`:iin (unohtuu päivittää) |
| 034 | 2026-11-13 | **Malli `lr-v1`: logistinen regressio puhtaalla Pythonilla** (IRLS + L2 = 1, luokat painotettu tasan), 20 piirrettä (17 session piirrettä + 3 C:n verkostopiirrettä), kohde = botti (good + bad) vs. ihminen; ei ansapiirrettä | Selitettävä (kertoimet → 3 syytä), deterministinen, ei riippuvuuksia (ei yhteistä `pyproject.toml`:ia, CI asentaa vain pytestin); 20 piirteelle lineaarinen malli riittää; ihmisiä on vähän → luokkapainot | scikit-learn / LightGBM + SHAP (riippuvuudet, A:n CI-muutos), gradient boosting (heikompi selitettävyys) |
| 035 | 2026-11-13 | **Opetus / kalibrointi / testi ajan mukaan:** opetusjakson myöhäisin 25 % on kalibrointia; malli opetetaan vain opetusosalla, kynnykset valitaan kalibrointiosalla. Ablaatiossa malli opetetaan uudelleen ilman verkostopiirteitä ja sille valitaan omat kynnykset. Tuotantomalli = arvioitu malli, sitä ei opeteta uudelleen koko datalla | Kynnykset samalla datalla, jolla malli opetettiin, olisivat liian optimistisia; uudelleenopetus koko datalla tekisi `metrics.json`:n luvuista toisen mallin lukuja | Kynnykset opetusdatalla; ablaatio samalla mallilla nollatuin syöttein |
| 036 | 2026-11-13 | **`score()` käyttää mallia vain, jos `models/model.json` on olemassa**; `save_model()` kieltäytyy synteettisellä datalla opetetusta ja kalibroimattomasta mallista. Syyt = 3 suurinta kerroin × standardoitu arvo -osuutta päätöksen suuntaan | Synteettisellä datalla opetettu malli ei saa päätyä tuotantoon; ilman mallia käytös = `rules-v1` | Mallitiedosto aina mukana (synteettinen malli näyttäisi oikealta) |
| 037 | 2026-11-13 | **Ajoskripti `python -m bouncer.eval.run`**: lähteet `sample` (A:n näyte, aina synteettinen) ja `db` (A:n S3); `--offline` ohittaa C:n DNS-haut; opetus vaatii ≥ 10 kumpaakin luokkaa; C:n kampanjat yhdistetään sessioon ID:n merkkijonona | Integraatiossa T+20 luvut syntyvät yhdellä komennolla ilman uutta koodia; näytettä ei voi vahingossa tallentaa oikeiksi luvuiksi; C:n `session_ids` voi olla int, kunnes S2-linjaus on mergetty | Notebook (ei toistettava), erillinen skripti per vaihe |
| 038 | 2026-11-13 | **Piilotettu hyökkäys (B-11) jäädytetyllä mallilla:** `models/model.json` ja sen kynnykset sellaisinaan, ei uudelleenopetusta. Pääluku ansat päällä (kuten tuotannossa), vertailuksi myös ilman ansoja. Tulos lisätään vain `split.hidden_attack`-kenttään; kieltäytyy stub- ja synteettisestä `metrics.json`:sta, eri mallin versiosta ja jo täytetystä kentästä | "Tulos raportoidaan sellaisenaan" (TODO B-11); ansat eivät ole kehämäisiä, koska label tulee `X-Sim-Run`-otsakkeesta, mutta muu arviointi on ilman ansoja, joten molemmat luvut näytetään; ylikirjoituksen esto estää tuloksen "parantelun" | Uudelleenopetus piilotetulla datalla, pelkkä ansat pois -luku (aliarvioisi tuotantoa) |
| 042 | 2026-11-13 | **Kun sessio kuuluu moneen C:n kampanjaan, B käyttää tarkinta: `credential_stuffing` ennen muita** (`run.CAMPAIGN_PRIORITY`) | Integraatiotesti paljasti, että sama sessio on sekä stuffing- että behavior-kampanjassa ja C palauttaa behaviorin ensin; stuffing on selittävämpi ja vastaa C:n `network_pass`-aikomusta | Ensimmäinen osuma (riippuu C:n järjestyksestä) |
| 043 | 2026-11-13 | **Mallin syihin otetaan vain sessiosta mitattavissa olevat piirteet** (`Feature.applies`): tahti ja kesto vaativat ≥ 2 pyyntöä, välien vaihtelu ≥ 3, Referer ≥ 2 sivua, otsakkeet selain-UA:n sivuja; arvo menee silti malliin | PoC:ssa yhden pyynnön sessioiden syynä luki "Keskitahti 0 pyyntöä/min (laski bottitodennäköisyyttä)", mikä on totta mallille mutta harhaanjohtavaa ihmiselle | Kaikki piirteet syinä |

Huom: numerot 015–043 voivat törmätä muiden kaistojen samanaikaisiin merkintöihin; numeroidaan uudelleen mergessä tarvittaessa.

## Kaista C — verkosto / kampanjat (2026-11-14)

*C:n päätökset numeroitu uudelleen 032–034 → 039–041, koska numerot 032–038 olivat jo kaistan B käytössä (yllä). Sisältö ennallaan.*

### 039 — S2: session- ja kampanja-ID:t merkkijonoina
Date: 2026-11-14
Context: A:n `contracts.Session.id` / `Campaign.session_ids` / `SessionLabel.session_id` on tyypitetty `str`:ksi; C:n aiemmat stubit ja testit käyttivät `int`-id:itä.
Decision: C hyväksyy S2:n merkkijonoina. `session_view.as_session_view` stringifioi aina (`str(id)`), `make_campaign()` rakentaa `tuple[str, ...]`, evaluaattori vertaa `str`-avaimilla. A:n sample-ingest stringifioi ID:t (korjattu).
Consequences: B/A voivat käyttää UUID/hash-id:itä ilman C-muutosta. Kampanja-metrics lukitaan vasta kun A:n login-stuffing -simu on merkitty `X-Sim-Run`:lla.
Revisit if: A vaihtaa id-tyypin takaisin intiksi (epätodennäköistä) tai Postgres-sarake vaatii uuid.

### 040 — IpIntel.country curated ASN-listasta, ei GeoIP
Date: 2026-11-14
Context: S4:ssä on `country`, mutta MaxMind/GeoLite lisäisi riippuvuuden ja lisenssikohinan 48 h:ssa.
Decision: `country` täytetään vain kun `asn_prefixes.json`-rivillä on eksplisiittinen `country` (nyt FI-prefixit). Muuten `None`. B:lle `ip_intel_contract()` strippaa `threat_label`.
Consequences: Demossa FI-koti/mobiili näyttää maan; globaalit cloud-IP:t jäävät ilman maata. Ei väitetä GeoIP-tarkkuutta.
Revisit if: tarvitaan oikea GeoIP pitchiin tai Hostinger tarjoaa valmiin feedin.

### 041 — C-10 hidden campaign eval ei saa uudelleensäätää
Date: 2026-11-14
Context: B-11 lukitsee mallin; C:n pitää raportoida löytyikö piilotettu ajo kampanjana ilman klusterointikynnysten säätöä.
Decision: `bouncer.network.hidden` ajaa nykyisen `find_campaigns()`:n sellaisenaan paljastetuille ajo-ID:ille. `--write` kieltäytyy synteettiseltä datalta ja ylikirjoitukselta.
Consequences: Jos kampanjaa ei löydy, se raportoidaan rehellisesti (`found_campaign: false`).
Revisit if: A:n paljastus tuo uuden label-muodon.

### 044 — Kaistarajat eivät estä toisen polun työtä
Date: 2026-11-13
Context: Hackathonissa pullonkaula (A:n S3) esti B/C:tä; tiimi pyysi, että AI/tekijä saa tehdä A-työtä C-kaistalta.
Decision: `AGENTS.md` §4/§8: kaistat = oletusvastuut + CODEOWNERS-review, ei kieltoa. Kuka tahansa saa korjata toisen polun; changelog-tunniste kertoo kaistan.
Consequences: Nopeampi integraatio; riskinä päällekkäiset editit — pidä PR:t pieninä ja pyydä omistajan review.
Revisit if: tiimi haluaa tiukan omistajuuden takaisin sunnuntaina.

### 045 — S3 paikallinen JSON-store ennen Postgres-writeria
Date: 2026-11-13
Context: B:n `eval.run --source db` tarvitsee `load_sessions`/`load_labels` heti; Compose-Postgres + writer vie kauemmin.
Decision: Ensimmäinen S3 = `.bouncer_store.json` + `python -m bouncer.db seed`. SQL-migraatio `001_init.sql` on valmiina; writer kytketään samaan rajapintaan myöhemmin.
Consequences: B/C voivat integroida ilman live-DB:tä; synteettinen store merkitään `synthetic: true`.
Revisit if: Postgres-writer on valmis → store jää vain offline-fallbackiksi.

## Public release preparation (2026-11-13)

- Local PostgreSQL and Adminer host ports bind to `127.0.0.1`. The public example credentials are suitable only for local development; exposing these tools requires a separate deployment decision.
- Keep raw visitor traffic, database exports and credentials outside Git and Docker build contexts. Commit synthetic fixtures for reproducibility.
- Preserve Git history: the release audit found a historical Stripe publishable browser key in a deleted event-page snapshot, not a private API credential. No history rewrite is required for that finding. This audit is not a guarantee that every form of sensitive data has been detected.

## Kaista A — MVP-korjaukset (2026-11-14, Niko)

### 046 — `X-Sim-Run` allekirjoitetaan (S10) · needs-ack: A, C
Date: 2026-11-14
Context: `X-Sim-Run` on B:n opetuksen ja arvioinnin oikea vastaus. Ilman tunnistusta kuka tahansa kävijä voi lähettää `X-Sim-Run: x:human` ja saada bottinsa labeloitua ihmiseksi (myrkytetty malli, väärä FPR). Lisäksi parseri kaatui virheelliseen tai ristiriitaiseen merkintään, joten yksi pahantahtoinen pyyntö pysäytti koko lukemisen.
Decision: Simulaattori lähettää `X-Sim-Sig: hex(HMAC-SHA256(SIM_RUN_SECRET, <X-Sim-Run-arvo>))` (`bouncer.ingest.simrun.sign`). Kun `SIM_RUN_SECRET` on asetettu, vain oikein allekirjoitetut merkinnät hyväksytään. Virheellinen tai ristiriitainen merkintä → sessio jää ilman labelia ja lasketaan `IngestStats`-laskuriin; lukeminen jatkuu. Molemmat otsakkeet poistetaan tallennettavista otsakkeista. Repoon commitoidut fixturet ovat luotettuja eikä niiltä vaadita allekirjoitusta.
Consequences: Tuotannossa `SIM_RUN_SECRET` on pakollinen (`.env.example`); A:n simulaattorit (A-8, A-9) käyttävät `simrun.sign()`. Ilman avainta (paikallinen kehitys) merkintöjä ei tarkisteta.
Revisit if: simulaattorit ajetaan ympäristössä, jossa avainta ei voi jakaa → IP-sallintalista lisäksi.

### 047 — Kirjautumistunnus demosivun vastausotsakkeesta (S2) · needs-ack: A, C
Date: 2026-11-14
Context: C:n tunnusten kokeilun tunnistus tarvitsee käyttäjätunnuksen, mutta Caddy ei lokita lomakkeen runkoa, eikä oikea hyökkääjä lähetä tunnusta otsakkeessa. Testiaineisto käytti `X-Login-User`-pyyntöotsaketta, jota oikeassa liikenteessä ei ole.
Decision: Demosivu (A-3) asettaa `POST /login` -vastaukseen otsakkeen `X-Login-User: <syötetty tunnus>`; Caddy lokittaa sen `resp_headers`-kenttään. Parseri tallentaa sen uuteen kenttään `Request.username` (vain `POST /login`, oletus `None`). C:n `session_view` lukee `username`-kentän jo ensimmäisenä, joten C:hen ei tarvita muutosta. Salasanaa, lomakkeen runkoa tai autentikointiotsakkeita ei koskaan lokiteta.
Consequences: Tunnusten kokeilu tunnistuu oikeasta lokimuodosta. Tunnus on henkilötieto: demo käyttää tiimin ja simulaattorien tunnuksia; oikeiden kävijöiden tunnuksia ei säilytetä pidempään kuin demo vaatii.
Revisit if: tunnukset halutaan pseudonymisoida (HMAC) ennen lokitusta.

## MVP (2026-11-14, Niko) — `docs/MVP.md`

| # | Date | Decision | Why | Alternative rejected |
|---|---|---|---|---|
| 048 | 2026-11-14 | **Yhteinen `pyproject.toml` (uv, `package = false`)**: riippuvuudet `fastapi`, `uvicorn`; dev: `pytest`, `httpx`, `ruff`; pytest lukee `src/` suoraan; `uv.lock` commitoidaan. Makefilen `test`/`lint`/`fmt` käyttävät sitä | Demosivu ja API tarvitsevat FastAPI:n; yksi toistettava ympäristö koko tiimille | `uv run --with …` jokaiseen komentoon (ei lukittu, unohtuu) |
| 049 | 2026-11-14 | **MVP ajetaan Docker Composella oikean Caddyn kanssa myös paikallisesti** (`deploy/`) | Sama kokoonpano siirtyy VPS:lle; todistaa oikean Caddy-lokimuodon | Demosivu kirjoittaa itse Caddy-muotoisen lokin (ei todista muotoa) |
| 050 | 2026-11-14 | **Paikallinen XFF-tila:** vain paikallisessa demossa Caddy luottaa `X-Forwarded-For`-otsakkeeseen (`trusted_proxies`), jotta monen IP:n hyökkäys syntyy yhdeltä koneelta; parseri käyttää Caddyn laskemaa `client_ip`:tä (sama kuin `remote_ip` ilman luotettua proxyä). Tuotannossa pois päältä | Tunnusten kokeilu monesta IP:stä on demon kohokohta; ilman tätä kaikki paikallinen liikenne näyttää yhdeltä IP:ltä | Kampanja vain VPS:llä (MVP ei näyttäisi kohokohtaa) |
| 051 | 2026-11-14 | **MVP:n dashboard Reactilla heti** (päätös 005) API:n yli | Tiimin valinta; sama käyttöliittymä jatkuu MVP:n jälkeen | Yksinkertainen HTML ensin |
| 052 | 2026-11-14 | **Demosivu polussa `src/bouncer/site/`** (TEAM.md: `src/site/`), projekti asennetaan pakettina (hatchling, src-rakenne) | Paketti nimeltä `site` törmäisi Pythonin vakiomoduuliin `site`; pakettina asennettuna `bouncer.*` toimii kaikkialla (uvicorn, Docker, skriptit) ilman `PYTHONPATH`-kikkoja | `src/site/` + `PYTHONPATH=src` jokaiseen komentoon |
| 053 | 2026-11-14 | **Varma sääntö: C:n kirjautumishyökkäyskampanja (`credential_stuffing`, `distributed_login_spray`, ≥ 3 sessiota) → `bad_bot`**; syynä kampanjan oma kuvaus. `behavior_cluster` ei laukaise sääntöä | Tunnusten kokeilu -sessio on usein yksi pyyntö, josta B ei näe mitään yksinään; C:n havainto sessioiden yli on vahva. MVP:ssä behavior_cluster niputti simuloidut ihmiset, joten se ei ole varma | Malli oppii kampanjan painon (vaatii kampanjoita opetusdatassa), kaikki kampanjatyypit (väärät positiiviset ihmisille) |
| 054 | 2026-11-14 | **MVP:n dashboard: Vite + React 19 + TypeScript + Tailwind v4 + TanStack Query (2 s päivitys), pnpm corepackin kautta; API tarjoilee käännetyn `frontend/dist`:in samasta palvelusta, oletusportti 8001.** shadcn/ui ja OpenAPI-tyypit (005–006) myöhemmin | Dashboardin liikenne ei kulje tarkkaillun Caddyn kautta (ei sotke dataa); yksi palvelu = yksi portti demossa; 8000 on usein jo varattu kehityskoneilla | Erillinen Node-palvelin, shadcn/ui heti (hitaampi MVP:hen) |
| 055 | 2026-11-14 | **Suositeltu toimenpide päätöksen perusteen mukaan** (`bouncer.session.actions`): kirjautumishyökkäys → rajoita; väärennetty crawler, haavoittuvuuspolut, ansa → estä; mallin `bad_bot` → haaste; epävarma → seuraa. Worker tallentaa `rule_id`:n ja `action`:in | IDEA.md lupaa portaat seuraa → rajoita → haaste → estä; IP-esto ei auta hajautettuun kirjautumishyökkäykseen, joten toimenpide riippuu perusteesta, ei pelkästä luokasta. Bouncer suosittelee, ei estä | Toimenpide pelkästä luokasta |
| 056 | 2026-11-14 | **Omistajan yleiskuva `/api/overview`** on dashboardin oletusnäkymä: käynnissä olevat kirjautumishyökkäykset hälytyksinä (ei `behavior_cluster`), pyynnöt aikaväleittäin (väli mukautuu datan kestoon 1 s … 15 min, enintään 40 palkkia, tyhjät alusta pois; täydennetty 2026-11-14: tiheämpi sarja), jakauma, haitalliset toimijat toimenpiteineen, ja simuloidun ajon väärät hälytykset Wilson-ylärajan kanssa. "Nyt" = uusimman pyynnön aika | Haasteen ydin on *coordinated*: kampanja kärkeen; omistaja tarvitsee kokonaiskuvan ja toimenpiteen, ei sessiotaulukkoa; tallennettu demoajo näyttää samalta myöhemminkin | Sessiolista etusivuna, kiinteä minuuttiväli (30 s demoajo = yksi palkki) |
| 057 | 2026-11-14 | **Dashboardin UI: shadcn/ui-komponentit käsin kopioituina (`components/ui/`, Radix vain Tabsille), lucide-kuvakkeet, värit CSS-muuttujina vaaleaan ja tumman tilaan erikseen; datavisualisoinnin paletti validoitu dataviz-skriptillä (luokkien järjestys kiinteä, tilavärit vain toimenpiteille ja aina kuvakkeen + tekstin kanssa)** | Haaste arvioi myös esityksen; shadcn on pinossa jo (päätös 054) ja kopioidut komponentit eivät tuo ajonaikaista riippuvuutta; validoitu paletti erottuu myös värisokeille | shadcn CLI (verkko + generoitu koodi), oma väripaletti silmämääräisesti |
| 058 | 2026-11-14 | **Vain tumma "lasi"-teema** (syvänvihreä tausta, läpikuultavat kortit, lime #c5ef5d vain käyttöliittymän korostuksena, ei datasarjana); kytkin pois. Sarjat ihminen #4a93e6 → hyvä botti #1d9e72 → haitallinen #df5f33 validoitu pintaa #1b2620 vasten (CVD ΔE ≥ 9,7, normaali ≥ 19,3); "epävarma" = harmaa + 45° vinoviivoitus | Tiimin valitsema tyyli (referenssi: tumma vihreä lasi-UI); yksi teema = vähemmän testattavaa demoon; tekstuuri erottaa de-emphasis-luokan myös värisokeille | Vaalea + tumma kytkimellä (päätös 057), lime datasarjana |
| 059 | 2026-11-14 | **Liikennekaavio omana HTML/CSS-komponenttina, ei Rechartsia**: ohuet pylväät täyskorkean himmeän raidan päällä, ei y-akselia; kokonaismäärä + huippu tekstinä, tarkat luvut vihjeessä ja taulukkonäkymässä | Tiimin valitsema tyyli (Dribbble-referenssi, tumma widget-UI); pyöreä yläpää oikein riippumatta siitä, mikä luokka on päällimmäisenä; paketti puolittuu | Recharts mukautetulla shape-funktiolla |
| 060 | 2026-11-14 | **Sarjavärit vihreään lasiteemaan**: ihminen #4f92e0 → hyvä botti #26a088 → haitallinen #bf8418 (kulta), validoitu pintaa #1b2620 vasten (CVD ΔE ≥ 11,9, normaali ≥ 15,6); toimenpiteet ilman tilavärejä (kuvake + teksti). Lataus- ja siirtymäanimaatiot CSS:llä, `prefers-reduced-motion` poistaa ne | Punainen/koralli riitelivät vihreän teeman kanssa (tiimin palaute); kulta erottuu sinisestä ja turkoosista myös värisokeille; CSS-animaatiot eivät tuo riippuvuuksia | Koralli (058), lime datasarjana, animaatiokirjasto (Framer Motion) |

`make lint` löytää 23 vanhaa huomautusta A:n ja C:n koodista (mm. `timezone.utc` → `UTC`); ei korjattu tässä, jotta muiden kesken olevaan työhön ei tule konflikteja.

### 061 — Featherless replaces Gemini for the selected reviewer (numeroitu uudelleen, oli 048: numero oli jo MVP:n käytössä)
Date: 2026-11-14
Context: The owner selected the Decision-1 plus final-review architecture and explicitly removed Gemini because no Gemini API key is available.
Decision: Use Featherless for the planned generative reviewer. Existing S7 defaults to `LLM_PROVIDER=featherless`, requires an explicit `LLM_MODEL` and `FEATHERLESS_API_KEY`, and keeps its local fallback. Hostinger is an explicit legacy explanation option and the intended Decision-1 route, subject to endpoint/model verification. No default Gemini model or automatic cross-provider fallback is used.
Consequences: Cache keys distinguish configured provider/model; SDK retries are disabled and responses are capped. Actual model access, pricing and the total $5 usage ledger remain preconditions for enabling the future orchestration path. This change does not implement final model-based verdicts or persist an API key.
Revisit if: held-out evaluation shows another available reviewer has better quality/cost, with explicit owner approval before changing provider.


### 062 — Persistent investigation evidence and conservative review accounting
Date: 2026-11-14
Context: Live investigations need durable evidence, independent assessments and a shared spending ceiling across workers.
Decision: Add SQLAlchemy investigation tables on PostgreSQL 16 in production, with SQLite for offline development. Persist redacted immutable evidence, not raw traffic or simulator labels, in model packets. Reserve the entire bounded two-stage review before queueing; cap total spending at $5, uncached configurations at 100 and outgoing requests at 200. Unknown charges remain reserved until reconciled. Only explicitly published synthetic cases are public; monitored traffic and administrative actions require bearer authentication.
Consequences: Repeated evidence/configuration requests are idempotent; failed workers do not silently retry paid calls. Missing crawler verification provenance stays unknown, even if an older worker recorded a boolean. Schema initialization runs once before concurrent services start.
Revisit if: an authenticated multi-tenant product requires migrations, per-account ledgers and separately governed publication.

### 063 — Owner-approved dual Featherless review and controlled manual enforcement
Date: 2026-11-14
Context: The owner approved implementation, then selected Featherless for both bounded decision and final review when native Microsoft Decision could not be verified through Hostinger. The owner also required preserving the existing GitHub dashboard.
Decision: Keep local detection independent. Use two explicitly identified Featherless roles, at most two requests per review, no retries or provider substitution. The bounded role sees original aggregates without local predictions; the final reviewer sees evidence and the preceding assessment. Enforce typed evidence checks and preserve uncertainty. Existing dashboard remains default; investigations are additive. Enforcement is an administrator-approved, HMAC-authenticated, actor-scoped manual test policy with 60-second default/300-second maximum expiry, actual 403/429 counters and immediate revoke. It is labelled manual_demo_override because aggregate evidence does not prove a demo actor's identity.
Consequences: Never claim Microsoft Decision ran for a Featherless call, that two calls are independent votes, or that test enforcement establishes evasion-resistant Internet blocking. Native Hostinger remains gated. Actual credentials, pricing/access metadata and a bounded validation experiment are required before live AI activation; missing access leaves an honest unavailable state.
Revisit if: evidence linkage and held-out measurements justify a different review or enforcement policy.


### 064 — Core audit hardening

2026-11-14. Demo login has a fixed 8 KiB streamed body limit and an ASCII telemetry username alphabet. Invalid parsed log records are counted and skipped; crawler lookup failures stay unknown and confirmation supports both IP families.

Session continuity metadata is private and persisted separately from retained requests. Keep each identity while its session is visible or until five idle event minutes elapse. This fixes reproduced retention/restart failures without storing duplicate requests or exposing continuity metadata in public projections. SQL persistence and atomic checkpoints remain separate required plan work.

Rejected: buffering arbitrary form bodies, treating lookup errors as spoofing, or deriving continuity only from an evictable request slice. These changes implement the owner-approved audit fixes and module plan.

### 065 — Checked PostgreSQL upgrades and bounded case history

2026-11-14. Run numbered SQL files in a single PostgreSQL transaction under an advisory lock. Record ordered file names and SHA256 checksums over UTF-8 SQL with normalized newlines/BOM; reject changed history and unsupported future versions. Validate the resulting types, keys and required defaults after pending upgrades, so a valid additive migration can introduce the columns current metadata expects. Preserve create_all only for SQLite local/tests. Existing 001 is immutable; 002 adopts the existing investigation/review/budget/enforcement schemas without replacing rows. SQL is part of the runtime wheel and deployment capsule. The natural request uniqueness constraint in 001 still requires the event-identity migration before enabling the durable traffic writer.

Case history defaults to 100 rows with validated limit/offset and server-side origin filtering before pagination. A bounded three-query read loads page cases, relevant jobs and assessments. Existing public/private checks remain mandatory; UI origin/page keys are separate and changing origin resets pagination. Offset pages follow current history rather than an immutable historical cursor.

Interrupted review recovery is an explicit operator action naming the running job and its expected worker, with confirmation that the worker has stopped. A transaction marks it unavailable/interrupted and releases only job.remaining. Dispatched pending/unknown reservations remain held, and no inference runner or retry is invoked. Automatic stale-job retry and automatic unknown-charge release were rejected.

### 066 — Execute the existing browser suite in CI

2026-11-14. Pin development-only Playwright 1.65.1 and run the existing browser checks through native Node tests and Vite's local server API. The runner starts on an ephemeral localhost port, creates isolated Chromium state, verifies nonempty checks, exits nonzero on failures, and closes browser/server even when startup or an assertion fails. CI uses Node 22.18.0 and installs Chromium system dependencies explicitly. No production bundle dependency or new UI test framework is introduced.

Verified 7 unit tests, production build and 36 browser checks locally, including the exact CI Node version. Injected assertion/startup failures exited nonzero and cleaned up resources. GitHub's Ubuntu execution remains external verification; it is not claimed as locally run.

### 067 — Durable traffic identities and source isolation

2026-11-14. Migration003 adds source-scoped external session IDs and immutable `(source_key,generation,byte_offset)` request identities while keeping internal bigint foreign keys. It removes the lossy natural uniqueness tuple; distinct identical requests stay distinct. Source rows serialize writers with checkpoint revision comparison, keeping normalized history, visibility, private resume state and explicit age pruning in one transaction. Historical readers and visible snapshots use one read transaction (PostgreSQL repeatable read; explicit SQLite read transaction).

Synthetic/non-synthetic provenance is immutable within a source. Unknown legacy origins remain unknown and cannot silently become real evaluation data. Frozen snapshot-backfill archives preserve IDs and canonical content but never invent source byte positions; they reject live batches and changed replacements. Raw source/continuity/marker state is private and excluded from SQL read-model metadata. Existing001/002 SQL files remain immutable.

Verified with disposable PostgreSQL/SQLite transaction, replay, exact multiplicity, collision, stale writer, label invalidation, provenance, archive, retention and concurrent read regressions. Runtime selection/cutover uses the same repository and is recorded in the next increment; no live Hostinger switch is implied by this schema commit.

### 068 — Explicit traffic cutover and replay-safe continuity

2026-11-14. SQL selection requires the dedicated traffic URL/source configuration; Hostinger compose generation keeps JSON unless `--traffic-sql` is supplied. Before the first SQL checkpoint, any nonempty legacy JSON or meaningful worker resume state must have an exact-byte SHA archive in the selected database. The original file is preserved. New JSON compatibility snapshots include private checkpoint/cache state so SQL cutover and fresh JSON rollback can resume rather than guess consumed offsets. Export refuses overwrite/unknown provenance and rejects checkpoint changes during capture. Older snapshots without resume state remain preserved in their archive while the new live source rebuilds from retained input logs; overlapping archives/live collections are not independent evaluation data.

The tail verifies complete consumed-prefix hashes through opened descriptors, reads bounded batches/lines, and tracks retained numeric/Caddy/gzip segments. Completed segments are revalidated even if their inode is reused; current-file inode changes cannot borrow an archived prefix identity. Unobserved deleted rotations cannot be reconstructed, and observed gaps remain explicit. This disk/decompression cost is accepted for the bounded hosted logs.

Full fresh history is normalized before view retention and only then scored in the bounded view. Committed private event ownership cannot change when late events bridge session windows. Verified marker conflicts are sticky until that identity expires; invalidated truth is removed from historical labels. Default configured historical age is 86400 seconds; age pruning and source acknowledgement share one SQL transaction and never prune visible rows. Archive/backup lifecycle and consent withdrawal remain explicit separate operations work.

Verified 616 backend tests with disposable PostgreSQL, frontend build/7 unit/36 browser checks, and an isolated packaged SQL stack with21 sessions/235 synthetic requests, advancing checkpoints, no primary JSON file and0 paid calls. The test stack's containers/network/volumes were removed. This records local implementation evidence, not a live Hostinger deployment or detector-quality result.

### 069 — Canonical client IPs at the native boundary

2026-11-14. Normalize plain IPv4/IPv6 addresses in the native parser and typed storage readers. Reject malformed/scoped addresses per record rather than allowing an invalid INET value to repeatedly abort a source transaction. Preserve opaque existing session IDs while normalizing their client identity. This closes reproduced PostgreSQL ingestion failures for malformed input, scoped IPv6 and expanded/compressed spellings; it does not infer that one IP identifies one person.

### 070 — Bounded S4 evidence and scoped review context

2026-11-14. The hosted worker selects LiveIntel around the existing S4 computation. A child performs one existing verifier pass; the parent validates its bounded protocol, caches verification/mismatch for 300 seconds and unknown outcomes for 60 seconds, caps cache at 2048 and admits at most four one-second lookups per cycle within a four-second DNS budget. Startup and cleanup time are charged; OS process creation cannot itself be preempted by Python. Capacity is not cached. DNS failures never become spoofing proof. ASN/country origin stays explicitly curated or inferred rather than pretending to be live GeoIP.

The worker captures each observation before cache eviction and retains the active trap-config hash, unique trap-path counts, finite allowlisted features and local rule IDs. Public case projection drops raw identifiers/requests/truth. Campaign relationships are derived from complete scoped member requests, with explicit source gaps/incompleteness. Intentional read-window retention is a scope limitation. The sampler includes connected campaign context up to 32 sessions; missing/oversized components remain review-ineligible rather than dropping relationships to obtain a paid review.

Packet validation rejects unknown nested keys, incoherent DNS status, invalid feature/count types, duplicate/missing/aggregate member references and inconsistent campaign counts. Decision input strips local rule IDs along with local labels/scores. Prompt version v4 reflects the new context, but coordination remains unknown and candidate relationships do not establish a common operator. Deterministic probe/trap evidence is still required for maliciousness/restrictive suggestions; all model output remains advisory.

Synthetic generator v2 adds transparent bounded-monitor/shared-NAT login controls. The previously viewed benchmark stays frozen; no new real-world accuracy or hidden-attack claim is made. Owner steering confirms permitted public data mixed with consented human activity as the intended later evaluation sources.

### 071 — Untrusted authentication bytes must not hide observations

2026-11-15. Compare administrator and controlled-actor credentials as bytes, and reject non-ASCII simulator signatures safely. Previously a non-ASCII string made compare_digest raise TypeError: admin/probe requests returned 500 and valid traffic carrying the malformed simulator signature was dropped by the tolerant parser. Invalid signatures now remove only untrusted labels, preserve traffic and increment unsigned markers. These are boundary fixes, not an expansion of actor authority or automatic enforcement.

### 072 — Bounded private import and source-context isolation

2026-11-15. POST /api/imports/traffic authenticates before reading, limits the JSON body to 10 MiB/10 seconds, and admits one job per API process. A separate thread lifetime guard retains capacity after request cancellation until the actual job finishes. The parser admits 2000 nonempty rows/256 KiB lines/seven-day time spans with fixed per-line errors and five-second parsing budget. Standard combined callbacks share the strict JSON import validator; formats/fields are not guessed.

Remove credentials, cookies, queries, fragments, URL authority, unsupported fields and supplied truth labels. Keep safe native fingerprint fields including Accept-Encoding. Retain only fixed Referer presence instead of its URL. HMAC-pseudonymize native strip/lower targets with a per-import key, documenting the case convention. Cap oversized allowed values and mark affected measurements unavailable rather than treating truncated fingerprints as complete. Generic path/header personal-data content remains a declared source-specific pre-redaction responsibility.

A fixed bounded child analyzes only sanitized records, with no provider/database/simulator environment, no DNS, no project-site traps and no learned model. Parent-owned temporary directories are cleaned on failure/kill. Safe per-session availability and native int/float/bool types survive the protocol; unsupported features and header fingerprints are excluded. The private source, safe report/provenance, redacted case and local assessment share one SQL transaction. Archives stay immutable; imports do not select the live source or enqueue paid work. Permission is owner-attested and never a trusted human/bot label.

Cases omit unknown target counts and preserve null shared-target counts when target logging is unavailable. Invalid source coverage stays incomplete, while optional missingness remains explicit. Generic imported path patterns do not establish source-site attacks; prompt v5/validators retain that boundary. CLI evaluation avoids current-DNS/project-trap labels, masks report features, keeps synthetic unlabeled origin explicit and refuses incomplete labeled native training. Public/source/consent provenance remains private; only explicitly synthetic publication exposes sanitized evidence.

Migration004 is additive BIGINT widening for real response sizes; no old SQL migration is edited. Full PostgreSQL/SQLite, parser/subprocess, cancellation, privacy, missingness, rollback, frontend/browser and packaged HTTP-import checks are recorded in the implementation plan. No live rollout or independent detector-quality claim is implied.

### 073 — Read-only operational health, recoverable archives and source erasure

2026-11-15. Keep API liveness independent from database/worker readiness. Probes use bounded read-only connections and return fixed diagnostics; worker progress, actual event age and optional review freshness remain separate. SQL heartbeat writes share the ingest transaction. JSON uses a bounded stat-matched sidecar. A matching review heartbeat declares worker/configuration availability only, never provider verification. Missing explicit review database configuration stays unknown.

Use full PostgreSQL custom archives and SQLite online backups with private adjacent checksum/schema manifests. Restore only to a distinct empty target, preserve all accounting, validate the immutable current migration ledger and never run startup initialization or an automatic upgrade. PostgreSQL client binaries are an operator prerequisite. Checksums are integrity checks for trusted backups, not authentication. Off-host storage, archive encryption and retention remain operator responsibilities.

Bind investigation origin source_id independently from its display/dedup scope. Include actual origin in newly created scoped evidence hashes so cross-source identical observations cannot reuse paid results. Preserve old hashes and ledger entries. Additive SQL005 stores runtime health; SQL006 backfills only exact known origin matches. Purge serializes with source/review writers, rejects active jobs and ambiguous unbound legacy monitored cases, removes private source/case/assessment payloads and preserves immutable financial audit/tombstone identity. Require explicitly shared traffic/investigation database configuration rather than assuming the API's default SQLite store is shared. Deletion is limited to that database; logs, exports and backups need their own deletion policy.

Add an 8 MiB retained-record byte bound alongside existing hosted count/time bounds; commit all fresh normalized history before visible eviction. Collapse duplicate cluster path comparisons without changing per-session graph semantics or thresholds. Keep the remaining quadratic unique/time-edge worst case explicit. Local resource/restore/smoke results establish bounded operation on those fixtures, not production detection quality or live rollout.

Operational review also reproduced repeated checkpoint denial from escaped lone surrogates and NUL characters in raw JSON values/keys, including otherwise ignored metadata. Validate the full raw-record text tree before it enters retention or JSONB resume storage; skip/count invalid records without inventing corrected path/header evidence. Simulator authentication values are a separate untrusted label boundary: replace invalid text only there with a fixed rejected marker, preserve the valid request and count the unsigned label. Apply the same rule to direct parsing and live tail reads; changing byte accounting alone would leave PostgreSQL resume writes broken.

When SQL is selected, the API read boundary attaches the selected stored source identity, even if a copied archive embeds its old live-source identity. The original archive metadata stays immutable. This allows creating/purging a case from its actual archived storage source without confusing it with the original live collection. JSON snapshots retain their explicit worker origin and reject conflicting configured identities.

### 074 — Consent does not supply behavior truth

2026-11-15. Add private study subjects, dedicated collection enrollments and append-only session-review revisions in additive migration007. A random pseudonymous subject ID can span multiple private non-synthetic sources; neither IP/UA nor a simulator human_real label establishes a participant identity. Record owner-held consent references/version, consent grant before a bounded awareUTC window, explicit evaluation permission, exclusive-source attestation, operator reference and actual source metadata digest or unavailable state. Enrollment alone creates no traffic truth. Real documents/identity mapping remain outside this database; these are recorded operator assertions, not independent permission or identity verification.

Separate observed manual/automated/mixed/unknown operation from benign/abusive/unknown intent. Only current approved manual/benign observations bridge to real study/human reference rows. Other observations retain provenance but stay unlabeled in the existing traffic task; they never become good_bot or bad_bot by inference. Source+native session+content digest provide composite evaluation keys; retain participant/collection groups, actual end time, review identity/revision and missing-feature masks. Keep simulator SessionLabel and SQL labels unchanged. The bridge does not train, split or authorize production metric publication.

Private inspection exports the exact native session, source missingness, digest and latest annotation revision to a new bounded private file outside Git. Every review supplies the inspected digest as well as expected revision; validate both under the source lock. Pending revisions cannot silently approve requests added after inspection. Current loading rechecks subject/consent/source/window/latest review and full session digest; changes/retention invalidate approval. Old objects/exports require fresh consent and review validation before later evaluation. CLI input16KiB/output8MiB, explicit shared traffic/investigation environment configuration, fixed errors and aggregate-only stdout avoid accidental publication.

Restrict each collection to one participant's dedicated private source initially. Shared-stream participant erasure would require additional selective removal from raw/resume/case payloads. Withdrawal locks sources consistently and atomically scrubs all enrolled subject source/review/consent payloads using existing purge, or rolls back completely when an active job/unknown legacy origin prevents safe deletion. Minimal subject/enrollment/source identities remain revoked; spending/reservations/enforcement audit retain existing policy. Other files, exports, external records and backups remain an explicit operator deletion/reconciliation responsibility. Full archive roundtrips include all study tables.

The next stage must replace legacy timestamp-only development splitting for release evidence: isolate complete actor/campaign/run groups, fit/calibration/test time windows and network context, freeze artifact bytes before test exposure, consume holdouts durably, and revalidate current consent/reviews. Public historical robot labels, simulations, reviewed actual humans and independently withheld attacks require distinct reports. No actual participants or independent attack were supplied; production metrics and all new module capability states remain unchanged.

Code review additionally reproduced a fresh-database deadlock: migration creates the financial table without its singleton, so study transactions cannot rely on that optional row as their only serializer. Current approval loading locks every selected source, then every selected subject in UUID order before per-enrollment checks. A real PostgreSQL regression forces opposing source/subject traversal and passed after the fix; no financial row is initialized or reset for this purpose. Inspection and eligible observations both retain the actual source unavailable-field mask so missing imported defaults do not appear to be measured evidence.

### 075 — Whole declared components before time partitioning

2026-11-15. The first Phase1.8 component partitions exact source/native-session/content references across explicit awareUTC fit/calibration/test windows. Connect every known actor, run and campaign identity across the entire input before assigning roles. Unknown required grouping metadata quarantines the whole known component; no synthetic unique IDs fill missing identities. Admit only a whole component whose full start/end interval fits one half-open window; quarantine straddles, gaps and outside intervals. Reject multiple versions of the same source/session and bound identity/campaign/example cardinality. Output is deterministic private metadata, including exclusions, not a published metric or independent-cohort proof.

Keep this component separate from the legacy development evaluator until a source-validated frozen orchestrator isolates role-specific network context, fits/calibrates on separate roles, freezes exact artifacts and durably consumes holdouts. Legacy source-level synthetic flags and timestamp-only --write remain an explicit publication gap to close in that integration; do not mistake a green partition test for end-to-end evaluation. External actual-human and independently withheld evidence remain required.

### 076 — Guarded native artifacts and irreversible test receipts

2026-11-15. Close unsafe legacy production writers rather than accept a new verified boolean: toggling synthetic=false on simulator rows or matching model_version does not create release evidence. Legacy write requests now fail before loading/DNS/training/writing; direct writer APIs refuse, while development evaluation and generic model serialization remain available. Production metrics/model are unchanged.

Build native references only from current guarded study approvals and bounded snapshots that exactly regenerate the current known native fixture generator. Canonical run identities/counts are checked before regeneration; checksums alone are owner-editable and cannot authenticate truth. Preserve unknown intent/classification and missing measurements, stable source/native/content references, actor/run/campaign groups, review/provenance hashes and separate human_study/simulation cohorts. Public ROBOT and genuinely hidden evidence remain unavailable. Move fixture/registry runtime implementations into the bouncer package with narrow tools compatibility exports so clean installed wheels can verify references without source-checkout tools.

Additive SQL008 stores preparations, globally reserved development/holdout unit hashes and source bindings. Reserve before fitting; development cannot become a holdout and a held-out group belongs only to its exact preparation. Canonical reservation digests and actual assignment checks prevent altered replay. Freeze artifacts once, claim before test CPU, retain consumption on failures and return only verified cached reports. Shared operations use savepoints; state/digest compare-and-swap closes SQLite deferred-transaction races, and ordered locks avoid financial-singleton assumptions. Never initialize/reset financial accounting for evaluation. Canonical report digests prevent valid-shaped cached prediction corruption; source purge scrubs private payloads/revokes receipt while retaining minimal irreversible use hashes. Active claims block purge until an explicitly stopped process is closed as interrupted. Older backup restoration requires reconciling later withdrawals/consumption; full snapshot roundtrips preserve completed claims.

Native rules or logistic preparation isolates each role and declared run before campaign inference; DNS, project traps, ambient models and truth labels are excluded from score inputs. Fit preprocessing/weights on fit only, calibrate on calibration only, independently fit the network ablation and physically omit holdout/excluded data from preparation's child. Bounded workers use fixed module choices, sanitized environments, finite typed JSON and parent-owned cleanup. Parents validate exact prediction coverage/score-label coherence and recompute separate class/FPR/uncertainty/support metrics; missing evidence cannot manufacture values or inflate denominators.

Bind exact model/threshold/config/source code, actual installed dependency runtime files/METADATA/RECORD, dependency versions/available lockfiles, interpreter/math binaries and platform. Traverse installed declared dependencies, including installed optionals conservatively, rather than maintain a fragile package allowlist. Revalidate current consent/review/content/code before use and after CPU; completed replay verifies report bytes and never rescored freshness. Operators use explicit persistent shared database environments, strict bounded UTF8 plans and new private report files outside Git/library directories; no production write or provider request occurs.

This increment implements private native preparation/evaluation and closes legacy publication gaps. Independently authored sealed/reveal attack support, actual independent data and a verified production publisher remain later gates; a green native workflow is not full Phase1.8 or full modules-plan completion.

Real PostgreSQL roundtrip tests also exposed JSONB normalizing signed zero and positive integral-exponent floating tokens. Canonical finite JSON now normalizes those forms with standard Decimal token parsing before hashing/storage, preserving ordinary float0.0/float1.0/int0. This keeps descriptor/artifact/report digests stable across SQLite and PostgreSQL without silently changing receipts. Fresh reports return the durable normalized payload; cached replay additionally requires recomputed validated report bytes to match its receipt. Native reports also expose per-class precision/recall/confusion and unknown/missing coverage, so zero observed human FPR cannot conceal missed bots or abstentions. These remain private experimental configuration-specific results, not production quality.

Two final fidelity checks closed substantive gaps before this increment was committed. Dedicated sources plus a100-source cap made the planned300+independent-subject study unreachable; storage/reference/root/CLI limits now consistently permit1000sources and256KiB plans, with351/1000-source fixture tests and1001 rejection. These identifiers do not constitute actual participant evidence. Direct native-cascade comparison also exposed double-thresholding that turned a hard-rule bad_bot/1 verdict into uncertain when model thresholds abstained. Evaluation now uses the shared scorer's exact final label; calibration uses model probabilities from calibration vectors only. Regression tests preserve2/3 benign-human fixture false alarms instead of hiding them; network ablations remain independently fitted. Both fixes received independent re-review.

### 077 — Ship current core and preserve unfinished workflow boundaries

2026-11-15. Owner explicitly requested pushing all current work live and a short remaining-work note. Capture actual native scorer input context privately with exact session/configuration binding and bounded optional metadata; public projections remain allowlisted and offline evaluation stays the default. Additive SQL009 stores independent attack commitments/reveals with private byte retention, pre-preparation timestamp and exact frozen-artifact linkage; declarations remain owner-attested, not independently verified. Registry/controller and captured-profile operator integration remain unfinished and are recorded in PROGRESS.md. No future module is enabled by shipping these foundations. Preserve current live secrets, volumes, spending/accounting and newer remote UI/simulator changes during deployment; verify actual state afterward.

### 078 — Variable private workloads with independent reference intent
Date: 2026-11-14
Context: The owner observed that repeating fixed scenarios lets a detector succeed on familiar templates rather than varied behavior.
Decision: Compose seeded stochastic actor journeys with changing timing, paths, headers, cache behavior, source mix and campaign shape. Choose fresh live entropy on every episode/restart, persist bounded private replay/intent manifests and retain the original fixed generator separately. Limit episodes to 24 actors/240 requests/120 seconds; globally pace actual private HTTP at 4 requests/second, burst 4, with 8 connections. Honor overload cooldowns and stop/deadline. Use role-independent addresses and shared realistic user agents; exclude reference intent, episode/seed identity and simulator tags from ordinary behavior headers. Unknown authorization stays unknown; no simulated DNS verification or fabricated login success is added.
Consequences: Continuous varying requests exercise the existing detector without changing its thresholds, weights or AI budget. Reference labels stay signed/private and are stripped from detector/provider input. The simulator alone mounts its rotated replay volume; recent session identities are excluded across restarts. Variety does not establish real-world or independently hidden-attack accuracy. Existing PostgreSQL state and review ceilings survive deployment.
Revisit if: consented real traffic or independently authored adversarial cases reveal gaps not represented by these procedural behaviors.
### 079 — Dashboard refresh cadence and route loading
Date: 2026-11-14
Context: The owner reported slow dashboard performance. Production profiling showed all views loaded in the initial bundle, latest activity requested the full session list, and queries refetched every two seconds.
Decision: Load non-active views on demand, cap the latest-activity request at eight sessions, refresh dashboard queries every five seconds, and shorten the branded launch overlay to 900 ms.
Consequences: The current overview keeps its traffic data and activity timestamps fresh within five seconds while transferring less data and doing less startup work. The session page retains its existing 500-row API limit.
Revisit if: operators need a tighter freshness target or production profiling points to another dominant cost.

### 080 — Landing page as the default home (needs-ack)
Date: 2026-11-15
Context: For the Junction pitch, judges and first-time visitors open bounceri.tech without context. The dashboard is built for operators and does not explain what Bounceri is, how it works or what has been measured. Decision-maker: Niko; Murtsi's earlier rule kept the owner overview as the default home.
Decision: `/` without a `tab` parameter opens a landing page (hero with the live gatehouse, problem, four-step pipeline, differentiators, measured synthetic results with their limits, Hostinger runtime, modules, call to action). The dashboard opens at `?tab=overview`; the sidebar logo returns home. All figures come from EVALUATION.md and are shown with their caveats; no market statistics without a source.
Consequences: Shared links without `tab` now land on the landing page instead of the overview. Old deep links with `tab`, `session`, `campaign` and `label` work as before.
Revisit if: the owner prefers the overview as home after the pitch, or a separate marketing domain is added.

### 081 — Submission-time historical research preview

2026-11-15. Owner set a45-minute submission deadline and atmost30minutes for one additional integration. Keep the working traffic MVP and add a narrow attributed public-data research preview instead of claiming a complete social detector. RQ2 from Zenodo13896309 is CC BY4.0,7.7MB/7816rows/99numericfeatures; first-row post deduplication yields7732posts with3866targeted/3866selectedcontrols. IDs/text/rows are not redistributed. Historical labels identify targeted posts versus selected controls, not bots, maliciousness, operator identity or present-day coordination. Actor/campaign grouping is unavailable.

Freeze SHA256 tweet-ID70/15/15 splits before fitting a predeclared mean_cosine decision stump; direction/threshold use training balanced accuracy only. Test1215:TP373/FP264/TN334/FN244,precision58.56%,recall60.45%,selected-controlFPR44.15%,F159.49%,zeroabstention. Show counts/intervals, selection bias and unverified actor/campaign independence explicitly. This weak baseline is an exploratory supplement, not production quality. Full Spot the Swarm and other future module flags remain unavailable; native production metrics/models stay untouched. The source CSV stays outside Git; only aggregate report/code/UI/source attribution ship. CLEF restricted access is not bypassed. The PDF pitch and form copy distinguish implemented traffic MVP, research preview and remaining work.

### 083 — Explain observed behavior without inventing confident verdicts

2026-11-15. The owner requested a quick reduction in uncertain verdicts before
submission. Live inspection found rules-only scoring, no trained model, and a
public projection that erased all useful reasons. Restore fixed, allowlisted
descriptions of actual rule IDs and aggregate browsing/tool observations. Never
publish private reasons, arbitrary paths or identifiers. Browser-like traffic is
described as observed behavior with unverified identity. Classification remains
uncertain when no decisive rule or calibrated model supports a stronger label;
no rushed threshold change or simulator truth is used to manufacture confidence.
### 082 — Explicit captured evidence in frozen native plans

2026-11-15. The worker already captures effective runtime inputs and the bounded
evaluation CPU supports four network/trap ablations. Connect those existing
components through the private frozen evaluator using optional plan field
`evidence_profile: captured`. Omitted profiles remain offline; retain omitted keys
so old plan normalization does not acquire new metadata implicitly. Freeze the
profile with the plan, bind captured inputs when rebuilding references, and check
the worker artifact profile both before freezing and before consuming/replaying
a holdout. A worker cannot silently downgrade a captured plan to offline.

Missing captures remain unavailable; no fresh DNS, current trap configuration or
invented human/attack evidence may substitute for them. Production publication
and independent attack integration remain separate unfinished gates. This work
is isolated from the hackathon release and does not alter live services.

### 084 — Separate observed activity from uncertain identity

2026-11-15. The owner flagged the high abstention share before submission. Add
optional, typed activity observations to public synthetic session rows. Existing
aggregate features distinguish browser-like activity, automation signals and
insufficient evidence. Session/feed badges show the observation; the original
classifier label, counts, filters and detail verdict retain uncertainty. Explain
that assets do not prove a human and tool signatures do not prove abuse. This is
an evidence presentation change, with no trained model or accuracy improvement
claimed. Keep the current design's neutral badge and existing drill-down.

### 085 — Distinguish activity observations with color

2026-11-15. The owner requested distinct activity colors because every uncertain
observation looked like missing evidence. Use cyan for browser-like observations,
violet for automation signals and the existing gray for insufficient evidence.
Retain existing human/verified-bot/bad-bot colors. Apply the color to the badge's
dot, text, outline and subtle fill; preserve readable status names and uncertainty
tooltips. Color conveys observation type, not a stronger classifier verdict.

### 086 — Activity breakdown in the traffic graph

2026-11-15. Session badges exposed browser-like and automation observations, but
the traffic graph still aggregated all uncertain sessions into gray. Add a
parallel `timeline.activity_points` projection with mutually exclusive categories:
confirmed local verdicts retain their class, while uncertain sessions are split
into browser-like, automation-signal and insufficient-evidence observations.
Reuse the same observation function for private/public views and the same colors
for graph segments, legend and badges. Every request contributes once; original
four-label points, distribution, human-error metrics and classifier outputs stay
unchanged. The frontend falls back to the original graph for older API responses.
Graph copy explains that observations do not establish human identity or intent.

### 087 — Make benchmark evidence visible in Metrics

2026-11-26. Inspired by [NoiseMap’s method and traceability view](https://github.com/AlexAnsart/DecodeTheNoise/blob/main/frontend/src/method/Traceability.tsx), reuse Bounceri’s existing published evaluation in Metrics and Investigations. Give readers direct links to the benchmark method, aggregate JSON and exact frozen commit. Keep the synthetic benchmark available when the separate runtime metrics endpoint fails. The dashboard reads the published artifact on request; detector results and evaluation data are unchanged.
