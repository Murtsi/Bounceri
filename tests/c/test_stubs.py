"""C-1: stub-sopimukset S4, S5, S7, S9."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from bouncer.explain import explain
from bouncer.network import Campaign, IpIntel, find_campaigns, ip_intel, make_campaign
from bouncer.network.eval import load_campaign_metrics


def test_ip_intel_unknown_ip_without_dns() -> None:
    """Dokumentoitu TEST-NET IP: ei ASN-osumaa; DNS mockattu offlineksi."""
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("offline"),
    ):
        intel = ip_intel("203.0.113.10")
    assert isinstance(intel, IpIntel)
    assert intel.verified_bot is None  # DNS epäonnistui → ei tarkistettu (S4)
    assert intel.asn is None
    assert intel.asn_type == "unknown"
    assert intel.country is None


def test_find_campaigns_stub_returns_empty() -> None:
    campaigns = find_campaigns([SimpleNamespace(id="1"), SimpleNamespace(id="2")])
    assert campaigns == []
    assert isinstance(campaigns, list)


def test_explain_stub_joins_reasons() -> None:
    verdict = SimpleNamespace(reasons=["fast crawl", "no static assets", "datacenter ASN"])
    text = explain(verdict, session=None, campaign=None)
    assert "fast crawl" in text
    assert "no static assets" in text
    assert "datacenter ASN" in text


def test_explain_stub_includes_campaign() -> None:
    verdict = SimpleNamespace(reasons=["credential stuffing pattern"])
    campaign = make_campaign(
        id="camp-1",
        kind="credential_stuffing",
        session_ids=["1", "2", "3"],
        reasons=["same username across 3 IPs"],
    )
    assert isinstance(campaign, Campaign)
    text = explain(verdict, session=None, campaign=campaign)
    assert "camp-1" in text
    assert "same username across 3 IPs" in text


def test_campaign_metrics_stub_flag() -> None:
    metrics = load_campaign_metrics()
    assert metrics["stub"] is True
    assert metrics["n_predicted"] == 0
    assert isinstance(metrics["known_weaknesses"], list)
