# Durable traffic storage

The SQL traffic path is explicit. An empty `BOUNCER_TRAFFIC_DATABASE_URL` selects the private JSON compatibility adapter. A configured URL selects normalized requests/sessions/labels plus source-scoped SQL read models and atomic checkpoints. `BOUNCER_TRAFFIC_SOURCE` defaults to `monitored`; the Hostinger packaging switch uses `private-simulation`. Never put credentials in Git.

## Guarantees and boundaries

- Request identity is `(source_key, generation, byte_offset)`, where the offset is the start of a complete source line. Two identical-looking requests at different offsets remain two requests. Replaying an identity with different data or a different session owner fails.
- A source transaction commits normalized history, current visible rows, private resume state and the next source byte offset together. Its expected checkpoint/revision rejects stale writers. Failure restores local source/window state for retry; a competing writer requires a restart from committed state.
- The detector's 6,000-record/30-minute hosted view is separate from durable history. Fresh valid requests persist before view eviction. Only explicit age retention removes nonvisible historical requests. Configured SQL runtime defaults to 86,400 seconds through `BOUNCER_TRAFFIC_RETENTION_SECONDS`; current visible rows are preserved. The prune and checkpoint share the same transaction.
- Session ownership remains stable for committed events, including out-of-order timestamps and requests that would otherwise bridge two old sessions. Private identity and signed-marker conflict state survive view eviction and restart. A conflict invalidates historical labels rather than keeping stale human truth.
- Source synthetic provenance is immutable. Use a new source key to change collection origin. Legacy SQL rows without provenance stay private/unknown; evaluation refuses to infer real traffic from a missing flag.
- The file tail drains retained numeric/Caddy rotations, including gzip, preserves partial lines and offsets, binds identity to opened file descriptors, and validates consumed prefixes. Batches, partial lines and segment inventories are bounded. Already-deleted, never-observed intermediate rotations cannot be reconstructed; observed missing segments are counted. Prefix validation/decompression costs work proportional to the consumed prefix.
- JSON snapshots and SQL resume state are private. Raw request caches, source coordinates, signatures and continuity state do not become public investigation packets. Public API projections remain allowlisted.

## Stop, archive, verify, then select SQL

These commands are operator steps, not automatic deployment actions. First stop the actual ingest writer and preserve its input logs/rotations. Keep the original private JSON file unchanged. Back up the database before applying a release/schema upgrade. Use the new release's CLI with its intended private database environment:

```sh
python -m bouncer.db backfill-json --snapshot /data/store.json
```

The URL comes from `BOUNCER_TRAFFIC_DATABASE_URL` or an explicit `--database-url`. This bounded import requires explicit boolean provenance, validates native session/request/label contracts, preserves opaque IDs, and verifies the normalized round trip. It prints only a content hash, archive source key and counts. The archive is `archive/<raw-file-sha256>`; it is immutable, idempotent for the same input, and rejects live batches. Its ordinal event IDs are declared snapshot-backfill identities, not invented original log offsets.

Only after the archive succeeds, configure API and worker with the same database URL and fresh live source. Hosted compose generation requires `tools.hostinger.package --traffic-sql`; leaving the flag absent keeps JSON. The simulator receives no traffic database URL. A SQL worker refuses a nonempty existing JSON file unless that exact byte hash has been archived. It also rejects a provenance mismatch.

A JSON file produced by this release includes private worker resume state. That state transfers retained records, stable session ownership, partial lines and source coordinates into SQL without rereading acknowledged bytes. Older JSON files remain fully preserved in their verified archive; if they lack resume state, the live source rebuilds from retained input logs. Keep its archive and new live collection separate: they can overlap and are not independent evaluation partitions. Do not sum their counts or invent a hidden holdout. Inspect IDs/counts, source origin, checkpoint progress and public/private responses before routing readers to the live source.

## Fresh rollback to JSON

Stop the SQL writer and keep its logs at the same configured location. Export a fresh private file rather than restoring a stale pre-cutover snapshot:

```sh
python -m bouncer.db export-json --output /data/rollback.json --source private-simulation
```

The command refuses existing output paths and unknown provenance, checks for checkpoint changes during capture, includes the private worker resume state, flushes and verifies the output. On POSIX it creates a private 0600 file. It does not reconfigure or restart anything.

Unset `BOUNCER_TRAFFIC_DATABASE_URL`, set `BOUNCER_STORE_PATH` to the new export, and start this release's JSON worker against the preserved log path. It restores the exported checkpoint/cache and session truth state. The database and original JSON archive remain intact. This is a configuration rollback using the new compatible binary; an older binary must not be started against a newer schema. Full database downgrade/restore requires its verified backup.

## Explicit retention and offline commands

```sh
python -m bouncer.db prune --before 2026-11-14T00:00:00+00:00 --source private-simulation
```

Prune requires a timezone-aware cutoff and removes only nonvisible expired requests and empty inactive sessions/labels in that source. Immutable archives remain visible; prune does not delete them. Explicit source purge and full-database backup/restore are documented in [OPERATIONS.md](OPERATIONS.md). Dataset/study retention and consent withdrawal are separate plan work. `seed` and `clear` are deliberately offline JSON operations: with SQL selected they require `--offline` so they cannot be mistaken for clearing SQL.

## Verification

The regression suite includes identical request multiplicity, replay/collision rejection, stale writers, transactional failure, retention-before-view history, late/bridging sessions, sticky truth conflicts, immutable origins/archives, rotated/gzipped input, fresh rollback exports and PostgreSQL-backed worker cutover/restart/rollback. Run `BOUNCER_TEST_POSTGRES=1 uv run --no-sync pytest -q` for disposable PostgreSQL tests. Runtime/deployment smoke evidence is recorded in the implementation checklist; passing storage tests does not establish detector quality or independent real/hidden evaluation.
