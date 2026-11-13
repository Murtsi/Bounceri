"""Kampanjagraafin visualisointidata dashboardille (A piirtää).

Palauttaa nodes/edges -rakenteen, jonka React/Recharts tai force-graph
voi renderöidä. Puhdas funktio — ei DB:tä.
"""

from __future__ import annotations

from typing import Any

from bouncer.network.session_view import SessionView, iter_session_views
from bouncer.network.types import Campaign


def campaign_graph(
    campaigns: list[Campaign],
    sessions: list[Any] | None = None,
) -> dict[str, Any]:
    """Rakenna graafi: session/IP -solmut + campaign-klusterit."""
    views = iter_session_views(sessions or [])
    by_id: dict[str, SessionView] = {v.id: v for v in views}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_sessions: set[str] = set()
    seen_ips: set[str] = set()

    for camp in campaigns:
        camp_node = f"campaign:{camp.id}"
        nodes.append(
            {
                "id": camp_node,
                "kind": "campaign",
                "label": camp.id,
                "campaign_kind": camp.kind,
                "reasons": list(camp.reasons),
                "size": len(camp.session_ids),
            }
        )
        for sid in camp.session_ids:
            sess_node = f"session:{sid}"
            if sid not in seen_sessions:
                view = by_id.get(sid)
                nodes.append(
                    {
                        "id": sess_node,
                        "kind": "session",
                        "label": str(sid),
                        "ip": view.ip if view else None,
                        "ua": (view.ua[:48] if view and view.ua else None),
                    }
                )
                seen_sessions.add(sid)
                if view and view.ip and view.ip not in seen_ips:
                    ip_node = f"ip:{view.ip}"
                    nodes.append(
                        {
                            "id": ip_node,
                            "kind": "ip",
                            "label": view.ip,
                        }
                    )
                    seen_ips.add(view.ip)
                    edges.append(
                        {
                            "source": sess_node,
                            "target": ip_node,
                            "kind": "from_ip",
                        }
                    )
                elif view and view.ip:
                    edges.append(
                        {
                            "source": sess_node,
                            "target": f"ip:{view.ip}",
                            "kind": "from_ip",
                        }
                    )
            edges.append(
                {
                    "source": sess_node,
                    "target": camp_node,
                    "kind": "in_campaign",
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "n_campaigns": len(campaigns),
        "n_sessions": len(seen_sessions),
        "n_ips": len(seen_ips),
    }
