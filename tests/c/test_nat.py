"""C-9: shared NAT should not become a behavior campaign."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bouncer.network import find_campaigns
from bouncer.network.nat import looks_like_shared_nat
from bouncer.network.session_view import iter_session_views


def _sess(sid: int, ip: str, ua: str, paths: list[str], minute: int = 0) -> SimpleNamespace:
    ts = datetime(2026, 11, 14, 16, 0, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return SimpleNamespace(
        id=sid,
        ip=ip,
        ua=ua,
        started_at=ts,
        ended_at=ts + timedelta(minutes=2),
        paths=paths,
        headers={"user-agent": ua, "accept": "text/html"},
    )


def test_same_residential_ip_diverse_uas_is_shared_nat() -> None:
    # 88.200.x = Elisa residential in asn_prefixes.json
    paths = ["/a", "/b", "/c", "/d"]
    sessions = [
        _sess(1, "88.200.10.1", "Mozilla/5.0 (Windows)", paths, 0),
        _sess(2, "88.200.10.1", "Mozilla/5.0 (Macintosh)", paths, 1),
        _sess(3, "88.200.10.1", "Mozilla/5.0 (iPhone)", paths, 2),
    ]
    assert looks_like_shared_nat(iter_session_views(sessions)) is True
    assert find_campaigns(sessions) == []


def test_datacenter_same_paths_still_campaign() -> None:
    paths = ["/robots.txt", "/.env", "/wp-login.php", "/admin"]
    sessions = [
        _sess(1, "167.99.10.1", "python-requests/2.32", paths, 0),
        _sess(2, "167.99.10.2", "python-requests/2.32", paths, 1),
        _sess(3, "167.99.10.3", "python-requests/2.32", paths, 2),
    ]
    camps = find_campaigns(sessions)
    assert any(c.kind == "behavior_cluster" for c in camps)
