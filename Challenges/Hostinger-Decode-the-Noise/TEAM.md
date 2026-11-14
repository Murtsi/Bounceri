# Team — Hostinger: Decode the Noise

Kolme henkilöä, kolme kaistaa (oletusvastuut). Hackathonissa kaistarajat **eivät estä** toisen polun korjausta (päätös 044); CODEOWNERS pyytää silti review’ta. Kaksi kolmesta tekee tunnistusta, koska tuomarit pisteyttävät ensisijaisesti tunnistuksen vahvuutta ja rehellisyyttä, eivät käyttöliittymää.

## Nykyiset integraatiorajat — 2026-11-14

Kaistat ovat oletusvastuita, eivät muokkauskieltoja. Alla säilytetty T+-aikataulu
ja stub-taulukko ovat alkuperäinen hackathon-suunnitelma, eivät nykyinen työtila.
Nykytila ja vaiheistus ovat [README.md](README.md):ssä ja [TODO.md](TODO.md):ssä.

- **A:** Caddy-demo, allekirjoitetut simulaattorit, ingest-worker, JSON-store ja
  `load_sessions()`/`load_labels()`, API sekä dashboard ovat toteutettu. Liikenteen
  SQL repository, yhtenäinen versioitu migraatioajo ja replay/checkpointit ovat
  seuraavaa ydintyötä; PostgreSQL-investigations ei vielä korvaa JSON-liikennestorea.
- **B:** paikalliset piirteet/säännöt, mallin latauspolku ja arviointityökalut ovat
  toteutettu. Production `models/metrics.json` on stub/null. Erillinen
  [synteettinen raportti](../../docs/EVALUATION.md) ei täytä oikeiden ihmisten
  FPR- tai aidosti piilotetun hyökkäyksen näyttövaatimusta.
- **C:** HTTP-kampanjat, IP/DNS-funktiot, NAT-suodatus ja selitykset ovat toteutettu.
  Hosted-worker käyttää nyt `intel_fn=None`; live-DNS-näyttöä ei pidä päätellä
  paikallisten funktioiden olemassaolosta. Investigation-paketista puuttuvat
  crawler-varmennuksen provenienssi ja mallille riittävä kampanjasuhdenäyttö.
- **Yhteinen review-runtime:** `src/bouncer/review/` sisältää asynkronisen bounded
  decision → final advisory reviewer -runnerin/workerin. Molemmat roolit käyttävät
  eksplisiittisesti aktivoitua Featherless-konfiguraatiota; investigation-store
  omistaa jobit, immutable-havainnot/arviot ja yhteisen reservation/budget-ledgerin.
  Native Microsoft Decision on erikseen varmennettava unavailable-optio.
- **Uudet moduulit:** [MODULES.md](../../docs/MODULES.md) määrittää erilliset syötteet,
  analyysit ja näyttörajat. Trust the Source, sosiaalinen Spot the Swarm ja tekstin
  Name the Technique ovat kaikki toteuttamatta ja pois käytöstä. Nykyinen HTTP-
  kampanjatunnistus pysyy Clean the Traffic -moduulissa.

Hostinger-deploy ja maksulliset synteettiset kokeet on kirjattu
[runtime-ohjeeseen](../../docs/HOSTINGER_LIVE.md) ja
[malliraporttiin](../../docs/LIVE_AI_VALIDATION.md). Dokumenttien sovitus ei ole uusi
live-terveystarkistus. Kaikki hyväksytyt lopulliset malliarviot kirjatussa kokeessa
olivat `uncertain`; ne eivät ole totuuslabeleita eivätkä osoita parempaa laatua.

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
| `src/bouncer/site/` (päätös 052) | A | Demosivusto, kirjautumislomake, ansapolut, QR-sivu |
| `src/bouncer/ingest/` | A | Tail, parsinta, sessiointi, **pipeline-worker** |
| `src/bouncer/db/` | A | Skeema, migraatiot, `load_sessions()` |
| `src/bouncer/contracts.py` | A (muutokset 3 hengen sopimuksella) | Jaetut tyypit: `Request`, `Session`, `IpIntel`, `Campaign`, `Verdict`, `SessionLabel`; **S2 lukittu (039):** `Session.id` / `Campaign.session_ids` / `SessionLabel.session_id` = `str` |
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
| `src/bouncer/investigations/`, `src/bouncer/review/`, `src/bouncer/enforcement/` | A/C, yhteinen integraatio | Toteutetut case/evidence-, job/budget-, advisory-review- ja manuaalisen testipolitiikan rajat |
| `src/bouncer/network/eval.py` | C | `campaign_metrics.json` |
| `notebooks/c/` | C | Tutkiminen |
| `tests/<kaista>/` | kukin omansa | `tests/a`, `tests/b`, `tests/c` |
| `docs/PITCH.md`, `docs/DEMO.md` | yhteinen T+38 jälkeen | Jokainen kirjoittaa omat osionsa |

