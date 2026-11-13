# Team — Hostinger: Decode the Noise

Kolme henkilöä, kolme kaistaa, **ei päällekkäisyyksiä**. Kaksi kolmesta tekee tunnistusta, koska tuomarit pisteyttävät ensisijaisesti tunnistuksen vahvuutta ja rehellisyyttä, eivät käyttöliittymää.

## Kuka tekee mitä

| | Kuka | GitHub | Haaraetuliite | Rooli | Vastaa kysymykseen |
|---|---|---|---|---|---|
| **A** | **Murtsi** | `@Murtsi` | `a/…` | Alusta + hyökkääjä | *"Tuleeko liikenne sisään, ja tiedämmekö kuka sen lähetti?"* |
| **B** | **Niko** | `@leppiskerttu` | `b/…` | Session tunnistus + arviointi | *"Käyttäytyykö tämä yksi kävijä kuin botti?"* + koko järjestelmän luvut |
| **C** | **Joonas** | `@Joonaswaa` | `c/…` | Verkosto- ja kampanjatunnistus + selitykset | *"Ovatko nämä kävijät sama toimija, ja kuka IP:n takana on?"* |

Päätös 014 (`docs/DECISIONS.md`). Kaistan polkujen katselmoija määräytyy automaattisesti `.github/CODEOWNERS`-tiedostosta.

- **A (Murtsi)** rakentaa palvelimen ja putken, ja on sen jälkeen **hyökkääjä**: kirjoittaa kaikki simulaattorit, myös yhden piilotetun hyökkäyksen, jota B ja C eivät näe ennen arviointia. Hyökkäyksiä ei siis kirjoita sama ihminen kuin tunnistimia → luvut ovat uskottavia. Lopuksi ohut API + dashboard valmiiden taulujen päälle.
- **B (Niko)** katsoo **yhtä sessiota kerrallaan**: piirteet, säännöt, malli, kynnykset, lopullinen päätös. Omistaa koko järjestelmän arvioinnin (`metrics.json`).
- **C (Joonas)** katsoo **monta sessiota yhdessä**: tunnusten kokeilu monesta IP:stä, kampanjat, IP-tiedot (hakukonebottien varmistus, datakeskus vs. koti). Kirjoittaa LLM-selitykset. Mittaa omat kampanjansa A:n simulaattorien tietämää totuutta vasten.

## Omistajuus

### Kansiot ja tiedostot

| Polku | Omistaja | Sisältö |
|---|---|---|
| `deploy/` | A | Caddyfile, docker-compose (VPS), `.env.example`, `traps.txt` |
| `src/site/` | A | Demosivusto, kirjautumislomake, ansapolut, QR-sivu |
| `src/bouncer/ingest/` | A | Tail, parsinta, sessiointi, **pipeline-worker** |
| `src/bouncer/db/` | A | Skeema, migraatiot, `load_sessions()` |
| `src/bouncer/contracts.py` | A (muutokset 3 hengen sopimuksella) | Jaetut tyypit: `Request`, `Session`, `IpIntel`, `Campaign`, `Verdict`, `SessionLabel`; **S2 lukittu (032):** `Session.id` / `Campaign.session_ids` / `SessionLabel.session_id` = `str` |
| `samples/` | A | Lokinäytteet, joita vasten kaikki testaavat |
| `tools/sim/` | A | Hyökkäys- ja ihmissimulaattorit |
| `tools/sim/hidden/` | A (**ei B:lle eikä C:lle** ennen T+34) | Piilotettu hyökkäys — omassa yksityisessä haarassa/gistissä kunnes paljastetaan |
| `src/bouncer/api/`, `frontend/` | A | Ohut API ja dashboard |
| `.github/workflows/` | A | CI |
| `src/bouncer/session/` | B | Session piirteet, säännöt, malli, kynnykset, `score()` |
| `src/bouncer/eval/` | B | Datasetin kokoaminen, train/test-jako, `metrics.json` |
| `models/` | B | Mallitiedostot + `model_version` |
| `notebooks/b/` | B | Tutkiminen |
| `src/bouncer/network/` | C | `ip_intel()`, tunnusten kokeilun tunnistus, `find_campaigns()` |
| `src/bouncer/explain/` | C | `explain()` AI Routerin kautta + varateksti |
| `src/bouncer/network/eval.py` | C | `campaign_metrics.json` |
| `notebooks/c/` | C | Tutkiminen |
| `tests/<kaista>/` | kukin omansa | `tests/a`, `tests/b`, `tests/c` |
| `docs/PITCH.md`, `docs/DEMO.md` | yhteinen T+38 jälkeen | Jokainen kirjoittaa omat osionsa |

