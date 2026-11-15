# Consented human collections

This is a private operator workflow for recording actual consent and reviewed
observations. It does not recruit participants, verify someone's identity, supply
a consent form or establish that collection is permitted. Keep the real consent
documents and contact mapping separately under the collection's access policy.
Only opaque references belong in this database. No actual participant evidence
has been supplied or collected by this implementation.

## Collection boundary

Use a dedicated private, non-synthetic SQL traffic source for each participant
collection. Import only that participant's permitted records through the existing
private log import, or select a dedicated worker source. The import response's
`source_key` identifies its immutable archive. An enrollment cannot contain
simulator labels or use a deleted/public/synthetic source. The operator must
explicitly attest that the source belongs exclusively to the participant.

Mixed participant streams require selective deletion that this workflow does not
implement. Mix permitted public datasets and participant sources at evaluation,
keeping their identities and reference tasks distinct. A historical public
`ROBOT` label establishes neither maliciousness nor independently observed manual
operation. A person's enrollment establishes neither manual behavior nor benign
intent in every session.

Enrollment creates a random pseudonymous subject ID. Reuse that ID for the same
participant across subsequent dedicated sources, so later splitting can keep the
whole participant together. Do not create a new ID for every session, infer one
from an IP/user agent or deliberately separate a returning participant. An actual
collection window must follow consent, use timezone-aware timestamps and span at
most 31 days. Evaluation permission is explicit; a record with permission disabled
does not produce eligible reviews. Source metadata is represented by its digest
or an explicit unavailable state. Missing provenance is never filled in.

## Operator commands

Set `BOUNCER_TRAFFIC_DATABASE_URL` and `BOUNCER_DATABASE_URL` privately to the same
database. URLs are read from the environment, never command arguments. Use a
locked checkout; commands and input files remain private. Each JSON input is
limited to 16 KiB. Examples below show the shape, not evidence of real consent.

```text
uv run --no-sync python -m tools.datasets participants enroll --input /private/enrollment.json
```

```json
{
  "source_key": "import/REPLACE_WITH_ACTUAL_SOURCE",
  "consent_ref": "consent/OPAQUE_REFERENCE",
  "consent_version": "study-v1",
  "consent_granted_at": "2026-11-14T09:00:00Z",
  "collection_from": "2026-11-14T10:00:00Z",
  "collection_until": "2026-11-14T11:00:00Z",
  "evaluation_allowed": true,
  "exclusive_source": true,
  "operator_ref": "operator/OPAQUE_REFERENCE"
}
```

The response gives `enrollment_id` and `subject_id`. Add `subject_id` to a later
enrollment to link another collection for that participant. References must be
bounded opaque ASCII identifiers; names, email addresses, raw consent documents
and unrestricted notes are excluded from this contract.

Inspect the actual stored session before reviewing it. The export contains private
native traffic and a content digest; it must be a new file outside Git in a
private directory. Exports are limited to 8 MiB and never printed to stdout.

```text
uv run --no-sync python -m tools.datasets participants inspect-session --enrollment ENROLLMENT_UUID --session STORED_SESSION_ID --output /private/inspection.json
uv run --no-sync python -m tools.datasets participants review-session --input /private/review.json
```

```json
{
  "enrollment_id": "REPLACE_WITH_ENROLLMENT_UUID",
  "external_session_id": "REPLACE_WITH_STORED_SESSION_ID",
  "expected_revision": 0,
  "expected_session_digest": "REPLACE_WITH_INSPECTED_CONTENT_SHA256",
  "status": "approved",
  "behavior": "manual",
  "intent": "benign",
  "mapping_ref": "mapping/OPAQUE_REFERENCE",
  "evidence_ref": "observation/OPAQUE_REFERENCE",
  "reviewer_ref": "reviewer/OPAQUE_REFERENCE"
}
```

Record observed behavior as `manual`, `automated`, `mixed` or `unknown`, and intent
separately as `benign`, `abusive` or `unknown`. A signed simulator marker, local
detector prediction, LLM opinion, DNS result or trap hit is not independent human
ground truth. Mapping and review references must point to actual supporting
observations held by the operator. These assertions are recorded, not magically
verified by the application.

Review status is `pending`, `approved` or `rejected`. Revisions append rather than
overwrite. Supply the latest revision when changing a review; a later rejection
invalidates earlier approval. The supplied inspected digest is compared under the
source lock and binds every native session field and request multiplicity. A
matching annotation revision alone does not establish that the inspected content
is current. New requests, retention or other content
changes require fresh review. The whole session and every request must fit the
consented collection window.

```text
uv run --no-sync python -m tools.datasets participants approved --source ACTUAL_SOURCE
```

The aggregate separates approved observations, recorded subjects, manual/benign
human references and automation. Only an approved manual/benign observation can
enter the real `study/human` reference subset. Automated benign activity is not
automatically a verified crawler; unknown/abusive intent is not automatically
`bad_bot`. Other approved observations retain their behavior/intent but remain
unlabeled in the existing three-class traffic task. Enrollment alone produces no
human labels. No command trains, calls a model or publishes metrics.

## Withdrawal and retention

Stop the participant's collection writers and resolve active review jobs first.

```text
uv run --no-sync python -m tools.datasets participants withdraw --subject SUBJECT_UUID --confirm-subject SUBJECT_UUID --confirm-writer-stopped
```

Withdrawal atomically revokes the subject and purges all their dedicated sources
in the selected database. It erases native requests/sessions/labels, private
source/resume payloads, study review/mapping/consent references and bound case/
assessment payloads. Minimal subject/enrollment/source tombstones prevent reuse.
The existing spending/reservation and enforcement audit policy is preserved.
An active paid review or ambiguous legacy case origin blocks the transaction;
resolve the cause and retry. Partial revocation/purge is not reported as success.

An ordinary source purge also scrubs that source's study records. It does not
withdraw the subject's other collections. Source keys and withdrawn subject IDs
cannot be reused. See [OPERATIONS.md](OPERATIONS.md) for the database-only deletion
boundary: original files, prior exports, backups and external records require their
own disposal. After restoring an older backup, reconcile subsequent withdrawals
before reading data for evaluation.

## Evaluation bridge and remaining gates

`StudyStore.load_approved()` rechecks current consent, status, source, window,
latest review and session digest. Its returned observations are a snapshot. Reload
them immediately before evaluation; an old in-memory object or exported copy
cannot establish that consent remains active.

`bouncer.eval.study.build_reviewed_corpus()` keeps source/session/content identity,
subject/collection groups, review revisions and missing-feature masks. It does not
convert study observations into simulator labels or change the existing learned
model. The [private frozen native workflow](FROZEN_EVALUATION.md) now keeps complete
participant/campaign/run/time groups together, separates fit/calibration/test
context and revalidates consent/review state before consuming a holdout. Legacy
timestamp-only publication is disabled. Independently withheld attack provenance,
actual independent collections and a verified production publisher remain separate
unfinished gates.

Public robot corpora, simulations, reviewed actual humans and independently
withheld attacks require separate reports. Real-human false-positive quality,
independent participant counts and hidden-attack generalization remain unverified.
`models/metrics.json` stays a stub until the required evaluation evidence exists.