### Tietokantataulut

**Kirjoituslogiikka pidetään store/ingest-rajalla.** B:n ja C:n tunnistusfunktiot
ovat puhtaita; worker integroi ne. Kaista ei estä korjaamasta yhteistä storea.
Seuraava taulukko on historiallinen tavoiteskeema; nykyinen liikennepolku käyttää
JSON-storea ja investigations/review/enforcement omia SQLAlchemy-taulujaan.

| Taulu | Lähde | Lukee |
|---|---|---|
| `requests`, `sessions` | A:n ingest | B, C |
| `labels` | A:n ingest (`X-Sim-Run`) | B, C |
| `ip_intel` (välimuisti) | A:n worker ← C:n `ip_intel()` | B, C |
| `campaigns` | A:n worker ← C:n `find_campaigns()` | B, A:n dashboard |
| `verdicts` | A:n worker ← B:n `score()` | A:n dashboard |
| `verdicts.explanation` | A:n API ← C:n `explain()` (pyydettäessä, välimuistiin) | A:n dashboard |

Historiallinen worker-tavoite: uudet sessiot → `ip_intel()` → `find_campaigns()`
(viimeinen 30 min) → `score(session, intel, campaign)` → `verdicts`. Nykyinen
worker ajaa syklin konfiguroidulla välillä ja tallentaa paikalliset selitykset;
asynkroninen maksullinen review on siitä erillinen prosessi.

## Sopimukset kaistojen välillä

Seuraava taulukko säilyttää **historiallisen T+1-stub- ja aikataulusopimuksen**.
Sen tulevaisuusmuotoja ja avoimia handoffeja ei pidä lukea nykytilana; nykyiset
rajat on kuvattu tämän tiedoston alussa.

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
| S10 | `X-Sim-Run: <ajo-id>:<luokka>:<kampanja-id>` | A (sisäinen) → `labels` | `X-Sim-Run` HTTP-pyyntöotsakkeessa; kampanja-id voi olla `-` tai puuttua. Asetetaan vain simulaattoripyynnöissä, poistetaan julkisista lokeista | Luokat ja lopullinen parseri vahvistetaan B:n/C:n kanssa ennen ajoa; **allekirjoitus `X-Sim-Sig` = HMAC-SHA256(`SIM_RUN_SECRET`, merkintä)** (046) |
| S11 | `deploy/traps.txt` | A → B | Lista | — |

`metrics.json` (B), nykyinen production-stub (ei esimerkkitulos):

```json
{
  "model_version": "rules-v2",
  "test_window": {"from": null, "to": null},
  "threshold": {"bot": null, "human": null},
  "human_fpr": null,
  "per_class": {},
  "uncertain_share": null,
  "confusion": [],
  "split": {"simulated": {}, "real": {}, "hidden_attack": {}},
  "ablation": {"without_network_signals": {"human_fpr": null, "recall": null}},
  "known_weaknesses": [],
  "stub": true
}
```

`ablation` näyttää, paljonko C:n verkostosignaalit parantavat B:n tulosta — kahden tunnistuskaistan arvo yhdellä luvulla.

## Integraatiopisteet

Historialliset T+-integraatiopisteet; taulukko ei todista toteutunutta ulkoista
labelkeräystä, hidden-hyökkäystä tai feature freezeä. A integroi, muut katselmoivat.

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

- **Haarat:** `a/…`, `b/…`, `c/…`. Kaistat ovat oletusvastuita; kuka tahansa saa korjata pullonkaulan toisella polulla (AGENTS.md, päätös 044). Sopimusmuutokset kirjataan ja katselmoidaan yhdessä.
- **Valmis aikaisin?** Auta nykyisen TODO-prioriteetin mukaan ja kirjaa muutos oikealla kaistatunnisteella; kaistaraja ei vaadi erillistä lupaa.
- **Standup** 10 min joka 4. tunti: tehty / seuraavaksi / jumissa / tarvitsee sopimusmuutoksen.
- **Jumissa > 15 min?** Sano ääneen.
- Päätökset `../../docs/DECISIONS.md`:hen.

## Vastuut tiivistettynä

- **Murtsi (A):** demo ja ingest/store-integraatio; historiallinen T+-suunnitelma antoi hänelle myös itsenäisen hidden-hyökkäyksen ja palautuksen. Tämä vastuu ei tarkoita, että ne olisi tehty.
- **Niko (B):** `score()` ja `metrics.json`; kukaan muu ei muuta lukuja. Lukitsee luvut T+42.
- **Joonas (C):** `ip_intel()`, `find_campaigns()`, `explain()` ja `campaign_metrics.json`. Hoitaa kysymykset Hostingerin mentoreille (PRE-4).
