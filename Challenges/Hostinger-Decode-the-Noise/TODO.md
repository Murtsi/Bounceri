# Todo — Hostinger: Decode the Noise

## Nykyinen toteutustyö — 2026-11-14

2026-11-15 submission fix: public session explanations now retain fixed safe
rule/behavior observations. Rules-only normal traffic still has unverified
identity; a trained real-world model and actual-human evaluation remain open.

Työjärjestys: [modules plan.md](../../modules%20plan.md). Kaistat kuvaavat
oletusvastuita, eivät muokkauskieltoja (AGENTS.md, päätös 044).

| Työ | Tila | Näyttö / seuraava portti |
|---|---|---|
| Kriittiset korjaukset ennen ydintyötä | **Verified / committed** | Virheellisten batch-rivien ohitus/laskenta ja origin-path `//`-käsittely; fixture-importin 201/list-serialisointi; DNS unknown/dual-stack; yksityisen sessioidentiteetin säilyminen retentionin, tyhjän ikkunan ja restartin yli idle-vanhenemisella; loginin 8 KiB/ASCII-rajat. Riippumaton koodikatselmointi hyväksyi korjaukset. |
| Phase 0 — dokumentit ja lähtötason tarkistus | **In progress** | Nykytila ja moduulimatriisi sovitetaan koodiin. Python-testit/Ruff, frontend-testit/build ja Docker-image build tarkistettu. Eristetty Docker/Caddy-demo läpäisi 5/6 ehtoa; crawler-varmistus jäi tuntemattomaksi, koska DNS-varmistus ei ollut saatavilla. Tätä ehtoa eikä uutta live-deployta väitetä varmennetuksi. |
| Phase 1 — ydin ennen moduuleja | **In progress** | Migraatiot, SQL/checkpointit, rajattu IP-näyttö, scoped-case-näyttö, yksityinen import, health/backup/restore/purge ja resurssirajat varmennettu paikallisesti. Yksityinen suostumus-/keruurekisteri, digest-sidottu sessioarviointi ja withdrawal on varmennettu paikallisesti erillään simulaattorilabeleista. Native-evalin ryhmä-/aikajako, jäädytetyt artefaktit ja kulutusreceiptit on varmennettu paikallisesti. Jäljellä riippumattoman hyökkäyksen commit/reveal ja julkaisuportit; oikea ihmisdata ja riippumaton piilotettu hyökkäys puuttuvat. Live-rollout on erillinen julkaisuportti. |
| Phase 2 — Trust the Source | **Pending / unavailable** | Erillinen media-import, C2PA-validointi, näyttö, conformance-arviointi ja UI. |
| Phase 3 — Spot the Swarm | **Pending / unavailable** | Erillinen sosiaalisten tapahtumien putki, koordinaatiosignaalit ja ryhmä-/aikaholdout; nykyiset HTTP-kampanjat eivät toteuta tätä. |
| Phase 4 — Name the Technique | **Pending / unavailable** | Rajattu tekstisyöte, tuettu taksonomia/kieli, tarkat spanit ja riippumaton korpusarviointi lisenssirajoineen. |
| Phase 5 — yhteinen rollout | **Pending** | Todellisiin adaptereihin/edellytyksiin perustuvat capabilities, moduulikohtaiset review-portit ja julkaisu-/restore-/resurssitestit. |

Nykyinen HTTP-demo, worker, API/dashboard, investigations, kahden Featherless-roolin
asynkroninen review/budget-ledger ja manuaalinen synteettisen toimijan testipolitiikka
ovat toteutettu. Maksullinen review on erikseen portitettu; Native Microsoft
Decision on unavailable kunnes varmennettu. Uudet kolme moduulia ovat edelleen
`implemented=false, enabled=false`; [MODULES.md](../../docs/MODULES.md) kertoo rajat.

`models/metrics.json` on production-stub. Erillinen
[synteettinen benchmark](../../docs/EVALUATION.md) ja
[kirjattu live-mallikoe](../../docs/LIVE_AI_VALIDATION.md) eivät korvaa suostumuksellista
ihmistutkimusta tai aidosti ulkopuolisesti pidettyä hyökkäystä. Näitä ulkoisia
tehtäviä, mentorivastauksia ja palautusta ei merkitä valmiiksi toteutuskoodin perusteella.

