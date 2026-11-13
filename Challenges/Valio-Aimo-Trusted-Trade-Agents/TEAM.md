# Team — Valio Aimo: Trusted Trade Agents

## People and roles

Kolme henkilöä, kolme kaistaa. Jokainen omistaa yhden kerroksen: **tukkurin järjestelmä** (A), **portti agenteille** (B), **agentti ja ihminen** (C). Kaistat on valittu niin, että kukaan ei odota toista ensimmäisten tuntien aikana.

| | Rooli | Omistaa | Ensimmäiset 8 h | Sen jälkeen |
|---|---|---|---|---|
| **A** | Tukkurin järjestelmä ("Valio Aimo") | Mock-backend, seed-data, adapteri, tilauspalvelu, tietokanta, deploy | Tuotteet, hinnastot, saatavuus ja tilaushistoria seed-datana + Python-funktiot niiden kyselyyn | Tarjous → tilaus -elinkaari, idempotenssi, toimitusvaihtoehdot, deploy julkiseen URLiin |
| **B** | Agenttiportti ja luottamus | MCP-palvelin, REST/OpenAPI, agentin tunnistus, mandaatit, sääntömoottori, datasuodatin, loki | MCP-palvelin stub-datalla (A:n funktiot mockattuna) + mandaatin YAML-muoto + sääntömoottori yksikkötesteineen | Kytkentä A:n palveluun, hash-ketjuloki, hyökkäystestit (injektio, valtuuksien ylitys, toisen asiakkaan data) |
| **C** | Agentti, ihmisen näkymät ja pitch | Demo-ostoagentti, hyväksyntänäkymä, aikajana, mandaatin muokkaus, skenaariotestit, pitch + video | Ostoagentti, joka ajaa esimerkkipyynnön B:n MCP-stubia vasten; 20 testiskenaarion lista | Hyväksyntänäkymä (mobiili), aikajana, skenaarioajo + tulostaulukko, pitch, varavideo |

Nobody owns "everything". If a file has no owner, A (integraattori) owns it.

### Kuka sopii mihinkin

- **A:** on tehnyt backendiä ja tietokantoja; ei pelkää datan generointia.
- **B:** tykkää tietoturvasta ja rajapintasuunnittelusta; kirjoittaa testejä. *Tämä kaista ratkaisee pisteet* — luottamus on haasteen ydin.
- **C:** on käyttänyt LLM-agentteja ja osaa tehdä yksinkertaisen käyttöliittymän; puhuu parhaiten yleisölle.

## Rajapinnat kaistojen välillä

Sovitaan ensimmäisen tunnin aikana, ei muuteta ilman kolmen hengen sopimusta.

- **A → B:** Python-moduuli `tiski.backend` funktioilla `search_products()`, `get_availability()`, `create_offer()`, `place_order()`, `get_order()` + Pydantic-mallit. B mockaa nämä kunnes A on valmis.
- **B → C:** MCP-työkalut ja niiden skeemat (`ARCHITECTURE.md` → *Agent interface*) + hyväksyntä-API (`GET /approvals`, `POST /approvals/{id}`) + aikajana-API (`GET /audit?agent=&order=`).
- **C → B:** skenaarioiden odotetut lopputulokset (sallittu / hyväksyntä / kielletty) → B:n sääntömoottorin testit.

## Communication

- **Standup:** 10 min joka 4. tunti: tehty / seuraavaksi / jumissa / tarvitsee päätöksen.
- **Jumissa > 15 min?** Sano ääneen.
- Päätökset kirjataan `../../docs/DECISIONS.md`:hen, ei chattiin.

## Working agreement

- Feature freeze T+40; sen jälkeen vain korjaukset, luvut ja pitch.
- Demopolku (esimerkkipyyntö alusta loppuun) toimii aina `main`-haarassa.
- Yksi ajaa konetta pitchissä, muut ovat hiljaa.
