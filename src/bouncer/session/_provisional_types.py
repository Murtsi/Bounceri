"""VÄLIAIKAISET tyypit kaistalle B — EIVÄT ole sopimus S2.

`src/bouncer/contracts.py` on kaistan A (Murtsi) omistama eikä ole vielä olemassa.
Nämä dataclassit ovat B:n *ehdotus* sen kentiksi, jotta B voi kirjoittaa ja testata
puhtaita funktioita jo nyt. Kun `contracts.py` on `main`-haarassa:

1. korvaa importit `from bouncer.contracts import ...`
2. poista tämä tiedosto
3. korjaa piirrefunktiot, jos kentät poikkeavat

Älä tuo näitä tyyppejä kaistan B ulkopuolelle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Label = Literal["human", "good_bot", "bad_bot", "uncertain"]
AsnType = Literal["datacenter", "residential", "mobile", "unknown"]


@dataclass(frozen=True, slots=True)
class Request:
    """Yksi Caddyn JSON-lokirivi normalisoituna (S1)."""

    ts: datetime  # aikavyöhykkeellinen (UTC)
    ip: str
    method: str
    path: str  # ilman query-osaa
    status: int
    user_agent: str = ""
    query: str = ""
    bytes: int = 0
    # Pyynnön otsakkeet, avaimet pienillä kirjaimilla; yksi arvo per otsake.
    headers: dict[str, str] = field(default_factory=dict)
    # Vastauksen Content-Type ilman parametreja, esim. "text/html". None = ei tiedossa.
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class Session:
    """Pyynnöt avaimella (IP, User-Agent), katkeaa 5 min hiljaisuuteen (ARCHITECTURE.md)."""

    id: str
    ip: str
    user_agent: str
    started_at: datetime
    ended_at: datetime
    requests: tuple[Request, ...]


@dataclass(frozen=True, slots=True)
class IpIntel:
    """C:n `ip_intel(ip)` (S4)."""

    # True = DNS-varmistettu hakukonebotti, False = tarkistettu eikä ole,
    # None = ei tarkistettu (esim. C:n stub tai UA ei väitä olevansa crawler).
    verified_bot: bool | None = None
    asn: int | None = None
    asn_type: AsnType = "unknown"
    country: str | None = None


@dataclass(frozen=True, slots=True)
class Campaign:
    """C:n `find_campaigns()` (S5)."""

    id: str
    kind: str
    session_ids: tuple[str, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Verdict:
    """B:n `score()` (S6)."""

    label: Label
    score: float  # 0 = varmasti ihminen, 1 = varmasti botti
    reasons: tuple[str, ...]  # enintään 3, tärkein ensin
    model_version: str
