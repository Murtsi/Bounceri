"""Duck-typing helpers: C ei omista Session-skeemaa (S2 = A).

Hyväksyy dataclassit / SimpleNamespace / dict. Kun A:n `contracts.py`
laskeutuu, nämä kentät peilaavat sitä.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


@dataclass(frozen=True, slots=True)
class LoginEvent:
    session_id: int
    ip: str
    username: str
    ts: datetime
    success: bool
    path: str = "/login"


@dataclass(frozen=True, slots=True)
class SessionView:
    id: int
    ip: str
    ua: str
    started_at: datetime | None
    ended_at: datetime | None
    paths: tuple[str, ...]
    header_fingerprint: str
    logins: tuple[LoginEvent, ...]
    raw: Any


def _header_fingerprint(session: Any) -> str:
    direct = _get(session, "header_fingerprint", "headers_fp")
    if isinstance(direct, str) and direct:
        return direct

    headers = _get(session, "headers", default=None)
    if isinstance(headers, dict):
        keys = []
        for key in ("user-agent", "accept", "accept-language", "accept-encoding", "sec-fetch-mode"):
            val = headers.get(key) or headers.get(key.title()) or headers.get(key.upper())
            keys.append(f"{key}={val or ''}")
        return "|".join(keys)

    ua = str(_get(session, "ua", "user_agent", default="") or "")
    return f"ua={ua}"


def _paths_from(session: Any) -> tuple[str, ...]:
    paths = _get(session, "paths", "path_sequence", default=None)
    if isinstance(paths, (list, tuple)):
        return tuple(str(p) for p in paths)

    features = _get(session, "features", default={}) or {}
    if isinstance(features, dict) and isinstance(features.get("paths"), list):
        return tuple(str(p) for p in features["paths"])

    requests = _get(session, "requests", default=[]) or []
    out: list[str] = []
    for req in requests:
        path = _get(req, "path", "uri", default=None)
        if path is not None:
            out.append(str(path))
    return tuple(out)


def _logins_from(session: Any, session_id: int, ip: str) -> tuple[LoginEvent, ...]:
    events: list[LoginEvent] = []

    embedded = _get(session, "login_attempts", "logins", default=None)
    features = _get(session, "features", default={}) or {}
    if embedded is None and isinstance(features, dict):
        embedded = features.get("login_attempts") or features.get("logins")

    if isinstance(embedded, list):
        for row in embedded:
            username = str(_get(row, "username", "user", default="") or "")
            if not username:
                continue
            ts = _as_dt(_get(row, "ts", "timestamp", "time")) or datetime.now(tz=timezone.utc)
            success = bool(_get(row, "success", "ok", default=False))
            events.append(
                LoginEvent(
                    session_id=session_id,
                    ip=ip,
                    username=username.lower(),
                    ts=ts,
                    success=success,
                    path=str(_get(row, "path", default="/login") or "/login"),
                )
            )
        return tuple(events)

    requests = _get(session, "requests", default=[]) or []
    for req in requests:
        method = str(_get(req, "method", default="") or "").upper()
        path = str(_get(req, "path", "uri", default="") or "")
        if method != "POST" or "/login" not in path.lower():
            continue
        username = _get(req, "username", default=None)
        body = _get(req, "body", "form", default={}) or {}
        if username is None and isinstance(body, dict):
            username = body.get("username") or body.get("user") or body.get("email")
        if not username:
            continue
        status = int(_get(req, "status", "status_code", default=401) or 401)
        ts = _as_dt(_get(req, "ts", "timestamp", "time")) or datetime.now(tz=timezone.utc)
        events.append(
            LoginEvent(
                session_id=session_id,
                ip=ip,
                username=str(username).lower(),
                ts=ts,
                success=200 <= status < 300,
                path=path or "/login",
            )
        )
    return tuple(events)


def as_session_view(session: Any, fallback_id: int = 0) -> SessionView:
    sid_raw = _get(session, "id", "session_id", default=fallback_id)
    try:
        sid = int(sid_raw)
    except (TypeError, ValueError):
        sid = fallback_id
    ip = str(_get(session, "ip", "client_ip", default="") or "")
    ua = str(_get(session, "ua", "user_agent", default="") or "")
    started = _as_dt(_get(session, "started_at", "start", "started"))
    ended = _as_dt(_get(session, "ended_at", "end", "ended"))
    return SessionView(
        id=sid,
        ip=ip,
        ua=ua,
        started_at=started,
        ended_at=ended,
        paths=_paths_from(session),
        header_fingerprint=_header_fingerprint(session),
        logins=_logins_from(session, sid, ip),
        raw=session,
    )


def iter_session_views(sessions: Any) -> list[SessionView]:
    return [as_session_view(s, fallback_id=i) for i, s in enumerate(sessions or [])]
