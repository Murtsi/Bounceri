"""Keep committed request ownership and signed simulator truth across window changes."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from bouncer.contracts import Session, SessionLabel
from bouncer.ingest.sample import SESSION_IDLE, parse_access_record, parse_sim_run
from bouncer.ingest.simrun import IngestStats


def sessionize(
    records: list[dict[str, Any]],
    previous: Sequence[Session],
    secret: str | None,
    label_state: dict,
) -> tuple[list[Session], list[SessionLabel], IngestStats, dict]:
    """Annotate trusted cached records with private ``_session_id`` ownership.

    Fresh records must have client-supplied private annotations removed by the caller.
    The caller also bounds returned label state alongside its private identity window.
    """
    stats = IngestStats()
    identities = {session.id: session for session in previous}
    intervals = {session.id: [session.started_at, session.ended_at] for session in previous}
    clients = defaultdict(list)
    for session in previous:
        clients[(session.ip, session.user_agent)].append(session.id)
    parsed = defaultdict(list)
    for record in records:
        try:
            request, marker = parse_access_record(record, secret=secret, stats=stats)
        except (ValueError, TypeError, OverflowError, OSError, AttributeError):
            stats.invalid_records += 1
            continue
        client = (request.ip, request.user_agent)
        owner = record.get("_session_id")
        if owner is not None:
            old = identities.get(owner)
            if old is None or (old.ip, old.user_agent) != client:
                raise ValueError("cached session identity does not match client")
            intervals[owner][0] = min(intervals[owner][0], request.ts)
            intervals[owner][1] = max(intervals[owner][1], request.ts)
        parsed[client].append((request, marker, record))

    grouped = defaultdict(list)
    next_state = {session_id: dict(state) for session_id, state in label_state.items()}
    for client, entries in sorted(parsed.items()):
        entries.sort(key=lambda entry: entry[0].ts)
        for request, marker, record in entries:
            owner = record.get("_session_id")
            if owner is None:
                candidates = []
                for session_id in clients[client]:
                    start, end = intervals[session_id]
                    distance = max(start - request.ts, request.ts - end, timedelta())
                    if distance <= SESSION_IDLE:
                        candidates.append((distance, start, session_id))
                if candidates:
                    owner = min(candidates)[2]
                else:
                    key = f"{request.ip}|{request.user_agent}|{request.ts.isoformat()}"
                    owner = hashlib.sha1(key.encode()).hexdigest()[:12]
                    if owner in intervals:
                        raise ValueError("session identity collision")
                    clients[client].append(owner)
                    intervals[owner] = [request.ts, request.ts]
                record["_session_id"] = owner
            intervals[owner][0] = min(intervals[owner][0], request.ts)
            intervals[owner][1] = max(intervals[owner][1], request.ts)
            grouped[owner].append(request)
            state = next_state.setdefault(owner, {"marker": None, "conflict": False})
            if marker:
                if state["marker"] is None:
                    state["marker"] = marker
                elif state["marker"] != marker:
                    state["conflict"] = True

    sessions = []
    for session_id, requests in grouped.items():
        requests.sort(key=lambda request: request.ts)
        first, last = requests[0], requests[-1]
        sessions.append(Session(
            session_id, first.ip, first.user_agent, first.ts, last.ts, tuple(requests)
        ))
    sessions.sort(key=lambda session: (session.started_at, session.id))
    labels = []
    for session in sessions:
        state = next_state[session.id]
        if state["conflict"]:
            stats.conflicting_sessions.append(session.id)
        elif state["marker"]:
            try:
                labels.append(parse_sim_run(state["marker"], session.id))
            except ValueError:
                stats.invalid_markers += 1
    return sessions, labels, stats, next_state
