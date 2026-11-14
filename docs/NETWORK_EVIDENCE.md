# Bounded network and scoped traffic evidence

Hosted runtime code and the non-offline worker use the existing S4 contract through `LiveIntel`. Each cycle admits at most four subprocess lookups, with a one-second lookup deadline and four-second DNS budget. Startup, wait, kill and reap time are charged; late results become unknown. The OS process-creation call itself cannot be preempted by Python, so this is an application budget rather than an operating-system real-time guarantee. No DNS thread is left blocking worker shutdown.

The cache holds at most 2048 entries. Successful verification/mismatch entries live 300 seconds; inconclusive entries live 60 seconds. Reads preserve the original checked_at. Capacity skips are uncached so later cycles can make progress. The worker snapshots each observation immediately, before cache eviction can discard another active client's metadata. There are no paid calls in this path.

Only a plain IP address can enter the child command. It uses the existing reverse/forward IPv4+IPv6 verification once, and the existing curated ASN/threat prefix mapping. A verified result requires a recognized crawler and a successful DNS round trip. Lookup failure, timeout or budget exhaustion stays unknown; it is never a spoofing verdict. A mismatch means the IP did not verify as a supported search crawler; it does not label an ordinary visitor malicious. Curated country/ASN metadata is labelled curated-prefix; inferred datacenter status is labelled inferred. It is not live GeoIP or verified human identity.

The DNS procedure follows the official [Google crawler verification guidance](https://developers.google.com/crawling/docs/crawlers-fetchers/verify-google-requests) and [Bingbot verification guidance](https://www.bing.com/webmasters/help/how-to-verify-bingbot-3905dc26) within this project's supported Googlebot/Bingbot scope. Other crawler/fetcher families are not silently added.

## Retained evidence

Private traffic snapshots store IP observations under ip_evidence and per-session deterministic observations under rule_observations. These persist through either the SQL metadata read model or the JSON compatibility adapter. Case projection redacts addresses, user agents, raw target accounts, paths, request headers and simulator labels. It retains typed check times/outcomes, coarse ASN origin, unique matching trap-path counts with the active trap-config hash, allowlisted feature values and rule IDs as local interpretation.

A campaign_summary references complete scoped session evidence IDs, hashes its campaign reference, and derives member/client/failure/shared-target/window counts from the retained requests. An absent member or known source rotation gap makes evidence incomplete. Intentional rolling-window retention is a stated scope limitation, not invented missing data. A one-session aggregate cannot become multi-session relationship proof.

The automatic case sampler includes complete connected campaign context when that scope has at most 32 sessions and every member exists. Otherwise it preserves the missing/oversized relationship as incomplete and review-ineligible. Neither storage nor review truncates a packet just to obtain eligibility. Existing byte/item gates remain; sufficiently large complete cases are stored with explicit review ineligibility.

The Decision model sees original count/feature/provenance observations, with local labels, scores and rule IDs removed. Candidate relationships are not proof of a shared operator, maliciousness or social coordination. The bounded coordination answer remains unknown, and an observed coordination recommendation is rejected. Restrictive recommendations and maliciousness still require retained deterministic probe/trap observations. All review remains advisory; no model output activates enforcement. Prompt version traffic-review-v5 separates this context from earlier review cache keys.

## Evaluation limits

Native synthetic generator version 2 adds a bounded service-monitor burst and same-NAT shared-account retry controls. These are transparent integration controls, not independent human evidence or a genuinely withheld attack. Existing frozen synthetic result files remain unchanged; production metrics stay unmeasured until valid labelled non-synthetic evaluation exists. The owner intends permitted public data mixed with consented human activity; provenance, permissions, source partitions and label review remain mandatory for that later collection.

Local checks and deployed behavior are distinct. A real bounded lookup may time out while still returning separately marked curated ASN metadata. DNS reachability, a live verified crawler, and Hostinger rollout must be recorded from their own checks; an installed resolver or configured LLM does not establish measured detection quality.
