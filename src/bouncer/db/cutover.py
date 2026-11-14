"""Explicit offline archives; never switch readers or start live ingestion.

Backfill event identities are synthetic ordinals in ``snapshot-backfill``;
they are not original log byte offsets and create no live checkpoint.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from sqlalchemy import select

from bouncer.db.store import (
    _label_from_dict,
    _serialize_label,
    _serialize_session,
    _session_from_dict,
)
from bouncer.db.traffic import TrafficRepository, sources

MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
_PRIVATE_STATE = {"session_identity_state", "session_label_state", "worker_resume_state"}


def _strings(row: dict, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> None:
    if any(not isinstance(row.get(key), str) for key in required):
        raise ValueError("invalid snapshot field types")
    if any(row.get(key) is not None and not isinstance(row[key], str) for key in optional):
        raise ValueError("invalid snapshot field types")


def _normalize(snapshot: Any) -> tuple[dict, list, list]:
    if not isinstance(snapshot, dict):
        raise ValueError("invalid snapshot document")
    if type(snapshot.get("synthetic")) is not bool:
        raise ValueError("snapshot synthetic provenance must be an explicit boolean")
    if not isinstance(snapshot.get("sessions"), list) or not isinstance(
        snapshot.get("labels"), list
    ):
        raise ValueError("invalid snapshot collections")
    try:
        for row in snapshot["sessions"]:
            _strings(row, ("id", "ip", "user_agent", "started_at", "ended_at"))
            if not row["id"] or not isinstance(row["requests"], list):
                raise ValueError("invalid snapshot session")
            for request in row["requests"]:
                _strings(
                    request,
                    ("ts", "ip", "method", "path"),
                    ("user_agent", "query", "content_type", "username"),
                )
                if type(request["status"]) is not int or (
                    request.get("bytes") is not None and type(request["bytes"]) is not int
                ):
                    raise ValueError("invalid snapshot request")
                headers = request.get("headers")
                headers = {} if headers is None else headers
                if not isinstance(headers, dict) or any(
                    not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()
                ):
                    raise ValueError("invalid snapshot headers")
        for row in snapshot["labels"]:
            _strings(row, ("session_id", "run_id", "sim_class"), ("campaign_id",))
        sessions = sorted(
            (_session_from_dict(row) for row in snapshot["sessions"]),
            key=lambda session: (session.started_at, session.id),
        )
        labels = sorted(
            (_label_from_dict(row) for row in snapshot["labels"]),
            key=lambda label: label.session_id,
        )
        ids = {session.id for session in sessions}
        if len(ids) != len(sessions) or len({label.session_id for label in labels}) != len(labels):
            raise ValueError("duplicate snapshot identities")
        if any(label.session_id not in ids for label in labels):
            raise ValueError("unknown snapshot label session")
    except (KeyError, TypeError, AttributeError, OverflowError, ValueError) as exc:
        raise ValueError("invalid snapshot sessions, requests or labels") from exc
    normalized = {key: value for key, value in snapshot.items() if key not in _PRIVATE_STATE}
    normalized["sessions"] = [_serialize_session(session) for session in sessions]
    normalized["labels"] = [_serialize_label(label) for label in labels]
    return normalized, sessions, labels


def backfill_json(snapshotpath: str | Path, repository: TrafficRepository) -> dict[str, Any]:
    """Verify an immutable hash-addressed archive, preserving the original file and IDs."""
    with Path(snapshotpath).open("rb") as stream:
        raw = stream.read(MAX_SNAPSHOT_BYTES + 1)
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot exceeds size limit")
    try:
        snapshot = json.loads(raw)
        json.dumps(snapshot, allow_nan=False)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid snapshot JSON") from exc
    normalized, sessions, labels = _normalize(snapshot)
    digest = hashlib.sha256(raw).hexdigest()
    source_key = "archive/" + digest
    repository.save_snapshot(normalized, source_key=source_key)
    history = [
        replace(session, requests=tuple(sorted(session.requests, key=lambda request: request.ts)))
        for session in sessions
    ]
    if (
        repository.load_snapshot(source_key) != normalized
        or repository.load_sessions(source_key=source_key) != history
        or repository.load_labels(source_key=source_key) != labels
    ):
        raise ValueError("archive verification failed")
    return {
        "source_key": source_key,
        "sha256": digest,
        "sessions": len(sessions),
        "requests": sum(len(session.requests) for session in sessions),
        "labels": len(labels),
    }


def export_json(
    repository: TrafficRepository, source_key: str, targetpath: str | Path
) -> dict[str, Any]:
    """Export a stopped writer's current state to a new private rollback file."""
    checkpoint = repository.load_checkpoint(source_key)
    # load_snapshot's missing-source fallback cannot establish real-data provenance.
    with repository.engine.connect() as conn:
        metadata = conn.scalar(select(sources.c.snapshot).where(sources.c.source_key == source_key))
    if not isinstance(metadata, dict) or type(metadata.get("synthetic")) is not bool:
        raise ValueError("export requires explicit source provenance")
    snapshot = repository.load_snapshot(source_key)
    resumed = repository.load_resume_state(source_key)
    if repository.load_checkpoint(source_key) != checkpoint:
        raise ValueError("source checkpoint changed during export")
    normalized, sessions, labels = _normalize(snapshot)
    exported = dict(normalized)
    if "tail" in resumed or "records" in resumed:
        if not isinstance(resumed.get("tail"), dict) or not isinstance(
            resumed.get("records"), list
        ):
            raise ValueError("invalid worker resume state")
        exported["worker_resume_state"] = resumed
        for key in ("session_identity_state", "session_label_state"):
            if key in resumed:
                exported[key] = resumed[key]
    raw = (
        json.dumps(exported, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    target = Path(targetpath)
    created = False
    complete = False
    try:
        with open(target, "xb", opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
            created = True
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        decoded = json.loads(target.read_bytes())
        if decoded != exported or _normalize(decoded)[0] != normalized:
            raise ValueError("export verification failed")
        complete = True
    finally:
        if created and not complete:
            target.unlink(missing_ok=True)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sessions": len(sessions),
        "requests": sum(len(session.requests) for session in sessions),
        "labels": len(labels),
    }
