"""A:n workerin kutsurajapinta — yksi passi C:n yli (ei DB:tä)."""

from __future__ import annotations

from typing import Any

from bouncer.network.campaigns import find_campaigns
from bouncer.network.graph import campaign_graph
from bouncer.network.intel import ip_intel
from bouncer.network.session_view import as_session_view
from bouncer.network.types import Campaign, IpIntel


def intel_for_sessions(sessions: list[Any]) -> dict[str, IpIntel]:
    """IP → IpIntel (yksi DNS/ASN-lookup per uniikki IP)."""
    cache: dict[str, IpIntel] = {}
    out: dict[str, IpIntel] = {}
    for session in sessions:
        view = as_session_view(session)
        if view.ip not in cache:
            cache[view.ip] = ip_intel(view.ip)
        out[view.id] = cache[view.ip]
    return out


def network_pass(
    sessions: list[Any],
    *,
    include_behavior: bool = True,
) -> dict[str, Any]:
    """S4 + S5 + graafi yhdellä kutsulla A:n workerille.

    Palauttaa:
      - ``intel_by_session``: session_id → IpIntel
      - ``intel_by_ip``: ip → IpIntel (contract-muoto `as_contract()` saatavilla)
      - ``campaigns``: list[Campaign]
      - ``graph``: campaign_graph(...)
    """
    intel_by_session = intel_for_sessions(sessions)
    intel_by_ip: dict[str, IpIntel] = {}
    for session in sessions:
        view = as_session_view(session)
        if view.ip not in intel_by_ip:
            intel_by_ip[view.ip] = intel_by_session[view.id]

    campaigns: list[Campaign] = find_campaigns(
        sessions,
        include_behavior=include_behavior,
    )
    return {
        "intel_by_session": intel_by_session,
        "intel_by_ip": intel_by_ip,
        "campaigns": campaigns,
        "graph": campaign_graph(campaigns, sessions),
    }
