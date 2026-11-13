"""Read the checked-in Caddy JSONL fixture (S1) into shared contracts (S2/S3).

This is a deterministic integration fixture, not a Postgres loader or a source
of measured evaluation metrics.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from bouncer.contracts import Request, Session, SessionLabel

SAMPLE_PATH = Path(__file__).resolve().parents[3] / "samples" / "access.sample.jsonl"
SESSION_IDLE = timedelta(minutes=5)


def _header_value(headers: Mapping[str, Any], name: str) -> str:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            if isinstance(value, list):
                return str(value[0]) if value else ""
            return str(value) if value is not None else ""
    return ""


def _normalised_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "x-sim-run":
            continue
        if isinstance(value, list):
            value = value[0] if value else ""
        if value is not None:
            result[key.lower()] = str(value)
    return result


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Caddy record is missing its timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid Caddy timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _content_type(response_headers: Mapping[str, Any]) -> str | None:
    value = _header_value(response_headers, "content-type")
    return value.split(";", 1)[0].strip().lower() or None


def parse_access_record(record: Mapping[str, Any]) -> tuple[Request, str | None]:
    """Convert one Caddy JSON record to a Request and optional S10 marker."""
    raw_request = record.get("request")
    if not isinstance(raw_request, Mapping):
        raise ValueError("Caddy record must contain a request object")
    raw_headers = raw_request.get("headers") or {}
    response_headers = record.get("resp_headers") or {}
    if not isinstance(raw_headers, Mapping) or not isinstance(response_headers, Mapping):
        raise ValueError("Caddy request and response headers must be objects")

    uri = str(raw_request.get("uri") or "/")
    parsed_uri = urlsplit(uri)
    path = parsed_uri.path or "/"
    request_headers = _normalised_headers(raw_headers)
    request = Request(
        ts=_timestamp(record.get("ts")),
        ip=str(raw_request.get("remote_ip") or ""),
        method=str(raw_request.get("method") or "GET").upper(),
        path=path,
        status=int(record.get("status", 0)),
        user_agent=_header_value(raw_headers, "user-agent"),
        query=parsed_uri.query,
        bytes=int(record.get("size", 0)),
        headers=request_headers,
        content_type=_content_type(response_headers),
    )
    marker = _header_value(raw_headers, "x-sim-run") or request_headers.get("x-sim-run", "")
    return request, marker or None


def parse_sim_run(value: str, session_id: int) -> SessionLabel:
    """Parse ``run-id:class[:campaign-id]`` without guessing unknown classes."""
    parts = value.split(":", 2)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid X-Sim-Run marker: {value!r}")
    campaign_id = parts[2] if len(parts) == 3 and parts[2] not in {"", "-"} else None
    return SessionLabel(session_id, parts[0], parts[1], campaign_id)


def parse_access_records(
    records: Iterable[Mapping[str, Any]],
    *,
    idle_timeout: timedelta = SESSION_IDLE,
) -> tuple[list[Session], list[SessionLabel]]:
    """Group fixture records by IP/UA and five-minute idle window.

    If multiple simulation markers occur in one session, the first is retained;
    conflicting markers raise instead of silently manufacturing ground truth.
    """
    grouped: dict[tuple[str, str], list[tuple[Request, str | None]]] = defaultdict(list)
    for record in records:
        request, marker = parse_access_record(record)
        grouped[(request.ip, request.user_agent)].append((request, marker))

    sessions: list[Session] = []
    labels: list[SessionLabel] = []
    for (ip, user_agent), entries in sorted(grouped.items()):
        entries.sort(key=lambda item: item[0].ts)
        batches: list[list[tuple[Request, str | None]]] = []
        for entry in entries:
            if not batches or entry[0].ts - batches[-1][-1][0].ts > idle_timeout:
                batches.append([entry])
            else:
                batches[-1].append(entry)

        for index, batch in enumerate(batches, start=1):
            session_id = len(sessions) + 1
            requests = tuple(item[0] for item in batch)
            sessions.append(
                Session(
                    id=session_id,
                    ip=ip,
                    user_agent=user_agent,
                    started_at=requests[0].ts,
                    ended_at=requests[-1].ts,
                    requests=requests,
                )
            )
            markers = {marker for _, marker in batch if marker}
            if len(markers) > 1:
                raise ValueError(f"Conflicting X-Sim-Run markers in session {session_id}")
            if markers:
                labels.append(parse_sim_run(next(iter(markers)), session_id))
    return sessions, labels


def load_sample_data(
    path: Path = SAMPLE_PATH,
) -> tuple[list[Session], list[SessionLabel]]:
    """Load sessions and labels together to preserve their shared IDs.

    This fixture-only helper has no ``since`` filter and performs no database I/O;
    it is not the production ``load_sessions(since)`` / ``load_labels()`` contract.
    """
    records = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}") from exc
            if not isinstance(row, Mapping):
                raise ValueError(f"Expected an object in {path}:{line_number}")
            records.append(row)
    return parse_access_records(records)


def load_sample_sessions(path: Path = SAMPLE_PATH) -> list[Session]:
    """Load and sessionize the committed JSONL fixture."""
    sessions, _ = load_sample_data(path)
    return sessions


def load_sample_labels(path: Path = SAMPLE_PATH) -> list[SessionLabel]:
    """Load fixture labels using the same session IDs as the sessions."""
    _, labels = load_sample_data(path)
    return labels
