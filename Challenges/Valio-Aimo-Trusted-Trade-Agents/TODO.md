# Todo — Junction kanban (Valio Aimo: Trusted Trade Agents)

**WIP limit: 1 card per person in *In Progress*.**
Sizes: S ≈ 15 min, M ≈ 1 h, L ≈ half a day. `P0` = demo dies without it, `P1` = judges notice, `P2` = only if idle.
Owners: **A** tukkurin järjestelmä, **B** agenttiportti + luottamus, **C** agentti + ihmisen näkymät + pitch (ks. `TEAM.md`).
Ajat suhteessa hackin alkuun (T+0). Virallinen palautusaika: `DEADLINE = ?`

---

## Ennen alkua

| ID | Card | Size | Owner | Notes |
|---|---|---|---|---|
| PRE-1 | Valion pisteelle: tuleeko heiltä mock-data/API? Arviointikriteerit? Esimerkkituotteet ja toimitusrytmit? | S | C | Kriteereitä ei ole haastesivulla — kysy |
| PRE-2 | Lue `IDEA.md` + `ARCHITECTURE.md`, sovi rajapinnat (`TEAM.md`) | S | kaikki | 30 min yhdessä |
| PRE-3 | LLM-avain ostoagentille (Gemini / Nemotron / OpenAI — ks. tech challenget) | S | C | |
| PRE-4 | Python 3.12 + Docker toimii jokaisella | S | kaikki | |

---

## Vaihe 1 — Kerrokset rinnakkain stubeja vasten (T+0 → T+8)

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| A-1 | Tietomalli + seed: ~300 tuotetta, 3 asiakasta hinnastoineen, saatavuus, tilaushistoria | P0 | L | A | Mukaan "1000 l laktoositonta maitoa" -tilanne, jossa yksi tuote ei riitä |
| A-2 | `tiski.backend`-funktiot + Pydantic-mallit | P0 | M | A | Sovittu rajapinta B:lle |
| B-1 | MCP-palvelin stub-datalla: `search_products`, `check_availability`, `request_offer`, `place_order`, `get_order_status` | P0 | L | B | MCP Python SDK |
| B-2 | Mandaatin YAML-muoto + sääntömoottori + yksikkötestit | P0 | M | B | Päätös + syyt, ei LLM:ää |
| C-1 | Ostoagentti MCP-stubia vasten: esimerkkipyyntö alusta loppuun | P0 | M | C | |
| C-2 | 20 testiskenaariota + odotettu lopputulos | P0 | M | C | Tavallinen, liian iso, väärä ryhmä, ei saatavilla, injektio, toisen asiakkaan data… |

## Vaihe 2 — Kytketään yhteen (T+8 → T+20)

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| A-3 | Tarjous → tilaus -elinkaari: kiinteä hinta, voimassaolo, idempotenssi, tilat | P0 | L | A | |
| A-4 | Postgres + Docker Compose + deploy julkiseen URLiin | P0 | M | A | Julki aikaisin |
| B-3 | Gateway kytketään A:n palveluun; agentin tunniste ↔ asiakas ↔ mandaatti | P0 | M | B | |
| B-4 | Datasuodatin: hinnat vain omalle asiakkaalle, saatavuus luokkina | P0 | M | B | |
| B-5 | Loki: append-only + hash-ketju | P0 | M | B | |
| C-3 | Hyväksyntänäkymä (mobiili): mitä, miksi pysähtyi, hyväksy/hylkää | P0 | L | C | Demon keskeinen näkymä |

## Vaihe 3 — Luottamus näkyväksi (T+20 → T+34)

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| C-4 | Aikajana: mitä agentti teki ja miksi | P0 | M | C | |
| C-5 | Skenaarioajo → tulostaulukko (oikein / väärin, läpimenneet ylitykset = 0) | P0 | M | C | Pitchin luvut |
| B-6 | Hyökkäystestit: injektio tuotekuvauksessa, valtuuksien ylitys, toisen asiakkaan data, tarjouksen manipulointi | P1 | M | B | Demon wow-hetki |
| B-7 | REST/OpenAPI + agenttikortti `/.well-known/` | P1 | M | B | "Avoimet standardit" |
| A-5 | Toimitusaika- ja vastuullisuusvertailu (merkit/sertifikaatit) | P1 | M | A | Valinnainen osa |
| A-6 | Korvaavat tuotteet → aina hyväksyntään | P2 | M | A | Valinnainen osa |
| C-6 | Mandaatin muokkausnäkymä ylläpitäjälle | P2 | M | C | YAML-tiedosto riittää demoon |

## Vaihe 4 — Viimeistely ja lukitus (T+34 → deadline)

**Feature freeze T+40.**

| ID | Card | Pri | Size | Owner | Notes |
|---|---|---|---|---|---|
| A-7 | Seed-datan reset-skripti demoa varten | P0 | S | A | |
| C-7 | Demokäsikirjoitus + tallennettu agenttiajo varalle | P0 | M | C | |
| C-8 | 90 s varavideo | P0 | S | C | Heti kun demopolku toimii |
| C-9 | Pitch: ongelma → demo → luvut → rajoitukset | P0 | M | C | Aloita rajapinnasta ja luottamuksesta, ei chatista |
| B-8 | README: miten oma agentti kytketään MCP:hen | P1 | S | B | Tuomarit voivat kokeilla |
| A-8 | Tech challenget: CRACI CI:hin, Aiven Postgres jos sopii | P2 | S | A | |

---

## In Progress (max 1 per person)

| ID | Card | Owner | Started | Blocker |
|---|---|---|---|---|
| | | | | |

---

## Done

| ID | Card | When | Commit |
|---|---|---|---|
| | | | |

---

## Cut line

Jos aika loppuu, toimitetaan tässä järjestyksessä ja lopetetaan:

1. Esimerkkipyyntö alusta loppuun: agentti → MCP → säännöt → hyväksyntä → tilaus (A-1…A-3, B-1…B-3, C-1, C-3)
2. Aikajana + skenaariotaulukko (C-4, C-5, B-5)
3. Varavideo + pitch (C-8, C-9)
4. Hyökkäystestit, OpenAPI, valinnaiset osat — sanotaan pitchissä jos jäivät kesken