## Historiallinen hackathon-kanban — korvattu nykyisellä vaiheistuksella

Alla säilytetään 13.11.2026 T+-suunnitelma ja sen silloiset tilat audit trailina.
Vanhat live/API/UI/Router-estot kuvaavat sen ajan tietoa, eivät nykyisiä estäjiä;
nykyiset toteutetut osat on lueteltu yllä. Historiallisia kortteja ei ole rastittu
valmiiksi ilman näyttöä niiden ulkoisista hyväksymisehdoista.

Alkuperäisen kanbanin kaistat ja sopimukset (S1–S11): `TEAM.md`.
Sizes: S ≈ 15 min, M ≈ 1 h, L ≈ half a day. `P0` = demo dies without it, `P1` = judges notice, `P2` = only if idle.
Ajat suhteessa hackin alkuun (T+0). Virallinen palautusaika: `DEADLINE = ?`

---

## Ennen alkua (kaikki yhdessä)

| ID | Card | Size | Owner | Notes |
|---|---|---|---|---|
| PRE-1 | Hostinger-VPS, domain ja AI Router -avain käsiin | S | Murtsi | Kick-off / Hostingerin piste |
| PRE-2 | Käydään `TEAM.md` läpi yhdessä | S | kaikki | 30 min — roolit päätetty (014) |
| PRE-3 | Python 3.12 + Docker toimii jokaisella | S | kaikki | |
| PRE-4 | Hostingerilta: saako DB olla muualla? Microsoft-Decision-1:n endpoint/mallitunniste ja rajat? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon? | S | Joonas | `MENTOR_QUESTIONS.md`; arvioija on Featherless (061) |

---

## Kaista A — Alusta + hyökkääjä · Murtsi

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| A-1 | T+0 → 1 | Repo scaffold + S2 `str` IDs + sample fixture/parser + `traps.txt` — **merged**; 50-row fixture + login-event schema still open | P0 | M | **DONE** (str IDs); 50-row S1 later |
| A-2 | T+1 → 4 | VPS: Docker, Caddy, TLS, domain, JSON-loki otsakkeineen — **BLOCKED: endpoint/DNS/TLS/deploy-pääsy vahvistamatta** | P0 | M | `curl https://<domain>` works and live access logs are written |
| A-3 | T+4 → 6 | Demosivusto: sivut + CSS/JS/kuvat + `POST /login` + ansapolut; **`POST /login` asettaa vastaukseen `X-Login-User: <tunnus>`** (047) — **MVP valmis** (`bouncer.site`) | P0 | M | Ansaosumat näkyvät lokissa |
| A-4 | T+6 → 7 | Pikasimulaattorit (curl-skanneri + scraper) + oikea lokinäyte `samples/`:iin — fixture on synteettinen, A-4 ei valmis | P0 | S | B ja C saavat oikeaa merkittyä dataa |
| A-5 | T+7 → 11 | Ingest: tail → `requests` → sessiointi → `sessions`; `X-Sim-Run` → `labels` | P0 | L | **MVP** `bouncer.ingest.worker`: Caddy-loki → JSON-store + päätökset; Postgres-writer myöhemmin |
| A-6 | T+11 → 12 | `load_sessions()`/`load_labels()` + worker kutsuu B/C | P0 | M | **PARTIAL** JSON-store loaders + SQL 001; Postgres wire-up next |
| A-7 | T+12 → 14 | `make deploy`: yksi komento päivittää VPS:n | P0 | M | |
| A-8 | T+14 → 18 | Täydet hyökkäyssimulaattorit: scraper, skanneri, hidas skanneri, **hajautettu tunnusten kokeilu**; merkinnät allekirjoitetaan `simrun.sign()` (046) — **MVP valmis** (`tools/sim/run.py`); hidas skanneri puuttuu | P0 | L | Ks. *monta IP:tä* alla |
| A-9 | T+18 → 20 | Playwright-"ihminen" + QR-sivu "selaa 30 s" | P0 | M | **Integraatio T+20**: ihmisdataa kertyy |
| A-10 | T+20 → 21 | **Piilotettu hyökkäys** (eri tekniikka kuin muut), yksityisesti | P0 | M | Ajetaan T+21 → 34 taustalla |
| A-11 | T+21 → 24 | Ohut API: sessiot, sessio, kampanjat, metrics, `/healthz`, `explain`-välimuisti | P0 | M | |
| A-12 | T+24 → 30 | Dashboard (React + shadcn/ui, tyypit OpenAPI:sta): sessiolista, session näkymä, kampanjanäkymä, `/metrics`-sivu, livehyökkäys-nappi | P0 | L | **Integraatio T+30** |
| A-13 | T+30 → 32 | Etusivu Hostinger AI Builderilla + linkki dashboardiin | P1 | S | Sponsorin työkalu näkyvissä |
| A-14 | T+32 → 34 | Lokin rotaatio, DB-varmuuskopio, rate limit, valvonta | P1 | M | |
| A-15 | T+34 | Paljasta piilotettu hyökkäys B:lle ja C:lle | P0 | S | **Integraatio T+34** |

