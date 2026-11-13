"""C-kaistan tyypit (peilaavat S2 / `contracts.py` kun A sen julkaisee).

Kun `bouncer.contracts` on olemassa, nämä voidaan korvata re-exporteilla.
Kentät on lukittu TEAM.md-sopimuksiin S4 ja S5 — muutos = BREAKING.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class IpIntel:
    """S4: `ip_intel(ip) -> IpIntel` (päätökset 020 + 027).

    verified_bot:
      True  — DNS-varmistettu hakukonebotti
      False — tarkistettu, ei ole (tai spoofattu PTR)
      None  — ei tarkistettu / DNS-haku epäonnistui
    """

    verified_bot: bool | None = None
    asn: int | None = None
    asn_type: str = "unknown"  # unknown | datacenter | residential | mobile
    country: str | None = None


@dataclass(frozen=True, slots=True)
class Campaign:
    """S5: `find_campaigns(sessions) -> list[Campaign]`."""

    id: str
    kind: str
    session_ids: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
