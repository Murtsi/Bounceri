# MVP — yksi komento, koko ketju

Tavoite: näyttää paikallisesti, ilman VPS:ää, että Bouncer toimii alusta loppuun
oikealla Caddy-lokilla. Sama Docker Compose siirtyy VPS:lle, kun PRE-1 on valmis.
Tämä on sopimus siitä, mitä rakennetaan — ei enempää ennen kuin tämä toimii.

## Hyväksymiskriteerit

`make demo` käynnistää kaiken, ajaa simuloitua liikennettä ~1 min, ja dashboardilla näkyy:

| # | Liikenne | Odotettu tulos | Mistä se tulee |
|---|---|---|---|
| 1 | Skanneri (`/.env`, `/.git/config`, …) | `bad_bot`, syynä haavoittuvuuspolut | B:n varma sääntö |
| 2 | Tunnusten kokeilu, sama tunnus monesta IP:stä | kampanja + `bad_bot` | C:n `find_campaigns` + B:n kampanjasääntö |
| 3 | Ihmistä matkiva selaus (sivut + CSS/JS + tauot) | `human` tai `uncertain`, **ei koskaan** `bad_bot` | B |
| 4 | Väärennetty Googlebot | `bad_bot` | C:n DNS-varmistus + B:n sääntö |
| 5 | Session kortti | päätös, 3 syytä, selitys | B + C:n `explain` (ilman LLM:ää) |
| 6 | `/metrics` | "STUB / synteettinen" näkyy selvästi; ei keksittyjä lukuja | B (S8) |

Jokainen rivi on automaattinen testi tai `make demo`:n tarkistus — ei käsin katsottava.

## Rakenne

```
simulaattorit (tools/sim) ──HTTP──▶ Caddy :8080 ──▶ demosivu (src/site, FastAPI)
                                       │ JSON access log
                                       ▼
                      worker (src/bouncer/ingest/worker.py)
                      lokin seuraus → parseri → store → C network_pass → B score
                                       │ päätökset
                                       ▼
                      API (src/bouncer/api, FastAPI) ──▶ dashboard (frontend/, React)
```

## Vaiheet (kukin tarkistetaan ennen seuraavaa)

| Vaihe | Sisältö | Valmis kun |
|---|---|---|
| 0 | `pyproject.toml`, Makefile, tämä tiedosto | `make test` ajaa kaikki testit |
| 1 | Demosivu + Caddy (Compose) | `curl` → Caddyn JSON-rivi → parseri lukee sen (client IP, `X-Login-User`) |
| 2 | Simulaattorit, allekirjoitetut merkinnät | lokissa labelit, allekirjoitukset hyväksytään |
| 3 | Worker + B:n kampanjasääntö | komentorivi näyttää kriteerit 1–4 |
| 4 | API + React-dashboard | selaimessa kriteerit 1–6 |
| 5 | `make demo` + README | toimii puhtaasta checkoutista |

**Tila 2026-11-14:** vaiheet 0–5 valmiit; `make demo` → 6/6 kriteeriä Docker Composella puhtaalta pöydältä.

## Päätökset (docs/DECISIONS.md 048–051)

- Caddy ajetaan Docker Composella myös paikallisesti (sama kuin VPS).
- Paikallisessa demossa Caddy luottaa simulaattorin `X-Forwarded-For`-otsakkeeseen
  (`trusted_proxies` vain tässä tilassa), jotta monen IP:n hyökkäys syntyy yhdeltä koneelta.
  Tuotannossa pois päältä. Parseri käyttää Caddyn laskemaa `client_ip`:tä.
- Dashboard Reactilla heti (päätös 005), API:n yli.
- Yhteinen `pyproject.toml` (uv), Makefilen `test`/`lint` käyttävät sitä.

## Rajattu pois MVP:stä

Postgres (JSON-store riittää), LLM-selitykset (fallback-teksti), oikea VPS, Playwright,
piilotettu hyökkäys. Nämä tulevat MVP:n jälkeen samaan rakenteeseen.
