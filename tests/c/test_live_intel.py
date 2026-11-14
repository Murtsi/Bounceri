"""Bounded live DNS and immutable provenance, without real resolver calls."""

from __future__ import annotations

import importlib
import importlib.util
import json
import socket
import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from bouncer.contracts import IpIntel


class Clock:
    def __init__(self):
        self.seconds = 0.0

    def monotonic(self):
        return self.seconds

    def now(self):
        return datetime(2026, 11, 14, tzinfo=UTC) + timedelta(seconds=self.seconds)


def live_module():
    assert importlib.util.find_spec("bouncer.network.live") is not None
    return importlib.import_module("bouncer.network.live")


def packet(clock, *, verified=True, crawler="googlebot", outcome="verified"):
    return json.dumps({
        "checked_at": clock.now().isoformat(), "resolver_outcome": outcome,
        "verified_bot": verified, "crawler": crawler,
        "asn": None, "asn_type": "datacenter", "country": None, "asn_origin": "inferred",
    }).encode()


def make_live(clock, runner, **kwargs):
    return live_module().LiveIntel(
        runner=runner, monotonic=clock.monotonic, utc_now=clock.now, **kwargs,
    )


def test_inspect_ip_keeps_contract_api_and_only_resolves_once():
    from bouncer.network import intel
    from bouncer.network.bots import BotCheck

    assert hasattr(intel, "inspect_ip")
    with patch.object(intel, "verify_search_bot", return_value=BotCheck(True, "googlebot")) as dns:
        result, bot = intel.inspect_ip("66.249.66.1")
    assert result.as_contract() == IpIntel(True, 15169, "datacenter", None)
    assert bot.name == "googlebot"
    assert dns.call_count == 1


def test_verified_cache_preserves_checked_at_and_expires_after_300_seconds():
    clock = Clock()
    calls = []
    def runner(ip, timeout):
        calls.append((ip, timeout))
        return packet(clock)
    live = make_live(clock, runner)
    assert isinstance(live("2001:db8::1"), IpIntel)
    original = live.observation("2001:db8::1")
    clock.seconds = 299
    live.begin_cycle()
    assert live("2001:0db8::1").verified_bot is True
    assert live.observation("2001:db8::1") == original
    assert len(calls) == 1
    clock.seconds = 300
    live.begin_cycle()
    live("2001:db8::1")
    assert len(calls) == 2
    assert live.observation("2001:db8::1")["checked_at"] != original["checked_at"]


def test_timeout_is_unknown_with_local_asn_and_unknown_ttl():
    clock = Clock()
    calls = []
    def runner(ip, timeout):
        calls.append(timeout)
        raise subprocess.TimeoutExpired("lookup", timeout)
    live = make_live(clock, runner)
    assert live("88.200.10.5") == IpIntel(None, 1759, "residential", "FI")
    snapshot = live.observation("88.200.10.5")
    assert snapshot["resolver_outcome"] == "timeout"
    assert snapshot["asn_origin"] == "curated-prefix"
    clock.seconds = 59
    live.begin_cycle()
    live("88.200.10.5")
    assert len(calls) == 1
    clock.seconds = 60
    live.begin_cycle()
    live("88.200.10.5")
    assert len(calls) == 2


def test_cycle_capacity_is_not_cached_and_budget_recovers_next_cycle():
    clock = Clock()
    calls = []
    def runner(ip, timeout):
        calls.append(ip)
        return packet(clock)
    live = make_live(clock, runner)
    for index in range(5):
        live(f"2001:db8::{index + 1}")
    assert len(calls) == 4
    assert live.observation("2001:db8::5")["resolver_outcome"] == "capacity"
    assert live("2001:db8::5").verified_bot is None
    live.begin_cycle()
    assert live("2001:db8::5").verified_bot is True
    assert len(calls) == 5


def test_elapsed_cycle_budget_limits_even_fast_count_and_uses_remaining_time():
    clock = Clock()
    timeouts = []
    def runner(ip, timeout):
        timeouts.append(timeout)
        clock.seconds += .7
        return packet(clock)
    live = make_live(clock, runner, cycle_budget_seconds=1.0)
    live("2001:db8::1")
    live("2001:db8::2")
    assert timeouts == pytest.approx([1.0, .3])
    assert live("2001:db8::3").verified_bot is None
    assert live.observation("2001:db8::3")["resolver_outcome"] == "capacity"


