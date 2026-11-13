# `src/bouncer/network` — kaista C (Joonas)

| Funktio | Sopimus | Status |
|---|---|---|
| `ip_intel(ip)` | S4 | DNS bot-verify + offline ASN (C-2); `country` vielä None |
| `find_campaigns(sessions)` | S5 | stuffing (C-3) + behavior clusters (C-5) |
| `evaluate_campaigns(...)` | S9 | purity/coverage (C-6); live lock odottaa A:n labeleita |

Puhtaita funktioita: **ei tietokantakirjoituksia**. A:n worker kutsuu näitä.

Duck-typing: `session_view.py` lukee `id/ip/ua/paths/headers/login_attempts/requests` — toimii ennen S2:ta.
