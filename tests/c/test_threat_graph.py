"""Threat-feed + campaign graph export."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from bouncer.network import campaign_graph, find_campaigns, ip_intel, lookup_threat
from bouncer.network.types import make_campaign


def test_threat_prefix_hit() -> None:
    hit = lookup_threat("185.220.100.10")
    assert hit is not None
    assert hit.label == "tor_exit_ish"


def test_ip_intel_sets_threat_label() -> None:
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("offline"),
    ):
        intel = ip_intel("185.220.100.10")
    assert intel.threat_label == "tor_exit_ish"
    assert intel.asn_type == "datacenter"


def test_campaign_graph_shape() -> None:
    ts = datetime(2026, 11, 14, tzinfo=timezone.utc)
    sessions = [
        SimpleNamespace(
            id="1",
            ip="203.0.113.1",
            ua="curl/8",
            started_at=ts,
            ended_at=ts,
            paths=["/login"],
            headers={"user-agent": "curl/8"},
        ),
        SimpleNamespace(
            id="2",
            ip="203.0.113.2",
            ua="curl/8",
            started_at=ts,
            ended_at=ts,
            paths=["/login"],
            headers={"user-agent": "curl/8"},
        ),
    ]
    camps = [
        make_campaign(
            id="stuffing:admin",
            kind="credential_stuffing",
            session_ids=["1", "2"],
            reasons=["same username"],
        )
    ]
    graph = campaign_graph(camps, sessions)
    assert graph["n_campaigns"] == 1
    assert graph["n_sessions"] == 2
    assert graph["n_ips"] == 2
    kinds = {n["kind"] for n in graph["nodes"]}
    assert kinds == {"campaign", "session", "ip"}
    assert any(e["kind"] == "in_campaign" for e in graph["edges"])


def test_find_campaigns_still_works_with_graph_export() -> None:
    assert find_campaigns([]) == []
    assert campaign_graph([])["nodes"] == []
