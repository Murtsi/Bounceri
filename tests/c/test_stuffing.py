"""C-3: credential stuffing across sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bouncer.network import find_campaigns
from bouncer.network.stuffing import StuffingConfig, detect_credential_stuffing
from bouncer.network.session_view import iter_session_views


def _session(sid: int, ip: str, username: str, minute: int) -> SimpleNamespace:
    ts = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return SimpleNamespace(
        id=sid,
        ip=ip,
        ua="curl/8.0",
        started_at=ts,
        ended_at=ts + timedelta(seconds=5),
        paths=["/login"],
        headers={"user-agent": "curl/8.0"},
        login_attempts=[
            {"username": username, "ts": ts.isoformat(), "success": False, "path": "/login"}
        ],
    )


def test_same_username_from_many_ips() -> None:
    sessions = [
        _session(1, "203.0.113.1", "alice", 0),
        _session(2, "203.0.113.2", "alice", 1),
        _session(3, "203.0.113.3", "alice", 2),
        _session(4, "198.51.100.9", "bob", 1),  # noise
    ]
    camps = detect_credential_stuffing(iter_session_views(sessions))
    assert any(c.kind == "credential_stuffing" for c in camps)
    alice = next(c for c in camps if "alice" in c.id)
    assert set(alice.session_ids) == {1, 2, 3}


def test_distributed_spray() -> None:
    cfg = StuffingConfig(spray_min_ips=5, min_ips_per_username=99)  # disable username path
    sessions = [
        _session(i, f"203.0.113.{i}", f"user{i}", i) for i in range(1, 7)
    ]
    camps = detect_credential_stuffing(iter_session_views(sessions), cfg)
    assert any(c.kind == "distributed_login_spray" for c in camps)


def test_find_campaigns_wires_stuffing() -> None:
    sessions = [_session(i, f"203.0.113.{i}", "admin", i) for i in range(1, 5)]
    camps = find_campaigns(sessions, include_behavior=False)
    assert len(camps) >= 1
    assert camps[0].session_ids
