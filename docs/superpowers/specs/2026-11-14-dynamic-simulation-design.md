# Variable private traffic simulation

The owner requested continuously changing traffic rather than repeating the same
human/scanner/scraper/login template. This extends the previously approved native
simulation and hard-negative work; it does not change detection thresholds or UI.

## Chosen design

Use a CPU-only stochastic behavior generator. Small behaviors compose into journeys
with varied state transitions, timing, paths, headers, cache behavior, actor counts,
request volumes and campaign shapes. Each live episode uses a fresh entropy seed;
the seed, generator version and episode identifier allow deterministic plan replay.
The original fixed generator remains available for legacy acceptance fixtures.

Human profiles include slow/rapid/assetless browsing, missing privacy headers,
ordinary failed-login retries and shared NAT. Automation includes benign monitors,
unknown-authorization scraping, browser-like automation, varied vulnerability
probing and coordinated or dispersed login attempts. Mixes may be benign-only,
attack-heavy or mixed. Synthetic identity/UA pools must not encode reference class.
Unknown authorization is not labelled malicious, and no crawler is DNS-verified by
the simulator. The demo never accepts real credentials or fabricates login success.

The simulator issues real HTTP requests exclusively to the private Docker gateway.
Do not follow redirects or honor proxy environment variables. Bound each episode
to at most 24 actors, 240 requests and 120 seconds, with a global rate limit and
bounded concurrency. Use a few seconds of varied inter-episode idle time instead
of six-minute fixed waves. Back off on overload responses; never automatically
increase rate to defeat protection. Check stop/deadline before issuing requests.

Persist bounded replay/intent manifests in a simulator-only named volume, separate
from the detector's store and PostgreSQL. Reference labels stay in signed simulator
markers and this private manifest; ingestion strips marker/signature headers from
detector inputs. Allocate source identities per episode to prevent five-minute
sessionization from mixing conflicting episode truth after restart. Shared-NAT
profiles explicitly share a common reference marker when their IP/UA group merges.

The live runner continuously creates episodes until stopped, with resource limits
unchanged. Simulation does not call an LLM, inspect detector output or train model
weights. Procedural variety is not evidence of real-world or novel-attack accuracy.
Existing paid-review budget/counters must survive deployment without reset or increase.

## Acceptance

- Identical seed/config/episode yields identical plan; live restarts choose fresh seeds.
- Across a fixed development seed suite, volumes, mixes, timing/path sequences and
  behavior fingerprints materially differ; include benign-only and attack-heavy runs.
- Every generated request satisfies target/path, actor, request and duration bounds.
- Benign and hostile roles can share user agents/address ranges; no reference label
  reaches normal parsed request headers or the provider evidence packet.
- Exercise actual private HTTP execution, stop/deadline, global pacing and overload
  behavior offline before deployment. Retain legacy tests and original dashboard.
- Deploy only after main is synchronized; verify two differing real VPS episodes
  and dashboard/API health, rather than relying solely on generated plan differences.
