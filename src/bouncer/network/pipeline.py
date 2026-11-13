"""A:n workerin + B:n arvioinnin kutsurajapinta — C:n yli (ei DB:tä)."""

from __future__ import annotations

from typing import Any

from bouncer.network.campaigns import find_campaigns
from bouncer.network.graph import campaign_graph
from bouncer.network.intel import ip_intel
from bouncer.network.session_view import as_session_view
from bouncer.network.types import Campaign, IpIntel


def intel_for_sessions(sessions: list[Any]) -> dict[str, IpIntel]:
    """session_id → IpIntel (yksi DNS/ASN-lookup per uniikki IP)."""
    cache: dict[str, IpIntel] = {}
    out: dict[str, IpIntel] = {}
    for session in sessions:
        view = as_session_view(session)
        if view.ip not in cache:
            cache[view.ip] = ip_intel(view.ip)
        out[view.id] = cache[view.ip]
    return out


def intel_by_ip(sessions: list[Any]) -> dict[str, IpIntel]:
    """ip → C:n IpIntel (sis. threat_label)."""
    by_session = intel_for_sessions(sessions)
    out: dict[str, IpIntel] = {}
    for session in sessions:
        view = as_session_view(session)
        if view.ip not in out and view.id in by_session:
            out[view.ip] = by_session[view.id]
    return out


def contract_intel_by_ip(sessions: list[Any]) -> dict[str, Any]:
    """ip → S4-contract IpIntel (B:n `score` / evaluate)."""
    return {ip: intel.as_contract() for ip, intel in intel_by_ip(sessions).items()}


def campaigns_by_session(campaigns: list[Campaign]) -> dict[str, Campaign]:
    """session_id → Campaign. Ensimmäinen osuma voittaa (stuffing ennen behavioria, jos sortattu)."""
    out: dict[str, Campaign] = {}
    for camp in campaigns:
        for sid in camp.session_ids:
            out.setdefault(str(sid), camp)
    return out


def campaign_to_api(camp: Campaign) -> dict[str, Any]:
    """JSON-muoto A:n `/campaigns` -endpointille (C-8)."""
    return {
        "id": camp.id,
        "kind": camp.kind,
        "session_ids": list(camp.session_ids),
        "reasons": list(camp.reasons),
        "size": len(camp.session_ids),
    }


def network_pass(
    sessions: list[Any],
    *,
    include_behavior: bool = True,
) -> dict[str, Any]:
    """S4 + S5 + graafi yhdellä kutsulla A:n workerille / B:n arvioinnille.

    Palauttaa:
      - ``intel_by_session``: session_id → C IpIntel
      - ``intel_by_ip``: ip → C IpIntel
      - ``intel_by_ip_contract``: ip → S4 IpIntel (B)
      - ``campaigns``: list[Campaign]
      - ``campaign_by_session``: session_id → Campaign (B)
      - ``campaigns_api``: list[dict] dashboardille
      - ``graph``: campaign_graph(...)
    """
    c_intel_by_ip = intel_by_ip(sessions)
    intel_by_session: dict[str, IpIntel] = {}
    for session in sessions:
        view = as_session_view(session)
        if view.ip in c_intel_by_ip:
            intel_by_session[view.id] = c_intel_by_ip[view.ip]

    campaigns: list[Campaign] = find_campaigns(
        sessions,
        include_behavior=include_behavior,
    )
    by_session = campaigns_by_session(campaigns)
    return {
        "intel_by_session": intel_by_session,
        "intel_by_ip": c_intel_by_ip,
        "intel_by_ip_contract": {ip: i.as_contract() for ip, i in c_intel_by_ip.items()},
        "campaigns": campaigns,
        "campaign_by_session": by_session,
        "campaigns_api": [campaign_to_api(c) for c in campaigns],
        "graph": campaign_graph(campaigns, sessions),
    }
