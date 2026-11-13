"""`metrics.json` — sopimus S8 (B → A).

Skeema: `Challenges/Hostinger-Decode-the-Noise/TEAM.md`. Tiedosto `models/metrics.json`.
Lukuja EI keksitä: kunnes oikea arviointi (B-7) on olemassa, kaikki luvut ovat `null`
ja `"stub": true`. Lukijan (A:n API/dashboard) pitää näyttää stub selvästi stubina.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bouncer.session.score import MODEL_VERSION

METRICS_PATH = Path(__file__).resolve().parents[3] / "models" / "metrics.json"

REQUIRED_KEYS = frozenset(
    {
        "model_version",
        "test_window",
        "threshold",
        "human_fpr",
        "per_class",
        "uncertain_share",
        "confusion",
        "split",
        "ablation",
        "known_weaknesses",
        "stub",
    }
)


def stub_metrics() -> dict[str, Any]:
    """S8-skeeman mukainen stub. Ei yhtään mitattua lukua."""
    return {
        "model_version": MODEL_VERSION,
        "test_window": {"from": None, "to": None},
        "threshold": {"bot": None, "human": None},
        "human_fpr": None,
        "per_class": {},
        "uncertain_share": None,
        "confusion": [],
        "split": {"simulated": {}, "real": {}, "hidden_attack": {}},
        "ablation": {"without_network_signals": {"human_fpr": None, "recall": None}},
        "known_weaknesses": [],
        "stub": True,
    }


def validate(metrics: dict[str, Any]) -> list[str]:
    """Palauttaa listan skeemavirheistä (tyhjä = ok)."""
    errors = [f"puuttuu: {k}" for k in sorted(REQUIRED_KEYS - metrics.keys())]
    if not isinstance(metrics.get("stub"), bool):
        errors.append("stub ei ole bool")
    split = metrics.get("split", {})
    for part in ("simulated", "real", "hidden_attack"):
        if part not in split:
            errors.append(f"split.{part} puuttuu")
    return errors


def write_stub(path: Path = METRICS_PATH) -> None:
    path.write_text(json.dumps(stub_metrics(), indent=2, ensure_ascii=False) + "\n", "utf-8")


if __name__ == "__main__":
    write_stub()
