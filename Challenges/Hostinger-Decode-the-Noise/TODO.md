# Todo — Junction kanban (Hostinger: Decode the Noise)

Kolme kaistaa, jokainen tekee **vain omia korttejaan** järjestyksessä ylhäältä alas. Omistajuus ja sopimukset (S1–S8): `TEAM.md`.
Sizes: S ≈ 15 min, M ≈ 1 h, L ≈ half a day. `P0` = demo dies without it, `P1` = judges notice, `P2` = only if idle.
Ajat suhteessa hackin alkuun (T+0). Virallinen palautusaika: `DEADLINE = ?`

---

## Ennen alkua (kaikki yhdessä)

| ID | Card | Size | Owner | Notes |
|---|---|---|---|---|
| PRE-1 | Hostinger-VPS, domain ja AI Router -avain käsiin | S | A | Kick-off / Hostingerin piste |
| PRE-2 | Käydään `TEAM.md` läpi, nimet A/B/C:lle | S | kaikki | 30 min |
| PRE-3 | Python 3.12 + Docker toimii jokaisella | S | kaikki | |
| PRE-4 | Hostingerilta: saako DB olla muualla? Onko Gemini AI Routerissa? | S | C | |

---

## Kaista A — Infra + data

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| A-1 | T+0 → 1 | Repo-rakenne + `contracts.py` + `samples/access.sample.jsonl` (stub) + `deploy/traps.txt` | P0 | M | S1, S2, S8 `main`-haarassa |
| A-2 | T+1 → 4 | VPS: Docker, Caddy, TLS, domain, JSON-loki otsakkeineen | P0 | M | `curl https://<domain>` toimii, loki kirjoittuu |
| A-3 | T+4 → 6 | Demosivusto: sivut + CSS/JS/kuvat + `POST /login` + ansapolut | P0 | M | Selaimella toimii, ansaosumat näkyvät lokissa |
| A-4 | T+6 | Oikea lokinäyte → `samples/` (korvaa stubin) | P0 | S | B ja C saavat oikeaa dataa |
| A-5 | T+6 → 10 | Ingest: tail → parsinta → `requests` → sessiointi → `sessions`; `X-Sim-Run` → `labels` | P0 | L | Sessiot kertyvät tietokantaan |
| A-6 | T+10 → 12 | `load_sessions()` Postgresista + pipeline-worker kutsuu `score()` → `verdicts` | P0 | M | **Integraatio T+12** |
| A-7 | T+12 → 16 | `make deploy` + compose VPS:lle (A:n, B:n ja C:n koodi samassa imagessa) | P0 | M | Yksi komento päivittää VPS:n |
| A-8 | T+16 → 18 | Lokin rotaatio + yöllinen varmuuskopio DB:stä | P1 | S | Data ei katoa |
| A-9 | T+18 → 20 | Rate limit + perussuojaus Caddyssa API:lle ja dashboardille | P1 | S | |
| A-10 | T+26 → 30 | Worker ajaa `find_campaigns()` minuutin välein → `campaigns` | P1 | M | **Integraatio T+30** |
| A-11 | T+30 → 34 | Valvonta: `/healthz`, ingest-viive, levytila; hälytys tiimin chattiin | P1 | M | |
| A-12 | T+40 → | README: URL, arkkitehtuuri, miten ajetaan | P1 | S | |

**Jos aikaa jää (vain A):** CRACI-runner CI:hin (tech challenge) · demo-DB:n reset-skripti · kuormitustesti (kestääkö worker 100 req/s).

---

