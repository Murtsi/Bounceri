"""C-2: DNS-botivarmistus + offline ASN."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from bouncer.network import VERIFIABLE_CRAWLER_TOKENS, ip_intel
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
    assert hit.country == "FI"


def test_ip_intel_sets_country_for_fi_prefix() -> None:
    from bouncer.contracts import IpIntel as ContractIpIntel
    from bouncer.network import ip_intel_contract

    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("offline"),
    ):
        intel = ip_intel("88.200.10.5")
        contract = ip_intel_contract("88.200.10.5")
    assert intel.country == "FI"
    assert isinstance(contract, ContractIpIntel)
    assert contract.country == "FI"
    assert not hasattr(contract, "threat_label")


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
            "bouncer.network.bots.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))],
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
            "bouncer.network.bots.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))],
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
            "bouncer.network.bots.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))],
        ),
    ):
        intel = ip_intel(ip)
    assert intel.verified_bot is True
    assert intel.asn_type == "datacenter"
    assert intel.asn == 15169


def test_dns_failure_returns_none_not_false() -> None:
    """Oikea Googlebot + DNS-timeout ei saa laukaista B:n fake-crawler -sääntöä."""
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("timeout"),
    ):
        check = verify_search_bot("66.249.66.1")
        intel = ip_intel("66.249.66.1")
    assert check.verified is None
    assert intel.verified_bot is None


@pytest.mark.parametrize("host", ["crawl.googlebot.com", "crawl.search.msn.com"])
@pytest.mark.parametrize("error", [socket.gaierror, socket.herror, TimeoutError, OSError])
def test_forward_dns_failure_returns_none(host: str, error: type[OSError]) -> None:
    ip = "66.249.66.1"
    with (
        patch(
            "bouncer.network.bots.socket.gethostbyaddr",
            return_value=(host, [], [ip]),
        ),
        patch("bouncer.network.bots.socket.getaddrinfo", side_effect=error("offline")),
    ):
        check = verify_search_bot(ip)
        intel = ip_intel(ip)
    assert check.verified is None
    assert check.name is None
    assert check.reverse_host == host
    assert intel.verified_bot is None


@pytest.mark.parametrize(
    ("host", "name"),
    [("crawl.googlebot.com", "googlebot"), ("crawl.search.msn.com", "bingbot")],
)
def test_ipv6_bot_verified_with_normalized_forward_confirm(host: str, name: str) -> None:
    ip = "2001:db8::1"
    with (
        patch(
            "bouncer.network.bots.socket.gethostbyaddr",
            return_value=(host, [], [ip]),
        ),
        patch(
            "bouncer.network.bots.socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.1", 0)),
                (
                    socket.AF_INET6,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    ("2001:0db8:0000:0000:0000:0000:0000:0001", 0, 0, 0),
                ),
            ],
        ) as forward,
    ):
        check = verify_search_bot(ip)
    assert check.verified is True
    assert check.name == name
    forward.assert_called_once_with(host, None, family=socket.AF_UNSPEC)


def test_ptr_without_search_bot_suffix_is_false() -> None:
    ip = "203.0.113.40"
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        return_value=("host.example.net", [], [ip]),
    ):
        check = verify_search_bot(ip)
    assert check.verified is False


def test_ip_intel_datacenter_dns_fail_still_has_asn() -> None:
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("no ptr"),
    ):
        intel = ip_intel("167.99.10.20")
    assert intel.verified_bot is None
    assert intel.asn_type == "datacenter"


def test_verifiable_tokens_match_b_contract() -> None:
    assert VERIFIABLE_CRAWLER_TOKENS == ("googlebot", "bingbot")
