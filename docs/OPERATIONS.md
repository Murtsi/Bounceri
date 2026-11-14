# Core operations

These commands are explicit operator actions. No backup, deletion, paid review or
deployment runs automatically. Storage selection and cutover are described in
[TRAFFIC_STORAGE.md](TRAFFIC_STORAGE.md).

## Health

`GET /api/healthz` reports API liveness without database access. `GET /api/readyz`
reports database, ingest, data and review separately. The probe is read-only,
does not initialize/migrate databases and never contacts a model provider.

Readiness returns 503 when the selected database or ingest source is unavailable,
unknown or more than 120 seconds behind. A fresh worker with no recent events is
ready but degraded: `last_event_at` describes traffic age while `updated_at`
describes loop progress. A read-only archive disables live ingest explicitly.
Deleted sources are unavailable. Optional review failure degrades status without
stopping the local detector. A review heartbeat must match the selected source
and current configuration; it never proves that a remote provider works.

SQL ingest publishes its heartbeat with the source transaction. JSON compatibility
uses a bounded `<store>.health.json` sidecar matched to the committed file's size
and modification time. A missing/mismatched sidecar stays unknown. Health responses
omit database URLs, source names, private paths and traffic payloads.

## Backup and restore

Run from the checkout with the locked environment. Set `DATABASE_URL` privately to
the source, and `RESTORE_DATABASE_URL` to a distinct empty target. Never paste
credentials into command arguments or logs.

```text
uv run --no-sync python -m tools.hostinger.backup backup --output /private/core.dump
uv run --no-sync python -m tools.hostinger.backup restore --manifest /private/core.dump.manifest.json
```

PostgreSQL needs `pg_dump` and `pg_restore` matching server major version 16 in
PATH. The application image does not bundle these tools: use the operator host or
an isolated PostgreSQL-client environment. Missing clients fail explicitly. The
default limits are 120 seconds and 1 GiB. SQLite local/test archives use its online
backup API rather than copying a live database file.

The full archive includes traffic, case/assessment history, jobs, reservations,
spending counters and enforcement records. Restore refuses existing nonempty
targets and the recorded source, checks the artifact digest and migration ledger,
and performs PostgreSQL restore in one transaction. It never runs store startup,
upgrades the schema or resets spending. Restore into isolation, verify the result,
then make a separate deployment decision. A post-restore validation failure leaves
the target for inspection; do not select it as the application database.

Archive and manifest must both stay private. Their checksum detects corruption,
not an attacker replacing both files. Accept only trusted backups. Set retention
and access controls on the operator's backup location; this tool does not schedule
retention, encrypt archives, delete old copies or guarantee off-host durability.

## Source deletion

Stop the source's ingest writer and any review jobs first. Set both
`BOUNCER_TRAFFIC_DATABASE_URL` and `BOUNCER_DATABASE_URL` explicitly to the same
database. The API's default investigations SQLite file is a separate database;
unset configuration must never be interpreted as a shared database.

```text
uv run --no-sync python -m bouncer.db purge-source --source SOURCE --confirm-source SOURCE --confirm-writer-stopped
```

Deletion checks the current checkpoint, refuses active related review jobs, erases
native records and private source/resume metadata, removes assessments, and turns
bound cases into private empty tombstones. It preserves source identity, case IDs,
evidence hashes, jobs and the financial ledger. A deleted source key cannot be
reused or restored by a stale writer/heartbeat. Use a new key for a new collection.

Cases bind their actual `source_id` separately from a scope such as `overview` or
a selected session. New evidence hashes include that binding, so identical packets
from distinct sources cannot share review results. Migration 006 backfills only
exact known source-key matches. Unbound legacy monitored cases with unknown origin
cause purge to fail closed; resolve their origin privately before retrying.

This action covers the selected SQL database only. It does not erase original
access logs, exported JSON, operator backups, external provider records or data in
other databases. Apply the collection's retention/deletion policy to those copies
separately. Uploaded original logs are not retained by the import endpoint; its
sanitized immutable SQL archive is covered here.

## Bounds and local measurements

Raw records with invalid UTF-8 scalar values or NUL characters are counted as bad
lines and skipped without stopping later records. Invalid simulator credentials
discard only the untrusted label and retain otherwise valid request evidence.
Path, client and header evidence is never repaired into an invented observation.

Hosted ingest retains at most 6,000 records/30 minutes, additionally bounded by
8 MiB of serialized records. Complete newly read traffic is committed before the
visible window is evicted. Imported analysis has its own admission/child bounds.
Behavior clustering avoids repeated path comparisons for identical fingerprints;
unique patterns and session-time comparisons still have a quadratic worst case.

On 2026-11-15, an isolated Linux container limited to 512 MiB and 0.5 CPU processed
6,000 one-request sessions sharing a path/header pattern in 14.511 and 16.026
seconds over two worker cycles. Peak process RSS was 203.9 MiB; retained records
were 1.62 MiB. DNS was disabled. These measurements exclude PostgreSQL, API, other
services and the extra bounded DNS lookup budget; they are not a throughput SLA.

The packaged simulation gateway rotates logs at 5 MiB with two retained files and
24-hour retention. Packaged Python services use Docker logs capped at 5 MiB with
two files. Root demo Caddy uses its separate 100 MiB/five-file policy. Ingest tests
cover rename/copytruncate/gzip rotation and report gaps rather than inventing lost
events. Rotation and database retention do not remove operator backups.

Before rollout, run the PostgreSQL migration/lifecycle/restore tests, repository
checks and the packaged private simulation. Check readiness and zero paid calls.
Local smoke evidence does not establish live Hostinger health, DNS quality or
real-human detection performance.
