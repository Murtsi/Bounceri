"""S5 — `find_campaigns(sessions) -> list[Campaign]`.

C-1 stub → C-3 stuffing → C-5 behavior clusters.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bouncer.network.cluster import ClusterConfig, find_behavior_campaigns
from bouncer.network.nat import looks_like_shared_nat
from bouncer.network.session_view import SessionView, iter_session_views
from bouncer.network.stuffing import StuffingConfig, detect_credential_stuffing
from bouncer.network.types import Campaign


def _by_id(views: list[SessionView]) -> dict[str, SessionView]:
    return {v.id: v for v in views}


def _filter_shared_nat(
    campaigns: list[Campaign],
    views: list[SessionView],
) -> list[Campaign]:
    """C-9: pudota behavior-kampanjat, jotka näyttävät venue/NAT -ihmisten klusterilta."""
    index = _by_id(views)
    kept: list[Campaign] = []
    for camp in campaigns:
        if camp.kind != "behavior_cluster":
            kept.append(camp)
            continue
        members = [index[sid] for sid in camp.session_ids if sid in index]
        if looks_like_shared_nat(members):
            continue
        kept.append(camp)
    return kept


def find_campaigns(
    sessions: Iterable[Any],
    *,
    stuffing_cfg: StuffingConfig | None = None,
    cluster_cfg: ClusterConfig | None = None,
    include_behavior: bool = True,
) -> list[Campaign]:
    """Etsi kampanjoita sessiojoukosta (puhdas funktio, ei DB:tä)."""
    views = iter_session_views(list(sessions))
    if not views:
        return []

    found = detect_credential_stuffing(views, stuffing_cfg)
    if include_behavior:
        found.extend(find_behavior_campaigns(views, cluster_cfg))
        found = _filter_shared_nat(found, views)

    # Stable order: kind then id
    found.sort(key=lambda c: (c.kind, c.id))
    return found
