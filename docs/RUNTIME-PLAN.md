# Selected Bounceri runtime

The owner approved implementation and selected **Featherless for both the bounded
decision and final advisory reviewer** after native Microsoft Decision could not
be verified through Hostinger. This supersedes the earlier Decision-1-first plan.
Gemini is excluded (decision 063).

The latest GitHub dashboard and its default overview remain intact. Investigations
is an additional view. Clean the traffic is implemented first; social coordination,
text manipulation and provenance remain explicitly gated future modules.

This is the implemented runtime, not a pending orchestration proposal. The
asynchronous runner (`src/bouncer/review/runner.py`), worker and persistent review,
reservation and assessment ledger exist. Deployment and paid synthetic inference
are recorded in [HOSTINGER_LIVE.md](HOSTINGER_LIVE.md) and
[LIVE_AI_VALIDATION.md](LIVE_AI_VALIDATION.md); those records are not a fresh live
health check. See [MODULES.md](MODULES.md) for the evidence and capability boundaries.

## Implemented flow

Hostinger private HTTP simulator → Caddy → bounded session/campaign detector →
immutable redacted PostgreSQL investigations → asynchronous Featherless bounded
assessment → Featherless final advisory review → backend evidence validation and
recorded history → existing dashboard plus Investigations.

Both model roles record actual provider/model identities. They are not independent
votes and never supply training truth. Local findings remain on failure. Native
Hostinger Decision is an explicit, unavailable-until-verified option.

The shared ledger caps known spending plus unknown reservations at $5, 100 uncached
executions and 200 requests. Each review has at most two requests, each with a
30-second HTTP timeout and 800 output tokens, without retry, repair or paid fallback.
Provider ceiling breaches halt later dispatch, including already queued jobs.
Oversized/incomplete model packets stay inspectable but explicitly AI-ineligible.

An optional 20-execution synthetic review experiment can be enabled after provider,
model and pricing validation. Missing credentials leave review visibly unavailable
with local detection running; they never produce a fabricated model result.

## Enforcement and evaluation

The mentor requested live enforcement. An authenticated administrator can apply
reversible manual test policies to HMAC-authenticated synthetic actors on a dedicated
demo route. Actual HTTP 429/403 effects, expiry, revoke and benign isolation are
tested and recorded. Model output cannot activate a policy or alter the VPS firewall.

Overnight simulation collects independently signed evaluation data; it does not
retrain production weights. Keep real, synthetic and held-out results separate.
Publish measured precision, human FPR, uncertainty, counts and confidence intervals
only after corresponding evaluation. The <1% real-human FPR remains a target.

The recorded reserved benchmark contains 14 synthetic human sessions, with zero
false positives and a 95% Wilson upper bound of 21.53%; it is not real-human
validation or an independently withheld attack. Every accepted final model review
in the recorded live experiment returned `uncertain`, so contract compatibility
does not establish improved detection quality. `models/metrics.json` remains a
stub with null production results.

## Next implementation gates

Core hardening precedes module expansion: versioned database migrations, a durable
traffic repository and replay/checkpoint handling, bounded hosted network evidence,
complete investigation evidence, private log import, operational checks and
consented leakage-safe evaluation remain work in the selected implementation plan.
The hosted runtime currently passes `intel_fn=None`; a local DNS adapter and tests
do not establish live crawler verification. No arbitrary log/media/social/text
upload or module-specific analyzer is implied by the existing case endpoint.

Trust the Source, social Spot the Swarm and text Name the Technique remain
`implemented=false, enabled=false` until their separate input, local analysis,
evidence, evaluation and UI slices pass. Configuring a model cannot enable them.

See [Hostinger setup and cost controls](HOSTINGER_LIVE.md) for reproducible deployment,
model activation, overnight runs and operator verification.
