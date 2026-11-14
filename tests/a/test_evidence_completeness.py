import copy
import json

import pytest

from bouncer.investigations.evidence import traffic_packet


def snapshot(count=1):
    return {
        "synthetic": True,
        "sessions": [
            {
                "id": f"private-session-{i}",
                "ip": f"192.0.2.{i + 1}",
                "user_agent": "PRIVATE-UA",
                "started_at": "2026-11-14T12:00:00Z",
                "ended_at": "2026-11-14T12:01:00Z",
                "requests": [
                    {
                        "ts": f"2026-11-14T12:00:0{i}Z",
                        "method": "POST",
                        "path": "/login",
                        "status": 401,
                        "username": "PRIVATE-ACCOUNT",
                        "headers": {"host": "PRIVATE-HOST", "authorization": "PRIVATE-HEADER"},
                    }
                ],
            }
            for i in range(count)
        ],
        "verdicts": {},
    }


def campaign(raw, ids=None):
    raw["campaigns"] = [
        {
            "id": "PRIVATE-CAMPAIGN",
            "kind": "credential_stuffing",
            "session_ids": ids or [s["id"] for s in raw["sessions"]],
            "reasons": ["PRIVATE-REASON claims malicious common operator"],
        }
    ]
    return raw


def summaries(packet, kind):
    return [e["data"] for e in packet["evidence"] if e["kind"] == kind]


def test_complete_campaign_retains_scoped_relationship_to_session_evidence():
    packet = traffic_packet(campaign(snapshot(3)))
    assert packet["complete"] is True
    (relation,) = summaries(packet, "campaign_summary")
    assert relation == {
        "campaign_ref": relation["campaign_ref"],
        "kind": "credential_stuffing",
        "member_refs": ["e1", "e2", "e3"],
        "n_sessions": 3,
        "distinct_client_count": 3,
        "failed_logins": 3,
        "shared_target_count": 1,
        "window_seconds": 2.0,
        "relationship_provenance": "scoped-requests-v1",
    }
    assert len(relation["campaign_ref"]) == 16


def test_single_session_aggregate_does_not_create_campaign_relationship():
    packet = traffic_packet(campaign(snapshot()))
    assert summaries(packet, "campaign_summary") == []


def test_missing_campaign_members_are_explicitly_incomplete():
    raw = campaign(snapshot(2), ["private-session-0", "private-session-1", "missing-session"])
    packet = traffic_packet(raw)
    assert packet["complete"] is False
    assert summaries(packet, "campaign_summary") == []
    assert any("campaign" in message.lower() for message in packet["missing_information"])


def test_shared_auth_target_counts_sessions_rather_than_duplicate_requests():
    raw = campaign(snapshot(2))
    raw["sessions"][1]["requests"][0]["username"] = "different-account"
    raw["sessions"][0]["requests"].append(copy.deepcopy(raw["sessions"][0]["requests"][0]))
    (relation,) = summaries(traffic_packet(raw), "campaign_summary")
    assert relation["shared_target_count"] == 0
    assert relation["failed_logins"] == 3


def test_observed_source_rotation_gap_marks_packet_incomplete():
    raw = snapshot()
    raw["ingest"] = {"rotation_gaps": 1}
    packet = traffic_packet(raw)
    assert packet["complete"] is False
    assert any("rotation" in message.lower() for message in packet["missing_information"])


@pytest.mark.parametrize("count", [0, 501])
def test_source_bounds_mark_missing_information(count):
    packet = traffic_packet(snapshot(count))
    assert packet["complete"] is False
    assert packet["missing_information"]


def test_relationship_evidence_has_no_private_source_strings():
    raw = campaign(snapshot(3))
    raw["labels"] = [{"sim_class": "PRIVATE-TRUTH"}]
    encoded = json.dumps(traffic_packet(raw))
    for private in (
        "192.0.2.",
        "private-session-",
        "PRIVATE-UA",
        "PRIVATE-ACCOUNT",
        "/login",
        "PRIVATE-HOST",
        "PRIVATE-HEADER",
        "PRIVATE-CAMPAIGN",
        "PRIVATE-REASON",
        "PRIVATE-TRUTH",
    ):
        assert private not in encoded


def ip_evidence(**overrides):
    return {
        "checked_at": "2026-11-14T12:00:00+00:00",
        "resolver_outcome": "verified",
        "verified_bot": True,
        "asn": 15169,
        "asn_type": "datacenter",
        "country": "US",
        "asn_origin": "curated-prefix",
        "crawler": "googlebot",
        **overrides,
    }


def test_dns_origin_requires_retained_successful_coherent_verification():
    raw = snapshot()
    raw["ip_evidence"] = {"192.0.2.1": ip_evidence()}
    (data,) = summaries(traffic_packet(raw), "session_summary")
    assert data["network_provenance"] == ip_evidence()
    assert data["verified_bot"] is True
    assert data["crawler_verification_origin"] == "forward_reverse_dns"


