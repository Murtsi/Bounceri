# Bounceri on Hostinger

The complete application runs on the existing Hostinger KVM 2 VPS. Hosted model
inference uses Featherless, as selected by the owner. Gemini is excluded. A local
GPU, a model-training VM and another paid hosting plan are unnecessary.

The latest GitHub dashboard remains the default, including its logo, theme toggle,
overview, sessions, campaigns and metrics. Investigations is an additional tab.
Clean the traffic is the implemented module. Social swarms, text techniques and
source provenance remain explicitly unavailable future modules.

## Runtime and public URLs

- Dashboard/API: `https://bounceri.tech` and `https://www.bounceri.tech`
- VPS preview: `https://bounceri.srv2159025.hstgr.cloud`
- Owned demo service: `https://demo-bounceri.srv2159025.hstgr.cloud`
- Existing Traefik terminates HTTPS. Existing Hermes and its configuration stay separate.

The new `bounceri-live` Compose project contains PostgreSQL 16, the demo service,
private Caddy simulation gateway, simulator, ingest/detection worker, API/dashboard
and asynchronous review worker. A one-shot init container installs the checksummed
source capsule, pinned Python dependencies and additive database schemas first.
Only API and the demo service receive public Traefik routes. PostgreSQL, raw logs,
the simulation gateway and worker processes have no published public endpoints.

The source capsule includes Python modules, a built dashboard and an explicit list
of runtime data files. It excludes Git, credentials, labels, private exports and
raw traffic. It works with a private GitHub repository without giving the VPS a Git
token. Runtime code is mounted read-only; services have bounded memory, CPU and
logs. Each release uses its checksum in service paths/configuration so an update
recreates application processes rather than leaving old imports running.

## Rebuild and package

Run from the repository root, with Node/corepack, uv and Docker available:

```powershell
Push-Location frontend
corepack pnpm install --frozen-lockfile
corepack pnpm run build
Pop-Location
uv run pytest -q
uv export --frozen --no-dev --no-emit-project --no-hashes --output-file deploy/requirements-runtime.txt
uv run python -m tools.hostinger.package --output C:/private/bounceri-deploy --alias bounceri.tech --alias www.bounceri.tech
```

The output directory contains `.env.hostinger` (generated operator/database/actor
secrets) and `compose.private.json` (source capsule plus private server settings).
Keep both private and preserve the generated secrets between deployments. Never
post their contents, commit them, or send them to the browser. The repository
ignores these private filenames, but an output outside the repository is preferred.

Deploy the **contents** of `compose.private.json` through Hostinger Connector
`vps_docker_create`, VPS `2159025`, project `bounceri-live`. Read project state first.
Do not use an existing Hermes/Traefik project name. Do not remove data volumes or
change the database password when updating existing data. Wait for init completion,
read container status back and verify the HTTPS URLs, not just the API's queue reply.
The hosted connector currently limits both content and environment fields to 8192
characters, so it cannot upload this complete capsule. Use the authorized SSH/SCP
fallback: verify the SSH host public key through the authenticated Hostinger
connection, retain strict host-key checking, copy the bundle to
`/docker/bounceri-live/docker-compose.yml`, set directory/file permissions to
0700/0600, validate it and run `docker compose -p bounceri-live -f
/docker/bounceri-live/docker-compose.yml up -d`. Use the connector to read projects,
containers and logs back afterward. Never disable host-key checking.

For a local production-stack smoke test, add `--local` and run:

```powershell
docker compose -p bounceri-integration -f C:/private/bounceri-deploy/compose.private.json up -d
uv run python -m tools.hostinger.operator smoke-enforcement --secrets C:/private/bounceri-deploy/.env.hostinger --local
```

Local API/demo ports are loopback 18181/18180. This is a separate project from the
older `make demo` stack; the deployment does not stop other local projects.

## Overnight simulation and learning foundation

The simulator sends actual HTTP requests through the private Caddy gateway into
our own demo service. The default is 12 browser-like actors, a scraper, a probe
scanner, six distributed failed-login actors and an unverified claimed crawler:
21 actors / 235 requests per round, every six minutes, at most 240 rounds per
process. It then idles. The target is fixed to `simulation-gateway:8080`; redirects
are not followed. It never sends attack requests to another person's website.

The six-minute interval exceeds the five-minute session idle window, preventing
different rounds' signed truth labels from conflicting in one session. Labels are
HMAC authenticated and kept out of model evidence. Browser timings/content vary
with each round's seed. This is a reproducible synthetic test environment, not
verified real-human traffic and not a comprehensive attack distribution.

