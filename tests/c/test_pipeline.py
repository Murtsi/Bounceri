"""C-8 prep: network_pass maps for A worker + B evaluate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from bouncer.contracts import Campaign, IpIntel
from bouncer.ingest.sample import load_sample_data
from bouncer.network import (
    campaign_to_api,
    campaigns_by_session,
    network_pass,
)
from bouncer.network.types import make_campaign

FIXTURE = Path(__file__).with_name("fixtures") / "stuffing_access.jsonl"


def test_campaigns_by_session_first_wins() -> None:
    a = make_campaign(
        id="stuffing:admin",
        kind="credential_stuffing",
        session_ids=["1", "2"],
        reasons=["a"],
    )
    b = make_campaign(
        id="behavior:x",
        kind="behavior_cluster",
        session_ids=["2", "3"],
        reasons=["b"],
    )
    mapping = campaigns_by_session([a, b])
    assert mapping["1"] is a
    assert mapping["2"] is a  # stuffing listed first
    assert mapping["3"] is b


def test_campaign_to_api_shape() -> None:
    camp = make_campaign(
        id="c1",
        kind="credential_stuffing",
        session_ids=["1", "2"],
        reasons=["same user"],
    )
    payload = campaign_to_api(camp)
    assert payload == {
        "id": "c1",
        "kind": "credential_stuffing",
        "session_ids": ["1", "2"],
        "reasons": ["same user"],
        "size": 2,
    }


def test_network_pass_b_ready_maps() -> None:
    sessions, _ = load_sample_data(FIXTURE)
    with patch(
        "bouncer.network.bots.socket.gethostbyaddr",
        side_effect=OSError("offline"),
    ):
        result = network_pass(sessions, include_behavior=False)

    assert result["campaigns"]
    assert result["campaign_by_session"]
    assert result["campaigns_api"]
    assert result["graph"]["n_campaigns"] >= 1

    for intel in result["intel_by_ip_contract"].values():
        assert isinstance(intel, IpIntel)
        assert not hasattr(intel, "threat_label")

    for camp in result["campaign_by_session"].values():
        assert isinstance(camp, Campaign)
        assert all(isinstance(sid, str) for sid in camp.session_ids)
