# `src/bouncer/network` — kaista C (Joonas)

| Funktio | Sopimus | Status |
|---|---|---|
| `ip_intel(ip)` | S4 | DNS bot-verify + offline ASN + threat-feed; `verified_bot: bool \| None`; `country` vielä None |
| `find_campaigns(sessions)` | S5 | stuffing (C-3/C-4) + behavior (C-5) + NAT-suodatin (C-9) |
| `campaign_graph(...)` | — | nodes/edges A:n dashboardille |
| `evaluate_campaigns(...)` | S9 | purity/coverage (C-6); live lock odottaa A:n stuffing-labeleita |
| `network_pass(sessions)` | — | S4+S5+graafi yhdellä kutsulla A:n workerille |

Puhtaita funktioita: **ei tietokantakirjoituksia**. A:n worker kutsuu näitä.

S2: session-/campaign-id:t `str` (päätös 032). Duck-typing: `session_view.py` lukee `id`/`user_agent`/`ua`/`paths`/`headers`/`login_attempts`/`requests` (+ `X-Login-User`).