The worker retains at most 30 minutes / 6000 records, including after a restart,
and publishes redacted immutable synthetic investigations. It keeps full traffic
snapshots plus round-robin cases covering one complete retained session. Those
small cases can fit the AI evidence budget without silently truncating a large
window. Large snapshots remain inspectable and explicitly AI-ineligible when they
exceed the shared contract. The old JSON store still feeds the existing dashboard;
PostgreSQL persists investigations, assessments, job reservations and policies.

This run collects evaluation data. It **does not change detector weights or train
on its own predictions**. Start with independently labelled simulations and hard
negatives, then add consented real logs and public datasets with provenance. Hold
out whole runs/scenario variants and time windows; fix thresholds on development
data before evaluating the held-out run. Report precision, human false positives,
uncertain share, sample counts and confidence intervals separately by source.
Model disagreement is review material, not an automatic training label.

The existing offline evaluator can inspect the store without paid calls:

```powershell
# BOUNCER_STORE_PATH must point at an explicitly exported private store.
uv run python -m bouncer.eval.run --source db --offline --report C:/private/features.md
```

Do not use `--write` to replace a production model with synthetic results. The
evaluator guards that path. The release metrics remain unmeasured/stub until the
required evaluation exists. A low observed FPR in a small synthetic demo does not
establish the project's <1% real-human FPR target.

## Activate cost-bounded Featherless review

The two roles are **bounded decision** and **final advisory reviewer**, not Microsoft
Decision-1. Each records requested/returned model, provider, prompt/schema version
and original evidence references. The first sees observations without local
predictions; the second sees observations plus the earlier assessment. Backend
checks reject unsupported attack/coordination claims and malformed observations.
Valid evidence references still do not prove arbitrary prose is semantically true.

1. Put a rotated `FEATHERLESS_API_KEY` into the ignored local credential file. Use
   the documented GET-only model/plan discovery helper to verify actual access,
   prices and context/output limits. Do not guess model availability or treat a
   chat API as a native Decision endpoint.
2. Validate at most two explicitly named reviewer candidates on development cases.
   Record schema failures, uncertainty, false positives, latency and costs. Do not
   activate a thinking model without verifying its full billable output limit.
3. Record the verified per-role settings from `.env.example` in private JSON. Set
   flags only from observed/documented provider contracts, never to silence a gate.
   Package with `--review-config <private-json> --credentials <ignored-dotenv>`.
4. The global ledger caps total known spending plus unknown reservations at $5,
   100 uncached executions and 200 outgoing requests. Preflight uses at most $0.50.
   An entire two-stage maximum is reserved before queueing. Each role has one
   request, 30-second HTTP timeout, 800 output tokens and no automatic retry,
   repair or paid fallback. Unknown charges stay held. Any provider ceiling breach
   halts later dispatch, including queued jobs. Reconcile unknown charges manually;
   never reset the database to bypass the cap.
5. Admin `POST /api/investigations/{id}/reviews` requests an eligible case review.
   `BOUNCERI_AUTO_REVIEW=true` optionally queues round-robin synthetic session cases;
   the default experiment cap is 20 executions, still subject to the shared ledger.
   This is a cumulative execution ceiling including preflight jobs; to authorize
   20 additional experiment jobs, set it to current executions + 20 (never above 100).
   Missing credentials/configuration leaves local detection and the public demo
   running with a visible unavailable review state and zero model requests.

No per-visitor model calls are made. The owner can inspect `/api/capabilities`,
`/api/usage` and separate assessment history. Paid results cannot change evidence,
create jobs/tools or automatically activate an enforcement policy.

## Controlled enforcement verification

An administrator may approve `rate_limit` or `temporary_block` for an enrolled
synthetic `attack`/`benign` actor on `/enforcement-demo/{actor}/probe` only. Actor
credentials are HMAC authenticated; missing/forged credentials are rejected. The
default TTL is 60 seconds, maximum 300; rate limiting is 10/minute with burst 3.
The site, dashboard, other customers and VPS firewall are outside this policy scope.

Policies are explicitly labelled **manual demo overrides**, because an aggregate
case does not prove that actor's identity. The UI displays persisted status,
expiry, affected-request counters and history; it has no operator secrets or write
actions. Operator verification performs actual requests, observes HTTP 429/403,
checks benign isolation, waits for expiry and tests immediate revocation:

```powershell
uv run python -m tools.hostinger.operator smoke-enforcement --secrets C:/private/bounceri-deploy/.env.hostinger
```

The check makes no paid model calls and revokes its own test policies at the end.
This is a functional actor-scoped demonstration, not proof of evasion-resistant
anonymous Internet blocking. A database lookup failure makes this dedicated route
unavailable while leaving normal pages and admin recovery accessible.
