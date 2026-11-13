# Team — Hostinger: Decode the Noise

## People and roles

Kolme henkilöä, kolme kaistaa. Kaistat on valittu niin, että kukaan ei odota toista ensimmäisten tuntien aikana.

| | Rooli | Omistaa | Ensimmäiset 8 h | Sen jälkeen |
|---|---|---|---|---|
| **A** | Infra + data pipeline, integraattori | VPS, Docker, Caddy, demosivusto, ingest, Postgres, CI, `main` | VPS + domain + TLS + demosivusto + ansapolut julki → JSON-lokit talteen | Ingest → sessiot → DB; deploy-putki; valvoo että demo pysyy pystyssä |
| **B** | Tunnistus + arviointi | Piirteet, säännöt, malli, kynnykset, kampanjat, `/metrics` | Piirteet tallennetusta lokinäytteestä notebookissa; labelien lähteet | Malli, kynnykset, temporaalinen arviointi, kampanjaklusterointi |
| **C** | Tuote + pitch | Simulaattorit, API, dashboard, LLM-selitykset, pitch, video | Hyökkäys- ja ihmissimulaattorit (merkityt) → B saa oikeat vastaukset | API, dashboard, AI Router -selitykset, lokin lataus, pitch + varavideo |

Nobody owns "everything". If a file has no owner, A (integraattori) owns it.

Rajapinnat kaistojen välillä (sovitaan ensimmäisen tunnin aikana, ei muuteta ilman kolmen hengen sopimusta):

- **A → B:** `requests`- ja `sessions`-taulujen skeema (ks. `ARCHITECTURE.md`).
- **B → C:** funktio `score(session) -> {label, score, reasons[], model_version}` ja `metrics.json`.
- **C → B:** simulaattorit merkitsevät liikenteensä otsakkeella `X-Sim-Run: <ajo-id>:<luokka>`; otsake poistetaan piirteistä ennen pisteytystä.
