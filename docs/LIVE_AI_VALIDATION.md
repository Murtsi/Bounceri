# Live model validation — 14 November 2026

These were paid inference requests from the Hostinger VPS against Featherless,
recorded in the application's existing PostgreSQL spending ledger. No mocked
provider results are counted. Simulator truth stayed outside model packets.

Two final-review candidates were fixed in advance: `Qwen/Qwen2.5-7B-Instruct` and
`Qwen/Qwen2.5-32B-Instruct`. The bounded decision role used the 7B model. Six signed
synthetic HTTP cases covered two browser actors, a scanner, scraper, failed login
and an unverified claimed crawler. These are exploratory synthetic checks, not
independently verified humans or a genuinely withheld attack.

Prompt v2 exposed cross-field consistency errors. The backend rejected them rather
than repairing or publishing unsupported findings. Prompt v3 clarified existing
rules; validation used a later signed simulator run after the prompt freeze.

| v3 configuration | Structured results accepted | Final labels |
|---|---:|---|
| Bounded 7B questions | 6/6 | Question answers; not a final traffic classifier |
| Bounded 7B + final 7B | 0/6 | Rejected under unchanged evidence/policy guards |
| Bounded 7B + final 32B | 6/6 | All `uncertain` |
| Direct final 32B, without preceding model findings | 6/6 | All `uncertain` |

All v3 requests returned the exact requested model identifier and completed within
the absolute 30-second deadline. Median bounded-stage latency was 2.696 seconds.
Median final-32B latency was 5.336 seconds in the cascade and 5.207 seconds directly;
the longest direct request took 29.016 seconds. Reported identifiers are provider
assertions, not cryptographic verification of model weights.

The v3 cascade cost attributable to the six cases was $0.008722, including cached
bounded decisions, versus $0.007381 for direct 32B review. Across both prompt
experiments the ledger recorded **48 requests / 36 jobs / $0.035080 settled / $0
unknown reservations** before the additional overnight experiment. Cached decisions
retain their original request/reservation provenance; they are not new paid calls.

The cascade demonstrated schema and evidence-contract compatibility after the
prompt correction. It **did not demonstrate improved detection quality** over direct
review or the local detector. Accepted results abstained on every final label.
The local detector also has cross-session context absent from scoped model packets,
so these checks do not establish a fair whole-population accuracy comparison.

Use 7B bounded assessment and 32B final review only as an explicitly experimental
advisory configuration. The owner separately approved at most 20 additional
synthetic-case reviews, alternating local findings and controls. The maximum pair
reservation is $0.04 ($0.01 + $0.03), hence at most $0.80 of additional reserved
exposure, within the existing $5 application cap. No private reasoning is requested
or stored, no automatic retries or model substitution occur, and model outputs
cannot activate enforcement or become training truth.

Model metadata reported 32,768-token contexts and prices per million input/output
tokens of $0.17/$0.20 for 7B and $0.68/$1.20 for 32B, with zero request fees. Output
ceiling metadata was absent; requests explicitly cap output at 800 tokens and are
checked against usage. Complete serialized request bounds are 24 KiB. Actual
account access, pricing and observed responses were checked before activation.

Production quality claims, real-human FPR below 1%, and novel-attack generalization
remain unestablished. See [the separately measured synthetic rules benchmark](EVALUATION.md).
