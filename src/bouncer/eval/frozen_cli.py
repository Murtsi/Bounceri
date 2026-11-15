"""Private frozen evaluation receipts and reports; no production publication."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from bouncer.db.backup import _path, _private_file
from bouncer.db.participants import StudyStore
from bouncer.db.store import shared_database_url
from bouncer.eval.frozen import MAX_PLAN_BYTES, FrozenEvaluator
from bouncer.eval.native_fixtures import outside_repository

MAX_REPORT_BYTES = 8 * 1024 * 1024


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "invalid frozen-evaluation arguments; use --help\n")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate plan key")
        result[key] = value
    return result


def _number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite plan number")
    return result


def _constant(value):
    raise ValueError("non-finite plan number")


def _plan(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError("plan exceeds limit")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                       parse_float=_number, parse_constant=_constant)
    if type(value) is not dict:
        raise ValueError("plan must be an object")
    return value


def _report(target: Path, envelope: dict) -> None:
    identity = None
    try:
        with _private_file(target) as stream:
            created = os.fstat(stream.fileno())
            identity = (created.st_dev, created.st_ino)
            size = 0
            for chunk in json.JSONEncoder(ensure_ascii=True, allow_nan=False).iterencode(envelope):
                encoded = chunk.encode("utf-8")
                size += len(encoded)
                if size > MAX_REPORT_BYTES:
                    raise ValueError("report exceeds limit")
                stream.write(encoded)
    except BaseException:
        if identity is not None:
            try:
                current = target.stat(follow_symlinks=False)
                if (current.st_dev, current.st_ino) == identity:
                    target.unlink()
            except FileNotFoundError:
                pass
        raise


def _receipt(record, keys):
    return {key: record[key].isoformat() if isinstance(record[key], datetime) else record[key]
            for key in keys}


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="freeze a private evaluation plan")
    prepare.add_argument("--plan", type=Path, required=True)
    evaluate = commands.add_parser("evaluate", help="consume a frozen holdout once")
    evaluate.add_argument("--preparation", required=True)
    evaluate.add_argument("--output", type=Path, required=True,
                          help="new private report outside the repository")
    status = commands.add_parser("status", help="show only receipt metadata")
    status.add_argument("--preparation", required=True)
    close = commands.add_parser("close-interrupted", help="close a stopped worker's claim")
    close.add_argument("--preparation", required=True)
    close.add_argument("--confirm-worker-stopped", action="store_true", required=True)
    args = parser.parse_args(argv)
    store = None
    try:
        plan = _plan(args.plan) if args.command == "prepare" else None
        if args.command != "prepare" and re.fullmatch(r"[0-9a-f]{64}", args.preparation) is None:
            raise ValueError("invalid preparation identifier")
        if args.command == "evaluate":
            target = outside_repository(_path(args.output))
            if not target.parent.is_dir():
                raise ValueError("report parent directory must exist")
        url = shared_database_url()
        store = StudyStore(url)
        evaluator = FrozenEvaluator(store)
        if args.command == "prepare":
            output = _receipt(evaluator.prepare(plan),
                              ("preparation_id", "state", "artifact_digest"))
        elif args.command == "evaluate":
            result = evaluator.evaluate(args.preparation)
            _report(target, result)
            output = _receipt(result, ("preparation_id", "artifact_digest", "cached"))
            output["report_written"] = True
        elif args.command == "status":
            output = _receipt(evaluator.ledger.get(args.preparation), (
                "preparation_id", "state", "artifact_digest", "failure_code",
                "claimed_at", "completed_at",
            ))
        else:
            output = _receipt(evaluator.close_interrupted(
                args.preparation, confirm_worker_stopped=args.confirm_worker_stopped,
            ), ("preparation_id", "state"))
        print(json.dumps(output, sort_keys=True, allow_nan=False))
        return 0
    except Exception:
        print("frozen evaluation failed; check private input and shared database configuration. "
              "Use status to inspect the receipt; close-interrupted requires a stopped worker "
              "and never retries a consumed holdout.", file=sys.stderr)
        return 2
    finally:
        if store is not None:
            store.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