@pytest.mark.parametrize("outcome", ["unavailable", "timeout", "capacity", "invalid"])
def test_resolver_errors_cannot_become_failed_or_successful_bot_verification(outcome):
    raw = snapshot()
    raw["ip_evidence"] = {"192.0.2.1": ip_evidence(resolver_outcome=outcome, verified_bot=False)}
    (data,) = summaries(traffic_packet(raw), "session_summary")
    assert data["verified_bot"] is None
    assert data["network_provenance"]["verified_bot"] is None
    assert data["network_provenance"]["resolver_outcome"] == outcome
    assert data["crawler_verification_origin"] == "unknown"


@pytest.mark.parametrize(
    "change",
    [
        {"checked_at": "PRIVATE-TIMESTAMP"},
        {"checked_at": "2026-11-14T12:00:00"},
        {"crawler": "PRIVATE-HOST"},
        {"verified_bot": False},
    ],
)
def test_invalid_success_metadata_does_not_support_dns_origin(change):
    raw = snapshot()
    raw["ip_evidence"] = {"192.0.2.1": ip_evidence(**change)}
    (data,) = summaries(traffic_packet(raw), "session_summary")
    assert data["verified_bot"] is None
    assert data["crawler_verification_origin"] == "unknown"


def test_successful_mismatch_is_false_without_claiming_dns_verified_origin():
    raw = snapshot()
    raw["ip_evidence"] = {"192.0.2.1": ip_evidence(resolver_outcome="mismatch", verified_bot=False)}
    (data,) = summaries(traffic_packet(raw), "session_summary")
    assert data["verified_bot"] is False
    assert data["crawler_verification_origin"] == "unknown"


def test_legacy_verdict_cannot_supply_verification_provenance():
    raw = snapshot()
    raw["verdicts"] = {"private-session-0": {"label": "good_bot", "verified_bot": True}}
    packet = traffic_packet(raw)
    (data,) = summaries(packet, "session_summary")
    assert data["verified_bot"] is None
    assert "network_provenance" not in data
    assert any("verification provenance" in text for text in packet["missing_information"])


def rule_observations(**overrides):
    return {
        "version": "bouncer-rule-observations-v1",
        "trap_hits": 1,
        "trap_config_version": "a" * 64,
        "rule_ids": ["trap"],
        "features": {"duration_s": 60.0, "ua_is_tool": True},
        **overrides,
    }


def test_retains_original_detector_observations_without_reloading_trap_config():
    raw = snapshot()
    raw["rule_observations"] = {"private-session-0": rule_observations()}
    (data,) = summaries(traffic_packet(raw), "session_summary")
    assert data["rule_observations"] == rule_observations()


def test_absent_trap_provenance_remains_unknown_rather_than_zero_hits():
    (data,) = summaries(traffic_packet(snapshot()), "session_summary")
    assert "rule_observations" not in data


def test_provenance_allowlist_drops_raw_source_fields_and_invalid_feature_values():
    raw = campaign(snapshot(3))
    raw["ip_evidence"] = {
        "192.0.2.1": ip_evidence(
            hostname="PRIVATE-HOST",
            asn_origin="PRIVATE-ORIGIN",
            country="PRIVATE-COUNTRY",
        )
    }
    raw["rule_observations"] = {
        "private-session-0": rule_observations(
            rule_ids=["trap", "PRIVATE-RULE"],
            features={"duration_s": float("nan"), "ua_is_tool": True, "raw_path": "PRIVATE-PATH"},
            reason="PRIVATE-RULE-REASON",
        )
    }
    packet = traffic_packet(raw)
    data = summaries(packet, "session_summary")[0]
    assert data["network_provenance"]["asn_origin"] == "unknown"
    assert data["network_provenance"]["country"] is None
    assert data["rule_observations"]["rule_ids"] == ["trap"]
    assert data["rule_observations"]["features"] == {"ua_is_tool": True}
    text = json.dumps(packet, allow_nan=False)
    assert "PRIVATE-" not in text


@pytest.mark.parametrize(
    "change",
    [
        {"trap_config_version": "PRIVATE-CONFIG"},
        {"trap_hits": True},
        {"trap_hits": 2},
        {"version": "PRIVATE-VERSION"},
    ],
)
def test_invalid_trap_proof_is_not_forwarded_as_deterministic_observation(change):
    raw = snapshot()
    raw["rule_observations"] = {"private-session-0": rule_observations(**change)}
    (data,) = summaries(traffic_packet(raw), "session_summary")
    assert "rule_observations" not in data


@pytest.mark.parametrize("features", [None, "PRIVATE-FEATURES", ["PRIVATE-FEATURES"]])
def test_malformed_retained_features_do_not_forward_or_crash(features):
    raw = snapshot()
    raw["rule_observations"] = {"private-session-0": rule_observations(features=features)}
    (data,) = summaries(traffic_packet(raw), "session_summary")
    assert data["rule_observations"]["features"] == {}


def test_source_with_only_empty_sessions_is_not_complete_traffic_evidence():
    raw = snapshot()
    raw["sessions"][0]["requests"] = []
    packet = traffic_packet(raw)
    assert packet["complete"] is False
    assert any("empty" in message.lower() for message in packet["missing_information"])


def test_deliberate_retention_window_is_complete_and_states_scope_limitation():
    raw = snapshot()
    raw["ingest"] = {"discarded_by_retention": 100, "rotation_gaps": 0}
    packet = traffic_packet(raw)
    assert packet["complete"] is True
    assert any("retained window" in text for text in packet["local_assessment"]["limitations"])
