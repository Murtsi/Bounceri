# Team — Hostinger: Decode the Noise

Kolme henkilöä, kolme kaistaa, **ei päällekkäisyyksiä**. Jokainen omistaa omat kansionsa, omat taulunsa ja omat funktionsa. Kaistojen välillä kulkee vain sovittuja asioita (*sopimukset*, alla). Jos joudut muokkaamaan toisen kaistan tiedostoa, se on merkki siitä, että sopimus puuttuu — sano ääneen.

## Yhdellä lauseella

| | Rooli | Vastaa kysymykseen |
|---|---|---|
| **A** | Infra + data | *"Tuleeko liikenne sisään ja päätyykö se tietokantaan sessioina?"* |
| **B** | Tunnistus + arviointi | *"Onko tämä sessio botti, miksi, ja kuinka usein olemme väärässä?"* |
| **C** | Tuote + pitch | *"Mitä käyttäjä ja tuomari näkevät, ja mistä oikeat vastaukset tulevat?"* |

## Omistajuus

### Kansiot ja tiedostot

| Polku | Omistaja | Sisältö |
|---|---|---|
| `deploy/` | A | Caddyfile, docker-compose (VPS), `.env.example` |
| `src/site/` | A | Demosivusto, kirjautumislomake, ansapolut |
| `src/bouncer/ingest/` | A | Lokin tail, parsinta, sessiointi, **pipeline-worker** |
| `src/bouncer/db/` | A | Skeema, migraatiot, `load_sessions()` |
| `src/bouncer/contracts.py` | A (muutokset 3 hengen sopimuksella) | Jaetut tietotyypit: `Request`, `Session`, `Verdict`, `Campaign` |
| `samples/` | A | Oikea lokinäyte (`access.sample.jsonl`) — kaikki testaavat tätä vasten |
| `.github/workflows/` | A | CI |
| `src/bouncer/detect/` | B | Piirteet, säännöt, rDNS/ASN, malli, kynnykset, kampanjat, `score()` |
| `src/bouncer/eval/` | B | Labelien kokoaminen, train/test-jako, `metrics.json` |
| `models/` | B | Mallitiedostot + `model_version` |
| `notebooks/` | B | Tutkiminen (ei tuotantokoodia) |
| `tools/sim/` | C | Hyökkäys- ja ihmissimulaattorit, livehyökkäys-nappi |
| `src/bouncer/api/` | C | FastAPI-endpointit |
| `src/bouncer/web/` | C | Dashboard, `/metrics`-sivu, QR-sivu |
| `src/bouncer/explain/` | C | LLM-selitykset AI Routerin kautta |
| `docs/PITCH.md`, `docs/DEMO.md` | C | Pitch, demokäsikirjoitus |
| `tests/<kaista>/` | kukin omansa | `tests/ingest`, `tests/detect`, `tests/api` |

### Tietokantataulut

| Taulu | Kirjoittaa | Lukee |
|---|---|---|
| `requests`, `sessions` | A | B, C |
| `labels` (lähde `sim`) | A (ingest siirtää `X-Sim-Run`-otsakkeen tänne) | B |
| `verdicts` (paitsi `explanation`) | A:n worker kutsuu B:n `score()`-funktiota ja tallentaa tuloksen | C |
| `verdicts.explanation` | C | C |
| `campaigns` | A:n worker kutsuu B:n `find_campaigns()`-funktiota | C |

**Periaate:** A omistaa *missä ja milloin* koodi ajetaan (worker, cron, DB), B omistaa *mitä* lasketaan (puhtaat funktiot ilman tietokantaa), C omistaa *miten se näytetään*.

## Sopimukset kaistojen välillä

Kaikki sopimukset ovat olemassa **stubeina tunnissa T+1**, jotta kukaan ei odota ketään.

| # | Sopimus | Tuottaja → käyttäjä | Stub T+1 | Oikea versio |
|---|---|---|---|---|
| S1 | `samples/access.sample.jsonl` — Caddyn JSON-lokin muoto | A → B, C | Käsin kirjoitettu 50 riviä | Oikea loki VPS:ltä (T+4) |
| S2 | `contracts.py`: `Request`, `Session`, `Verdict`, `Campaign` | A → B, C | Dataclassit | Sama, muutokset vain sopimalla |
| S3 | `load_sessions(since) -> list[Session]` | A → B | Lukee `samples/` | Lukee Postgresista (T+12) |
| S4 | `score(session) -> Verdict` (label, score, reasons[3], model_version) | B → A | Palauttaa aina `uncertain` | Säännöt (T+12), malli (T+20) |
| S5 | `find_campaigns(sessions) -> list[Campaign]` | B → A | Palauttaa `[]` | T+28 |
| S6 | `metrics.json` (skeema alla) | B → C | Keksityt luvut, `"stub": true` | Oikeat luvut (T+20), lukittu (T+42) |
| S7 | `X-Sim-Run: <ajo-id>:<luokka>` -otsake | C → A | Sovittu muoto | — |
| S8 | Ansapolkujen lista `deploy/traps.txt` | A → B | Lista | — |

`metrics.json`:

```json
{
  "model_version": "rules-v1",
  "test_window": {"from": "...", "to": "..."},
  "threshold": {"bot": 0.8, "human": 0.3},
  "human_fpr": 0.006,
  "per_class": {"scraper": {"precision": 0.97, "recall": 0.91}},
  "uncertain_share": 0.07,
  "confusion": [[...]],
  "split": {"simulated": {...}, "real": {...}},
  "known_weaknesses": ["hidas skanneri kotiliittymästä", "..."],
  "stub": false
}
```

## Integraatiopisteet

Ainoat hetket, jolloin kaistat kytketään yhteen. A integroi, muut ovat paikalla.

| Aika | Mitä kytketään | Valmis kun |
|---|---|---|
| **T+1** | Kaikki stubit (S1–S8) `main`-haarassa | Jokainen ajaa oman koodinsa stubeja vasten |
| **T+12** | A:n worker + B:n säännöt + C:n API | Oikea liikenne → sessio → verdict → näkyy dashboardissa |
| **T+20** | B:n malli + `metrics.json` oikeilla luvuilla | `/metrics` näyttää oikeat luvut |
| **T+30** | Kampanjat + LLM-selitykset | Livehyökkäys → kampanja ilmestyy dashboardiin |
| **T+40** | Feature freeze | Vain korjaukset |

## Työtavat

- **Haarat:** `a/…`, `b/…`, `c/…`. PR koskee vain omia polkuja. Poikkeus = sopimusmuutos, jonka kaikki kolme hyväksyvät.
- **Valmis aikaisin?** Ota oman kaistan *jos aikaa jää* -kortti (`TODO.md`), älä toisen kaistan korttia. Jos haluat auttaa toista, kysy ensin — omistaja päättää.
- **Standup** 10 min joka 4. tunti: tehty / seuraavaksi / jumissa / tarvitsee sopimusmuutoksen.
- **Jumissa > 15 min?** Sano ääneen.
- Päätökset `../../docs/DECISIONS.md`:hen.
- Yksi ajaa konetta pitchissä (C), muut ovat hiljaa.

## Kuka sopii mihinkin

- **A:** on säätänyt Linux-palvelimia, Dockeria tai nginxiä. Rauhallinen — pitää demon pystyssä.
- **B:** on tehnyt dataa, tilastoja tai koneoppimista. Epäluuloinen omia lukujaan kohtaan.
- **C:** on tehnyt web-käyttöliittymiä tai skriptejä, puhuu parhaiten yleisölle.
