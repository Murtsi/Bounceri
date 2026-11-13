"""CLI: seedaa paikallinen S3-store samplella.

    PYTHONPATH=src python -m bouncer.db seed
    PYTHONPATH=src python -m bouncer.db clear
"""

from __future__ import annotations

import argparse
import sys

from bouncer.db.store import clear_store, seed_from_sample, store_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bouncer.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="lataa samples/access.sample.jsonl storeen")
    sub.add_parser("clear", help="tyhjennä store")
    args = ap.parse_args(argv)

    if args.cmd == "clear":
        clear_store()
        print(f"cleared {store_path()}")
        return 0

    n_s, n_l = seed_from_sample()
    print(f"seeded {n_s} sessions, {n_l} labels → {store_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
