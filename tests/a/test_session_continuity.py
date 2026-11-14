"""Committed session ownership and simulator truth survive late and evicted records."""

import copy
import importlib
import importlib.util
import json

import pytest

from tests.a.test_worker import SECRET, _rec


def sessionize(records, previous=(), label_state=None):
    assert importlib.util.find_spec("bouncer.ingest.continuity") is not None, (
        "session continuity helper missing"
    )
    return importlib.import_module("bouncer.ingest.continuity").sessionize(
        records, previous, SECRET, label_state or {}
    )


def test_late_first_timestamp_preserves_committed_session_id():
    records = [_rec(1001, "192.0.2.1")]
    first, _, _, state = sessionize(records)
    records.append(_rec(1000, "192.0.2.1"))
    second, _, _, _ = sessionize(records, first, state)
    assert [session.id for session in second] == [first[0].id]
    assert [request.ts.timestamp() for request in second[0].requests] == [1000, 1001]
    assert {record["_session_id"] for record in records} == {first[0].id}


def test_late_bridge_keeps_both_committed_groups_and_cached_record_ownership():
    records = [_rec(1000, "192.0.2.1"), _rec(2000, "192.0.2.1")]
    previous, _, _, state = sessionize(records)
    owners = [record["_session_id"] for record in records]
    records = json.loads(json.dumps(records))
    records.extend(_rec(timestamp, "192.0.2.1") for timestamp in [1250, 1500, 1750])
    sessions, _, _, _ = sessionize(records, previous, state)
    assert {session.id for session in sessions} == set(owners)
    assert [record["_session_id"] for record in records[:2]] == owners
    assert sum(len(session.requests) for session in sessions) == 5
    assert len({request.ts for session in sessions for request in session.requests}) == 5


def test_full_fresh_batch_is_sessionized_before_caller_limits_visible_records():
    records = [_rec(timestamp, "192.0.2.1") for timestamp in [1000, 1001, 1400]]
    sessions, _, stats, _ = sessionize(records)
    assert sorted(len(session.requests) for session in sessions) == [1, 2]
    assert stats.records == 3
    assert all(record.get("_session_id") for record in records)
    assert {record["_session_id"] for record in records} == {session.id for session in sessions}


def test_historical_signed_marker_and_conflict_survive_eviction_and_restart():
    sessions, labels, _, state = sessionize([_rec(1000, "192.0.2.1", marker="run:human")])
    original = copy.deepcopy(state)
    records = [_rec(1001, "192.0.2.1")]
    sessions, retained, _, state = sessionize(records, sessions, state)
    assert retained == labels
    assert state == original
    sessions, labels, stats, conflicted = sessionize(
        [_rec(1002, "192.0.2.1", marker="other:credential_stuffing")], sessions, state
    )
    assert not labels
    assert stats.conflicting_sessions == [sessions[0].id]
    assert state == original
    _, labels, stats, _ = sessionize(
        [_rec(1003, "192.0.2.1")], sessions, json.loads(json.dumps(conflicted))
    )
    assert not labels
    assert stats.conflicting_sessions == [sessions[0].id]


def test_bad_records_and_unsigned_markers_do_not_add_truth_or_stop_later_records():
    unsigned = _rec(1000, "192.0.2.1", marker="forged:human")
    unsigned["request"]["headers"]["X-Sim-Sig"] = ["wrong-signature"]
    records = [dict(unsigned, ts="invalid"), unsigned, _rec(1001, "192.0.2.1")]
    sessions, labels, stats, state = sessionize(records)
    assert len(sessions[0].requests) == 2
    assert not labels
    assert stats.invalid_records == 1
    assert stats.unsigned_markers == 1
    assert state[sessions[0].id] == {"marker": None, "conflict": False}


def test_cached_ownership_cannot_be_reassigned_to_a_different_client():
    records = [_rec(1000, "192.0.2.1")]
    sessions, _, _, state = sessionize(records)
    records[0]["request"]["client_ip"] = "192.0.2.2"
    with pytest.raises(ValueError, match="identity.*client"):
        sessionize(records, sessions, state)


def test_nearest_interval_ties_do_not_depend_on_previous_identity_order():
    previous, _, _, state = sessionize([
        _rec(1000, "192.0.2.1"), _rec(1600, "192.0.2.1")
    ])
    first, _, _, _ = sessionize([_rec(1300, "192.0.2.1")], previous, state)
    reversed_order, _, _, _ = sessionize([_rec(1300, "192.0.2.1")], previous[::-1], state)
    assert first[0].id == previous[0].id
    assert reversed_order == first


@pytest.mark.parametrize("marker,expected", [("bad-format", None), ("run:new-class", "new-class")])
def test_simulator_marker_validation_matches_existing_parser(marker, expected):
    _, labels, stats, _ = sessionize([_rec(1000, "192.0.2.1", marker=marker)])
    assert [label.sim_class for label in labels] == ([] if expected is None else [expected])
    assert stats.invalid_markers == (expected is None)
