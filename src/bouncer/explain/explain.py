"""S7 — `explain(verdict, session, campaign) -> str`.

Stub (C-1): yhdistää B:n `reasons`-kentän tekstiksi.
Oikea toteutus (C-7): Hostinger AI Router, vain syiden pohjalta + varateksti.
"""

from __future__ import annotations

from typing import Any


def _reasons_from(verdict: Any) -> list[str]:
    reasons = getattr(verdict, "reasons", None)
    if reasons is None and isinstance(verdict, dict):
        reasons = verdict.get("reasons")
    if not reasons:
        return []
    return [str(r) for r in reasons]


def explain(
    verdict: Any,
    session: Any = None,
    campaign: Any = None,
) -> str:
    """Selitä päätös. Stub: ei LLM-kutsua, vain reasons → teksti."""
    _ = session
    reasons = _reasons_from(verdict)
    parts: list[str] = []

    if reasons:
        parts.append("Reasons: " + "; ".join(reasons) + ".")
    else:
        parts.append("No scoring reasons available yet.")

    if campaign is not None:
        camp_id = getattr(campaign, "id", None)
        if camp_id is None and isinstance(campaign, dict):
            camp_id = campaign.get("id")
        camp_reasons = getattr(campaign, "reasons", None)
        if camp_reasons is None and isinstance(campaign, dict):
            camp_reasons = campaign.get("reasons")
        if camp_id:
            parts.append(f"Campaign {camp_id}.")
        if camp_reasons:
            parts.append("Campaign signals: " + "; ".join(str(r) for r in camp_reasons) + ".")

    return " ".join(parts)
