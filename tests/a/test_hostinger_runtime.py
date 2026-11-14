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
    }
    result = selected_session_snapshot(snapshot, 1)
    assert result["sessions"] == [sessions[1]]
    assert result["verdicts"] == {"b": {"label": "uncertain"}}
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
