"""One isolated, IP-only DNS lookup; stdout is a bounded private JSON observation."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from ipaddress import ip_address

from bouncer.network.asn import lookup_asn
from bouncer.network.intel import inspect_ip
from bouncer.network.threat import lookup_threat

MAX_OUTPUT_BYTES = 16 * 1024


def normalize_ip(ip: str) -> str:
    if not isinstance(ip, str) or "%" in ip:
        raise ValueError("a plain IP address is required")
    return str(ip_address(ip))


def offline_observation(ip: str, checked_at: str, outcome: str) -> dict:
    """Curated local prefix metadata is available even when DNS is unknown."""
    asn = lookup_asn(ip)
    threat = lookup_threat(ip)
    return {
        "checked_at": checked_at,
        "resolver_outcome": outcome,
        "verified_bot": None,
        "crawler": None,
        "asn": asn.asn if asn.asn is not None else threat.asn if threat else None,
        "asn_type": "datacenter" if threat else asn.asn_type,
        "country": asn.country,
        "asn_origin": "curated-prefix" if asn.asn is not None or threat else "unknown",
    }


def lookup_ip(ip: str) -> dict:
    ip = normalize_ip(ip)
    result, bot = inspect_ip(ip)
    snapshot = offline_observation(ip, datetime.now(UTC).isoformat(), "unavailable")
    snapshot.update(
        verified_bot=bot.verified,
        resolver_outcome=(
            "verified" if bot.verified is True else "mismatch" if bot.verified is False
            else "unavailable"
        ),
        crawler=bot.name if bot.verified is True else None,
        asn=result.asn,
        asn_type=result.asn_type,
        country=result.country,
    )
    if snapshot["asn_origin"] == "unknown" and result.asn_type != "unknown":
        snapshot["asn_origin"] = "inferred"
    return snapshot


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return 2
    try:
        ip = normalize_ip(args[0])
    except ValueError:
        return 2
    try:
        snapshot = lookup_ip(ip)
    except (OSError, ValueError):
        snapshot = offline_observation(ip, datetime.now(UTC).isoformat(), "unavailable")
    payload = (json.dumps(snapshot, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > MAX_OUTPUT_BYTES:
        return 1
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
