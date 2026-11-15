# Frozen evaluation implementation status

Private native preparation, frozen rules/logistic artifacts, separate partition
contexts and durable test-consumption receipts are implemented. They support
current consented reviews and exact, known synthetic generator references. Actual
independently withheld attack evidence and production publication remain separate
unfinished gates. This does not announce a real study or release-quality metric;
production metrics remain a stub.

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

## Private operator workflow

Set `BOUNCER_TRAFFIC_DATABASE_URL` and `BOUNCER_DATABASE_URL` privately to the same
persistent PostgreSQL database or explicit SQLite file. SQLite memory/URI/query
forms and unnamed PostgreSQL databases are refused. URLs never belong in command
arguments. SQLite is the local/test adapter; PostgreSQL is the shared runtime.

```text
uv run --no-sync python -m bouncer.eval.frozen_cli prepare --plan /private/plan.json
uv run --no-sync python -m bouncer.eval.frozen_cli evaluate --preparation PREPARATION_SHA256 --output /private/report.json
uv run --no-sync python -m bouncer.eval.frozen_cli status --preparation PREPARATION_SHA256
```

The source-checkout equivalent is `python -m tools.datasets frozen-evaluation`.
The installed wheel supports the first form without needing the repository's
`tools` package. The native fixture and registry implementations are now runtime
package modules; old source CLI imports remain compatibility exports.

A plan is strict UTF-8 JSON, limited to 256 KiB, with at most 1,000 dedicated
collection sources. This permits studies above the plan's 300-participant minimum;
fixture identifiers do not establish actual people or independence. Duplicate
keys, non-finite values and unknown fields are rejected. This example exercises known public templates
only; it is not a real-human or genuinely withheld dataset:

```json
{
  "schema_version": "frozen-native-plan-v1",
  "detector": "logistic",
  "collections": [],
  "synthetic_manifests": ["/private/native/manifest.json"],
  "windows": {
    "fit": {"from": "2026-01-01T00:00:00Z", "until": "2026-01-01T01:00:00Z"},
    "calibration": {"from": "2026-01-01T01:00:00Z", "until": "2026-01-01T02:00:00Z"},
    "test": {"from": "2026-01-01T02:00:00Z", "until": "2026-01-02T00:00:00Z"}
  }
}
```

Generate such a fixture through the existing source CLI, with one run per
partition, outside Git. The template's dates do not become dates for actual
participants. For actual sources add explicit collection entries with
`source_key`, `run_id` and `campaign_ids`, and use windows matching their real
collection times. Current approved reviews are loaded from those dedicated
sources. Preserve the participant ID across collections. Unknown run/campaign
metadata is `null` and quarantines the connected component; do not invent an ID
per session to rescue a partition. An empty campaign list explicitly asserts that
campaign identity is not applicable.

Only approved manual/benign study observations are human reference truth. Other
approved operation/intent observations remain unknown traffic classes. Synthetic
truth comes only from a bounded snapshot that exactly regenerates from the current
known fixture generator, including canonical run identities and file bytes.
Owner-editable checksums alone cannot authenticate labels. Public historical
`ROBOT` feature files cannot enter this native maliciousness task.

Preparation reserves actor/run/campaign/native-identity hashes before fitting.
Development groups may be reused only as development. A holdout belongs to its
exact preparation; it cannot become development or a new candidate's fresh test.
This conservative workflow freezes one candidate family, including its network
ablation, for each reservation. Choose the detector before preparation. Exact
reserved preparation can resume fitting if no test was claimed; frozen artifacts
cannot change. Ledger state is shared SQL, not a filename or in-memory flag.

`rules` freezes the explicit local baseline. `logistic` fits preprocessing and
weights on fit references only and calibrates thresholds on calibration only.
Both classes and complete labeled native evidence are required for logistic fit
and calibration. Network and no-network variants have independent fitted models.
Calibration uses model probabilities; test labels come directly from the shared
native cascade, including its hard-rule priority. Learned abstention thresholds
cannot erase a deterministic rule's false alarm from the evaluation.
Campaign context is computed separately for each role and declared run. DNS and
project traps are disabled; ambient model files are never loaded. Missing
evidence is reported unavailable rather than invented.

Preparation's child physically receives fit/calibration data only; scoring's
child receives test data only. Workers have fixed module entrypoints, minimal
environments without provider/database credentials, finite JSON protocols, a
30-second deadline including startup/cleanup, 16 MiB input/output bounds, at most
6,000 sessions and 20,000 requests. OS process creation itself cannot be preempted
by Python. Parent validation checks artifacts, prediction coverage and score/label
coherence and recomputes aggregates from trusted references. No provider is called.

The immutable candidate binds code, configuration, actual dependency/runtime file
hashes, installed versions, available lockfiles, model bytes and thresholds.
Installed declared dependency closure includes installed optional requirements
conservatively. Different code, package files, runtime or references invalidate
reuse; changing a version string alone cannot hide changed dependency bytes.

Evaluation commits its claim before test CPU runs. A crash or failure does not
restore independence. Current consent, review revisions, native content and code
are rechecked before use and after scoring. Completed exact replay verifies its
report digest and returns cached results without scoring again. Report exports
are new private files outside Git/library directories, limited to 8 MiB; stdout
contains receipt metadata only. Existing files and symlinks are refused.

## Recovery, deletion and remaining gates

A claimed evaluation blocks source purge/withdrawal. Stop the owning process
before explicitly closing a stranded claim:

```text
uv run --no-sync python -m bouncer.eval.frozen_cli close-interrupted --preparation PREPARATION_SHA256 --confirm-worker-stopped
```

Closure marks the holdout unavailable and consumed; it does not retry, release
groups or reset counters. Source deletion then revokes bound preparations and
scrubs private reference/artifact/report payloads. Minimal group-use and receipt
hashes remain. Original files, exports and external records need their own
deletion. Restoring an older archive requires reconciling subsequent withdrawals
and holdout consumption before evaluation; restored complete receipts remain
consumed. No restored database is selected automatically.

Legacy timestamp-only `--write`, `write_metrics` and version-only hidden-result
publication are now unavailable before loading, network access or writing files.
Development scoring/reports remain available. A `synthetic=false` flag cannot
publish simulator reference labels as real quality. No new boolean/protocol flag
bypasses a release check.

Still required before complete Phase 1.8/release evidence:

- Actual permitted public sources and independently reviewed human collections,
  with group independence established by their collection procedure.
- Independently authored attack commitment/reveal metadata and frozen-artifact
  linkage. Known generator templates and arbitrary run names are not hidden.
- A verified production publisher using frozen receipts and actual cohort support;
  it must also verify target-runtime/configuration and source applicability.
  These offline DNS/trap-disabled reports do not establish the deployed live
  detector's false-positive rate. Private native reports alone do not overwrite
  production metrics or models.

Reports must preserve reference counts, uncertainty, human false positives and
confidence intervals with session and participant/run support. Repeated sessions
do not establish independent-user power. Public `ROBOT` labels do not become
maliciousness labels; unknown automation intent stays unknown. Real-human and
independent-hidden-attack quality remain unavailable until actual evidence exists.

Each private cohort report includes known-label confusion, precision/recall with
exact denominators and Wilson intervals, FPR, uncertainty, coverage and actor/run
support. Unknown truth and missing evidence cannot inflate class denominators.
Known benign automation flags are counted separately from unknown intent. A zero
observed human false-positive rate does not conceal missed bots or abstentions.

Historical synthetic results remain in [EVALUATION.md](EVALUATION.md). Current
private collection/review instructions are in [HUMAN_STUDY.md](HUMAN_STUDY.md).