### Tietokantataulut

**Vain A kirjoittaa tietokantaan.** B ja C kirjoittavat puhtaita funktioita, joita A:n worker kutsuu. Näin kukaan ei kilpaile samoista riveistä.

| Taulu | Lähde | Lukee |
|---|---|---|
| `requests`, `sessions` | A:n ingest | B, C |
| `labels` | A:n ingest (`X-Sim-Run`) | B, C |
| `ip_intel` (välimuisti) | A:n worker ← C:n `ip_intel()` | B, C |
| `campaigns` | A:n worker ← C:n `find_campaigns()` | B, A:n dashboard |
| `verdicts` | A:n worker ← B:n `score()` | A:n dashboard |
| `verdicts.explanation` | A:n API ← C:n `explain()` (pyydettäessä, välimuistiin) | A:n dashboard |

Workerin järjestys minuutin välein: uudet sessiot → `ip_intel()` → `find_campaigns()` (viimeinen 30 min) → `score(session, intel, campaign)` → `verdicts`.

## Sopimukset kaistojen välillä

Kaikki ovat olemassa **stubeina tunnissa T+1**, jotta kukaan ei odota ketään.

| # | Sopimus | Tuottaja → käyttäjä | Stub T+1 | Oikea versio |
|---|---|---|---|---|
| S1 | `samples/access.sample.jsonl` — Caddyn JSON-lokin muoto | A → B, C | 50 riviä (nykyinen kuuden rivin JSONL on parserin fixture, ei korvaa sovittua stubia) | Oikea loki (T+7) |
| S2 | `contracts.py` | A → B, C | Dataclassit | **ID:t `str` (039, C hyväksynyt)**; muutokset vain sopimalla |
| S3 | `load_sessions(since)` + `load_labels()` | A → B, C | JSONL-fixture ja `load_sample_data()` kehitykseen (ei vielä sopimuksen tuotantolataaja) | Postgres (T+12) |
| S4 | `ip_intel(ip) -> IpIntel` (`verified_bot: bool \| None`, `asn`, `asn_type`, `country`) | C → B, A | `verified_bot=None`, `asn_type="unknown"` | T+5 — **sovittu 020+027:** DNS-virhe → `None`; lista = Googlebot+Bingbot (026) |
| S5 | `find_campaigns(sessions) -> list[Campaign]` (`id`, `kind`, `session_ids: tuple[str,…]`, `reasons`) | C → B, A | `[]` | Stuffing + behavior + NAT (C-3…C-5/C-9); C-4 fixture ok; live metrics → A-8 |
| S6 | `score(session, intel, campaign) -> Verdict` (`label`, `score`, `reasons[3]`, `model_version`) | B → A | Aina `uncertain` | Säännöt T+12, malli T+20 |
| S7 | `explain(verdict, session, campaign) -> str` | C → A | B:n `reasons` tekstinä | LLM T+28 |
| S8 | `metrics.json` (koko järjestelmä) | B → A | `"stub": true` | T+20, lukittu T+42 |
| S9 | `campaign_metrics.json` (kampanjoiden puhtaus/kattavuus) | C → A | `"stub": true` | T+24 |
| S10 | `X-Sim-Run: <ajo-id>:<luokka>:<kampanja-id>` | A (sisäinen) → `labels` | `X-Sim-Run` HTTP-pyyntöotsakkeessa; kampanja-id voi olla `-` tai puuttua. Asetetaan vain simulaattoripyynnöissä, poistetaan julkisista lokeista | Luokat ja lopullinen parseri vahvistetaan B:n/C:n kanssa ennen ajoa |
| S11 | `deploy/traps.txt` | A → B | Lista | — |

