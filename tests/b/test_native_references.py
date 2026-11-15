"""Private source-bound references; synthetic truth never establishes real evidence."""

import hashlib
import json
import shutil
from dataclasses import replace

import pytest

from bouncer.db.participants import session_digest
from tests.b.test_reviewed_study import observation
from tools.datasets.native import generate_bundle
from tools.datasets.registry import checksum


def collection(source="private-one", *, run="declared-run", campaigns=()):
    return {
        "source_key": source,
        "run_id": run,
        "campaign_ids": list(campaigns) if campaigns is not None else None,
    }


def references(reviewed=(), collections=(), manifests=(), *, evidence_profile="offline"):
    from bouncer.eval.reference import build_references

    return build_references(reviewed, collections, manifests, evidence_profile=evidence_profile)


def test_study_truth_is_only_manual_benign_and_groups_are_explicit():
    observations = [
        observation(source=str(i), behavior=behavior, intent=intent)
        for i, (behavior, intent) in enumerate(
            [
                ("manual", "benign"),
                ("automated", "benign"),
                ("manual", "abusive"),
                ("unknown", "unknown"),
            ]
        )
    ]
    result = references(observations, [collection(str(i)) for i in range(4)])
    assert len(result.rows) == 1 and len(result.examples) == 4
    row = result.rows[0]
    assert (row.truth, row.origin, row.source) == ("human", "real", "study")
    assert row.run_id == "declared-run" and row.campaign_id is None
    assert {e.actor_id for e in result.examples} == {"actor-one"}
    assert {e.run_id for e in result.examples} == {"declared-run"}
    assert {e.campaign_ids for e in result.examples} == {()}
    assert result.source_ids == ("0", "1", "2", "3")
    assert set(result.sessions) == set(result.metadata) == set(result.unavailable_fields)
    assert all(key == session.id for key, session in result.sessions.items())
    assert sorted(m["truth"] or "unknown" for m in result.metadata.values()) == [
        "human",
        "unknown",
        "unknown",
        "unknown",
    ]
    assert all(m["cohort"] == "human_study" for m in result.metadata.values())


def test_same_native_id_across_sources_preserves_actual_actor_and_full_interval():
    first, second = observation(source="one"), observation(source="two")
    result = references([first, second], [collection("one"), collection("two")])
    assert len(result.sessions) == 2
    assert {e.session_id for e in result.examples} == {first.session.id}
    assert {e.actor_id for e in result.examples} == {first.subject_id}
    assert {e.ended_at for e in result.examples} == {first.session.ended_at}
    assert all(m["external_session_id"] == first.session.id for m in result.metadata.values())


def test_unknown_collection_groups_stay_unknown_without_ip_or_session_inference():
    result = references([observation()], [collection(run=None, campaigns=None)])
    assert result.examples[0].run_id is None and result.examples[0].campaign_ids is None


@pytest.mark.parametrize(
    "collections",
    [
        [collection(), collection()],
        [collection("absent")],
        [],
        [{"source_key": "private-one", "run_id": "run"}],
        [{"source_key": "private-one", "campaign_ids": []}],
        [collection() | {"extra": True}],
        [collection(run=3)],
        [collection(campaigns=["x" * 257])],
        [collection(campaigns=["x"] * 65)],
    ],
)
def test_invalid_or_missing_collection_bindings_fail(collections):
    with pytest.raises(ValueError):
        references([observation()], collections)


def test_selected_source_requires_current_approved_observation():
    with pytest.raises(ValueError, match="approved|reviewed"):
        references([], [collection()])


def test_duplicate_native_versions_and_stale_digest_fail():
    first = observation()
    changed = replace(first.session, requests=first.session.requests[:-1])
    second = replace(first, session=changed, digest=session_digest(changed))
    with pytest.raises(ValueError, match="duplicate"):
        references([first, second], [collection()])
    with pytest.raises(ValueError, match="changed"):
        references([replace(first, session=changed)], [collection()])


def test_private_provenance_and_missingness_are_hash_bound_without_raw_dump():
    first = replace(
        observation(),
        provenance={
            "source": {"unavailable_fields": ["target"], "origin_digest": "a" * 64},
            "review": {"private_note": "secret"},
            "consent": {"private": "do-not-copy"},
        },
    )
    result = references([first], [collection()])
    key = next(iter(result.sessions))
    metadata = result.metadata[key]
    assert result.unavailable_fields[key] == ("target",)
    assert len(metadata["provenance_digest"]) == 64
    assert len(metadata["source_metadata_digest"]) == 64
    assert len(metadata["missingness_digest"]) == 64
    assert "secret" not in json.dumps(metadata) and "do-not-copy" not in json.dumps(metadata)
    changed = replace(first, provenance={"source": {"unavailable_fields": []}})
    assert references([changed], [collection()]).metadata[key] != metadata
    assert references([replace(first, revision=2)], [collection()]).metadata[key] != metadata


