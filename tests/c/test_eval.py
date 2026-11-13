"""C-6: campaign metrics purity/coverage."""

from __future__ import annotations

from bouncer.network.eval import evaluate_campaigns
from bouncer.network.types import make_campaign


def test_evaluate_perfect_match() -> None:
    predicted = [
        make_campaign(
            id="p1",
            kind="credential_stuffing",
            session_ids=["1", "2", "3"],
            reasons=["x"],
        ),
    ]
    truth = [("1", "truth-a"), ("2", "truth-a"), ("3", "truth-a"), ("4", None)]
    metrics = evaluate_campaigns(predicted, truth)
    assert metrics["stub"] is False
    assert metrics["purity"] == 1.0
    assert metrics["coverage"] == 1.0
    assert metrics["n_truth"] == 1


def test_evaluate_partial_coverage() -> None:
    predicted = [
        make_campaign(
            id="p1",
            kind="behavior_cluster",
            session_ids=["1", "2"],
            reasons=["x"],
        ),
    ]
    truth = [("1", "t1"), ("2", "t1"), ("3", "t1"), ("4", "t1")]
    metrics = evaluate_campaigns(predicted, truth)
    assert metrics["coverage"] == 0.5
    assert metrics["purity"] == 1.0
