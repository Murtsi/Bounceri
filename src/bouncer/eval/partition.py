"""Pure partitions that preserve declared groups; metadata is private, not quality evidence."""

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

ROLES = ("fit", "calibration", "test")


@dataclass(frozen=True, slots=True)
class GroupedExample:
    source_id: str
    session_id: str
    session_digest: str
    started_at: datetime
    ended_at: datetime
    actor_id: str | None
    run_id: str | None
    campaign_ids: tuple[str, ...] | None


def _identifier(value: object) -> None:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("identifiers must be nonempty strings without NUL")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("identifiers must be valid UTF-8") from exc
    if size > 256:
        raise ValueError("identifiers must be at most 256 UTF-8 bytes")


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware datetimes")
    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise ValueError("timestamps must be representable in UTC") from exc


def _hash(content: list[str]) -> str:
    return sha256(json.dumps(content, separators=(",", ":")).encode()).hexdigest()


def partition_examples(
    examples: Iterable[GroupedExample],
    windows: Mapping[str, tuple[datetime, datetime]],
) -> dict[str, Any]:
    """Keep every connected declared group in one explicit half-open role window.

    Unknown required identities quarantine their entire known component. No IDs
    are inferred, and the returned private manifest includes excluded metadata.
    Equal string IDs link globally across sources, within their identity type.
    """
    if not isinstance(windows, Mapping) or set(windows) != set(ROLES):
        raise ValueError("windows require exactly fit, calibration, test roles")
    bounds = {}
    for role in ROLES:
        interval = windows[role]
        if not isinstance(interval, tuple) or len(interval) != 2:
            raise ValueError("window bounds must be (from, until) tuples")
        start, end = map(_utc, interval)
        if start >= end:
            raise ValueError("window from must precede until")
        bounds[role] = start, end
    for earlier, later in zip(ROLES, ROLES[1:], strict=False):
        if bounds[earlier][1] > bounds[later][0]:
            raise ValueError("windows must be chronological and nonoverlapping")

    try:
        iterator = iter(examples)
    except TypeError as exc:
        raise ValueError("examples must be iterable") from exc
    records = {}
    source_sessions = set()
    for index, row in enumerate(iterator):
        if index >= 20000:
            raise ValueError("at most 20000 examples are allowed")
        if not isinstance(row, GroupedExample):
            raise ValueError("examples must be GroupedExample instances")
        _identifier(row.source_id)
        _identifier(row.session_id)
        if not isinstance(row.session_digest, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", row.session_digest,
        ):
            raise ValueError("session_digest must be 64 hex characters")
        identity = row.source_id, row.session_id
        if identity in source_sessions:
            raise ValueError("duplicate source/session identity")
        source_sessions.add(identity)
        for value in (row.actor_id, row.run_id):
            if value is not None:
                _identifier(value)
        campaigns = row.campaign_ids
        if campaigns is not None:
            if not isinstance(campaigns, tuple) or len(campaigns) > 64:
                raise ValueError("campaign_ids must be a tuple of at most 64 IDs or None")
            for campaign in campaigns:
                _identifier(campaign)
        start, end = _utc(row.started_at), _utc(row.ended_at)
        if end < start:
            raise ValueError("ended_at must not precede started_at")
        key = _hash([row.source_id, row.session_id, row.session_digest])
        records[key] = {
            "source_id": row.source_id, "session_id": row.session_id,
            "session_digest": row.session_digest,
            "started_at": start.isoformat(), "ended_at": end.isoformat(),
            "actor_id": row.actor_id, "run_id": row.run_id,
            "campaign_ids": sorted(campaigns) if campaigns is not None else None,
        }

    keys = sorted(records)
    parents = {key: key for key in keys}

    def find(key: str) -> str:
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    owners = {}
    for key in keys:
        row = records[key]
        identities = [(kind, row[kind]) for kind in ("actor_id", "run_id")
                      if row[kind] is not None]
        identities.extend(("campaign_id", value) for value in row["campaign_ids"] or ())
        for identity in identities:
            if identity in owners:
                parents[find(key)] = find(owners[identity])
            else:
                owners[identity] = key

    groups = {}
    for key in keys:
        groups.setdefault(find(key), []).append(key)
    components = {_hash(members): members for members in groups.values()}
    roles = {role: [] for role in ROLES}
    exclusions = {}
    for component in sorted(components):
        members = components[component]
        rows = [records[key] for key in members]
        start = min(datetime.fromisoformat(row["started_at"]) for row in rows)
        end = max(datetime.fromisoformat(row["ended_at"]) for row in rows)
        if any(row[name] is None for row in rows
               for name in ("actor_id", "run_id", "campaign_ids")):
            reason = "unknown_group_identity"
        else:
            role = next((role for role in ROLES
                         if start >= bounds[role][0] and end < bounds[role][1]), None)
            if role is not None:
                roles[role].extend(members)
                continue
            if start < bounds["fit"][0] or end >= bounds["test"][1]:
                reason = "outside_windows"
            elif any(start < until and end >= lower for lower, until in bounds.values()):
                reason = "spans_windows"
            else:
                reason = "window_gap"
        exclusions.update(dict.fromkeys(members, reason))

    return {
        "schema_version": "grouped-temporal-partition-v1",
        "windows": {role: {"from": bounds[role][0].isoformat(),
                           "until": bounds[role][1].isoformat()} for role in ROLES},
        "roles": {role: sorted(roles[role]) for role in ROLES},
        "exclusions": dict(sorted(exclusions.items())),
        "components": dict(sorted(components.items())),
        "examples": {key: records[key] for key in keys},
    }
