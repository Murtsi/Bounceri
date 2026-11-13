# `src/bouncer/network` — kaista C (Joonas)

| Funktio | Sopimus | Status |
|---|---|---|
| `ip_intel(ip)` | S4 | DNS bot-verify + offline ASN + threat-feed; `country` curated FI-prefixeistä; `ip_intel_contract()` B:lle |
| `find_campaigns(sessions)` | S5 | stuffing (C-3/C-4) + behavior (C-5) + NAT-suodatin (C-9) |
| `campaign_graph(...)` | — | nodes/edges A:n dashboardille |
| `evaluate_campaigns(...)` | S9 | purity/coverage (C-6); live lock odottaa A:n stuffing-labeleita |
| `network_pass(sessions)` | C-8 | S4+S5+graafi + B-maps (`intel_by_ip_contract`, `campaign_by_session`, `campaigns_api`) |
| `python -m bouncer.network.hidden` | C-10 | Piilotettu ajo → löytyikö kampanja (ei retunea); `--write` vasta oikealla datalla |
| `python -m bouncer.network.lock_fixture` | C-4/C-6 | Synteettiset purity/coverage → `campaign_metrics.fixture.json` (ei tuotanto-S9) |
| `ExplainCache` (`bouncer.explain`) | C-8 | In-memory S7-välimuisti A:n API:lle |

Puhtaita funktioita: **ei tietokantakirjoituksia**. A:n worker kutsuu näitä.

S2: session-/campaign-id:t `str` (päätös 039). Duck-typing: `session_view.py` lukee `id`/`user_agent`/`ua`/`paths`/`headers`/`login_attempts`/`requests` (+ `X-Login-User`).