@pytest.mark.parametrize("payload", [
    b"not json", b"[]", b"{}", b"x" * 16385,
    b'{"verified_bot": "true"}',
], ids=["non-json", "array", "missing-fields", "oversized", "string-boolean"])
def test_malformed_protocol_is_unknown_not_spoof(payload):
    clock = Clock()
    live = make_live(clock, lambda ip, timeout: payload)
    assert live("203.0.113.1").verified_bot is None
    assert live.observation("203.0.113.1")["resolver_outcome"] == "unavailable"


@pytest.mark.parametrize("change", [
    {"verified_bot": 1}, {"asn": True}, {"asn_type": "invented"},
    {"checked_at": "yesterday"}, {"checked_at": "2026-11-14T00:00:00"},
    {"resolver_outcome": "mismatch"}, {"crawler": None}, {"crawler": "evil"},
    {"country": "not a country"}, {"asn_origin": "live-geoip"},
])
def test_protocol_requires_native_types_and_consistent_verification(change):
    clock = Clock()
    value = json.loads(packet(clock))
    value.update(change)
    live = make_live(clock, lambda ip, timeout: json.dumps(value).encode())
    assert live("203.0.113.1").verified_bot is None
    assert live.observation("203.0.113.1")["resolver_outcome"] == "unavailable"


def test_invalid_ip_never_starts_a_child():
    clock = Clock()
    def runner(ip, timeout):
        pytest.fail("invalid input must not start DNS")
    live = make_live(clock, runner)
    for ip in ["https://example.com", "example.com", "--help", "fe80::1%eth0"]:
        assert live(ip) == IpIntel()
        assert live.observation(ip)["resolver_outcome"] == "invalid"


def test_cache_is_bounded_lru_and_snapshot_cannot_mutate_internal_state():
    clock = Clock()
    calls = []
    def runner(ip, timeout):
        calls.append(ip)
        return packet(clock)
    live = make_live(clock, runner, cache_size=2)
    live("2001:db8::1")
    live("2001:db8::2")
    live("2001:db8::1")
    live("2001:db8::3")
    live.observation("2001:db8::1")["verified_bot"] = False
    assert live("2001:db8::1").verified_bot is True
    live.begin_cycle()
    live("2001:db8::2")
    assert calls == ["2001:db8::1", "2001:db8::2", "2001:db8::3", "2001:db8::2"]
    assert len(live._cache) == 2


def test_child_dns_failure_and_double_stack_provenance():
    live_module()
    lookup = importlib.import_module("bouncer.network.lookup")
    with patch("bouncer.network.bots.socket.gethostbyaddr", side_effect=OSError("offline")):
        unknown = lookup.lookup_ip("88.200.10.5")
    assert unknown["verified_bot"] is None
    assert unknown["resolver_outcome"] == "unavailable"
    assert unknown["country"] == "FI"
    assert unknown["asn_origin"] == "curated-prefix"
    with (
        patch("bouncer.network.bots.socket.gethostbyaddr",
              return_value=("crawl.googlebot.com", [], ["2001:db8::1"])),
        patch("bouncer.network.bots.socket.getaddrinfo", return_value=[
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:0db8::1", 0, 0, 0)),
        ]) as forward,
    ):
        verified = lookup.lookup_ip("2001:db8::1")
    assert verified["verified_bot"] is True
    assert verified["crawler"] == "googlebot"
    assert verified["asn_origin"] == "inferred"
    forward.assert_called_once_with("crawl.googlebot.com", None, family=socket.AF_UNSPEC)


def test_runner_subprocess_is_shell_free_and_checks_bounded_output():
    module = live_module()
    with patch.object(module.subprocess, "Popen") as popen:
        process = popen.return_value
        process.wait.return_value = 0
        assert module.run_lookup("203.0.113.1", .9) == b""
    args, kwargs = popen.call_args
    assert args[0][-3:] == ["-m", "bouncer.network.lookup", "203.0.113.1"]
    assert kwargs["shell"] is False
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert process.wait.call_args.kwargs["timeout"] < .9