def test_native_bundle_is_parsed_with_verified_truth_and_stable_composite_ids(tmp_path):
    manifest = generate_bundle(tmp_path / "bundle", seed=51, runs_per_partition=1)
    result = references(manifests=[manifest])
    truth = {
        r["session_id"]: r
        for r in map(json.loads, (manifest.parent / "truth.jsonl").read_text().splitlines())
    }
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert len(result.sessions) == len(truth) == 72
    assert result.source_ids == ()
    assert {row.truth for row in result.rows} == {"human", "bad_bot"}
    assert all((row.origin, row.source) == ("simulated", "sim") for row in result.rows)
    for example in result.examples:
        reference = truth[example.session_id]
        assert example.source_id == f"synthetic/{digest}/{reference['run_id']}"
        assert example.actor_id == reference["actor_id"]
        assert example.run_id == reference["run_id"]
        assert example.campaign_ids == (
            (reference["campaign_group"],) if reference["campaign_group"] else ()
        )
    for key, metadata in result.metadata.items():
        reference = truth[metadata["external_session_id"]]
        assert metadata["truth"] == reference["traffic_truth"]
        assert metadata["cohort"] == "simulation"
        assert metadata["profile"] == reference["profile"]
        assert metadata["automation_truth"] == reference["automation_truth"]
        assert metadata["maliciousness_truth"] == reference["maliciousness_truth"]
        assert metadata["reference_source"] == "known_public_generator_template"
        assert metadata["genuinely_hidden_attack"] == "unavailable"
        original = replace(result.sessions[key], id=metadata["external_session_id"])
        assert session_digest(original) == metadata["digest"]
        assert all("x-sim-run" not in r.headers for r in original.requests)
    shutil.copytree(manifest.parent, tmp_path / "copy")
    copy = references(manifests=[tmp_path / "copy" / "manifest.json"])
    assert result.examples == copy.examples and result.metadata == copy.metadata
    with pytest.raises(ValueError, match="duplicate"):
        references(manifests=[manifest, tmp_path / "copy" / "manifest.json"])


def test_snapshot_validation_never_reopens_supplied_bundle(tmp_path, monkeypatch):
    manifest = generate_bundle(tmp_path / "bundle", seed=52, runs_per_partition=1)
    from bouncer.eval import reference

    original = reference.verify_bundle

    def change_original_after_snapshot(snapshot):
        assert snapshot.parent != manifest.parent
        (manifest.parent / "access.jsonl").write_text("tampered")
        return original(snapshot)

    monkeypatch.setattr(reference, "verify_bundle", change_original_after_snapshot)
    assert len(references(manifests=[manifest]).examples) == 72


@pytest.mark.parametrize(
    "change",
    [
        "checksum",
        "extra_file",
        "traversal",
        "version",
        "human",
        "hidden",
        "public_robot",
        "oversize",
    ],
)
def test_invalid_native_bundle_is_rejected(tmp_path, change):
    manifest = generate_bundle(tmp_path / "bundle", seed=53, runs_per_partition=1)
    data = json.loads(manifest.read_text())
    if change == "checksum":
        (manifest.parent / "access.jsonl").write_text("{}\n")
    elif change == "extra_file":
        data["files"]["unexpected.csv"] = {"sha256": "a" * 64, "bytes": 1}
    elif change == "traversal":
        data["files"]["../truth.jsonl"] = data["files"].pop("truth.jsonl")
    elif change == "version":
        data["version"] = "arbitrary"
    elif change == "human":
        data["synthetic"] = False
    elif change == "hidden":
        data["genuinely_hidden_attack"] = "available"
    elif change == "public_robot":
        data = {"task": "historical_robot_label", "ROBOT": True}
    elif change == "oversize":
        with (manifest.parent / "access.jsonl").open("wb") as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        references(manifests=[manifest])


def test_reference_input_caps_reject_before_loading():
    with pytest.raises(ValueError):
        references([observation()] * 20001, [collection()])
    with pytest.raises(ValueError):
        references(collections=[collection(str(i)) for i in range(1001)])
    with pytest.raises(ValueError):
        references(manifests=["unused"] * 11)


