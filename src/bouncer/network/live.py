"""Bounded process-isolated resolver, per-cycle budget and expiring LRU evidence."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime

from bouncer.contracts import IpIntel
from bouncer.network.lookup import MAX_OUTPUT_BYTES, normalize_ip, offline_observation


def run_lookup(ip: str, timeout: float) -> bytes:
    """Charge process startup and bounded kill/reap time to the lookup deadline."""
    ip = normalize_ip(ip)
    deadline = time.monotonic() + timeout
    cleanup_budget = min(.1, timeout / 4)
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "bouncer.network.lookup", ip],
            shell=False, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            remaining = deadline - time.monotonic() - cleanup_budget
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            status = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            # Never wait indefinitely for resolver cleanup.
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=max(0, min(cleanup_budget, deadline - time.monotonic())))
            raise
        if status != 0:
            raise OSError("resolver child failed")
        output.seek(0)
        return output.read(MAX_OUTPUT_BYTES + 1)


def _decode(payload: bytes) -> dict:
    if not isinstance(payload, bytes) or len(payload) > MAX_OUTPUT_BYTES:
        raise ValueError("invalid resolver output size")
    value = json.loads(payload)
    fields = {
        "checked_at", "resolver_outcome", "verified_bot", "crawler", "asn", "asn_type",
        "country", "asn_origin",
    }
    if not isinstance(value, dict) or value.keys() != fields:
        raise ValueError("invalid resolver fields")
    verified = value["verified_bot"]
    if verified is not None and type(verified) is not bool:
        raise ValueError("invalid verified_bot")
    expected_outcome = "verified" if verified is True else (
        "mismatch" if verified is False else "unavailable"
    )
    if value["resolver_outcome"] != expected_outcome:
        raise ValueError("inconsistent resolver status")
    if (verified is True and value["crawler"] not in ("googlebot", "bingbot")) or (
        verified is not True and value["crawler"] is not None
    ):
        raise ValueError("inconsistent crawler")
    if value["asn"] is not None and (
        type(value["asn"]) is not int or not 0 < value["asn"] <= 4294967295
    ):
        raise ValueError("invalid ASN")
    if value["asn_type"] not in ("unknown", "datacenter", "residential", "mobile"):
        raise ValueError("invalid ASN type")
    country = value["country"]
    if country is not None and (
        not isinstance(country, str) or len(country) != 2
        or not country.isascii() or not country.isalpha() or not country.isupper()
    ):
        raise ValueError("invalid country")
    if value["asn_origin"] not in ("curated-prefix", "inferred", "unknown"):
        raise ValueError("invalid ASN origin")
    checked_at = datetime.fromisoformat(value["checked_at"])
    if checked_at.utcoffset() is None or checked_at.utcoffset().total_seconds() != 0:
        raise ValueError("checked_at must be UTC")
    return value


class LiveIntel:
    """S4 callable. Call begin_cycle once; observation returns a private snapshot."""

    def __init__(
        self, *, runner: Callable[[str, float], bytes] = run_lookup,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout_seconds: float = 1.0, max_lookups_per_cycle: int = 4,
        cycle_budget_seconds: float = 4.0, cache_size: int = 2048,
    ):
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 1:
            raise ValueError("lookup timeout must be in (0, 1]")
        if not math.isfinite(cycle_budget_seconds) or not 0 < cycle_budget_seconds <= 4:
            raise ValueError("cycle budget must be in (0, 4]")
        if type(max_lookups_per_cycle) is not int or not 1 <= max_lookups_per_cycle <= 4:
            raise ValueError("cycle lookup count must be in [1, 4]")
        if type(cache_size) is not int or not 1 <= cache_size <= 2048:
            raise ValueError("cache size must be in [1, 2048]")
        self._runner, self._monotonic, self._utc_now = runner, monotonic, utc_now
        self._timeout, self._max_lookups = timeout_seconds, max_lookups_per_cycle
        self._cycle_budget, self._cache_size = cycle_budget_seconds, cache_size
        self._cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._observations: OrderedDict[str, dict] = OrderedDict()
        self.begin_cycle()

    def begin_cycle(self) -> None:
        self._lookups = 0
        self._spent = 0.0
        self._observations.clear()

    def _remember(self, ip: str, value: dict) -> dict:
        self._observations[ip] = value
        self._observations.move_to_end(ip)
        while len(self._observations) > self._cache_size:
            self._observations.popitem(last=False)
        return value

    def _lookup(self, ip: str) -> dict:
        now = self._monotonic()
        cached = self._cache.get(ip)
        if cached and now < cached[0]:
            self._cache.move_to_end(ip)
            return self._remember(ip, cached[1])
        if cached:
            del self._cache[ip]
        value = offline_observation(ip, self._utc_now().isoformat(), "capacity")
        remaining = self._cycle_budget - self._spent
        if self._lookups >= self._max_lookups or remaining <= 0:
            return self._remember(ip, value)
        self._lookups += 1
        timeout = min(self._timeout, remaining)
        try:
            payload = self._runner(ip, timeout)
            if self._monotonic() - now > timeout:
                raise subprocess.TimeoutExpired("lookup", timeout)
            value = _decode(payload)
        except subprocess.TimeoutExpired:
            value["resolver_outcome"] = "timeout"
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            value["resolver_outcome"] = "unavailable"
        finally:
            self._spent += max(0, self._monotonic() - now)
        ttl = 60 if value["verified_bot"] is None else 300
        self._cache[ip] = (self._monotonic() + ttl, value)
        self._cache.move_to_end(ip)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return self._remember(ip, value)

    def __call__(self, ip: str) -> IpIntel:
        try:
            ip = normalize_ip(ip)
        except ValueError:
            return IpIntel()
        value = self._lookup(ip)
        return IpIntel(
            verified_bot=value["verified_bot"], asn=value["asn"],
            asn_type=value["asn_type"], country=value["country"],
        )

    def observation(self, ip: str) -> dict:
        try:
            ip = normalize_ip(ip)
        except ValueError:
            return offline_observation("", self._utc_now().isoformat(), "invalid")
        value = self._observations.get(ip)
        if value is None:
            cached = self._cache.get(ip)
            if cached and self._monotonic() < cached[0]:
                value = cached[1]
        if value is None:
            value = offline_observation(ip, self._utc_now().isoformat(), "capacity")
        return value.copy()
