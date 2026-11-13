# Todo — Junction kanban (Hostinger: Decode the Noise)

Kolme kaistaa, jokainen tekee **vain omia korttejaan** järjestyksessä ylhäältä alas. Omistajuus ja sopimukset (S1–S11): `TEAM.md`.
Sizes: S ≈ 15 min, M ≈ 1 h, L ≈ half a day. `P0` = demo dies without it, `P1` = judges notice, `P2` = only if idle.
Ajat suhteessa hackin alkuun (T+0). Virallinen palautusaika: `DEADLINE = ?`

---

## Ennen alkua (kaikki yhdessä)

| ID | Card | Size | Owner | Notes |
|---|---|---|---|---|
| PRE-1 | Hostinger-VPS, domain ja AI Router -avain käsiin | S | Murtsi | Kick-off / Hostingerin piste |
| PRE-2 | Käydään `TEAM.md` läpi yhdessä | S | kaikki | 30 min — roolit päätetty (014) |
| PRE-3 | Python 3.12 + Docker toimii jokaisella | S | kaikki | |
| PRE-4 | Hostingerilta: saako DB olla muualla? Onko Gemini AI Routerissa? Kelpaako self-hosted TimescaleDB Tiger Data -palkintoon? | S | Joonas | |

---

## Kaista A — Alusta + hyökkääjä · Murtsi

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| A-1 | T+0 → 1 | Repo-rakenne, `contracts.py`, stub-lokinäyte, `traps.txt`, `X-Sim-Run`-muoto | P0 | M | S1, S2, S10, S11 `main`-haarassa |
| A-2 | T+1 → 4 | VPS: Docker, Caddy, TLS, domain, JSON-loki otsakkeineen | P0 | M | `curl https://<domain>` toimii, loki kirjoittuu |
| A-3 | T+4 → 6 | Demosivusto: sivut + CSS/JS/kuvat + `POST /login` + ansapolut | P0 | M | Ansaosumat näkyvät lokissa |
| A-4 | T+6 → 7 | Pikasimulaattorit (curl-skanneri + scraper) + oikea lokinäyte `samples/`:iin | P0 | S | B ja C saavat oikeaa merkittyä dataa |
| A-5 | T+7 → 11 | Ingest: tail → `requests` → sessiointi → `sessions`; `X-Sim-Run` → `labels` | P0 | L | Sessiot kertyvät tietokantaan |
| A-6 | T+11 → 12 | `load_sessions()`/`load_labels()` Postgresista + worker kutsuu stubeja | P0 | M | **Integraatio T+12** |
| A-7 | T+12 → 14 | `make deploy`: yksi komento päivittää VPS:n | P0 | M | |
| A-8 | T+14 → 18 | Täydet hyökkäyssimulaattorit: scraper, skanneri, hidas skanneri, **hajautettu tunnusten kokeilu** | P0 | L | Ks. *monta IP:tä* alla |
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
| B-1 | T+0 → 1 | `score()`-stub + `metrics.json`-stub | P0 | S | S6, S8 `main`-haarassa |
| B-2 | T+1 → 6 | Session piirteet: tahti, aikavälien vaihtelu, staattisten resurssien osuus, 4xx, haavoittuvuuspolut, otsakkeiden johdonmukaisuus, `robots.txt` | P0 | L | Piirrefunktiot + testit `tests/b` |
| B-3 | T+6 → 8 | Piirteet oikeaa lokinäytettä vasten, korjaukset | P0 | M | |
| B-4 | T+8 → 12 | Varmat säännöt (ansat, C:n `verified_bot`, haavoittuvuuspolut) + `reasons` | P0 | M | **Integraatio T+12**: oikea `score()` |
| B-5 | T+12 → 14 | Datasetti: `labels` + ansat + C:n varmistetut botit | P0 | M | Labeloitu datasetti |
| B-6 | T+14 → 18 | Malli; syötteinä myös C:n `IpIntel` ja kampanjajäsenyys; 3 syytä per päätös | P0 | L | |
| B-7 | T+18 → 20 | Arviointi: temporaalinen jako, simuloitu vs. oikea erikseen, kynnykset (ihmisten FPR < 1 %) | P0 | M | **Integraatio T+20**: oikea `metrics.json` |
| B-8 | T+20 → 24 | Ablaatio: tulos ilman C:n verkostosignaaleja | P1 | M | `ablation` `metrics.json`:issa |
| B-9 | T+24 → 30 | Virheanalyysi: väärät positiiviset käsin läpi → `known_weaknesses`, piirteiden korjaus | P1 | L | |
| B-10 | T+30 → 34 | Uudelleenopetus kertyneellä datalla, kalibrointi | P1 | M | |
| B-11 | T+34 → 36 | Piilotettu hyökkäys läpi **ilman uudelleenopetusta** → `split.hidden_attack` | P0 | M | **Integraatio T+34** — tulos raportoidaan sellaisenaan |
| B-12 | T+38 → 40 | Omat diat: luvut, ablaatio, heikkoudet | P0 | M | |
| B-13 | T+42 | **Lukitse** `metrics.json` + `model_version` | P0 | S | |

