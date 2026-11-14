"""C-9: jaettu IP / venue-WiFi / mobiili-NAT -väärien positiivisten esto.

Monta ihmistä saman NAT:n takana näyttää yhdeltä toimijalta, jos klusteroidaan
vain IP:n tai heikon polkusimilaarisuuden perusteella. Estetään behavior-
kampanjat, jotka näyttävät shared-NAT -kuvioilta, ja kirjataan heikkous.
"""

from __future__ import annotations

from collections import Counter

from bouncer.network.asn import lookup_asn
from bouncer.network.session_view import SessionView

KNOWN_WEAKNESS = (
    "Shared NAT / venue Wi-Fi / mobile carrier NAT: many humans behind one IP "
    "can look like a single actor (C-9)."
)

_SHARED_ASN_TYPES = frozenset({"residential", "mobile", "unknown"})


def looks_like_shared_nat(sessions: list[SessionView]) -> bool:
    """True jos klusteri näyttää jaetulta IP:ltä eikä hajautetulta bottiverkolta."""
    if len(sessions) < 2:
        return False

    ips = [s.ip for s in sessions if s.ip]
    if not ips:
        return False

    ip_counts = Counter(ips)
    dominant_ip, dominant_n = ip_counts.most_common(1)[0]
    # ≥70 % sessioista samasta IP:stä
    if dominant_n / len(sessions) < 0.7:
        return False

    asn = lookup_asn(dominant_ip)
    if asn.asn_type not in _SHARED_ASN_TYPES:
        # Datacenter-IP:n "yksi IP, monta sessiota" on tyypillisempi botti
        return False

    uas = {s.ua for s in sessions if s.ua}
    # Useat eri UA:t saman IP:n takana → todennäköisesti ihmisiä NAT:ssa
    if len(uas) >= 2:
        return True

    # Yksi UA mutta residential + eri polut ilman login-stuffingia
    has_logins = any(s.logins for s in sessions)
    return not has_logins and len({s.paths for s in sessions}) >= 2
