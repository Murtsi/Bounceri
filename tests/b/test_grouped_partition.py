"""Small generated examples exercise declared-group partitioning, not model quality."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from bouncer.eval.partition import GroupedExample, partition_examples

BASE = datetime(2026, 1, 1, tzinfo=UTC)
WINDOWS = {
    "fit": (BASE, BASE + timedelta(days=1)),
    "calibration": (BASE + timedelta(days=1), BASE + timedelta(days=2)),
    "test": (BASE + timedelta(days=2), BASE + timedelta(days=3)),
}


def example(name="one", *, hour=1, **changes):
    return replace(GroupedExample(
        source_id="source", session_id=name, session_digest="a" * 64,
        started_at=BASE + timedelta(hours=hour), ended_at=BASE + timedelta(hours=hour),
        actor_id="actor-" + name, run_id="run-" + name, campaign_ids=(),
    ), **changes)


def key(row):
    return hashlib.sha256(json.dumps(
        [row.source_id, row.session_id, row.session_digest], separators=(",", ":"),
    ).encode()).hexdigest()


def test_roles_are_disjoint_deterministic_and_preserve_exact_references():
    rows = [example("test", hour=48), example("fit"), example("cal", hour=24)]
    result = partition_examples(rows, WINDOWS)
    assert result == partition_examples(reversed(rows), dict(reversed(list(WINDOWS.items()))))
    assert result["schema_version"] == "grouped-temporal-partition-v1"
    assert result["roles"] == {
        "fit": [key(rows[1])], "calibration": [key(rows[2])], "test": [key(rows[0])],
    }
    assert result["exclusions"] == {}
    assert result["examples"][key(rows[0])] == {
        "source_id": "source", "session_id": "test", "session_digest": "a" * 64,
        "started_at": "2026-01-03T00:00:00+00:00", "ended_at": "2026-01-03T00:00:00+00:00",
        "actor_id": "actor-test", "run_id": "run-test", "campaign_ids": [],
    }
    assert result["windows"]["fit"] == {
        "from": BASE.isoformat(), "until": (BASE + timedelta(days=1)).isoformat(),
    }
    memberships = list(result["components"].values())
    assert sorted(member for group in memberships for member in group) == sorted(map(key, rows))
    for component_id, members in result["components"].items():
        assert component_id == hashlib.sha256(
            json.dumps(members, separators=(",", ":")).encode(),
        ).hexdigest()
    json.dumps(result, allow_nan=False)


def test_same_actor_across_sources_is_quarantined_as_one_component():
    rows = [example("early", actor_id="same"),
            example("later", source_id="another", hour=49, actor_id="same")]
    result = partition_examples(rows, WINDOWS)
    assert result["exclusions"] == dict.fromkeys(sorted(map(key, rows)), "spans_windows")
    assert list(result["components"].values()) == [sorted(map(key, rows))]
    assert all(not members for members in result["roles"].values())


def test_transitive_actor_run_and_every_campaign_link_are_all_applied_first():
    rows = [example("a", actor_id="shared-actor"),
            example("b", actor_id="shared-actor", run_id="shared-run"),
            example("c", run_id="shared-run", campaign_ids=("c1", "c2")),
            example("d", hour=49, campaign_ids=("c2",))]
    result = partition_examples(rows, WINDOWS)
    assert list(result["components"].values()) == [sorted(map(key, rows))]
    assert set(result["exclusions"].values()) == {"spans_windows"}


def test_identity_types_are_namespaced_and_ids_are_opaque():
    rows = [example("a", actor_id="same", run_id="different"),
            example("b", hour=49, actor_id="else", run_id="same", campaign_ids=("same",))]
    result = partition_examples(rows, WINDOWS)
    assert result["roles"]["fit"] == [key(rows[0])]
    assert result["roles"]["test"] == [key(rows[1])]


@pytest.mark.parametrize("field", ["actor_id", "run_id", "campaign_ids"])
def test_unknown_identity_quarantines_known_neighbors(field):
    rows = [example("unknown", actor_id="shared", run_id="shared"),
            example("known", actor_id="shared", run_id="shared")]
    rows[0] = replace(rows[0], **{field: None})
    result = partition_examples(rows, WINDOWS)
    assert result["exclusions"] == dict.fromkeys(sorted(map(key, rows)), "unknown_group_identity")
    assert len(result["examples"]) == 2
    assert all(not members for members in result["roles"].values())


def test_whole_session_interval_and_component_interval_must_fit():
    rows = [example("session", hour=23, ended_at=BASE + timedelta(hours=25)),
            example("end-boundary", hour=23, ended_at=BASE + timedelta(hours=24)),
            example("linked-a", hour=23, actor_id="linked"),
            example("linked-b", hour=24, actor_id="linked"),
            example("next-boundary", hour=24)]
    result = partition_examples(rows, WINDOWS)
    assert result["roles"]["calibration"] == [key(rows[-1])]
    assert result["exclusions"] == dict.fromkeys(sorted(map(key, rows[:-1])), "spans_windows")


def test_gap_and_outside_reasons_are_explicit():
    windows = dict(WINDOWS, calibration=(BASE + timedelta(hours=30), BASE + timedelta(days=2)))
    rows = [example("gap", hour=25), example("before", hour=-1), example("after", hour=72)]
    result = partition_examples(rows, windows)
    assert result["exclusions"] == {
        key(rows[0]): "window_gap",
        key(rows[1]): "outside_windows", key(rows[2]): "outside_windows",
    }


@pytest.mark.parametrize("digest", ["a" * 64, "b" * 64])
def test_duplicate_source_session_rejected_even_when_digest_changes(digest):
    with pytest.raises(ValueError, match="duplicate source/session"):
        partition_examples([example(), example(session_digest=digest)], WINDOWS)


@pytest.mark.parametrize("changes", [
    {"source_id": ""}, {"session_id": "x\x00"}, {"actor_id": ""}, {"run_id": ""},
    {"session_digest": "a" * 63}, {"session_digest": "z" * 64}, {"session_digest": 1},
    {"source_id": 2}, {"session_id": True}, {"actor_id": []}, {"run_id": False},
    {"source_id": "ö" * 129}, {"actor_id": "\ud800"}, {"campaign_ids": ["a"]},
    {"campaign_ids": (None,)}, {"campaign_ids": ("",)}, {"campaign_ids": ("\x00",)},
    {"campaign_ids": tuple(str(i) for i in range(65))},
    {"started_at": BASE.replace(tzinfo=None)}, {"ended_at": BASE.replace(tzinfo=None)},
    {"started_at": "2026-01-01"}, {"ended_at": BASE - timedelta(seconds=1)},
])
def test_invalid_example_metadata_is_rejected(changes):
    with pytest.raises(ValueError):
        partition_examples([example(**changes)], WINDOWS)


@pytest.mark.parametrize("windows", [
    {}, {"fit": WINDOWS["fit"], "test": WINDOWS["test"]}, dict(WINDOWS, extra=WINDOWS["fit"]),
    dict(WINDOWS, fit=(BASE, BASE)), dict(WINDOWS, fit=(BASE, BASE - timedelta(seconds=1))),
    dict(WINDOWS, fit=(BASE.replace(tzinfo=None), BASE + timedelta(days=1))),
    dict(WINDOWS, fit=(BASE, "bad")), dict(WINDOWS, fit=(BASE,)),
    dict(WINDOWS, calibration=(BASE + timedelta(hours=23), BASE + timedelta(days=2))),
    {"fit": WINDOWS["test"], "calibration": WINDOWS["calibration"], "test": WINDOWS["fit"]},
    [], None,
])
def test_invalid_windows_are_rejected(windows):
    with pytest.raises(ValueError):
        partition_examples([], windows)


def test_non_example_values_and_workload_over_cap_are_rejected():
    with pytest.raises(ValueError, match="GroupedExample"):
        partition_examples([{}], WINDOWS)
    with pytest.raises(ValueError, match="20000"):
        partition_examples((example(str(i)) for i in range(20001)), WINDOWS)


def test_empty_input_and_utc_normalization():
    assert partition_examples([], WINDOWS)["roles"] == {"fit": [], "calibration": [], "test": []}
    row = example()
    offset = timezone(timedelta(hours=2))
    localized = replace(row, started_at=row.started_at.astimezone(offset),
                        ended_at=row.ended_at.astimezone(offset))
    windows = {role: tuple(t.astimezone(offset) for t in bounds)
               for role, bounds in WINDOWS.items()}
    assert partition_examples([row], WINDOWS) == partition_examples([localized], windows)


def test_known_connected_component_is_admitted_whole_inside_one_window():
    rows = [example("a", actor_id="linked"),
            example("b", actor_id="linked", campaign_ids=("one", "two")),
            example("c", source_id="another", campaign_ids=("two",), hour=23)]
    result = partition_examples(rows, WINDOWS)
    assert result["roles"]["fit"] == sorted(map(key, rows))
    assert list(result["components"].values()) == [sorted(map(key, rows))]
    assert result["exclusions"] == {}


def test_identifier_and_campaign_caps_accept_the_exact_bounds():
    row = example(source_id="ö" * 128, session_id="x" * 256,
                  campaign_ids=tuple(str(i) for i in range(64)))
    result = partition_examples([row], WINDOWS)
    assert result["roles"]["fit"] == [key(row)]
