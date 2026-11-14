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

### 048 — Featherless replaces Gemini for the selected reviewer
Date: 2026-11-14
Context: The owner selected the Decision-1 plus final-review architecture and explicitly removed Gemini because no Gemini API key is available.
Decision: Use Featherless for the planned generative reviewer. Existing S7 defaults to `LLM_PROVIDER=featherless`, requires an explicit `LLM_MODEL` and `FEATHERLESS_API_KEY`, and keeps its local fallback. Hostinger is an explicit legacy explanation option and the intended Decision-1 route, subject to endpoint/model verification. No default Gemini model or automatic cross-provider fallback is used.
Consequences: Cache keys distinguish configured provider/model; SDK retries are disabled and responses are capped. Actual model access, pricing and the total $5 usage ledger remain preconditions for enabling the future orchestration path. This change does not implement final model-based verdicts or persist an API key.
Revisit if: held-out evaluation shows another available reviewer has better quality/cost, with explicit owner approval before changing provider.

