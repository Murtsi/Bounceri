"""Shared data contracts for the Bouncer pipeline (S2).

Request headers are lowercase and single-valued.  ``Session.id`` is a stable
string at the Python boundary; database loaders stringify generated IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Label = Literal["human", "good_bot", "bad_bot", "uncertain"]
AsnType = Literal["datacenter", "residential", "mobile", "unknown"]


@dataclass(frozen=True, slots=True)
class Request:
    """One normalized request from the Caddy JSON access log (S1)."""

    ts: datetime
    ip: str
    method: str
    path: str
    status: int
    user_agent: str = ""
    query: str = ""
    bytes: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str | None = None
    # Kirjautumisyrityksen käyttäjätunnus (vain POST /login), demosivun
    # `X-Login-User`-vastausotsakkeesta. Salasanaa ei koskaan (päätös 047).
    username: str | None = None


@dataclass(frozen=True, slots=True)
class Session:
    """Requests grouped by (IP, User-Agent), split after five idle minutes."""

    id: str
    ip: str
    user_agent: str
    started_at: datetime
    ended_at: datetime
    requests: tuple[Request, ...]


@dataclass(frozen=True, slots=True)
class IpIntel:
    """C's S4 result: None means not checked or the DNS check was inconclusive."""

    verified_bot: bool | None = None
    asn: int | None = None
    asn_type: AsnType = "unknown"
    country: str | None = None


@dataclass(frozen=True, slots=True)
class Campaign:
    """C's S5 result. ``session_ids`` are strings (S2 / päätös 039)."""

    id: str
    kind: str
    session_ids: tuple[str, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Verdict:
    """B's S6 result."""

    label: Label
    score: float
    reasons: tuple[str, ...]
    model_version: str


@dataclass(frozen=True, slots=True)
class SessionLabel:
    """Trusted simulator truth from ``X-Sim-Run`` (S3/S10)."""

    session_id: str
    run_id: str
    sim_class: str
    campaign_id: str | None = None
