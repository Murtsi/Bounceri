"""Synthetic campaign metrics from C-4 stuffing fixture."""

from __future__ import annotations

from bouncer.network.lock_fixture import measure_fixture


def test_measure_fixture_is_synthetic_and_non_stub() -> None:
    metrics = measure_fixture()
    assert metrics["stub"] is False
    assert metrics["synthetic"] is True
    assert metrics["purity"] is not None and metrics["purity"] >= 0.5
    assert metrics["coverage"] is not None and metrics["coverage"] >= 0.5
    assert "Synthetic" in metrics["note"]