def test_runner_kills_timed_out_child_without_blocking_cleanup():
    module = live_module()
    with patch.object(module.subprocess, "Popen") as popen:
        process = popen.return_value
        process.wait.side_effect = [subprocess.TimeoutExpired("lookup", .8), 0]
        with pytest.raises(subprocess.TimeoutExpired):
            module.run_lookup("203.0.113.1", .9)
    process.kill.assert_called_once()
    assert process.wait.call_count == 2
    assert process.wait.call_args.kwargs["timeout"] <= .1


def test_runner_charges_process_startup_before_waiting():
    module = live_module()
    clock = Clock()
    with (
        patch.object(module.time, "monotonic", clock.monotonic),
        patch.object(module.subprocess, "Popen") as popen,
    ):
        def start(*args, **kwargs):
            clock.seconds += .3
            return process
        process = popen.return_value
        popen.side_effect = start
        process.wait.return_value = 0
        module.run_lookup("203.0.113.1", 1.0)
    assert process.wait.call_args.kwargs["timeout"] == pytest.approx(.6)


def test_success_after_deadline_is_discarded_as_timeout():
    clock = Clock()
    def runner(ip, timeout):
        clock.seconds += timeout + .01
        return packet(clock)
    live = make_live(clock, runner)
    assert live("203.0.113.1").verified_bot is None
    assert live.observation("203.0.113.1")["resolver_outcome"] == "timeout"


def test_child_cli_rejects_hosts_and_extra_arguments_without_dns(capsys):
    live_module()
    lookup = importlib.import_module("bouncer.network.lookup")
    with patch.object(lookup, "inspect_ip", side_effect=AssertionError("must not resolve")):
        assert lookup.main(["example.com"]) == 2
        assert lookup.main(["203.0.113.1", "other"]) == 2
    assert capsys.readouterr().out == ""


def test_child_cli_emits_bounded_typed_protocol(capsys):
    module = live_module()
    lookup = importlib.import_module("bouncer.network.lookup")
    with patch("bouncer.network.bots.socket.gethostbyaddr", side_effect=OSError("offline")):
        assert lookup.main(["88.200.10.5"]) == 0
    payload = capsys.readouterr().out.encode()
    assert len(payload) < 16384
    assert module._decode(payload)["asn"] == 1759


def test_child_output_bound_includes_terminating_newline(capsys):
    live_module()
    lookup = importlib.import_module("bouncer.network.lookup")
    with (
        patch.object(lookup, "lookup_ip", return_value={}),
        patch.object(lookup.json, "dumps", return_value="x" * 16384),
    ):
        assert lookup.main(["203.0.113.1"]) == 1
    assert capsys.readouterr().out == ""


def test_runner_only_reads_bounded_stdout():
    module = live_module()
    with patch.object(module.subprocess, "Popen") as popen:
        def start(*args, **kwargs):
            kwargs["stdout"].write(b"x" * 20000)
            return process
        process = popen.return_value
        popen.side_effect = start
        process.wait.return_value = 0
        result = module.run_lookup("203.0.113.1", 1.0)
    assert len(result) == 16385
    with pytest.raises(ValueError):
        module._decode(result)


def test_process_failure_is_unknown_and_keeps_offline_metadata():
    clock = Clock()
    def runner(ip, timeout):
        raise OSError("child failed")
    live = make_live(clock, runner)
    assert live("3.5.140.2") == IpIntel(None, 16509, "datacenter", None)
    assert live.observation("3.5.140.2")["resolver_outcome"] == "unavailable"


@pytest.mark.parametrize("kwargs", [
    {"timeout_seconds": 1.1}, {"timeout_seconds": float("nan")},
    {"cycle_budget_seconds": 4.1}, {"max_lookups_per_cycle": 5},
    {"cache_size": 2049}, {"cache_size": 0},
])
def test_configuration_cannot_remove_resource_bounds(kwargs):
    with pytest.raises(ValueError):
        live_module().LiveIntel(**kwargs)
