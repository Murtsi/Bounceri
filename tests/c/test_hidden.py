"""C-10 prep: hidden-attack campaign evaluation (no retune)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bouncer.ingest.sample import load_sample_data
from bouncer.network.hidden import (
    add_hidden_to_metrics,
    evaluate_hidden_campaigns,
    summary_lines,
)

FIXTURE = Path(__file__).with_name("fixtures") / "stuffing_access.jsonl"


def test_evaluate_hidden_on_stuffing_fixture() -> None:
    sessions, labels = load_sample_data(FIXTURE)
    result = evaluate_hidden_campaigns(sessions, labels, ["stuff-001"])
    assert result["retrained"] is False
    assert result["found_campaign"] is True
    assert result["n_predicted"] >= 1
    assert result["purity"] is not None and result["purity"] >= 0.5
    assert result["coverage"] is not None and result["coverage"] >= 0.5
    assert "found_campaign: True" in "\n".join(summary_lines(result))


def test_evaluate_hidden_missing_run_raises() -> None:
    sessions, labels = load_sample_data(FIXTURE)
    with pytest.raises(ValueError, match="ei labeleita"):
        evaluate_hidden_campaigns(sessions, labels, ["no-such-run"])


def test_add_hidden_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "campaign_metrics.json"
    path.write_text(
        json.dumps(
            {
                "stub": True,
                "purity": None,
                "coverage": None,
                "n_predicted": 0,
                "n_truth": 0,
                "known_weaknesses": [],
            }
        ),
        encoding="utf-8",
    )
    hidden = {
        "run_ids": ["x"],
        "found_campaign": False,
        "n_predicted": 0,
        "purity": None,
        "coverage": None,
    }
    add_hidden_to_metrics(hidden, path)
    with pytest.raises(ValueError, match="jo täytetty"):
        add_hidden_to_metrics(hidden, path)
