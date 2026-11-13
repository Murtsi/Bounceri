"""C-2: DNS-botivarmistus + offline ASN."""

from __future__ import annotations

from unittest.mock import patch

from bouncer.network import ip_intel
from bouncer.network.asn import lookup_asn
from bouncer.network.bots import verify_search_bot


def test_asn_aws_prefix_is_datacenter() -> None:
    hit = lookup_asn("3.5.140.2")
    assert hit.asn_type == "datacenter"
    assert hit.asn == 16509


def test_asn_elisa_prefix_is_residential() -> None:
    hit = lookup_asn("88.200.10.5")
    assert hit.asn_type == "residential"
    assert hit.asn == 1759


def test_asn_unknown_ip() -> None:
    hit = lookup_asn("203.0.113.50")
    assert hit.asn_type == "unknown"
    assert hit.asn is None


def test_googlebot_verified_with_forward_confirm() -> None:
    ip = "66.249.66.1"
    with (
        patch(
            "bouncer.network.bots.socket.gethostbyaddr",
            return_value=("crawl-66-249-66-1.googlebot.com", [], [ip]),
        ),
        patch(
            "bouncer.network.bots.socket.gethostbyname_ex",
            return_value=("crawl-66-249-66-1.googlebot.com", [], [ip]),
        ),
    ):
        check = verify_search_bot(ip)
    assert check.verified is True
    assert check.name == "googlebot"


def test_fake_googlebot_ua_ip_fails_forward_confirm() -> None:
    """Hyökkääjä spoofaa PTR:n mutta forward ei osoita samaan IP:hen."""
    ip = "203.0.113.99"
    with (
        patch(
            "bouncer.network.bots.socket.gethostbyaddr",
            return_value=("crawl-fake.googlebot.com", [], [ip]),
        ),
        patch(
            "bouncer.network.bots.socket.gethostbyname_ex",
            return_value=("crawl-fake.googlebot.com", [], ["8.8.8.8"]),
        ),
    ):
        check = verify_search_bot(ip)
    assert check.verified is False


def test_ip_intel_wires_bot_and_asn() -> None:
    ip = "66.249.66.1"
    with (
        patch(
            "bouncer.network.bots.socket.gethostbyaddr",
            return_value=("crawl-66-249-66-1.googlebot.com", [], [ip]),
        ),
        patch(
            "bouncer.network.bots.socket.gethostbyname_ex",
            return_value=("crawl-66-249-66-1.googlebot.com", [], [ip]),
        ),
    ):
        intel = ip_intel(ip)
    assert intel.verified_bot is True
    assert intel.asn_type == "datacenter"
    assert intel.asn == 15169


def test_ip_intel_datacenter_without_bot() -> None:
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("no ptr"),
    ):
        intel = ip_intel("167.99.10.20")
    assert intel.verified_bot is False
    assert intel.asn_type == "datacenter"
