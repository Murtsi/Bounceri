# Advisory traffic review

`ReviewRunner` claims one persistent job and performs at most one native Decision request and
one Featherless review request. It never retries, switches models, repairs malformed output,
executes tools, or creates another job. The existing local assessment remains available on failure.
The store owns transactions, the shared $5 ceiling, execution/request caps, immutable assessments
and evidence/configuration job deduplication. Unknown request charges remain reserved.

Paid review is disabled by default. `capabilities()` is the authoritative activation check;
`ReviewSettings.enabled` alone is insufficient. Enqueue with `settings.config_key`,
`settings.maximum_cost_microusd`, and `max_requests=2`. The configuration key pins both models,
routes, expected response identities, prompts, schema and conservative charge ceilings.

Configuration declarations do not verify a provider. Before setting any verification flag, record
external evidence for the native contract, exact model identity, enforceable no-substitution
behavior, access, current prices, billing units and model/plan limits. `LIMITS_VERIFIED` means the
entire bounded request, schema and prompts fit the actual context and the full billable output
(including reasoning tokens) fits the 800-token ceiling and conservative request charge.
The implementation bounds model packets to 16 KiB and complete serialized requests to 32 KiB;
these are byte bounds, not claims about a tokenizer. Lower model/plan limits require a separately
verified bound before activation.

Hostinger OpenAI-compatible chat support does **not** establish native Microsoft Decision support.
No native Hostinger route is supplied by default. Public Hostinger documentation advertises model
fallback; absent verified controls, leave this capability unavailable. The adapter requires an
explicit HTTPS native route on `router.hostinger.com`, a request model and an independently pinned
response model. It sends bounded `state`/typed `questions`, never a disguised chat request.
Native billing responses are not assumed to use Featherless USD units, so their actual charge
remains unknown and reserved until authoritative reconciliation is available.

Featherless sends nonstreaming chat requests with `max_completion_tokens=800` and a 30-second HTTP
timeout. There is no assumed `response_format`/JSON-schema enforcement. A bounded JSON prompt and
strict local schema validate output. Checkable observations must match original evidence, crawler
verification requires explicit provenance, and coordination claims cannot be established by this
phase-one aggregate packet. Finite schema/evidence checks do not prove arbitrary prose entailment;
assessments explicitly retain that limitation. Private reasoning fields are never stored.

Environment:

- Global: `BOUNCERI_REVIEW_ENABLED=true`; `BOUNCERI_DATABASE_URL` for the worker.
- Prefixes: `BOUNCERI_DECISION_` and `BOUNCERI_REVIEWER_`.
- Each prefix: `ENABLED`, `MODEL`, `EXPECTED_MODEL`, `ENDPOINT`, `CONTRACT_VERIFIED`,
  `IDENTITY_VERIFIED`, `NO_FALLBACK_VERIFIED`, `PRICING_VERIFIED`, `LIMITS_VERIFIED`,
  `MAXIMUM_COST_MICROUSD`, `PRICING_VERSION`.
- The verification/enabled flags accept `true` explicitly; missing or malformed values disable.
- Dedicated credentials only: `HOSTINGER_ROUTER_API_KEY`, `FEATHERLESS_API_KEY`.
  Legacy OpenAI credentials, model defaults and provider fallbacks are never consulted.

`discover_featherless(api_key, model)` reads only the documented authenticated `/v1/plan` and exact
`/v1/models/{id}` metadata endpoints. It returns sanitized access, effective context and pricing,
omits account balance, and never activates inference. These reads do not prove model quality,
strict schema support, routing identity guarantees or a conservative total charge ceiling.

Run `python -m bouncer.review.worker --capabilities` for sanitized, offline capability status;
`--once` handles at most one queued job. The default worker polls every five seconds and stops on
persistence failure, preserving running-job/reservation state instead of replaying inference.
Do not automatically reclaim interrupted jobs: a dispatched request may already have incurred a
charge. Run offline tests with `uv run pytest tests/c/test_review.py`.

Primary contracts:

- [Microsoft native Decision API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision)
- [Hostinger API compatibility](https://www.hostinger.com/support/what-is-hostinger-ai-router-and-how-to-get-started/)
- [Hostinger advertised fallback](https://www.hostinger.com/support/migrating-your-credits-from-nexos-ai-to-hostinger-credits/)
- [Featherless completions](https://featherless.ai/docs/completions)
- [Featherless models](https://featherless.ai/docs/api-reference-models)
- [Featherless plan](https://featherless.ai/docs/api-reference-plan)
