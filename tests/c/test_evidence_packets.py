"""Offline bounds for retained network, rule and session-relationship evidence."""

from __future__ import annotations

import copy
import json

import pytest

from bouncer.review.providers import decision_chat_request, decision_request, reviewer_request
from bouncer.review.validation import (
    validate_decision_result,
    validate_packet,
    validate_recommendation,
)
from tests.c.test_review import packet, recommendation


def retained_packet():
    value = packet()
    value["synthetic"] = False
    first = value["evidence"][0]
    first["data"].update(
        distinct_client_count=1,
        verified_bot=True,
        crawler_verification_origin="dns",
        network_provenance={
            "checked_at": "2026-11-14T12:00:00+00:00",
            "resolver_outcome": "verified",
            "verified_bot": True,
            "asn": 15169,
            "asn_type": "datacenter",
            "country": "US",
            "asn_origin": "curated-prefix",
            "crawler": "googlebot",
        },
        rule_observations={
            "version": "bouncer-rule-observations-v1",
            "trap_hits": 1,
            "trap_config_version": "a" * 64,
            "rule_ids": ["trap"],
            "features": {"duration_s": 10.0, "ua_is_tool": True, "vuln_path_hits": 2},
        },
    )
    second = copy.deepcopy(first)
    second["id"] = "ev-2"
    second["data"]["session_ref"] = "session-2"
    value["evidence"].extend(
        [
            second,
            {
                "id": "campaign-1",
                "kind": "campaign_summary",
                "data": {
                    "campaign_ref": "b" * 16,
                    "kind": "distributed_login_spray",
                    "member_refs": ["ev-1", "ev-2"],
                    "n_sessions": 2,
                    "distinct_client_count": 2,
                    "failed_logins": 8,
                    "shared_target_count": 2,
                    "window_seconds": 10.0,
                    "relationship_provenance": "scoped-requests-v1",
                },
            },
        ]
    )
    return value


def test_valid_typed_evidence_is_preserved_without_truncation():
    value = retained_packet()
    assert validate_packet(value)["evidence"] == value["evidence"]
    assert validate_packet(packet())["evidence"] == packet()["evidence"]


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("network_provenance", "ip", "192.0.2.1"),
        ("network_provenance", "resolver_outcome", {"address": "192.0.2.1"}),
        ("network_provenance", "asn", True),
        ("network_provenance", "asn", 4294967296),
        ("network_provenance", "country", "us"),
        ("network_provenance", "checked_at", "2026-11-14T14:00:00+02:00"),
        ("network_provenance", "checked_at", None),
        ("network_provenance", "crawler", None),
        ("network_provenance", "verified_bot", False),
        ("rule_observations", "path", "/secret"),
        ("rule_observations", "trap_config_version", "unbounded text"),
        ("rule_observations", "trap_hits", True),
        ("rule_observations", "trap_hits", 13),
        ("rule_observations", "rule_ids", ["unknown"]),
        ("rule_observations", "features", {"raw_ua": "secret"}),
        ("rule_observations", "features", {"duration_s": float("inf")}),
        ("rule_observations", "features", {"html_share": 1.1}),
        ("rule_observations", "features", {"ua_is_tool": 1}),
    ],
)
def test_nested_evidence_rejects_unknown_private_or_invalid_values(section, key, value):
    data = retained_packet()
    data["evidence"][0]["data"][section][key] = value
    with pytest.raises(ValueError, match="invalid_evidence_packet"):
        validate_packet(data)


@pytest.mark.parametrize(
    "change",
    [
        {"member_refs": ["ev-1", "missing"]},
        {"member_refs": ["ev-1", "campaign-1"]},
        {"member_refs": ["ev-1", "ev-1"]},
        {"member_refs": ["ev-1"]},
        {"n_sessions": 3},
        {"failed_logins": 7},
        {"distinct_client_count": 3},
        {"shared_target_count": 3},
        {"window_seconds": float("nan")},
        {"raw_username": "private"},
        {"campaign_ref": "unbounded"},
    ],
)
def test_campaign_relationships_require_complete_unique_coherent_session_members(change):
    value = retained_packet()
    value["evidence"][-1]["data"].update(change)
    with pytest.raises(ValueError, match="invalid_evidence_packet"):
        validate_packet(value)


def test_aggregate_session_cannot_be_campaign_relationship_member():
    value = retained_packet()
    value["evidence"][0]["data"]["n_sessions"] = 2
    with pytest.raises(ValueError, match="invalid_evidence_packet"):
        validate_packet(value)


def test_forged_flat_verification_and_broken_count_maps_remain_rejected():
    for key, value in [
        ("verified_bot", False),
        ("crawler_verification_origin", "synthetic"),
        ("status_counts", {"200": 1}),
    ]:
        data = retained_packet()
        data["evidence"][0]["data"][key] = value
        with pytest.raises(ValueError, match="invalid_evidence_packet"):
            validate_packet(data)


def test_model_view_omits_local_rule_predictions_but_retains_observations():
    value = validate_packet(retained_packet())
    native = decision_request("fixture", value)["state"]["untrusted_evidence"]
    chat = json.loads(decision_chat_request("fixture", value)["messages"][1]["content"])
    for view in [native, chat["original_evidence_packet"]]:
        text = json.dumps(view)
        assert "local_label" not in text and "local_score" not in text
        assert "rule_ids" not in text
        assert view["evidence"][0]["data"]["rule_observations"]["trap_hits"] == 1
        assert "ua_is_tool" in text
    assert value["evidence"][0]["data"]["rule_observations"]["rule_ids"] == ["trap"]


