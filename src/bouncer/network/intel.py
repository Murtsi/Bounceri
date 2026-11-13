"""S4 — `ip_intel(ip) -> IpIntel`.

C-1 stub → C-2: DNS-varmistetut hakukonebotit + offline ASN-tyyppi.
S4 hyväksytty: `verified_bot: bool | None` (päätökset 020 + 027).
"""

from __future__ import annotations

from bouncer.network.asn import lookup_asn
from bouncer.network.bots import verify_search_bot
from bouncer.network.types import IpIntel


def ip_intel(ip: str) -> IpIntel:
    """Palauta IP-tiedot: verified_bot, ASN, asn_type, country.

    `country` jätetään toistaiseksi None (ei GeoIP-tietokantaa C-2:ssa).
    """
    bot = verify_search_bot(ip)
    asn = lookup_asn(ip)

    asn_type = asn.asn_type
    # Varmistettu hakukonebotti on aina datacenter-luokkaa demossa
    if bot.verified is True and asn_type == "unknown":
        asn_type = "datacenter"

    return IpIntel(
        verified_bot=bot.verified,
        asn=asn.asn,
        asn_type=asn_type,
        country=None,
    )
