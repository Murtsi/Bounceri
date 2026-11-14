"""Explicit local archive tooling. URLs come only from environment, never argv.

DATABASE_URL selects backup source; RESTORE_DATABASE_URL selects the empty restore
target. Requires PostgreSQL client binaries in PATH for PostgreSQL operations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from bouncer.db.backup import MAX_BYTES, backup_database, restore_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.hostinger.backup")
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="archive DATABASE_URL to a new private file")
    backup.add_argument("--output", required=True)
    restore = commands.add_parser("restore", help="restore to empty RESTORE_DATABASE_URL")
    restore.add_argument("--manifest", required=True)
    for command in (backup, restore):
        command.add_argument("--timeout", type=float, default=120)
        command.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    args = parser.parse_args(argv)
    variable = "DATABASE_URL" if args.command == "backup" else "RESTORE_DATABASE_URL"
    url = os.environ.get(variable, "").strip()
    if not url:
        print(f"{variable} is required", file=sys.stderr)
        return 2
    try:
        options = {"timeout": args.timeout, "max_bytes": args.max_bytes}
        if args.command == "backup":
            result = backup_database(url, args.output, **options)
        else:
            result = restore_database(args.manifest, url, **options)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        if isinstance(exc, RuntimeError) and str(exc).startswith(
            "PostgreSQL backup client unavailable"
        ):
            print("PostgreSQL backup unavailable: install pg_dump and pg_restore", file=sys.stderr)
        else:
            print(
                f"database {args.command} failed; check archive and configuration", file=sys.stderr
            )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
