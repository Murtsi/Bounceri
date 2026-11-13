"""S9 — kampanjoiden arviointi → `campaign_metrics.json`.

Stub (C-1): `stub: true`. Oikeat luvut C-6:ssa A:n kampanja-id:itä vasten.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    """Lue `campaign_metrics.json` (stub tai lukittu arviointi)."""
    target = path or METRICS_PATH
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_stub_metrics(path: Path | None = None) -> Path:
    """Kirjoita stub-metriikat levylle (idempotentti)."""
    target = path or METRICS_PATH
    target.write_text(
        json.dumps(STUB_METRICS, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target
