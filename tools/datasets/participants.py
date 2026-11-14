"""Private operator records; never collects visitors, trains, or publishes metrics."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from bouncer.db.backup import _path, _private_file
from bouncer.db.participants import StudyStore

from .native import outside_repository


def _input(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(16_385)
    if len(raw) > 16_384:
        raise ValueError("study input exceeds limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("study input must be an object")
    return value


def _database() -> str:
    traffic = os.getenv("BOUNCER_TRAFFIC_DATABASE_URL", "").strip()
    cases = os.getenv("BOUNCER_DATABASE_URL", "").strip()
    if not traffic or not cases:
        raise ValueError("explicit shared database configuration required")
    selected, configured = make_url(traffic), make_url(cases)
    if selected.set(drivername=selected.get_backend_name()) != configured.set(
        drivername=configured.get_backend_name()
    ):
        raise ValueError("study commands require one shared database")
    return traffic


def _inspection(path: Path, record: dict) -> None:
    target = outside_repository(_path(path))
    owned = False
    try:
        with _private_file(target) as stream:
            owned = True
            size = 0
            for chunk in json.JSONEncoder(ensure_ascii=True, allow_nan=False).iterencode(record):
                encoded = chunk.encode("utf-8")
                size += len(encoded)
                if size > 8 * 1024 * 1024:
                    raise ValueError("session inspection exceeds limit")
                stream.write(encoded)
    except BaseException:
        if owned:
            target.unlink(missing_ok=True)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("enroll", "review-session"):
        commands.add_parser(name).add_argument("--input", type=Path, required=True)
    inspection = commands.add_parser("inspect-session", help="private content for explicit review")
    inspection.add_argument("--enrollment", required=True)
    inspection.add_argument("--session", required=True)
    inspection.add_argument("--output", type=Path, required=True)
    approved = commands.add_parser("approved", help="private aggregate of current approvals")
    approved.add_argument("--source", action="append", required=True)
    withdraw = commands.add_parser("withdraw", help="erase dedicated participant sources")
    withdraw.add_argument("--subject", required=True)
    withdraw.add_argument("--confirm-subject", required=True)
    withdraw.add_argument("--confirm-writer-stopped", action="store_true", required=True)
    args = parser.parse_args(argv)
    store = None
    try:
        url = _database()
        values = _input(args.input) if args.command in {"enroll", "review-session"} else None
        if args.command == "approved" and len(args.source) > 100:
            raise ValueError("too many sources")
        if args.command == "enroll":
            for name in ("consent_granted_at", "collection_from", "collection_until"):
                if name in values:
                    values[name] = datetime.fromisoformat(values[name].replace("Z", "+00:00"))
        store = StudyStore(url)
        if args.command == "enroll":
            result = store.enroll(**values)
            output = {key: result[key] for key in ("enrollment_id", "subject_id", "source_key")}
        elif args.command == "review-session":
            result = store.review_session(**values)
            output = {key: result[key] for key in (
                "review_id", "revision", "status", "behavior", "intent",
            )}
        elif args.command == "inspect-session":
            result = store.inspect_session(enrollment_id=args.enrollment,
                                           external_session_id=args.session)
            _inspection(args.output, result)
            output = {"digest": result["digest"], "expected_revision": result["expected_revision"],
                      "private_export": True}
        elif args.command == "approved":
            observations = store.load_approved(args.source)
            human = sum(row.behavior == "manual" and row.intent == "benign" for row in observations)
            automated = sum(row.behavior == "automated" for row in observations)
            output = {
                "approved_observations": len(observations),
                "subjects": len({row.subject_id for row in observations}),
                "human_reference_sessions": human, "automated_observations": automated,
                "other_observations": len(observations) - human - automated,
                "release_evaluation_available": False,
            }
        else:
            output = store.withdraw(args.subject, confirm_subject=args.confirm_subject,
                                    writer_stopped=args.confirm_writer_stopped)
        print(json.dumps(output, sort_keys=True))
        return 0
    except Exception:
        print("study operation failed; check private input, consent and database configuration",
              file=sys.stderr)
        return 2
    finally:
        if store is not None:
            store.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
