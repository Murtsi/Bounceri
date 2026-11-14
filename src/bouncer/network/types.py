"""C-kaistan tyypit — S2/S4/S5.

S2 hyväksytty A:n kanssa (päätös 039): `Session.id` ja `Campaign.session_ids`
ovat merkkijonoja. `Campaign` / perus-`IpIntel` tulevat `bouncer.contracts`:sta
kun saatavilla; `threat_label` on C:n lisäkenttä S4:ään.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from bouncer.contracts import Campaign as Campaign
    from bouncer.contracts import IpIntel as _ContractIpIntel
except ImportError:  # pragma: no cover - before A merges contracts

    @dataclass(frozen=True, slots=True)
    class Campaign:  # type: ignore[no-redef]
        id: str
        kind: str
        session_ids: tuple[str, ...] = ()
        reasons: tuple[str, ...] = ()

    @dataclass(frozen=True, slots=True)
    class _ContractIpIntel:  # type: ignore[no-redef]
        verified_bot: bool | None = None
        asn: int | None = None
        asn_type: str = "unknown"
        country: str | None = None


@dataclass(frozen=True, slots=True)
class IpIntel:
    """S4 + C:n threat-feed -laajennus (`threat_label`)."""

    verified_bot: bool | None = None
    asn: int | None = None
    asn_type: str = "unknown"
    country: str | None = None
    threat_label: str | None = None

    def as_contract(self) -> _ContractIpIntel:
        """Strippaa C-only -kentät A/B:n S4-muotoon."""
        return _ContractIpIntel(
            verified_bot=self.verified_bot,
            asn=self.asn,
            asn_type=self.asn_type,  # type: ignore[arg-type]
            country=self.country,
        )


def make_campaign(
    *,
    id: str,
    kind: str,
    session_ids: list[str] | tuple[str, ...],
    reasons: list[str] | tuple[str, ...] = (),
) -> Campaign:
    """Rakenna S5-Campaign tuplilla (S2)."""
    return Campaign(
        id=id,
        kind=kind,
        session_ids=tuple(str(s) for s in session_ids),
        reasons=tuple(str(r) for r in reasons),
    )