def test_reference_capacity_supports_351_distinct_fixture_subjects_and_sources():
    observations = [
        observation(
            source=f"fixture-source-{index}",
            subject=f"fixture-subject-{index}",
            behavior="automated",
            intent="unknown",
        )
        for index in range(351)
    ]
    result = references(observations, [collection(row.source_id) for row in observations])
    assert len(result.examples) == len(result.sessions) == len(result.source_ids) == 351
    assert len({example.actor_id for example in result.examples}) == 351
    assert len({(example.source_id, example.session_id) for example in result.examples}) == 351
    assert len(set(result.sessions)) == 351
    assert result.rows == []
    assert all(metadata["truth"] is None for metadata in result.metadata.values())
    from bouncer.db.evaluations import MAX_SOURCE_BINDINGS
    from bouncer.eval.reference import MAX_COLLECTIONS

    assert MAX_COLLECTIONS == MAX_SOURCE_BINDINGS == 1000


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", []),
        ("behavior", []),
        ("intent", 42),
        ("review_id", None),
        ("revision", True),
        ("subject_id", "x" * 257),
        ("digest", None),
    ],
)
def test_malformed_reviewed_fields_fail_closed(field, value):
    with pytest.raises(ValueError):
        references([replace(observation(), **{field: value})], [collection()])


def test_arbitrary_session_labels_cannot_be_loaded_as_human_evidence():
    from bouncer.contracts import SessionLabel

    with pytest.raises(ValueError):
        references([SessionLabel("s1", "owner-says-real", "human_real")], [collection()])


def test_rehashed_unknown_intent_truth_cannot_be_promoted_to_bot_truth(tmp_path):
    manifest = generate_bundle(tmp_path / "bundle", seed=54, runs_per_partition=1)
    truth_path = manifest.parent / "truth.jsonl"
    rows = [json.loads(line) for line in truth_path.read_text().splitlines()]
    next(row for row in rows if row["profile"] == "scraper_ambiguous")["traffic_truth"] = "bad_bot"
    truth_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    data = json.loads(manifest.read_text())
    data["files"]["truth.jsonl"] = checksum(truth_path)
    manifest.write_text(json.dumps(data))
    from tools.datasets.native import verify_bundle

    verify_bundle(manifest)  # Owner-editable checksums alone cannot establish generator truth.
    with pytest.raises(ValueError, match="generator"):
        references(manifests=[manifest])


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_runs",
        "duplicate_runs_and_count",
        "unknown_run_field",
        "missing_run_field",
        "wrong_run_id",
        "wrong_run_partition",
        "wrong_run_seed",
        "reordered_runs",
        "missing_run",
        "session_count",
        "boolean_run_seed",
    ],
)
def test_invalid_tiny_snapshot_cannot_trigger_large_regeneration(tmp_path, monkeypatch, change):
    manifest = generate_bundle(tmp_path / "bundle", seed=55, runs_per_partition=1)
    data = json.loads(manifest.read_text())
    if change.startswith("duplicate_runs"):
        data["runs"] *= 100
        if change == "duplicate_runs_and_count":
            data["n_sessions"] = 7200
    elif change == "unknown_run_field":
        data["runs"][0]["unknown"] = "owner-supplied"
    elif change == "missing_run_field":
        del data["runs"][0]["generator_seed"]
    elif change == "wrong_run_id":
        data["runs"][0]["run_id"] = "native-55-run-400"
    elif change == "wrong_run_partition":
        data["runs"][0]["partition"] = "reserved"
    elif change == "wrong_run_seed":
        data["runs"][0]["generator_seed"] = 56
    elif change == "boolean_run_seed":
        data["seed"] = 1
        for index, run in enumerate(data["runs"]):
            run["run_id"] = f"native-1-run-{index}"
            run["generator_seed"] = True
    elif change == "reordered_runs":
        data["runs"].reverse()
    elif change == "missing_run":
        data["runs"].pop()
    elif change == "session_count":
        data["n_sessions"] -= 1
    manifest.write_text(json.dumps(data))
    from bouncer.eval import reference

    calls = []

    def forbid_expensive_work(*args, **kwargs):
        calls.append(args)
        pytest.fail("noncanonical run metadata reached verification or regeneration")

    monkeypatch.setattr(reference, "generate_bundle", forbid_expensive_work)
    monkeypatch.setattr(reference, "verify_bundle", forbid_expensive_work)
    with pytest.raises(ValueError):
        references(manifests=[manifest])
    assert calls == []


