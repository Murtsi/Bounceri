"""Source-validated native freezes and durable, one-shot private evaluation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

from bouncer.db.evaluations import EvaluationLedger
from bouncer.db.participants import StudyStore
from bouncer.eval.frozen_analysis import (
    evaluate_in_worker,
    prepare_in_worker,
    validate_artifacts,
    validate_report,
)
from bouncer.eval.native_fixtures import outside_repository
from bouncer.eval.partition import ROLES, _identifier, partition_examples
from bouncer.eval.reference import MAX_COLLECTIONS, build_references
from bouncer.eval.source_registry import checksum

MAX_PLAN_BYTES = 256 * 1024


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _dependency_fingerprint(name):
    distribution = importlib.metadata.distribution(name)
    base = Path(distribution.locate_file("")).resolve()
    if distribution.files is None:
        raise ValueError("evaluation dependency has no file manifest")
    files = {}
    for relative in distribution.files:
        relative = Path(relative)
        if not (relative.suffix in {".py", ".pyd", ".dll", ".dylib"}
                or ".so" in relative.name or relative.name in {"METADATA", "RECORD"}):
            continue
        actual = Path(distribution.locate_file(relative)).resolve()
        if not actual.is_relative_to(base) or not actual.is_file():
            raise ValueError("evaluation dependency file is unavailable")
        files[relative.as_posix()] = checksum(actual)["sha256"]
    return {"version": distribution.version, "files": dict(sorted(files.items()))}


def _dependencies():
    pending = ["fastapi", "httpx", "psycopg", "sqlalchemy", "uvicorn"]
    seen, result = set(), {}
    while pending:
        name = re.sub(r"[-_.]+", "-", pending.pop()).lower()
        if name in seen:
            continue
        seen.add(name)
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        result[name] = _dependency_fingerprint(name)
        # Include installed optional requirements too, avoiding a second marker evaluator.
        for requirement in distribution.requires or ():
            match = re.match(r"[A-Za-z0-9][A-Za-z0-9_.-]*", requirement)
            if match is None:
                raise ValueError("invalid evaluation dependency metadata")
            pending.append(match[0])
    return dict(sorted(result.items()))


def fingerprint() -> dict:
    package = Path(__file__).resolve().parents[1]
    paths = {package / "contracts.py"}
    for directory in ("session", "network", "ingest"):
        paths.update((package / directory).rglob("*.py"))
    for name in ("frozen", "frozen_cli", "frozen_analysis", "reference", "partition", "study",
                 "evaluate", "dataset", "native_fixtures", "source_registry"):
        path = package / "eval" / (name + ".py")
        if path.is_file():
            paths.add(path)
    for name in ("participants", "evaluations", "traffic", "migrate", "store"):
        paths.add(package / "db" / (name + ".py"))
    code = {str(path.relative_to(package)).replace("\\", "/"):
            hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}
    dependencies = _dependencies()
    locks = {}
    for name in ("uv.lock", "pyproject.toml", "deploy/requirements-runtime.txt"):
        path = package.parent.parent / name
        if path.is_file():
            locks[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    runtime_paths = {Path(getattr(sys, "_base_executable", sys.executable)).resolve()}
    if getattr(math, "__file__", None):
        runtime_paths.add(Path(math.__file__).resolve())
    runtime_paths.update(Path(sys.base_prefix).glob("python*.dll"))
    runtime_files = {path.name: checksum(path)["sha256"] for path in sorted(runtime_paths)}
    return {"code": code, "dependencies": dependencies, "lockfiles": locks,
            "python": platform.python_version(), "implementation": sys.implementation.name,
            "platform": sys.platform, "machine": platform.machine(), "runtime_files": runtime_files}


def _plan(value):
    if (type(value) is not dict or set(value) - {"evidence_profile"} != {
        "schema_version", "detector", "collections", "synthetic_manifests", "windows",
        } or value["schema_version"] != "frozen-native-plan-v1"
            or type(value["detector"]) is not str
            or value["detector"] not in {"rules", "logistic"}
            or type(value.get("evidence_profile", "offline")) is not str
            or value.get("evidence_profile", "offline") not in {"offline", "captured"}):
        raise ValueError("invalid frozen native plan")
    # Round-trip before reading sources: no aliases, arbitrary objects or non-finite metadata.
    try:
        raw = json.dumps(value, allow_nan=False)
        if len(raw.encode()) > MAX_PLAN_BYTES:
            raise ValueError("plan exceeds limit")
        value = json.loads(raw)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError("invalid frozen native plan") from None
    if (type(value["synthetic_manifests"]) is not list
            or len(value["synthetic_manifests"]) > 10
            or any(type(path) is not str or not path or "\0" in path
                   for path in value["synthetic_manifests"])
            or type(value["windows"]) is not dict or set(value["windows"]) != set(ROLES)):
        raise ValueError("invalid frozen native plan")
    collections = value["collections"]
    if type(collections) is not list or len(collections) > MAX_COLLECTIONS:
        raise ValueError("invalid frozen collection plan")
    seen = set()
    for collection in collections:
        if (type(collection) is not dict
                or set(collection) != {"source_key", "run_id", "campaign_ids"}):
            raise ValueError("invalid frozen collection plan")
        _identifier(collection["source_key"])
        if collection["source_key"] in seen:
            raise ValueError("duplicate frozen collection source")
        seen.add(collection["source_key"])
        if collection["run_id"] is not None:
            _identifier(collection["run_id"])
        campaigns = collection["campaign_ids"]
        if campaigns is not None:
            if type(campaigns) is not list or len(campaigns) > 64:
                raise ValueError("invalid frozen campaign groups")
            for campaign in campaigns:
                _identifier(campaign)
            collection["campaign_ids"] = sorted(set(campaigns))
    value["collections"] = sorted(collections, key=lambda row: row["source_key"])
    windows = {}
    for role in ROLES:
        window = value["windows"][role]
        if type(window) is not dict or set(window) != {"from", "until"}:
            raise ValueError("invalid frozen native windows")
        try:
            windows[role] = tuple(datetime.fromisoformat(window[name].replace("Z", "+00:00"))
                                  for name in ("from", "until"))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("invalid frozen native windows") from None
    # Validate windows even when a collection has no usable observations.
    value["windows"] = partition_examples([], windows)["windows"]
    try:
        paths = [str(outside_repository(Path(path))) for path in value["synthetic_manifests"]]
    except (OSError, ValueError, RuntimeError):
        raise ValueError("invalid private synthetic source path") from None
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate synthetic source path")
    value["synthetic_manifests"] = sorted(paths)
    return value, windows


def _units(partition):
    assignments = {"development": set(), "holdout": set()}
    for role in ROLES:
        destination = assignments["holdout" if role == "test" else "development"]
        for key in partition["roles"][role]:
            row = partition["examples"][key]
            destination.add(digest(["native_identity", row["source_id"], row["session_id"]]))
            destination.add(digest(["actor", row["actor_id"]]))
            destination.add(digest(["run", row["run_id"]]))
            destination.update(digest(["campaign", campaign]) for campaign in row["campaign_ids"])
    return assignments


class FrozenEvaluator:
    def __init__(self, study: StudyStore):
        self.study = study
        self.ledger = EvaluationLedger(study.engine)

    def _references(self, conn, plan, windows):
        collections = plan["collections"]
        if type(collections) is not list or any(type(row) is not dict for row in collections):
            raise ValueError("invalid frozen collection plan")
        sources = [row.get("source_key") for row in collections]
        current = self.study._load_approved_connection(conn, sources)
        references = build_references(current, collections,
                                      [Path(path) for path in plan["synthetic_manifests"]],
                                      evidence_profile=plan.get("evidence_profile", "offline"))
        partition = partition_examples(references.examples, windows)
        if not partition["roles"]["test"]:
            raise ValueError("no eligible native holdout observations")
        return references, partition

    def _descriptor(self, plan, partition, references):
        return {"schema_version": "frozen-native-preparation-v1", "plan": plan,
                "partition": partition, "references": references.metadata,
                "fingerprint": fingerprint()}

    def _current(self, conn, record):
        if record["state"] == "revoked":
            raise ValueError("evaluation preparation is revoked")
        descriptor = record["descriptor"]
        if descriptor.get("fingerprint") != fingerprint():
            raise ValueError("evaluation fingerprint changed")
        plan, windows = _plan(descriptor["plan"])
        references, partition = self._references(conn, plan, windows)
        if digest(self._descriptor(plan, partition, references)) != record["preparation_id"]:
            raise ValueError("evaluation references changed")
        return references, partition

    def prepare(self, plan):
        plan, windows = _plan(plan)
        with self.study._transaction() as conn:
            references, partition = self._references(conn, plan, windows)
            if plan["detector"] == "logistic":
                for role in ("fit", "calibration"):
                    rows = [row for row in references.rows
                            if row.session_id in partition["roles"][role]]
                    if {row.truth == "human" for row in rows} != {True, False}:
                        raise ValueError("logistic preparation requires both reference classes")
                    if any(references.unavailable_fields[row.session_id] for row in rows):
                        raise ValueError("logistic preparation has incomplete labeled evidence")
            assignments = _units(partition)
            record = self.ledger.reserve(
                descriptor=self._descriptor(plan, partition, references),
                development_units=assignments["development"], holdout_units=assignments["holdout"],
                source_keys=references.source_ids, connection=conn,
            )
        if record["state"] != "reserved":
            return record
        # The reservation commits before fitting; consent/source locks cover the bounded fit.
        with self.study._transaction() as conn:
            references, partition = self._current(conn, record)
            analysis = prepare_in_worker(
                references, partition, detector=plan["detector"],
                evidence_profile=plan.get("evidence_profile", "offline"),
            )
            validate_artifacts(analysis)
            if analysis["config"]["evidence_profile"] != plan.get("evidence_profile", "offline"):
                raise ValueError("candidate evidence profile changed during preparation")
            if (analysis["detector"] != plan["detector"]
                    or fingerprint() != record["descriptor"]["fingerprint"]):
                raise ValueError("candidate fingerprint changed during preparation")
            artifacts = {"schema_version": "frozen-native-candidate-v1",
                         "fingerprint": record["descriptor"]["fingerprint"], "analysis": analysis}
            return self.ledger.set_artifacts(record["preparation_id"], artifacts=artifacts,
                                             connection=conn)

    def _artifacts(self, record):
        artifacts = record["artifacts"]
        if (type(artifacts) is not dict or set(artifacts) != {
            "schema_version", "fingerprint", "analysis",
        } or artifacts["schema_version"] != "frozen-native-candidate-v1"
                or digest(artifacts) != record["artifact_digest"]
                or artifacts["fingerprint"] != record["descriptor"]["fingerprint"]):
            raise ValueError("frozen evaluation artifact changed")
        if artifacts["analysis"].get("detector") != record["descriptor"]["plan"]["detector"]:
            raise ValueError("frozen evaluation detector changed")
        analysis = validate_artifacts(artifacts["analysis"])
        if analysis["config"]["evidence_profile"] != record["descriptor"]["plan"].get(
            "evidence_profile", "offline",
        ):
            raise ValueError("frozen evaluation evidence profile changed")
        return analysis

    def evaluate(self, preparation_id):
        record = self.ledger.get(preparation_id)
        with self.study._transaction() as conn:
            references, partition = self._current(conn, record)
            analysis = self._artifacts(record)
            claim = self.ledger.claim(preparation_id, artifact_digest=record["artifact_digest"],
                                      connection=conn)
        if claim["cached"]:
            report = validate_report(references, partition, analysis, claim["report"])
            if digest(report) != claim["report_digest"]:
                raise ValueError("cached evaluation report differs from current references")
            return {"preparation_id": preparation_id, "artifact_digest": record["artifact_digest"],
                    "report_digest": claim["report_digest"], "cached": True, "report": report}
        # Claim is durable before test CPU; active claims block withdrawal/purge.
        try:
            report = evaluate_in_worker(references, partition, analysis)
        except BaseException as exc:
            code = "interrupted" if not isinstance(exc, Exception) else "analysis_failed"
            self.ledger.finish(preparation_id, artifact_digest=record["artifact_digest"],
                               failure_code=code)
            if not isinstance(exc, Exception):
                raise
            raise ValueError("frozen native analysis failed; holdout remains consumed") from None
        try:
            with self.study._transaction() as conn:
                current = self.ledger.get(preparation_id, connection=conn)
                references, partition = self._current(conn, current)
                report = validate_report(references, partition, analysis, report)
                completed = self.ledger.finish(preparation_id,
                                                artifact_digest=record["artifact_digest"],
                                                report=report, connection=conn)
        except Exception:
            self.ledger.finish(preparation_id, artifact_digest=record["artifact_digest"],
                               failure_code="validation_failed")
            raise ValueError("frozen native validation failed; holdout remains consumed") from None
        return {"preparation_id": preparation_id, "artifact_digest": record["artifact_digest"],
                "report_digest": completed["report_digest"], "cached": False,
                "report": completed["report"]}

    def close_interrupted(self, preparation_id, *, confirm_worker_stopped):
        if confirm_worker_stopped is not True:
            raise ValueError("confirm evaluation worker is stopped")
        record = self.ledger.get(preparation_id)
        return self.ledger.finish(preparation_id, artifact_digest=record["artifact_digest"],
                                   failure_code="interrupted")
