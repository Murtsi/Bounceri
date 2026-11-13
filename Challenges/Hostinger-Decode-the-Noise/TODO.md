# Todo — Junction kanban (Hostinger: Decode the Noise)

**WIP limit: 1 card per person in *In Progress*.** Kolme henkeä = enintään kolme korttia kerrallaan.
Sizes: S ≈ 15 min, M ≈ 1 h, L ≈ half a day. `P0` = demo dies without it, `P1` = judges notice, `P2` = only if idle.
Owners: **A** infra + pipeline, **B** tunnistus + arviointi, **C** tuote + pitch (ks. `TEAM.md`).
Ajat ovat suhteessa hackin alkuun (T+0). Tarkista virallinen palautusaika ja kirjoita se tähän: `DEADLINE = ?`

---

## Ennen alkua (tänään)

| ID | Card | Size | Owner | Notes |
|---|---|---|---|---|
| PRE-1 | Hostinger-VPS, domain ja AI Router -avain käsiin (booth / kick-off) | S | A | Ilman näitä kaista A ei pääse alkuun |
| PRE-2 | Lue `IDEA.md` + `ARCHITECTURE.md`, sovi rajapinnat (`TEAM.md`) | S | kaikki | 30 min yhdessä, ei enempää |
| PRE-3 | Python 3.12 + Docker toimii jokaisella koneella | S | kaikki | |
| PRE-4 | Selvitä: saako demon DB olla muualla kuin Hostingerilla? Onko Gemini AI Routerissa? | S | C | Kysytään Hostingerin mentoreilta |

---

## Vaihe 1 — Julki ja dataa keräämään (T+0 → T+8)

Tavoite: oikeaa liikennettä kertyy VPS:lle koko loppuviikonlopun.

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| A-1 | VPS: Docker, Caddy, TLS, domain, JSON access log (otsakkeet mukaan) | P0 | M | A | **Ensimmäinen asia.** Jokainen tunti myöhemmin = vähemmän oikeaa bottidataa |
| A-2 | Demosivusto: muutama sivu + CSS/JS/kuvat + kirjautumislomake | P0 | M | A | Riittää staattinen + yksi POST /login |
| A-3 | Ansapolut: piilolinkki, `/wp-admin`, `/.env`, `/.git/config` | P0 | S | A | Lokitetaan, palautetaan uskottava vastaus |
| A-4 | Lokin rotaatio + varmuuskopio | P1 | S | A | Lokit ovat koko projektin raaka-aine |
| C-1 | Simulaattorit: scraper, skanneri, tunnusten kokeilu, hidas skanneri | P0 | M | C | Merkintä `X-Sim-Run: <ajo-id>:<luokka>` |
| C-2 | Playwright-"ihminen": satunnaiset viiveet, lataa resurssit, kirjautuu oikein | P0 | M | C | |
| C-3 | QR-koodi + lyhyt sivu "auta meitä: selaa sivua 30 s" | P1 | S | C | Oikeaa ihmisdataa tapahtumapaikalta |
| B-1 | Lataa ensimmäinen lokinäyte, parsinta + sessiointi notebookissa | P0 | M | B | Ei odoteta A:n pipelinea |
| B-2 | Piirteet v1 (taulukko ARCHITECTURE.md:ssä) | P0 | L | B | |
| B-3 | Labelien kokoaminen: ansat, rDNS-hakukonebotit, simulaattorien merkinnät | P0 | M | B | |

## Vaihe 2 — Tunnistus päästä päähän (T+8 → T+20)

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| A-5 | Ingest-worker: tail → parsinta → sessiot → Postgres | P0 | L | A | Siirtää B:n notebook-koodin tuotantoon |
| A-6 | Compose-kokonaisuus VPS:lle + `make deploy` | P0 | M | A | |
| B-4 | Säännöt + malli v1 + kaksi kynnystä (epävarma-vyöhyke) | P0 | L | B | `score(session)` C:n käyttöön |
| B-5 | Arviointi: temporaalinen jako + piilotettu hyökkäysskripti → `metrics.json` | P0 | M | B | Simuloitu ja oikea liikenne erikseen |
| C-4 | API: `/api/sessions`, `/api/sessions/{id}`, `/api/metrics`, `/healthz` | P0 | M | C | |
| C-5 | Dashboard v1: sessiolista + yhden session näkymä syineen | P0 | L | C | Jinja + HTMX, ei SPA:ta |

## Vaihe 3 — Erottuvat ominaisuudet (T+20 → T+34)

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| B-6 | Kampanjat: sormenjälki + polkujärjestys + ajoitus → klusterit | P1 | L | B | Demon wow-hetki |
| C-6 | LLM-selitykset AI Routerin kautta + sääntöpohjainen varaselitys | P1 | M | C | LLM ei tee päätöstä |
| C-7 | `/metrics`-sivu: sekaannusmatriisi, FPR, tunnetut heikkoudet | P0 | M | C | B toimittaa luvut |
| C-8 | `POST /api/analyze`: lataa oma access-loki → raportti | P1 | M | C | Tuomarit voivat kokeilla omalla datallaan |
| A-7 | Rate limit + perussuojaus omalle API:lle | P1 | S | A | Hostinger-talk la 13:00: "securing" |
| A-8 | Hostinger-talk la 13:00 — joku käy | P2 | S | A | |

## Vaihe 4 — Viimeistely ja lukitus (T+34 → deadline)

**Feature freeze T+40.** Sen jälkeen vain bugikorjaukset, luvut ja pitch.

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| B-7 | Lukitse testijoukon tulokset + model_version | P0 | S | B | Luvut eivät muutu pitchin jälkeen |
| C-9 | Demokäsikirjoitus (docs/DEMO.md) + livehyökkäys napin takana | P0 | M | C | |
| C-10 | 90 s varavideo | P0 | S | C | Tee heti kun demo toimii |
| C-11 | Pitch: ongelma → demo → luvut → rehelliset rajoitukset | P0 | M | C | |
| A-9 | README: URL, arkkitehtuuri, miten luvut lasketaan | P1 | S | A | |
| A-10 | Tech challenget: CRACI-runner CI:hin (+ muut jos sopii) | P2 | S | A | |

---

## In Progress (max 1 per person)

| ID | Card | Owner | Started | Blocker |
|---|---|---|---|---|
| | | | | |

---

## Review / Verify

Definition of done: runs from a clean checkout, `make check` passes, toimii VPS:llä, `.env.example` päivitetty jos lisättiin muuttuja.

| ID | Card | Reviewer | Evidence |
|---|---|---|---|
| | | | |

---

## Done

| ID | Card | When | Commit |
|---|---|---|---|
| PRE-0 | Hackathon scaffold: docs, CI, compose, hooks, devcontainer | 2026-11-13 | `c8a7ed8` |

---

## Cut line

Jos aika loppuu, toimitetaan tässä järjestyksessä ja lopetetaan:

1. Julkinen URL + ingest + pisteytys + dashboard (A-1…A-6, B-4, C-4, C-5)
2. `/metrics` rehellisillä luvuilla (B-5, C-7, B-7)
3. Varavideo + pitch (C-10, C-11)
4. Kampanjat, LLM-selitykset, lokin lataus — sanotaan pitchissä jos jäivät kesken

## Blocked

| ID | Card | Blocked on | Since | Owner |
|---|---|---|---|---|
| | | | | |