def test_relationship_prompts_preserve_unknown_coordination_and_candidate_status():
    value = validate_packet(retained_packet())
    decision = decision_chat_request("fixture", value)["messages"][0]["content"]
    reviewer = reviewer_request("fixture", value, {})["messages"][0]["content"]
    for prompt in [decision, reviewer]:
        assert "relationship evidence is absent" not in prompt.lower()
        assert "No relationship evidence is present" not in prompt
        assert "candidate" in prompt and "unknown" in prompt
    from bouncer.review.providers import QUESTIONS

    answers = {"answers": {name: {"choice": "unknown"} for name in QUESTIONS}}
    for choice in ["yes", "no"]:
        answers["answers"]["coordination"]["choice"] = choice
        with pytest.raises(ValueError):
            validate_decision_result(answers, value)
    with pytest.raises(ValueError):
        validate_recommendation(recommendation() | {"coordination": "observed"}, value)


def test_retained_trap_count_is_original_attack_evidence_without_rule_prediction():
    value = retained_packet()
    for item in value["evidence"][:2]:
        item["data"]["path_category_counts"] = {"other": 12}
        item["data"]["rule_observations"]["rule_ids"] = []
    value = validate_packet(value)
    result = recommendation() | {"authentication_pattern": "repeated_failures"}
    assert validate_recommendation(result, value)["label"] == "bad_bot"


def test_checked_mismatch_is_false_without_requiring_successful_crawler_identity():
    value = retained_packet()
    data = value["evidence"][0]["data"]
    data["network_provenance"].update(
        resolver_outcome="mismatch",
        verified_bot=False,
        crawler=None,
    )
    data.update(verified_bot=False, crawler_verification_origin="unknown")
    assert validate_packet(value)["evidence"][0]["data"]["verified_bot"] is False


def test_two_ids_cannot_claim_a_relationship_for_the_same_session():
    value = retained_packet()
    value["evidence"][1]["data"]["session_ref"] = "session-1"
    with pytest.raises(ValueError, match="invalid_evidence_packet"):
        validate_packet(value)


def test_multi_client_aggregate_cannot_be_campaign_member():
    value = retained_packet()
    value["evidence"][0]["data"]["distinct_client_count"] = 2
    with pytest.raises(ValueError, match="invalid_evidence_packet"):
        validate_packet(value)


def test_shared_targets_need_two_members_rather_than_every_member():
    value = retained_packet()
    third = copy.deepcopy(value["evidence"][1])
    third["id"] = "ev-3"
    third["data"].update(session_ref="session-3", distinct_account_count=0)
    value["evidence"].insert(2, third)
    value["evidence"][-1]["data"].update(
        member_refs=["ev-1", "ev-2", "ev-3"],
        n_sessions=3,
        distinct_client_count=3,
        failed_logins=12,
    )
    assert validate_packet(value)["evidence"] == value["evidence"]


@pytest.mark.parametrize("outcome", ["unavailable", "timeout", "capacity", "invalid"])
def test_resolver_error_is_preserved_as_unknown_verification(outcome):
    value = retained_packet()
    data = value["evidence"][0]["data"]
    data["network_provenance"].update(resolver_outcome=outcome, verified_bot=None, checked_at=None)
    data.update(verified_bot=None, crawler_verification_origin="unknown")
    assert validate_packet(value)["evidence"][0]["data"]["verified_bot"] is None


def test_reviewer_can_cite_original_nested_trap_count_and_not_local_rule_ids():
    value = validate_packet(retained_packet())
    result = recommendation() | {
        "authentication_pattern": "repeated_failures",
        "observations": [
            {"evidence_id": "ev-1", "field": "rule_observations.trap_hits", "value": 1}
        ],
    }
    assert validate_recommendation(result, value)["observations"] == result["observations"]
    result["observations"][0]["field"] = "rule_observations.rule_ids"
    with pytest.raises(ValueError):
        validate_recommendation(result, value)


def test_retained_adapter_packet_survives_investigation_store_and_model_validation():
    from bouncer.investigations import InvestigationStore
    from bouncer.investigations.store import model_packet
    from tests.a.test_evidence_completeness import (
        campaign,
        ip_evidence,
        rule_observations,
        snapshot,
    )

    raw = campaign(snapshot(3))
    raw["ip_evidence"] = {"192.0.2.1": ip_evidence()}
    raw["rule_observations"] = {"private-session-0": rule_observations()}
    store = InvestigationStore("sqlite:///:memory:")
    case = store.create_from_legacy(raw, public_demo=True)
    value = validate_packet(model_packet(case))
    assert value["evidence"] == case["evidence"]
    assert value["evidence"][-1]["data"]["member_refs"] == ["e1", "e2", "e3"]
    assert value["evidence"][0]["data"]["network_provenance"]["verified_bot"] is True


def test_unavailable_header_measurements_cannot_be_reported_as_observed():
    value = retained_packet()
    data = value["evidence"][0]["data"]
    data["unavailable_fields"] = ["headers"]
    data["rule_observations"]["features"]["header_inconsistency_share"] = 1.0
    with pytest.raises(ValueError):
        validate_packet(value)


def test_missing_target_logging_requires_unknown_campaign_count():
    value = retained_packet()
    member = next(e["data"] for e in value["evidence"] if e["kind"] == "session_summary")
    member["unavailable_fields"] = ["username"]
    member.pop("distinct_account_count", None)
    relation = next(e["data"] for e in value["evidence"] if e["kind"] == "campaign_summary")
    relation["shared_target_count"] = None
    validate_packet(value)
    relation["shared_target_count"] = 0
    with pytest.raises(ValueError):
        validate_packet(value)
