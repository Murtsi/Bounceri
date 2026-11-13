"""C-4: kampanjatunnistus A:n sample-ingestia ja C:n stuffing-fixturea vasten."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from bouncer.ingest.sample import load_sample_data
from bouncer.network import evaluate_campaigns, find_campaigns, ip_intel
from bouncer.network.types import Campaign

FIXTURE = Path(__file__).with_name("fixtures") / "stuffing_access.jsonl"
A_SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "access.sample.jsonl"


def test_a_sample_loads_and_find_campaigns_runs() -> None:
    sessions, labels = load_sample_data(A_SAMPLE)
    assert sessions
    assert any(lab.campaign_id for lab in labels)

    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("offline"),
    ):
        for session in sessions:
            intel = ip_intel(session.ip)
            assert intel.verified_bot is None or isinstance(intel.verified_bot, bool)
            _ = intel.as_contract()

    camps = find_campaigns(sessions)
    # Scanner paths may or may not cluster (only 1 session in sample) — must not crash
    assert isinstance(camps, list)
    for camp in camps:
        assert isinstance(camp, Campaign)
        assert all(isinstance(sid, str) for sid in camp.session_ids)


def test_stuffing_fixture_detects_campaign_against_truth() -> None:
    sessions, labels = load_sample_data(FIXTURE)
    assert len(sessions) >= 4

    camps = find_campaigns(sessions, include_behavior=False)
    stuffing = [c for c in camps if c.kind == "credential_stuffing"]
    assert stuffing, f"expected stuffing campaign, got {camps!r}"
    assert all(isinstance(sid, str) for sid in stuffing[0].session_ids)

    truth = [(lab.session_id, lab.campaign_id) for lab in labels]
    # A:n ingest still stores session_id as int in SessionLabel today — normalize
    truth = [(str(sid), cid) for sid, cid in truth]
    metrics = evaluate_campaigns(stuffing, truth)
    assert metrics["stub"] is False
    assert metrics["coverage"] is not None
    assert metrics["coverage"] >= 0.5
    assert metrics["purity"] is not None
    assert metrics["purity"] >= 0.5


def test_campaign_matches_s2_contract_shape() -> None:
    assert find_campaigns([]) == []
    from bouncer.network.types import make_campaign

    built = make_campaign(
        id="x",
        kind="credential_stuffing",
        session_ids=["1", "2"],
        reasons=["a"],
    )
    assert built.session_ids == ("1", "2")
    assert built.reasons == ("a",)


def test_network_pass_smoke_on_stuffing_fixture() -> None:
    from bouncer.network import network_pass

    sessions, _ = load_sample_data(FIXTURE)
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("offline"),
    ):
        result = network_pass(sessions, include_behavior=False)
    assert result["campaigns"]
    assert result["intel_by_session"]
    assert result["graph"]["n_campaigns"] >= 1