## Kaista B — Tunnistus + arviointi

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| B-1 | T+0 → 1 | `score()`-stub (aina `uncertain`) + `find_campaigns()`-stub + `metrics.json`-stub | P0 | S | S4, S5, S6 `main`-haarassa |
| B-2 | T+1 → 6 | Piirteet `Session`-olioista (`contracts.py`) stub-näytettä vasten | P0 | L | Piirrefunktiot + testit `tests/detect` |
| B-3 | T+6 → 8 | Piirteet oikeaa lokinäytettä vasten, korjaukset | P0 | M | |
| B-4 | T+8 → 12 | Varmat säännöt: ansaosuma, rDNS-hakukonebotit, haavoittuvuuspolut + `reasons` | P0 | M | **Integraatio T+12**: oikea `score()` |
| B-5 | T+12 → 14 | Labelien kokoaminen: `labels`-taulu (sim) + ansat + rDNS | P0 | M | Labeloitu datasetti |
| B-6 | T+14 → 18 | Malli + SHAP/kertoimet → 3 syytä per päätös | P0 | L | |
| B-7 | T+18 → 20 | Arviointi: temporaalinen jako, piilotettu hyökkäys, simuloitu vs. oikea erikseen, kynnykset (FPR < 1 %) | P0 | M | **Integraatio T+20**: oikea `metrics.json` |
| B-8 | T+20 → 28 | Kampanjat: otsakesormenjälki + polkujärjestys (MinHash) + ajoitus → klusterit | P1 | L | **Integraatio T+30**: oikea `find_campaigns()` |
| B-9 | T+28 → 34 | Virheanalyysi: väärät positiiviset käsin läpi → `known_weaknesses` | P1 | M | Pitchin rehellisyysosio |
| B-10 | T+34 → 40 | Uudelleenopetus kertyneellä datalla, kynnysten tarkistus | P1 | M | |
| B-11 | T+42 | **Lukitse** `metrics.json` + `model_version` | P0 | S | Luvut eivät muutu enää |

**Jos aikaa jää (vain B):** kalibrointikäyrä `metrics.json`:iin · ASN-pohjainen datakeskuspiirre · julkinen bottidatasetti lisätestiksi.

---

## Kaista C — Tuote + pitch

| ID | Aika | Card | Pri | Size | Valmis kun |
|---|---|---|---|---|---|
| C-1 | T+0 → 1 | `X-Sim-Run`-muoto (S7) + simulaattorirunko | P0 | S | S7 `main`-haarassa |
| C-2 | T+1 → 5 | Hyökkäyssimulaattorit: scraper, skanneri, tunnusten kokeilu (monesta IP:stä), hidas skanneri | P0 | L | Ajetaan VPS:ää vasten heti kun A-3 on valmis |
| C-3 | T+5 → 8 | Playwright-"ihminen" + QR-sivu "selaa 30 s" | P0 | M | Ihmisdataa kertyy |
| C-4 | T+8 → 12 | API: `/api/sessions`, `/api/sessions/{id}`, `/api/metrics`, `/healthz` (lukee DB:tä + `metrics.json`) | P0 | M | **Integraatio T+12** |
| C-5 | T+12 → 18 | Dashboard v1: sessiolista + session näkymä (pyynnöt, syyt, piirteet) | P0 | L | |
| C-6 | T+18 → 22 | `/metrics`-sivu `metrics.json`:sta: sekaannusmatriisi, FPR, heikkoudet | P0 | M | **Integraatio T+20** |
| C-7 | T+22 → 26 | LLM-selitykset (AI Router) → `verdicts.explanation`; varana B:n `reasons` sellaisenaan | P1 | M | |
| C-8 | T+26 → 30 | Kampanjanäkymä + livehyökkäys-nappi | P1 | M | **Integraatio T+30** |
| C-9 | T+30 → 34 | `POST /api/analyze`: lataa oma loki → raportti (kutsuu A:n parseria ja B:n `score()`) | P1 | M | |
| C-10 | T+34 → 38 | Demokäsikirjoitus `docs/DEMO.md` + harjoitus | P0 | M | |
| C-11 | T+38 → 40 | 90 s varavideo | P0 | S | |
| C-12 | T+40 → | Pitch `docs/PITCH.md`: ongelma → demo → luvut → rajoitukset | P0 | M | |

**Jos aikaa jää (vain C):** ulkoasun hiominen · mobiilinäkymä · screenshotit palautukseen.

---

## Cut line

Jos aika loppuu, toimitetaan tässä järjestyksessä ja lopetetaan:

1. Integraatio T+12 (A-1…A-6, B-1…B-4, C-1…C-5): oikea liikenne → sääntöpohjainen tulos → dashboard
2. Integraatio T+20 (B-5…B-7, C-6): `/metrics` rehellisillä luvuilla
3. Varavideo + pitch (C-10…C-12, B-11)
4. Kampanjat, LLM-selitykset, lokin lataus — sanotaan pitchissä jos jäivät kesken

## Blocked

| ID | Card | Blocked on | Since | Owner |
|---|---|---|---|---|
| | | | | |
