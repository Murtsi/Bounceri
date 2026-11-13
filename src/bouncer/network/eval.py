"""S9 — kampanjoiden arviointi → `campaign_metrics.json` (C-6).

Totuus: A:n `X-Sim-Run` / labelien kampanja-id.
Purity = osuus predicted-jäsenistä, jotka kuuluvat dominanttiin truth-kampanjaan.
Coverage = osuus truth-kampanjan sessioista, jotka löytyivät jostain predicted-kampanjasta.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from bouncer.network.types import Campaign

METRICS_PATH = Path(__file__).with_name("campaign_metrics.json")

STUB_METRICS: dict[str, Any] = {
    "stub": True,
    "purity": None,
    "coverage": None,
    "n_predicted": 0,
    "n_truth": 0,
    "known_weaknesses": [
        "Shared NAT / venue Wi-Fi: many humans look like one actor (C-9).",
    ],
}


def load_campaign_metrics(path: Path | None = None) -> dict[str, Any]:
    target = path or METRICS_PATH
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_metrics(metrics: dict[str, Any], path: Path | None = None) -> Path:
    target = path or METRICS_PATH
    target.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def write_stub_metrics(path: Path | None = None) -> Path:
    return write_metrics(STUB_METRICS, path)


def _truth_map(
    session_truth: Iterable[tuple[int, str | None]],
) -> dict[str, set[int]]:
    """session_id → truth campaign id (None = ei kampanjaa) → invert."""
    out: dict[str, set[int]] = defaultdict(set)
    for session_id, camp_id in session_truth:
        if camp_id:
            out[str(camp_id)].add(int(session_id))
    return dict(out)


def evaluate_campaigns(
    predicted: list[Campaign],
    session_truth: Iterable[tuple[int, str | None]],
    *,
    known_weaknesses: list[str] | None = None,
) -> dict[str, Any]:
    """Laske purity + coverage. `session_truth`: (session_id, truth_campaign_id|None)."""
    truth_sessions = list(session_truth)
    truth_groups = _truth_map(truth_sessions)
    session_to_truth = {int(sid): cid for sid, cid in truth_sessions if cid}

    purities: list[float] = []
    for camp in predicted:
        labels = [session_to_truth.get(sid) for sid in camp.session_ids]
        labeled = [lab for lab in labels if lab]
        if not camp.session_ids:
            continue
        if not labeled:
            purities.append(0.0)
            continue
        dominant, count = Counter(labeled).most_common(1)[0]
        _ = dominant
        purities.append(count / len(camp.session_ids))

    covered: set[int] = set()
    all_truth_sessions: set[int] = set()
    for members in truth_groups.values():
        all_truth_sessions |= members
    predicted_members = {sid for camp in predicted for sid in camp.session_ids}
    covered = all_truth_sessions & predicted_members

    purity = sum(purities) / len(purities) if purities else None
    coverage = (
        len(covered) / len(all_truth_sessions) if all_truth_sessions else None
    )

    weaknesses = known_weaknesses or list(STUB_METRICS["known_weaknesses"])
    return {
        "stub": False,
        "purity": purity,
        "coverage": coverage,
        "n_predicted": len(predicted),
        "n_truth": len(truth_groups),
        "per_campaign": [
            {
                "id": c.id,
                "kind": c.kind,
                "size": len(c.session_ids),
            }
            for c in predicted
        ],
        "known_weaknesses": weaknesses,
    }