def runtime_wrapper(session, *, intel=None, traps=(), observation=None, enabled=True):
    from dataclasses import asdict

    from bouncer.contracts import IpIntel
    from bouncer.ingest.runtime_context import capture_configuration, capture_session

    intel = intel or IpIntel()
    config = capture_configuration(frozenset(traps))
    captured = capture_session(
        session,
        intel,
        configuration=config,
        captured_at=session.ended_at.isoformat(),
        intel_enabled=enabled,
        observation=observation,
    )
    assert captured["available"] is True
    return {
        "availability": "available",
        "effective": {
            "intel": asdict(intel),
            "traps": config["trap_paths"],
            "provenance": {
                "availability": "available" if observation is not None else "unavailable",
                "intel_enabled": enabled,
                "observation": observation,
            },
        },
        "config_digest": config["trap_config_version"],
        "session_digest": captured["session_digest"],
        "captured_at": captured["captured_at"],
    }


def test_runtime_reference_binds_exact_session_and_keeps_private_inputs_out_of_metadata():
    row = observation()
    wrapper = runtime_wrapper(row.session, traps=("/private-trap",))
    row = replace(row, provenance={"source": {"runtime_context": wrapper}})
    refs = references([row], [collection()], evidence_profile="captured")
    key = next(iter(refs.sessions))
    assert refs.runtime_contexts[key] == wrapper
    assert refs.metadata[key]["runtime_context_status"] == "available"
    assert len(refs.metadata[key]["runtime_context_digest"]) == 64
    assert "/private-trap" not in json.dumps(refs.metadata)
    assert "verified_bot" not in json.dumps(refs.metadata)


@pytest.mark.parametrize("fault", ["old", "digest", "traps", "intel", "provenance", "truncated"])
def test_invalid_runtime_reference_is_unavailable_without_guessing(fault):
    row = observation()
    wrapper = runtime_wrapper(row.session, traps=("/private-trap",))
    if fault == "digest":
        wrapper["session_digest"] = "a" * 64
    elif fault == "traps":
        wrapper["effective"]["traps"].append("/tampered")
    elif fault == "intel":
        wrapper["effective"]["intel"]["verified_bot"] = 1
    elif fault == "provenance":
        wrapper["effective"]["provenance"]["availability"] = "available"
    elif fault == "truncated":
        wrapper.pop("captured_at")
    source = {} if fault == "old" else {"runtime_context": wrapper}
    refs = references(
        [replace(row, provenance={"source": source})], [collection()], evidence_profile="captured"
    )
    key = next(iter(refs.sessions))
    assert key not in refs.runtime_contexts
    assert refs.metadata[key]["runtime_context_status"] == "unavailable"


def test_current_generator_context_is_explicitly_offline_simulation(tmp_path):
    manifest = generate_bundle(tmp_path / "bundle", seed=60, runs_per_partition=1)
    refs = references(manifests=[manifest])
    assert refs.runtime_contexts.keys() == refs.sessions.keys()
    for key, context in refs.runtime_contexts.items():
        assert (
            context["availability"]
            == refs.metadata[key]["runtime_context_status"]
            == "synthetic_offline"
        )
        assert context["effective"]["traps"] == []
        assert context["effective"]["intel"]["verified_bot"] is None
        assert context["effective"]["provenance"]["availability"] == "unavailable"


def test_offline_references_ignore_unused_runtime_capture_refresh():
    row = observation()
    wrapper = runtime_wrapper(row.session, traps=("/private-trap",))
    first = replace(
        row, provenance={"source": {"origin_digest": "a" * 64, "runtime_context": wrapper}}
    )
    changed = replace(
        row,
        provenance={
            "source": {
                "origin_digest": "a" * 64,
                "runtime_context": wrapper | {"captured_at": "2030-01-01T00:00:00+00:00"},
            }
        },
    )
    from bouncer.eval.reference import build_references

    before = build_references([first], [collection()], [], evidence_profile="offline")
    after = build_references([changed], [collection()], [], evidence_profile="offline")
    assert before.metadata == after.metadata
    assert before.runtime_contexts == after.runtime_contexts == {}
    assert "runtime_context_digest" not in next(iter(before.metadata.values()))
    captured_before = build_references([first], [collection()], [], evidence_profile="captured")
    captured_after = build_references([changed], [collection()], [], evidence_profile="captured")
    assert captured_before.metadata != captured_after.metadata
