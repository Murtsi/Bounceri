"""Bounded native references for private evaluation, never inferred truth.

The caller must load reviews freshly under its consent/source guard. This module
owns no database connection and retains no raw provenance in frozen metadata.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from bouncer.contracts import IpIntel, Session
from bouncer.db.evaluations import MAX_SOURCE_BINDINGS
from bouncer.db.participants import ReviewedSession, session_digest
from bouncer.eval.dataset import DatasetRow
from bouncer.eval.native_fixtures import (
    PARTITIONS,
    PROFILES,
    fixture_signing_key,
    generate_bundle,
    verify_bundle,
)
from bouncer.eval.partition import GroupedExample, _identifier, _utc
from bouncer.eval.study import build_reviewed_corpus, observation_key
from bouncer.ingest.runtime_context import capture_configuration, validate_effective_context
from bouncer.ingest.sample import parse_access_records
from bouncer.ingest.worker import stable_id
from bouncer.session.features import compute_features

MAX_OBSERVATIONS = 20000
MAX_COLLECTIONS = MAX_SOURCE_BINDINGS
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
_FILES = ("manifest.json", "access.jsonl", "truth.jsonl", "features.jsonl")


@dataclass
class ReferenceSet:
    examples: list[GroupedExample]
    sessions: dict[str, Session]
    rows: list[DatasetRow]
    metadata: dict[str, dict]
    unavailable_fields: dict[str, tuple[str, ...]]
    source_ids: tuple[str, ...]
    runtime_contexts: dict[str, dict] = field(default_factory=dict)
    runtime_configurations: dict[str, dict] = field(default_factory=dict)


def validate_recorded_context(session: Session, wrapper: dict, *, synthetic=False) -> dict:
    """Validate private replay inputs; synthetic defaults never establish runtime evidence."""
    if (
        type(wrapper) is not dict
        or set(wrapper)
        != {
            "availability",
            "effective",
            "config_digest",
            "session_digest",
            "captured_at",
        }
        or wrapper["availability"] != ("synthetic_offline" if synthetic else "available")
    ):
        raise ValueError("Invalid recorded runtime context")
    effective = validate_effective_context(
        session,
        wrapper["effective"],
        session_digest=wrapper["session_digest"],
        config_digest=wrapper["config_digest"],
        captured_at=wrapper["captured_at"],
    )
    if synthetic and effective != {
        "intel": asdict(IpIntel()),
        "traps": [],
        "provenance": {"availability": "unavailable", "intel_enabled": False, "observation": None},
    }:
        raise ValueError("Invalid synthetic offline context")
    return wrapper | {"effective": effective}


def _runtime(result: ReferenceSet, key: str, session: Session, wrapper, *, synthetic=False):
    result.metadata[key].update(
        runtime_context_status="unavailable", runtime_context_digest=_digest(wrapper)
    )
    try:
        validated = validate_recorded_context(session, wrapper, synthetic=synthetic)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        return
    config = result.runtime_configurations.setdefault(
        validated["config_digest"], capture_configuration(validated["effective"]["traps"])
    )
    validated["effective"]["traps"] = config["trap_paths"]
    result.runtime_contexts[key] = validated
    result.metadata[key]["runtime_context_status"] = validated["availability"]


def _digest(value: object) -> str:
    try:
        content = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("reference metadata must be finite JSON") from exc
    return hashlib.sha256(content.encode()).hexdigest()


def _bounded(values: object, maximum: int, name: str) -> None:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or len(values) > maximum
    ):
        raise ValueError(f"{name} must be a sequence of at most {maximum} items")


def _campaigns(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("campaign_ids must be a list of at most 64 IDs or None")
    for item in value:
        _identifier(item)
    return tuple(sorted(set(value)))


def _add(
    result: ReferenceSet,
    seen: set[tuple[str, str]],
    session: Session,
    example: GroupedExample,
    metadata: dict,
    missing: tuple[str, ...],
) -> str:
    if len(result.examples) >= MAX_OBSERVATIONS:
        raise ValueError("at most 20000 observations are allowed")
    for value in (example.source_id, example.session_id, example.actor_id, example.run_id):
        if value is not None:
            _identifier(value)
    if example.campaign_ids is not None:
        if len(example.campaign_ids) > 64:
            raise ValueError("at most 64 campaigns are allowed")
        for campaign in example.campaign_ids:
            _identifier(campaign)
    start, end = _utc(example.started_at), _utc(example.ended_at)
    if end < start:
        raise ValueError("ended_at must not precede started_at")
    identity = example.source_id, example.session_id
    if identity in seen:
        raise ValueError("duplicate source/session identity")
    seen.add(identity)
    key = _digest([example.source_id, example.session_id, example.session_digest])
    result.examples.append(example)
    result.sessions[key] = replace(session, id=key)
    result.metadata[key] = metadata | {
        "source_id": example.source_id,
        "external_session_id": example.session_id,
        "digest": example.session_digest,
        "actor_id": example.actor_id,
        "run_id": example.run_id,
        "campaign_ids": list(example.campaign_ids) if example.campaign_ids is not None else None,
        "missingness_digest": _digest(list(missing)),
    }
    result.unavailable_fields[key] = missing
    return key


def _study(
    result: ReferenceSet,
    reviewed: Sequence[ReviewedSession],
    collections: dict[str, tuple[str | None, tuple[str, ...] | None]],
    seen: set[tuple[str, str]],
    evidence_profile: str,
) -> None:
    for row in reviewed:
        if not isinstance(row, ReviewedSession) or not isinstance(row.session, Session):
            raise ValueError("reviewed observations must be ReviewedSession instances")
        _identifier(row.source_id)
        if row.source_id not in collections:
            raise ValueError("reviewed source is outside selected collections")
        for value in (row.subject_id, row.enrollment_id, row.review_id):
            _identifier(value)
        if type(row.revision) is not int or row.revision < 1:
            raise ValueError("annotation revision must be a positive integer")
        if (
            not isinstance(row.behavior, str)
            or not isinstance(row.intent, str)
            or row.behavior not in {"manual", "automated", "mixed", "unknown"}
            or row.intent not in {"benign", "abusive", "unknown"}
        ):
            raise ValueError("invalid reviewed behavior or intent")
        if not isinstance(row.provenance, dict):
            raise ValueError("reviewed provenance must be an object")
        source = row.provenance.get("source", {})
        if not isinstance(source, dict):
            raise ValueError("source provenance must be an object")
        missing = source.get("unavailable_fields", [])
        if not isinstance(missing, (list, tuple)) or len(missing) > 64:
            raise ValueError("unavailable_fields must be a bounded list")
        for value in missing:
            _identifier(value)
    corpus = build_reviewed_corpus(reviewed)
    by_key = {row.session_id: row for row in corpus.dataset.rows}
    for row in reviewed:
        run, campaigns = collections[row.source_id]
        provenance = row.provenance
        if evidence_profile == "offline" and "runtime_context" in provenance.get("source", {}):
            provenance = provenance | {
                "source": {
                    key: value
                    for key, value in provenance["source"].items()
                    if key != "runtime_context"
                }
            }
        truth = "human" if row.behavior == "manual" and row.intent == "benign" else None
        key = _add(
            result,
            seen,
            row.session,
            GroupedExample(
                row.source_id,
                row.session.id,
                row.digest,
                row.session.started_at,
                row.session.ended_at,
                row.subject_id,
                run,
                campaigns,
            ),
            {
                "cohort": "human_study",
                "truth": truth,
                "truth_source": "consented_manual_benign" if truth else "reviewed_unknown_class",
                "annotation_id": row.review_id,
                "annotation_revision": row.revision,
                "behavior": row.behavior,
                "intent": row.intent,
                "provenance_digest": _digest(provenance),
                "source_metadata_digest": _digest(provenance.get("source", {})),
            },
            corpus.unavailable_fields[observation_key(row)],
        )
        if evidence_profile == "captured":
            _runtime(result, key, row.session, provenance.get("source", {}).get("runtime_context"))
        if truth is not None:
            result.rows.append(
                replace(by_key[key], run_id=run, campaign_id=campaigns[0] if campaigns else None)
            )
    if set(collections) != {row.source_id for row in reviewed}:
        raise ValueError("every selected source requires a current approved reviewed observation")


def _snapshot(manifest: Path, target: Path, remaining: int) -> tuple[dict, str, int]:
    """Read each supplied file once; verification and parsing use only our copy."""
    target.mkdir()
    total = 0
    contents = {}
    for name in _FILES:
        path = manifest if name == "manifest.json" else manifest.parent / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("native bundle requires regular known files")
        with path.open("rb") as stream:
            content = stream.read(remaining - total + 1)
        total += len(content)
        if total > remaining:
            raise ValueError("native bundles exceed 16 MiB total")
        contents[name] = content
        (target / name).write_bytes(content)
    try:
        data = json.loads(contents["manifest.json"])
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid native manifest JSON") from exc
    if not isinstance(data, dict) or set(data.get("files", {})) != set(_FILES[1:]):
        raise ValueError("native manifest must list exactly the known files")
    return data, hashlib.sha256(contents["manifest.json"]).hexdigest(), total


def _synthetic(
    result: ReferenceSet,
    manifest_path: Path,
    directory: Path,
    remaining: int,
    seen: set[tuple[str, str]],
) -> int:
    data, manifest_digest, size = _snapshot(manifest_path, directory / "snapshot", remaining)
    seed, runs = data.get("seed"), data.get("runs")
    if (
        type(seed) is not int
        or not 0 <= seed <= 2**31 - 1
        or not isinstance(runs, list)
        or not runs
        or len(runs) % len(PARTITIONS)
        or len(runs) > 100 * len(PARTITIONS)
    ):
        raise ValueError("unsupported current native generator parameters")
    if type(data.get("n_sessions")) is not int or not 1 <= data[
        "n_sessions"
    ] <= MAX_OBSERVATIONS - len(result.examples):
        raise ValueError("at most 20000 observations are allowed")
    count = len(runs) // len(PARTITIONS)
    canonical_runs = [
        {
            "run_id": f"native-{seed}-run-{partition_index * count + repetition}",
            "partition": partition,
            "generator_seed": seed,
        }
        for partition_index, partition in enumerate(PARTITIONS)
        for repetition in range(count)
    ]
    if (
        any(not isinstance(run, dict) or type(run.get("generator_seed")) is not int for run in runs)
        or runs != canonical_runs
        or data["n_sessions"] != len(PROFILES) * len(runs)
    ):
        raise ValueError("native runs and session count must match canonical generator parameters")
    snapshot_path = directory / "snapshot" / "manifest.json"
    verify_bundle(snapshot_path)
    expected_path = generate_bundle(directory / "expected", seed=seed, runs_per_partition=count)
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    # Checksums alone are owner-editable. Exact deterministic regeneration binds
    # public template truth, grouping and provenance to this generator version.
    if data != expected:
        raise ValueError("bundle differs from current public native generator provenance")
    for name in _FILES[1:]:
        if (snapshot_path.parent / name).read_bytes() != (expected_path.parent / name).read_bytes():
            raise ValueError("bundle differs from current public native generator content")
    records = [
        json.loads(line)
        for line in (snapshot_path.parent / "access.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    sessions, _ = parse_access_records(records, secret=fixture_signing_key(seed))
    truth = {
        row["session_id"]: row
        for row in map(
            json.loads,
            (snapshot_path.parent / "truth.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    for session in sessions:
        native_id = stable_id(session)
        reference = truth[native_id]
        session = replace(session, id=native_id)
        digest = session_digest(session)
        source_id = f"synthetic/{manifest_digest}/{reference['run_id']}"
        campaign = reference["campaign_group"]
        example = GroupedExample(
            source_id,
            native_id,
            digest,
            session.started_at,
            session.ended_at,
            reference["actor_id"],
            reference["run_id"],
            (campaign,) if campaign else (),
        )
        key = _add(
            result,
            seen,
            session,
            example,
            {
                "cohort": "simulation",
                "truth": reference["traffic_truth"],
                "truth_source": "generator_reference_intent",
                "profile": reference["profile"],
                "automation_truth": reference["automation_truth"],
                "maliciousness_truth": reference["maliciousness_truth"],
                "reference_source": "known_public_generator_template",
                "genuinely_hidden_attack": "unavailable",
                "provenance_digest": manifest_digest,
                "source_metadata_digest": _digest(data),
                "manifest_digest": manifest_digest,
            },
            (),
        )
        _runtime(
            result,
            key,
            session,
            {
                "availability": "synthetic_offline",
                "session_digest": digest,
                "config_digest": capture_configuration(())["trap_config_version"],
                "captured_at": session.ended_at.isoformat(),
                "effective": {
                    "intel": asdict(IpIntel()),
                    "traps": [],
                    "provenance": {
                        "availability": "unavailable",
                        "intel_enabled": False,
                        "observation": None,
                    },
                },
            },
            synthetic=True,
        )
        if reference["traffic_truth"] is not None:
            result.rows.append(
                DatasetRow(
                    key,
                    session.started_at,
                    compute_features(session),
                    reference["traffic_truth"],
                    reference["profile"],
                    "sim",
                    "simulated",
                    run_id=reference["run_id"],
                    campaign_id=campaign,
                    source_id=source_id,
                    external_session_id=native_id,
                    actor_id=reference["actor_id"],
                    ended_at=session.ended_at,
                    session_digest=digest,
                    group_ids=("actor:" + reference["actor_id"], "run:" + reference["run_id"])
                    + (("campaign:" + campaign,) if campaign else ()),
                )
            )
    return size


def build_references(
    reviewed: Sequence[ReviewedSession],
    collections: Sequence[dict],
    synthetic_manifests: Sequence[Path],
    *,
    evidence_profile="offline",
) -> ReferenceSet:
    """Map freshly guarded approvals and verified generator bundles to native references."""
    _bounded(reviewed, MAX_OBSERVATIONS, "reviewed observations")
    _bounded(collections, MAX_COLLECTIONS, "collections")
    _bounded(synthetic_manifests, 10, "synthetic manifests")
    if evidence_profile not in ("offline", "captured"):
        raise ValueError("Invalid native reference evidence profile")
    selected = {}
    for collection in collections:
        if not isinstance(collection, dict) or set(collection) != {
            "source_key",
            "run_id",
            "campaign_ids",
        }:
            raise ValueError("collections require source_key, run_id and campaign_ids")
        source, run = collection["source_key"], collection["run_id"]
        _identifier(source)
        if source in selected:
            raise ValueError("duplicate collection source")
        if run is not None:
            _identifier(run)
        selected[source] = run, _campaigns(collection["campaign_ids"])
    result = ReferenceSet([], {}, [], {}, {}, tuple(sorted(selected)))
    seen: set[tuple[str, str]] = set()
    _study(result, reviewed, selected, seen, evidence_profile)
    with TemporaryDirectory(prefix="bouncer-native-references-") as temporary:
        used = 0
        for index, manifest in enumerate(synthetic_manifests):
            if not isinstance(manifest, Path):
                raise ValueError("synthetic manifests must be Path objects")
            directory = Path(temporary) / str(index)
            directory.mkdir()
            try:
                used += _synthetic(result, manifest, directory, MAX_BUNDLE_BYTES - used, seen)
            except (OSError, KeyError, TypeError, UnicodeError, RecursionError) as exc:
                raise ValueError("invalid native generator bundle") from exc
    return result
