# Progress — 2026-11-15

Live and verified: https://bounceri.tech · public source: https://github.com/Murtsi/Bounceri
Traffic/research release: 3b137e8 · API explanation update: 0523bba.
Research preview: Metrics. Submission PDF and form text are ready.

Done:
- Core parsing, privacy, durable SQL/checkpoints, bounded network evidence and private log imports.
- Health, backup/restore, deletion/withdrawal, consent/session reviews and frozen native evaluation.
- Private captured-runtime evidence and independent-attack seal registry; their full operator workflow is not wired yet.
- Historical reply-targeting research preview: real attributed dataset, frozen post-level split and transparent weak baseline; full swarm validation remains unfinished.
- Public verdicts explain safe browsing, automation and attack observations; API healthy after the focused update (56 checks passed, 6 PostgreSQL checks skipped). Rules-only normal traffic can still be uncertain; no calibrated human model is active.

Separate development branch `b/captured-evidence-plan`: captured runtime profile
wired into private frozen plans and cached replay (81 focused checks passed,
18 skipped). Pushed for review; not merged or deployed for submission.

Still left:
- Finish captured-runtime/production configuration parity, hidden-attack reveal/scoring and verified publication.
- Collect permitted real/public data, actual consented humans and an independently withheld attack; production quality remains unverified.
- Implement **Trust the Source** (C2PA), **Spot the Swarm** (social coordination) and **Name the Technique** (text spans).
- Complete module UI/integration, evaluation and final release gates.

New modules remain unavailable. No automatic blocking or unverified quality claim is enabled.

Submission package: PDF (1.08 MB), paste-ready fields and demo script prepared. Hosted CI could not start because of a GitHub account restriction; local and live verification passed.
