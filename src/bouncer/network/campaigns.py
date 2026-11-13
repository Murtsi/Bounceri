"""S5 — `find_campaigns(sessions) -> list[Campaign]`.

C-1 stub → C-3 stuffing → C-5 behavior clusters.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bouncer.network.cluster import ClusterConfig, find_behavior_campaigns
from bouncer.network.session_view import iter_session_views
from bouncer.network.stuffing import StuffingConfig, detect_credential_stuffing
from bouncer.network.types import Campaign


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

    # Stable order: kind then id
    found.sort(key=lambda c: (c.kind, c.id))
    return found
