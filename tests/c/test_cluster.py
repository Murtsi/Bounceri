"""C-5: behavior campaign clustering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from bouncer.network.cluster import find_behavior_campaigns, jaccard
from bouncer.network.session_view import iter_session_views


def _sess(sid: str, ip: str, paths: list[str], minute: int = 0) -> SimpleNamespace:
    ts = datetime(2026, 11, 14, 15, 0, tzinfo=UTC) + timedelta(minutes=minute)
    return SimpleNamespace(
        id=sid,
        ip=ip,
        ua="python-requests/2.32",
        started_at=ts,
        ended_at=ts + timedelta(minutes=2),
        paths=paths,
        headers={
            "user-agent": "python-requests/2.32",
            "accept": "*/*",
            "accept-language": "",
        },
    )


def test_jaccard_identical() -> None:
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_similar_path_sequences_cluster() -> None:
    paths = ["/robots.txt", "/.env", "/wp-login.php", "/admin", "/api/v1"]
    sessions = [
        _sess("1", "203.0.113.10", paths, 0),
        _sess("2", "203.0.113.11", paths, 1),
        _sess("3", "203.0.113.12", paths[:-1] + ["/api/v2"], 2),
        _sess("4", "198.51.100.1", ["/", "/about", "/contact"], 0),  # human-ish
    ]
    camps = find_behavior_campaigns(iter_session_views(sessions))
    assert len(camps) == 1
    assert camps[0].kind == "behavior_cluster"
    assert set(camps[0].session_ids) == {"1", "2", "3"}


def test_different_header_fp_not_clustered() -> None:
    paths = ["/a", "/b", "/c", "/d"]
    a = _sess("1", "203.0.113.1", paths, 0)
    b = _sess("2", "203.0.113.2", paths, 1)
    c = _sess("3", "203.0.113.3", paths, 2)
    c.headers = {"user-agent": "Mozilla/5.0", "accept": "text/html"}
    camps = find_behavior_campaigns(iter_session_views([a, b, c]))
    # a+b may cluster if only 2 — min_sessions=3, so none
    assert camps == []
