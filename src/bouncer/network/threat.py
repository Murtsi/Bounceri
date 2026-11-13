"""Threat-feed: offline tunnetut haitalliset CIDR:t (jos aikaa jää).

Ei live-feediä — curated demo-lista. Osuma näkyy IpIntelissä
`threat_label`-kentän kautta (lisäinfo B:lle / dashboardille).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from pathlib import Path

DATA_PATH = Path(__file__).with_name("data") / "threat_prefixes.json"


@dataclass(frozen=True, slots=True)
class ThreatHit:
    label: str
    asn: int | None = None
    org: str | None = None


@dataclass(frozen=True, slots=True)
class _Rule:
    network: IPv4Network
    label: str
    asn: int | None
    org: str | None


@lru_cache(maxsize=1)
def _load_rules(path: str | None = None) -> tuple[_Rule, ...]:
    target = Path(path) if path else DATA_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    rules: list[_Rule] = []
    for row in raw.get("prefixes", []):
        net = ip_network(row["cidr"], strict=False)
        if not isinstance(net, IPv4Network):
            continue
        rules.append(
            _Rule(
                network=net,
                label=str(row["label"]),
                asn=int(row["asn"]) if row.get("asn") is not None else None,
                org=row.get("org"),
            )
        )
    rules.sort(key=lambda r: r.network.prefixlen, reverse=True)
    return tuple(rules)


def lookup_threat(ip: str, data_path: str | None = None) -> ThreatHit | None:
    try:
        addr = ip_address(ip)
    except ValueError:
        return None
    if not isinstance(addr, IPv4Address):
        return None
    for rule in _load_rules(data_path):
        if addr in rule.network:
            return ThreatHit(label=rule.label, asn=rule.asn, org=rule.org)
    return None
