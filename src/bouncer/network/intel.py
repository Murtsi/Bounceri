"""S4 — `ip_intel(ip) -> IpIntel`.

C-1 stub → C-2: DNS-varmistetut hakukonebotit + offline ASN-tyyppi.
S4 hyväksytty: `verified_bot: bool | None` (päätökset 020 + 027).
"""

from __future__ import annotations

from bouncer.network.asn import lookup_asn
from bouncer.network.bots import verify_search_bot
from bouncer.network.threat import lookup_threat
from bouncer.network.types import IpIntel


def ip_intel(ip: str) -> IpIntel:
    """Palauta IP-tiedot: verified_bot, ASN, asn_type, country, threat_label.

    `country` tulee curated ASN-prefixeistä (ei MaxMind/GeoIP) — vain kun
    listassa on eksplisiittinen `country`-kenttä (päätös 033).
    """
    bot = verify_search_bot(ip)
    asn = lookup_asn(ip)
    threat = lookup_threat(ip)

    asn_type = asn.asn_type
    asn_num = asn.asn
    # Varmistettu hakukonebotti on aina datacenter-luokkaa demossa
    if bot.verified is True and asn_type == "unknown":
        asn_type = "datacenter"
    if threat is not None:
        asn_type = "datacenter"
        if asn_num is None:
            asn_num = threat.asn

    return IpIntel(
        verified_bot=bot.verified,
        asn=asn_num,
        asn_type=asn_type,
        country=asn.country,
        threat_label=threat.label if threat else None,
    )


def ip_intel_contract(ip: str) -> object:
    """S4-muoto B:n `score` / `eval.run` -polulle (ilman threat_label)."""
    return ip_intel(ip).as_contract()
