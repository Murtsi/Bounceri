"""Explicit offline JSON tools and SQL traffic archive/retention commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from bouncer.db.cutover import backfill_json, export_json
from bouncer.db.store import clear_store, seed_from_sample, store_path
from bouncer.db.traffic import TrafficRepository


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bouncer.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, help_text in (
        ("seed", "seed offline JSON from sample"),
        ("clear", "clear offline JSON"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument(
            "--offline", action="store_true", help="explicitly target offline JSON"
        )
        command.add_argument("--database-url", help=argparse.SUPPRESS)
    archive = sub.add_parser("backfill-json", help="create and verify an immutable SQL archive")
    archive.add_argument("--snapshot", required=True)
    archive.add_argument("--database-url")
    prune = sub.add_parser("prune", help="explicitly remove expired non-visible private requests")
    prune.add_argument("--before", required=True, help="ISO timestamp with timezone")
    prune.add_argument("--source")
    prune.add_argument("--database-url")
    export = sub.add_parser("export-json", help="export stopped SQL writer state for JSON rollback")
    export.add_argument("--output", required=True, help="new private JSON file; never overwrite")
    export.add_argument("--source")
    export.add_argument("--database-url")
    args = ap.parse_args(argv)

    database_url = (args.database_url or os.getenv("BOUNCER_TRAFFIC_DATABASE_URL", "")).strip()
    if args.cmd in {"seed", "clear"}:
        if database_url and not args.offline:
            print("SQL traffic selected; use --offline to target the JSON store", file=sys.stderr)
            return 2
        if args.cmd == "clear":
            clear_store()
            print(f"cleared {store_path()}")
        else:
            n_s, n_l = seed_from_sample()
            print(f"seeded {n_s} sessions, {n_l} labels → {store_path()}")
        return 0

    if not database_url:
        print("traffic database URL is required", file=sys.stderr)
        return 2
    if args.cmd == "prune":
        try:
            cutoff = datetime.fromisoformat(args.before.replace("Z", "+00:00"))
            if cutoff.utcoffset() is None:
                raise ValueError("missing timezone")
        except ValueError:
            print("--before requires an ISO timestamp with timezone", file=sys.stderr)
            return 2

    repository = None
    try:
        repository = TrafficRepository(database_url)
        if args.cmd == "backfill-json":
            report = backfill_json(args.snapshot, repository)
        else:
            source = args.source or os.getenv("BOUNCER_TRAFFIC_SOURCE", "monitored")
            if args.cmd == "export-json":
                report = export_json(repository, source, args.output)
            else:
                report = {"requests_deleted": repository.prune_before(source, cutoff)}
        print(json.dumps(report, sort_keys=True))
    except Exception:
        # Driver exceptions can contain credentials, request values and SQL parameters.
        print(f"{args.cmd} failed; verify input and database configuration", file=sys.stderr)
        return 2
    finally:
        if repository is not None:
            repository.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
