# Frozen evaluation implementation status

The consent/review foundation is implemented. The first partitioning component is
also implemented; the frozen evaluator and durable holdout receipts are still in
progress. This document does not announce an actual study, untouched holdout or
release-quality metric. Production metrics remain a stub.

## Declared groups and time windows

`bouncer.eval.partition.partition_examples(examples, windows)` accepts private
`GroupedExample` metadata: source/native session/content digest, full start/end
interval, stable actor ID, collection/run ID and every declared campaign ID.
Required unknown identity is `None`; an empty campaign tuple explicitly means
not applicable. Neither shared IPs nor per-session IDs create participant truth.

The fixed roles are `fit`, `calibration` and `test`. Windows are explicit,
timezone-aware, chronological and nonoverlapping; valid offsets normalize to UTC.
Each window is half-open. A component's start must be at or after its lower bound
and its end strictly before the upper bound. A point session on an adjacent
boundary belongs to the next window. A session spanning the boundary does not.

Known actor, run and campaign links form complete connected components across all
sources before role assignment. Transitive links count. Any unknown required
identity quarantines its whole known component. Components crossing windows,
falling into a gap or outside the collection windows receive explicit exclusion
reasons. No future observation moves into training to rescue a split.

Duplicate source/native-session identities are rejected even if their supplied
digests differ. Composite observation keys match the study bridge. The private
JSON-ready result preserves normalized exact references, components, role members
and excluded metadata, deterministically regardless of input order. Limits are
20,000 observations, 64 declared campaigns per observation and 256 UTF-8 bytes per
opaque identity. Invalid dates, types, digests and storage-unsafe identities fail.

These guarantees cover declared metadata. They do not verify that two supplied
actor IDs represent different people, that campaigns are genuinely independent,
or that an omitted relationship does not exist. Collection and annotation
procedures must establish those facts separately.

## Remaining implementation and evidence gates

The following work is required before end-to-end frozen evaluation is complete:

- Load current source-validated reviews and permitted native reference data; keep
  human studies, synthetic fixtures and public historical robot tasks separate.
  Require authoritative actor/run/campaign metadata, not inferred unique IDs.
- Build and validate the exact private partition manifest before fitting/tuning.
  Select admitted role/context observations before network or campaign inference;
  exclusions and withheld rows cannot influence another role's detector context.
- Fit preprocessing/weights on fit only and choose thresholds on calibration only.
  Freeze exact model/threshold/code/config/dependency/feature bytes before test
  exposure. Rules-only and learned/network ablations require explicit artifacts.
- Claim holdout consumption durably and atomically, bind it to those artifacts,
  and retain a receipt on failure. Cached reproduction cannot make a viewed
  holdout independent again. Revalidate current consent/review/content before use.
- Gate production publication on verified frozen evidence and real cohort support.
  The legacy sample/database timestamp splitter and its `--write` path do not
  enforce this protocol and must not be used as release evidence. In particular,
  a source-level `synthetic=false` switch cannot turn simulator labels into real
  human truth. The frozen path must close that publication gap.
- Record a genuinely withheld attack's independent author, sealed/reveal times and
  frozen-artifact linkage. A known generator template or an arbitrary run name is
  not independently withheld evidence.

Reports must preserve reference counts, uncertainty, human false positives and
confidence intervals with session and participant/run support. Repeated sessions
do not establish independent-user power. Public `ROBOT` labels do not become
maliciousness labels; unknown automation intent stays unknown. Real-human and
independent-hidden-attack quality remain unavailable until actual evidence exists.

Historical synthetic results remain in [EVALUATION.md](EVALUATION.md). Current
private collection/review instructions are in [HUMAN_STUDY.md](HUMAN_STUDY.md).