**Monta IP:tä (A-8):** yhdeltä koneelta ei voi oikeasti lähettää monesta IP:stä, eikä `X-Forwarded-For`-huijausta käytetä. Lähteet: tiimin läppärit, puhelinten hotspotit, venue-verkko, VPS itse ja pilvifunktiot eri alueilla (esim. Modal — tech challenge). Lisäksi erillinen **synteettinen lokigeneraattori** isoille kampanjoille offline-testaukseen, aina merkittynä `synthetic`. Oikea maailma tuo hajautettuja botteja VPS:lle joka tapauksessa.

**Jos aikaa jää (vain A):** CRACI-runner CI:hin · demo-DB:n reset-skripti · kuormitustesti.

---

## Kaista B — Session tunnistus + arviointi · Niko

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| B-1 | T+0 → 1 | `score()`-stub + `metrics.json`-stub — **tehty** (`main`, PR #1) | P0 | S | S6, S8 `main`-haarassa |
| B-2 | T+1 → 6 | Session piirteet: tahti, aikavälien vaihtelu, staattisten resurssien osuus, 4xx, haavoittuvuuspolut, otsakkeiden johdonmukaisuus, `robots.txt` — **tehty** (`main`, PR #1; oikeaa lokia vasten B-3:ssa) | P0 | L | Piirrefunktiot + testit `tests/b` |
| B-3 | T+6 → 8 | Piirteet oikeaa lokinäytettä vasten, korjaukset — **työkalu valmis** (`b/dataset`: piirreraportti + ihmishälytykset); odottaa A:n lokinäytettä (A-4) | P0 | M | |
| B-4 | T+8 → 12 | Varmat säännöt (ansat, C:n `verified_bot`, haavoittuvuuspolut) + `reasons` — **tehty** (`b/rules`, odottaa PR:ää; ansat aktivoituvat kun A:n `traps.txt` on olemassa) | P0 | M | **Integraatio T+12**: oikea `score()` |
| B-5 | T+12 → 14 | Datasetti: `labels` + ansat + C:n varmistetut botit — **koodi valmis** (`b/dataset`); odottaa A:n `load_sessions()`/`load_labels()` (S3) ja simulaattoriluokkien nimiä | P0 | M | Labeloitu datasetti |
| B-6 | T+14 → 18 | Malli; syötteinä myös C:n `IpIntel` ja kampanjajäsenyys; 3 syytä per päätös — **koodi valmis** (`b/model`, `lr-v1`); opetus oikealla datalla odottaa A:n liikennettä | P0 | L | |
| B-7 | T+18 → 20 | Arviointi: temporaalinen jako, simuloitu vs. oikea erikseen, kynnykset (ihmisten FPR < 1 %) — **koodi valmis** (`main`) + ajoskripti `python -m bouncer.eval.run`; oikeat luvut odottavat A:n dataa (S1, S3) | P0 | M | **Integraatio T+20**: oikea `metrics.json` |
| B-8 | T+20 → 24 | Ablaatio: tulos ilman C:n verkostosignaaleja — **koodi valmis** (`main`, osa arviointia) | P1 | M | `ablation` `metrics.json`:issa |
| B-9 | T+24 → 30 | Virheanalyysi: väärät positiiviset käsin läpi → `known_weaknesses`, piirteiden korjaus | P1 | L | |
| B-10 | T+30 → 34 | Uudelleenopetus kertyneellä datalla, kalibrointi | P1 | M | |
| B-11 | T+34 → 36 | Piilotettu hyökkäys läpi **ilman uudelleenopetusta** → `split.hidden_attack` — **koodi valmis** (`b/hidden`, `python -m bouncer.eval.hidden`); ajetaan T+34 | P0 | M | **Integraatio T+34** — tulos raportoidaan sellaisenaan |
| B-12 | T+38 → 40 | Omat diat: luvut, ablaatio, heikkoudet | P0 | M | |
| B-13 | T+42 | **Lukitse** `metrics.json` + `model_version` | P0 | S | |

**Jos aikaa jää (vain B):** kalibrointikäyrä · julkinen bottidatasetti lisätestiksi · piirteiden tärkeyskuva dashboardiin (A näyttää).

---

## Kaista C — Verkosto- ja kampanjatunnistus + selitykset · Joonas

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| C-1 | T+0 → 1 | `ip_intel()`-, `find_campaigns()`- ja `explain()`-stubit + `campaign_metrics.json`-stub | P0 | S | **DONE** |
| C-2 | T+1 → 5 | `ip_intel()`: hakukonebottien varmistus (käänteinen + eteenpäin DNS), offline-ASN-tietokanta, datakeskus / koti / mobiili | P0 | M | **DONE** |
| C-3 | T+5 → 10 | Tunnusten kokeilu sessioiden yli: sama tunnus monesta IP:stä, hajautetut epäonnistuneet kirjautumiset, hidas tahti | P0 | L | **DONE** (syntettinen data; C-4 = oikea loki) |
| C-4 | T+10 → 12 | Tunnusten kokeilu oikeaa dataa vasten | P0 | M | **DONE** fixture + A ingest-smoke (`tests/c/test_c4_a_samples.py`); live lock odottaa A-8 stuffing-simua |
| C-5 | T+12 → 20 | Kampanjat: otsakesormenjälki + polkujärjestys (MinHash) + ajoituksen synkronointi → klusterointi (union-find / DBSCAN) | P0 | L | **DONE** union-find+Jaccard/MinHash; DBSCAN skip |
| C-6 | T+20 → 24 | Kampanjoiden arviointi A:n `kampanja-id`:tä vasten: puhtaus, kattavuus | P1 | M | **DONE** evaluaattori; lukitus odottaa A:n labeleita |
| C-7 | T+24 → 28 | `explain()`: AI Router, vain B:n ja C:n syiden pohjalta; tarkistus ettei selitys väitä mitään syiden ulkopuolelta; varateksti | P1 | M | **DONE** koodi + fallback; live Router kun avain saadaan |
| C-8 | T+28 → 30 | Integraatio dashboardiin (A) | P1 | S | **PREP** `network_pass` + `ExplainCache`; odottaa A-11/A-12 UI |
| C-9 | T+30 → 34 | Virheanalyysi: jaettu IP (toimisto, venue-WiFi, mobiili-NAT) → monta ihmistä näyttää yhdeltä toimijalta | P1 | M | **DONE** suodatin + `known_weaknesses` (oikea data myöhemmin) |
| C-10 | T+34 → 36 | Piilotettu hyökkäys: löytyykö kampanjana? Tulos sellaisenaan | P0 | M | **PREP** `bouncer.network.hidden` valmis; ajo odottaa A-15 paljastusta |
| C-11 | T+38 → 40 | Omat diat: kampanjat, selitykset | P0 | M | **DRAFT** valmis puhuttavaksi (`docs/PITCH.md` C-osio); diat A:n kanssa T+38 |

**Jos aikaa jää (vain C):**
- [x] kampanjagraafin visualisointidata (`campaign_graph`) — A piirtää
- [x] threat-feed-lista (`threat_prefixes.json` → `threat_label` IpIntelissä)

---

## Yhteinen loppu (T+38 → palautus)

| ID | Card | Owner | Notes |
|---|---|---|---|
| X-1 | Demokäsikirjoitus `docs/DEMO.md` + harjoitus ×2 | Murtsi vetää, kaikki | |
| X-2 | 90 s varavideo | Murtsi | Heti kun demopolku toimii |
| X-3 | Pitch `docs/PITCH.md`: ongelma → demo → luvut → kampanjat → rajoitukset | kaikki omat osionsa | |
| X-4 | README: URL, arkkitehtuuri, miten luvut lasketaan | Murtsi | |
| X-5 | Palautus | Murtsi | |

---

## Cut line

Jos aika loppuu, toimitetaan tässä järjestyksessä ja lopetetaan:

1. Integraatio T+12: oikea liikenne → sääntöpohjainen tulos → lista
2. Integraatio T+20: malli + kampanjat + `metrics.json`
3. Dashboard (A-12) + varavideo + pitch
4. Selitykset, piilotettu hyökkäys, ablaatio — sanotaan pitchissä jos jäivät kesken

## Historiallinen Blocked — ei nykyinen estolista

| ID | Card | Blocked on | Since | Owner |
|---|---|---|---|---|
| PRE-1 | Hostinger-live-tilan vahvistus | VPS/domain raportoitu olemassa oleviksi; julkista sovellusta ja AI Router -avainta ei ole todennettu | 2026-11-13 | Murtsi |
| A-2 | Julkinen VPS-deploy (Docker/Caddy/TLS) | Todennetun endpointin, DNS/TLS:n ja deploy-pääsyn tarkistus; paikallinen S3-putki ei riipu tästä | 2026-11-13 | Murtsi |
| C-8 | Integraatio dashboardiin | A-11/A-12 API + UI | — | Joonas |
| C-10 | Piilotettu hyökkäys | A-15 paljastus T+34 | — | Joonas |
| PRE-4 | Mentorivastaukset | Hostinger kick-off | — | Joonas |


### Core/module implementation checkpoint — 14 November 2026

Committed core fixes are independently reviewed. Versioned PostgreSQL schema upgrades, bounded three-query case pages with origin filtering/UI controls, and explicit stopped-worker review recovery are verified locally. Integrated checks: 492 Python tests including 20 disposable-PostgreSQL acceptance tests, Ruff, 7 frontend tests/build, repository/Compose checks; browser suite reports 36 passing checks. Browser CI runner remains pending. Main traffic still uses the JSON compatibility path: SQL repository, atomic event checkpoints, backfill/read cutover and retention are the next Phase 1 task. New modules remain unavailable. External DNS, real-human/independent-hidden evidence and Hostinger release smoke gates remain open.


### Durable traffic checkpoint — 14 November 2026

Phase 1.2 is implemented and verified locally: normalized SQL history, atomic source checkpoints/retention, stable late-event/session truth state, retained rotations/gzip recovery, explicit readers, immutable backfill and fresh rollback. Integrated backend616 tests pass with PostgreSQL; packagedDocker SQL runtime ingests21 sessions/235 synthetic requests without a JSON primary or paidcalls. Browser CI now executes the36-check suite. Live deployment/cutover is not claimed. Next work is bounded network evidence and scoped case completeness; imports, remaining operations/study evaluation and all 3 new modules remain pending.


### Network/evidence checkpoint — 14 November 2026

Phase 1.3–4 implementation is locally verified: bounded live S4 code, retained resolver/rule/config/feature observations, complete scoped campaign summaries, strict advisory review packets, and native v2 bounded/shared-NAT controls. Backend 739 tests/Ruff and packaged 21-session / 235-request SQL simulation pass, with no paid requests. Real resolver timeout remains unknown; no live deployment or real/hidden detector quality is claimed. Next: private log imports, remaining operations, consented/public evaluation data and the three new modules.


### Private import checkpoint — 15 November 2026

Phase 1.5 locally verified: bounded authenticated Caddy/normalized/combined uploads, per-line reports, credential removal/HMAC targets, availability-aware isolated local analysis, atomic private SQL/case persistence and explicit synthetic publication. Imported source context cannot create project trap/current DNS truth or unsupported training facts; paid calls/enforcement remain separately gated. Backend 888 tests with PostgreSQL, frontend 8 tests/build/36 browser checks and a private packaged HTTP import pass. Live rollout and real/hidden evaluation are not claimed. Next: health/backup/restore/resource/lifecycle operations, consent and evaluation, then new modules.
