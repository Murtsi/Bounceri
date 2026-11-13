"""S5 — `find_campaigns(sessions) -> list[Campaign]`.

Stub (C-1): palauttaa tyhjän listan.
Oikea toteutus: C-3/C-4 tunnusten kokeilu, C-5 MinHash-kampanjat.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bouncer.network.types import Campaign


def find_campaigns(sessions: Iterable[Any]) -> list[Campaign]:
    """Etsi kampanjoita sessiojoukosta. Stub: ei klusterointia."""
    _ = sessions
    return []
