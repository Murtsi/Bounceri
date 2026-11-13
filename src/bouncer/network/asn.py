"""Offline ASN / verkko­tyyppi -haku CIDR-listasta (C-2)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from pathlib import Path

DATA_PATH = Path(__file__).with_name("data") / "asn_prefixes.json"


@dataclass(frozen=True, slots=True)
class AsnHit:
    asn: int | None
    asn_type: str  # unknown | datacenter | residential | mobile
    org: str | None = None


@dataclass(frozen=True, slots=True)
class _PrefixRule:
    network: IPv4Network
    asn: int
    asn_type: str
    org: str | None


@lru_cache(maxsize=1)
def _load_rules(path: str | None = None) -> tuple[_PrefixRule, ...]:
    target = Path(path) if path else DATA_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    rules: list[_PrefixRule] = []
    for row in raw.get("prefixes", []):
        net = ip_network(row["cidr"], strict=False)
        if not isinstance(net, IPv4Network):
            continue
        rules.append(
            _PrefixRule(
                network=net,
                asn=int(row["asn"]),
                asn_type=str(row["asn_type"]),
                org=row.get("org"),
            )
        )
    # Longest prefix first
    rules.sort(key=lambda r: r.network.prefixlen, reverse=True)
    return tuple(rules)


def lookup_asn(ip: str, data_path: str | None = None) -> AsnHit:
    """Palauta ASN-tyyppi offline-listasta; muuten unknown."""
    try:
        addr = ip_address(ip)
    except ValueError:
        return AsnHit(asn=None, asn_type="unknown")

    if not isinstance(addr, IPv4Address):
        # IPv6 left as unknown until we curate v6 prefixes
        return AsnHit(asn=None, asn_type="unknown")

    for rule in _load_rules(data_path):
        if addr in rule.network:
            return AsnHit(asn=rule.asn, asn_type=rule.asn_type, org=rule.org)

    return AsnHit(asn=None, asn_type="unknown")
