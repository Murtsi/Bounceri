# `src/bouncer/explain` — kaista C (Joonas)

| Funktio | Sopimus | Status |
|---|---|---|
| `explain(verdict, session, campaign)` | S7 | AI Router jos `HOSTINGER_AI_API_KEY`/`OPENAI_API_KEY` + grounded; muuten fallback |

LLM ei tee tunnistuspäätöstä. Env: `LLM_MODEL`, `HOSTINGER_AI_BASE_URL` (oletus Hostinger Router).