**Jos aikaa jää (vain B):** kalibrointikäyrä · julkinen bottidatasetti lisätestiksi · piirteiden tärkeyskuva dashboardiin (A näyttää).

---

## Kaista C — Verkosto- ja kampanjatunnistus + selitykset · Joonas

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| C-1 | T+0 → 1 | `ip_intel()`-, `find_campaigns()`- ja `explain()`-stubit + `campaign_metrics.json`-stub | P0 | S | S4, S5, S7, S9 `main`-haarassa |
| C-2 | T+1 → 5 | `ip_intel()`: hakukonebottien varmistus (käänteinen + eteenpäin DNS), offline-ASN-tietokanta, datakeskus / koti / mobiili | P0 | M | Googlebot-väärennös tunnistetaan |
| C-3 | T+5 → 10 | Tunnusten kokeilu sessioiden yli: sama tunnus monesta IP:stä, hajautetut epäonnistuneet kirjautumiset, hidas tahti | P0 | L | Testit `tests/c` stub-dataa vasten |
| C-4 | T+10 → 12 | Tunnusten kokeilu oikeaa dataa vasten | P0 | M | **Integraatio T+12** |
| C-5 | T+12 → 20 | Kampanjat: otsakesormenjälki + polkujärjestys (MinHash) + ajoituksen synkronointi → klusterointi (union-find / DBSCAN) | P0 | L | **Integraatio T+20** |
| C-6 | T+20 → 24 | Kampanjoiden arviointi A:n `kampanja-id`:tä vasten: puhtaus, kattavuus | P1 | M | `campaign_metrics.json` |
| C-7 | T+24 → 28 | `explain()`: AI Router, vain B:n ja C:n syiden pohjalta; tarkistus ettei selitys väitä mitään syiden ulkopuolelta; varateksti | P1 | M | |
| C-8 | T+28 → 30 | Integraatio dashboardiin (A) | P1 | S | **Integraatio T+30** |
| C-9 | T+30 → 34 | Virheanalyysi: jaettu IP (toimisto, venue-WiFi, mobiili-NAT) → monta ihmistä näyttää yhdeltä toimijalta | P1 | M | Kirjattu `known_weaknesses`:iin |
| C-10 | T+34 → 36 | Piilotettu hyökkäys: löytyykö kampanjana? Tulos sellaisenaan | P0 | M | **Integraatio T+34** |
| C-11 | T+38 → 40 | Omat diat: kampanjat, selitykset | P0 | M | |

**Jos aikaa jää (vain C):** kampanjagraafin visualisointidata (A piirtää) · threat-feed-lista (tunnetut haitalliset IP-alueet) piirteeksi.

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

## Blocked

| ID | Card | Blocked on | Since | Owner |
|---|---|---|---|---|
| | | | | |
