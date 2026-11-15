# Bounceri — ready-to-paste submission fields

Copy only the contents of each field block. Character counts and readiness notes are outside the fields.

## Project Name

```text
Bounceri
```

## Punchline

```text
Turn noisy web traffic into evidence you can act on.
```

## Description

```markdown
## The problem

A small website owner sees a spike in visits. Is it customers, harmless automation or a login attack? Raw access logs leave the interpretation to the owner. An unexplained threat score makes the next decision difficult: intervene, or leave visitors alone?

## What Bounceri does

Bounceri turns HTTP traffic into inspectable sessions and related campaigns. It shows request timing, visited paths, failed logins and shared targets, alongside a local assessment and readable reasons. Ambiguous activity can remain **uncertain**. Campaign links expose related behavior without claiming to identify a person or operator.

The working **Clean the Traffic MVP** runs at [bounceri.tech](https://bounceri.tech). Owners can inspect sessions, follow related HTTP activity and preserve a redacted investigation snapshot. Authenticated private log imports, durable traffic storage, source deletion and explicit manual test policies are implemented. Model assessments cannot activate enforcement.

## Built on Hostinger

The application runs on a **Hostinger KVM 2 VPS**. Caddy captures requests to our demo service; a Python/FastAPI worker builds sessions and applies local rules and network analysis. PostgreSQL stores traffic, investigations and review records. A React dashboard makes the evidence inspectable.

Local detection works without an AI key. Two optional **Featherless** roles answer bounded evidence questions and produce a final advisory review. Backend validation, persistent jobs, spending reservations and a shared budget cap bound that process. Evidence, local interpretation and model assessment remain separate records.

## What the demo proves

The public demo sends varied, signed **synthetic traffic** through the real HTTP pipeline. It demonstrates operation, not independently verified detection accuracy. Simulator truth is kept outside model evidence packets.

Our separate historical synthetic rules benchmark observed **0 false positives among 14 simulated-human sessions**. Its two-sided 95% Wilson upper bound is **21.53%**; this does not establish a real-human false-positive rate below 1%. In the recorded live synthetic model experiment, every accepted final review returned uncertain. That demonstrated evidence-contract compatibility, not improved detection quality. Production detection quality, independent human false-positive performance and novel-attack recall remain unverified.

## Separate research preview

We also built a small historical reply-targeting research preview from Manita Pote's [Coordinated Reply Attacks dataset](https://zenodo.org/records/13896309), attributed under **CC BY 4.0**. It uses 7,732 unique post IDs, a fixed tweet-ID split and a transparent, train-only similarity baseline. Its selected-control false-positive rate is 44.15%, and actor/campaign independence is unverified. Labels describe historical targeted tweets versus selected controls, not bots or malicious users. This is exploratory research, not a validated coordination detector; the full social Spot the Swarm capability remains unavailable.

## Next step

We want a consented pilot with small website owners and Hostinger support teams: real logs, independently reviewed sessions and measured false alarms. Source-provenance and text-technique analysis remain planned modules. Bounceri helps owners inspect the evidence and its limits before deciding what to do.
```

## Challenge

```text
Decode the Noise
```

## Demo Link

```text
https://bounceri.tech
```

## Code Link

```text
https://github.com/Murtsi/Bounceri
```

## Video Link — optional

Leave blank. No recorded-video link has been provided.

## Other Link — optional

```text
https://bounceri.tech/?tab=metrics
```

## Presentation

Upload **Bounceri-pitch.pdf** from this output folder. The supplied PDF is approximately 1.08 MB, below the 20 MB limit.

## Character counts

Counts include spaces, punctuation and Markdown inside each field block; field labels and code fences are excluded. Verified with Python `len()` after UTF-8 decoding.

- Project Name: **8 characters** / 30 maximum.
- Punchline: **52 characters** / 200 maximum.
- Description: **3404 characters** / 5000 maximum.
- Challenge: **16 characters**.
- Demo Link: **21 characters**.
- Code Link: **34 characters**.
- Other Link — optional: **34 characters**.

## Readiness notes — do not paste into the form

- The core traffic MVP and research preview are live. Metrics and research APIs returned HTTP 200; the focused public browser check passed at 07:31 UTC.
- The repository is public following the owner's approval. Logged-out access to https://github.com/Murtsi/Bounceri returned HTTP 200.
- The optional Video Link can remain blank. No team emails or full-name fields were specified in the supplied form requirements.
- The 90-second click script is in Bounceri-demo-script.md. The three-minute English pitch and seven-slide content are in Bounceri-submission.md.
