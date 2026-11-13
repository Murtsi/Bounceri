# `src/bouncer/network` — kaista C (Joonas)

| Funktio | Sopimus | Status |
|---|---|---|
| `ip_intel(ip)` | S4 | DNS bot-verify + offline ASN (C-2); `country` vielä None |
| `find_campaigns(sessions)` | S5 | stub `[]` (C-1) → stuffing (C-3/4) → MinHash (C-5) |
| `eval.py` → `campaign_metrics.json` | S9 | stub (C-1) → lukittu C-6 |

Puhtaita funktioita: **ei tietokantakirjoituksia**. A:n worker kutsuu näitä.
