from datetime import UTC, datetime

import pytest

from tools.hostinger.runtime import bounded_records, selected_session_snapshot, simulation_target


def test_simulator_cannot_target_public_or_arbitrary_hosts():
    assert simulation_target("http://simulation-gateway:8080") == "http://simulation-gateway:8080"
    for url in (
        "https://example.org",
        "http://site:8000",
        "http://user@simulation-gateway:8080",
        "http://simulation-gateway:8080/path",
        "http://127.0.0.1:80",
    ):
        with pytest.raises(ValueError):
            simulation_target(url)


def test_runtime_window_discards_old_malformed_and_excess_records():
    now = datetime.now(UTC).timestamp()
    rows = [{"ts": now - 2000}, {"ts": "invalid"}, {"ts": now - 10}, {"ts": now}]
    assert bounded_records(rows, now, max_records=1, window_seconds=1800) == [rows[-1]]
    assert bounded_records(rows, now, max_records=10, window_seconds=1800) == rows[-2:]


def test_selected_case_keeps_one_entire_session_without_other_actor_truth():
    sessions = [{"id": "a", "requests": [1, 2]}, {"id": "b", "requests": [3, 4]}]
    snapshot = {
        "sessions": sessions,
        "verdicts": {"a": {"label": "bad_bot"}, "b": {"label": "uncertain"}},
        "labels": ["not-evidence"],
        "synthetic": True,
        "traffic_source_id": "physical-source",
    }
    result = selected_session_snapshot(snapshot, 1)
    assert result["sessions"] == [sessions[1]]
    assert result["verdicts"] == {"b": {"label": "uncertain"}}
    assert result["traffic_source_id"] == "physical-source"
    assert "labels" not in result
    assert snapshot["sessions"] == sessions


def test_review_selection_includes_findings_and_controls_without_reference_labels():
    snapshot = {
        "synthetic": True,
        "sessions": [{"id": "human"}, {"id": "scanner"}],
        "verdicts": {
            "human": {"label": "uncertain"},
            "scanner": {"label": "bad_bot", "rule_id": "vuln_paths"},
        },
    }
    assert selected_session_snapshot(snapshot, 0)["sessions"][0]["id"] == "scanner"
    assert selected_session_snapshot(snapshot, 1)["sessions"][0]["id"] == "human"


def test_review_scope_includes_complete_bounded_campaign_component():
    snapshot = {
        "synthetic": True,
        "sessions": [{"id": str(i), "ip": f"192.0.2.{i + 1}", "requests": [{
            "ts": "2026-11-14T12:00:00+00:00", "method": "POST", "path": "/login",
            "status": 401, "username": "private-target",
        }]} for i in range(3)],
        "verdicts": {str(i): {"label": "bad_bot"} for i in range(3)},
        "campaigns": [{"id": "group", "kind": "credential_stuffing",
                       "session_ids": ["0", "1", "2"]}],
    }
    selected = selected_session_snapshot(snapshot, 0)
    assert {s["id"] for s in selected["sessions"]} == {"0", "1", "2"}
    from bouncer.investigations import InvestigationStore
    store = InvestigationStore("sqlite:///:memory:")
    case = store.create_from_legacy(selected)
    assert case["complete"] is True
    assert case["review_eligibility"]["eligible"] is True
    assert any(e["kind"] == "campaign_summary" for e in case["evidence"])
    store.engine.dispose()


def test_oversized_campaign_scope_remains_explicitly_incomplete():
    from bouncer.investigations.evidence import traffic_packet
    source = {
        "synthetic": True,
        "sessions": [{"id": str(i), "requests": []} for i in range(33)],
        "verdicts": {},
        "campaigns": [{"id": "large", "kind": "behavior_cluster",
                       "session_ids": [str(i) for i in range(33)]}],
    }
    selected = selected_session_snapshot(source, 1)
    assert len(selected["sessions"]) == 1
    assert len(selected["campaigns"][0]["session_ids"]) == 33
    assert traffic_packet(selected)["complete"] is False