`metrics.json` (B):

```json
{
  "model_version": "rules-v1",
  "test_window": {"from": "...", "to": "..."},
  "threshold": {"bot": 0.8, "human": 0.3},
  "human_fpr": 0.006,
  "per_class": {"scraper": {"precision": 0.97, "recall": 0.91}},
  "uncertain_share": 0.07,
  "confusion": [[0]],
  "split": {"simulated": {}, "real": {}, "hidden_attack": {}},
  "ablation": {"without_network_signals": {"human_fpr": 0.0, "recall": 0.0}},
  "known_weaknesses": [],
  "stub": false
}
```

`ablation` näyttää, paljonko C:n verkostosignaalit parantavat B:n tulosta — kahden tunnistuskaistan arvo yhdellä luvulla.

## Integraatiopisteet

Ainoat hetket, jolloin kaistat kytketään yhteen. A integroi, muut ovat paikalla.

| Aika | Mitä kytketään | Valmis kun |
|---|---|---|
| **T+1** | Kaikki stubit (S1–S11) `main`-haarassa | Jokainen ajaa oman koodinsa stubeja vasten |
| **T+12** | Worker + B:n säännöt + C:n IP-tiedot ja tunnusten kokeilu | Oikea liikenne → sessio → verdict → näkyy listana |
| **T+20** | B:n malli + C:n kampanjat + `metrics.json` | Oikeat luvut, kampanjat näkyvät |
| **T+30** | Selitykset + dashboard + livehyökkäys | Demopolku toimii alusta loppuun |
| **T+34** | **Piilotettu hyökkäys paljastetaan** | B ja C ajavat sen läpi, tulos `metrics.json`:iin sellaisenaan |
| **T+40** | Feature freeze | Vain korjaukset, luvut ja pitch |

## Pitch

Yhteinen. T+38 jälkeen jokainen kirjoittaa omat diansa: **A** demo ja arkkitehtuuri, **B** luvut ja rehellisyys, **C** kampanjat ja selitykset. Esittäjä valitaan sen mukaan, kuka puhuu parhaiten.

## Työtavat

- **Haarat:** `a/…`, `b/…`, `c/…`. PR koskee vain omia polkuja. Poikkeus = sopimusmuutos, jonka kaikki kolme hyväksyvät.
- **Valmis aikaisin?** Ota oman kaistan *jos aikaa jää* -kortti (`TODO.md`). Jos haluat auttaa toista, kysy ensin — omistaja päättää.
- **Standup** 10 min joka 4. tunti: tehty / seuraavaksi / jumissa / tarvitsee sopimusmuutoksen.
- **Jumissa > 15 min?** Sano ääneen.
- Päätökset `../../docs/DECISIONS.md`:hen.

## Vastuut tiivistettynä

- **Murtsi (A):** demo pysyy pystyssä, vain hän kirjoittaa tietokantaan, integroi kaistat (T+1, T+12, T+20, T+30, T+34), pitää piilotetun hyökkäyksen salassa T+34 asti, tekee palautuksen.
- **Niko (B):** `score()` ja `metrics.json`; kukaan muu ei muuta lukuja. Lukitsee luvut T+42.
- **Joonas (C):** `ip_intel()`, `find_campaigns()`, `explain()` ja `campaign_metrics.json`. Hoitaa kysymykset Hostingerin mentoreille (PRE-4).
