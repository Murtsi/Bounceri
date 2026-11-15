"""Bounded offline native fitting and frozen test scoring; no publication path.

The caller owns consent, source revalidation, reservation and immutable receipts.
Only admitted role observations enter context; worker preparation physically
receives no holdout observations. Missing native evidence is never imputed.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime
from types import SimpleNamespace

from bouncer.contracts import Request, Session, Verdict
from bouncer.eval.evaluate import Thresholds, apply_thresholds, choose_thresholds, wilson_upper
from bouncer.eval.partition import ROLES, partition_examples
from bouncer.ingest.import_analysis import _Session, run_analysis
from bouncer.network.campaigns import find_campaigns
from bouncer.session import model as mdl
from bouncer.session.features import compute_features
from bouncer.session.score import score

MAX_BYTES = 16 * 1024**2
MAX_SESSIONS = 6000
MAX_REQUESTS = 20000
CONFIG = {"dns": False, "traps": False, "context": "role-and-declared-run",
          "missing_evidence": "unavailable"}
VARIANTS = {"with_network": True, "without_network": False}
LABELS = {"human", "good_bot", "bad_bot", "uncertain"}


def _keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError("Invalid frozen native schema")


def _number(value, *, probability=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or probability and not 0 <= value <= 1):
        raise ValueError("Invalid frozen native number")


def _encode(value):
    try:
        data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise ValueError("Invalid frozen native JSON") from None
    if len(data) > MAX_BYTES:
        raise ValueError("Frozen native payload exceeds 16 MiB")
    return data


def _decode(payload):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate frozen native JSON key")
            result[key] = value
        return result

    if type(payload) is not bytes or len(payload) > MAX_BYTES:
        raise ValueError("Invalid frozen native output size")
    try:
        return json.loads(payload, object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ValueError("Nonfinite frozen native JSON")))
    except (UnicodeError, RecursionError):
        raise ValueError("Invalid frozen native JSON") from None


def _roles(refs, partition):
    roles = partition.get("roles")
    _keys(roles, ROLES)
    seen = set()
    for keys in roles.values():
        if type(keys) is not list or any(type(k) is not str for k in keys):
            raise ValueError("Invalid frozen native role keys")
        if len(set(keys)) != len(keys) or seen.intersection(keys):
            raise ValueError("Duplicate frozen native role keys")
        seen.update(keys)
    if (not seen <= refs.sessions.keys() or not seen <= refs.metadata.keys()
            or not seen <= refs.unavailable_fields.keys()
            or len(refs.sessions) > MAX_SESSIONS
            or sum(len(s.requests) for s in refs.sessions.values()) > MAX_REQUESTS):
        raise ValueError("Invalid or oversized frozen native references")
    for key in seen:
        md = refs.metadata[key]
        if (not re.fullmatch(r"[0-9a-f]{64}", key) or refs.sessions[key].id != key
                or md.get("cohort") not in {"human_study", "simulation"}
                or md.get("truth") not in {None, "human", "good_bot", "bad_bot"}
                or not isinstance(md.get("run_id"), str) or not md["run_id"]
                or not isinstance(md.get("actor_id"), str) or not md["actor_id"]
                or type(refs.unavailable_fields[key]) not in (list, tuple)
                or any(type(v) is not str for v in refs.unavailable_fields[key])):
            raise ValueError("Invalid frozen native observation metadata")
    return roles


def _verify_partition(refs, partition):
    try:
        windows = {r: (datetime.fromisoformat(partition["windows"][r]["from"]),
                       datetime.fromisoformat(partition["windows"][r]["until"])) for r in ROLES}
        expected = partition_examples(refs.examples, windows)
        if partition != expected or set(refs.sessions) != set(expected["examples"]):
            raise ValueError("Frozen native partition differs from current references")
        roles = _roles(refs, partition)
        for key in (k for keys in roles.values() for k in keys):
            if any(refs.metadata[key][field] != expected["examples"][key][field]
                   for field in ("actor_id", "run_id")):
                raise ValueError("Frozen native reference metadata differs from partition")
    except (TypeError, KeyError, AttributeError):
        raise ValueError("Invalid frozen native partition") from None


def _contexts(refs, keys):
    runs = {}
    for key in keys:
        if not refs.unavailable_fields[key]:
            runs.setdefault(refs.metadata[key]["run_id"], []).append(refs.sessions[key])
    result = {}
    for sessions in runs.values():
        ids = {s.id for s in sessions}
        for campaign in find_campaigns(sessions):
            if not set(campaign.session_ids) <= ids:
                raise ValueError("Campaign crossed frozen native context")
            for sid in campaign.session_ids:
                result.setdefault(sid, campaign)
    return result


def validate_artifacts(artifacts):
    """Validate every coefficient and explicit offline option; return a detached copy."""
    _keys(artifacts, {"schema_version", "detector", "config", "variants"})
    _keys(artifacts["config"], CONFIG)
    if (artifacts["schema_version"] != "frozen-native-artifacts-v1"
            or artifacts["detector"] not in {"rules", "logistic"}
            or any(type(artifacts["config"][key]) is not type(value)
                   or artifacts["config"][key] != value for key, value in CONFIG.items())):
        raise ValueError("Invalid frozen native artifact configuration")
    _keys(artifacts["variants"], VARIANTS)
    for name, network in VARIANTS.items():
        variant = artifacts["variants"][name]
        _keys(variant, {"network", "model", "thresholds"})
        if variant["network"] is not network:
            raise ValueError("Invalid frozen native ablation")
        model, thresholds = variant["model"], variant["thresholds"]
        if artifacts["detector"] == "rules":
            if model is not None or thresholds is not None:
                raise ValueError("Rules artifacts cannot contain a model")
            continue
        _keys(thresholds, {"bot", "human", "calibrated", "note"})
        if thresholds["calibrated"] is not True or type(thresholds["note"]) is not str:
            raise ValueError("Frozen native thresholds are not calibrated")
        for key in ("bot", "human"):
            if thresholds[key] is not None:
                _number(thresholds[key], probability=True)
        if (thresholds["bot"] is not None and thresholds["human"] is not None
                and thresholds["human"] >= thresholds["bot"]):
            raise ValueError("Invalid frozen native threshold order")
        _keys(model, {"model_version", "kind", "names", "means", "stds", "weights",
                      "bias", "network", "thresholds", "trained"})
        if (model["kind"] != "logistic_regression" or model["model_version"] != mdl.MODEL_VERSION
                or model["network"] is not network
                or model["names"] != list(mdl.feature_names(network))
                or model["thresholds"] != {k: thresholds[k] for k in ("bot", "human")}
                or model["trained"] != {}):
            raise ValueError("Invalid frozen native model configuration")
        for key in ("means", "stds", "weights"):
            values = model[key]
            if type(values) is not list or len(values) != len(mdl.feature_names(network)):
                raise ValueError("Invalid frozen native model vector length")
            for value in values:
                _number(value)
                if key == "stds" and value <= 0:
                    raise ValueError("Invalid frozen native standard deviation")
        _number(model["bias"])
        mdl.LogisticModel.from_dict(model)
    return _decode(_encode(artifacts))


def prepare_artifacts(refs, partition, *, detector):
    """Fit only admitted fit rows and choose thresholds only on calibration rows."""
    roles = _roles(refs, partition)
    if detector not in {"rules", "logistic"}:
        raise ValueError("Frozen native detector must be rules or logistic")
    result = {"schema_version": "frozen-native-artifacts-v1", "detector": detector,
              "config": CONFIG.copy(), "variants": {}}
    labeled = {}
    if detector == "logistic":
        for role in ("fit", "calibration"):
            labeled[role] = [k for k in roles[role] if refs.metadata[k]["truth"] is not None]
            if any(refs.unavailable_fields[k] for k in labeled[role]):
                raise ValueError("Frozen native labeled rows have incomplete or missing evidence")
            classes = {refs.metadata[k]["truth"] == "human" for k in labeled[role]}
            if classes != {True, False}:
                raise ValueError("Frozen native fit and calibration require human and bot classes")
    contexts = ({role: _contexts(refs, roles[role]) for role in ("fit", "calibration")}
                if detector == "logistic" else {})
    for name, network in VARIANTS.items():
        variant = {"network": network, "model": None, "thresholds": None}
        if detector == "logistic":
            vectors = [mdl.vectorize(compute_features(refs.sessions[k]), None,
                                     contexts["fit"].get(k) if network else None, network)
                       for k in labeled["fit"]]
            model = mdl.fit(vectors, [int(refs.metadata[k]["truth"] != "human")
                                      for k in labeled["fit"]], network=network)
            humans, bots = [], []
            for key in labeled["calibration"]:
                probability = model.predict_proba(mdl.vectorize(
                    compute_features(refs.sessions[key]), None,
                    contexts["calibration"].get(key) if network else None, network))
                (humans if refs.metadata[key]["truth"] == "human" else bots).append(probability)
            thresholds = choose_thresholds(humans, bots)
            if not thresholds.calibrated:
                raise ValueError("Frozen native calibration unavailable")
            model.thresholds = {"bot": thresholds.bot, "human": thresholds.human}
            variant.update(model=model.to_dict(), thresholds=asdict(thresholds))
        result["variants"][name] = variant
    return validate_artifacts(result)


def _rate(k, n):
    return k / n if n else None


def _proportion(k, n):
    return {"numerator": k, "denominator": n, "value": _rate(k, n),
            "ci95_lower": max(0., 1-wilson_upper(n-k, n)) if n else None,
            "ci95_upper": wilson_upper(k, n)}


def _cohort(refs, keys, predictions):
    supported = [k for k in keys if predictions[k]["status"] == "available"]
    known = [k for k in supported if refs.metadata[k]["truth"] is not None]
    unknown = [k for k in keys if refs.metadata[k]["truth"] is None]
    unknown_supported = [k for k in supported if refs.metadata[k]["truth"] is None]
    truth_labels = ("human", "good_bot", "bad_bot")
    confusion = {truth: {pred: sum(refs.metadata[k]["truth"] == truth
                                  and predictions[k]["label"] == pred for k in known)
                         for pred in (*truth_labels, "uncertain")} for truth in truth_labels}
    per_class = {label: {
        "precision": _proportion(confusion[label][label],
                                 sum(row[label] for row in confusion.values())),
        "recall": _proportion(confusion[label][label], sum(confusion[label].values())),
    } for label in truth_labels}
    benign_automated = [k for k in supported if refs.metadata[k].get("behavior") == "automated"
                        and refs.metadata[k].get("intent") == "benign"]
    humans = [k for k in supported if refs.metadata[k]["truth"] == "human"]
    false_alarms = [k for k in humans if predictions[k]["label"] in {"bad_bot", "good_bot"}]
    subjects = {refs.metadata[k]["actor_id"] for k in humans}
    flagged_subjects = {refs.metadata[k]["actor_id"] for k in false_alarms}
    n, fp = len(humans), len(false_alarms)
    return {
        "n": len(keys), "available": len(supported), "missing_evidence": len(keys)-len(supported),
        "coverage": _rate(len(supported), len(keys)),
        "truth_counts": {label: sum(refs.metadata[k]["truth"] == label for k in keys)
                         for label in truth_labels},
        "known_reference_available": len(known),
        "known_reference_coverage": _rate(len(known), len(keys)-len(unknown)),
        "unknown_truth": len(unknown), "unknown_truth_available": len(unknown_supported),
        "unknown_truth_coverage": _rate(len(unknown_supported), len(unknown)),
        "confusion": confusion, "per_class": per_class,
        "human_fpr_numerator": fp, "human_fpr_denominator": n, "human_fpr": _rate(fp, n),
        "human_fpr_ci95_lower": max(0., 1-wilson_upper(n-fp, n)) if n else None,
        "human_fpr_ci95_upper": wilson_upper(fp, n),
        "uncertain": sum(predictions[k]["label"] == "uncertain" for k in supported),
        "uncertain_share": _proportion(
            sum(predictions[k]["label"] == "uncertain" for k in supported), len(supported)),
        "known_benign_automated_bad_flags": _proportion(
            sum(predictions[k]["label"] == "bad_bot" for k in benign_automated),
            len(benign_automated)),
        "unknown_intent_bad_flags": sum(
            refs.metadata[k]["truth"] is None and refs.metadata[k].get("intent") == "unknown"
            and predictions[k]["label"] == "bad_bot" for k in supported),
        "unique_actors": len({refs.metadata[k]["actor_id"] for k in keys}),
        "unique_runs": len({refs.metadata[k]["run_id"] for k in keys}),
        "human_subject_any_bot_false_alarm_numerator": len(flagged_subjects),
        "human_subject_any_bot_false_alarm_denominator": len(subjects),
        "human_subject_any_bot_false_alarm_rate": _rate(len(flagged_subjects), len(subjects)),
        "human_subject_any_bot_false_alarm_ci95_upper": wilson_upper(
            len(flagged_subjects), len(subjects)),
        "uncertainty": "Session Wilson intervals are descriptive; repeated sessions and shared "
                       "runs are not independent subjects. Small support cannot establish quality.",
    }


def _report(refs, roles, artifacts, predictions):
    return {"schema_version": "frozen-native-report-v1", "detector": artifacts["detector"],
            "variants": {name: {"predictions": predictions[name], "cohorts": {
                cohort: _cohort(refs, [k for k in roles["test"]
                                      if refs.metadata[k]["cohort"] == cohort], predictions[name])
                for cohort in ("human_study", "simulation")}} for name in VARIANTS},
            "public_robot": {"status": "unavailable"},
            "genuinely_hidden_attack": {"status": "unavailable"}, "production_quality": None}


def evaluate_artifacts(refs, partition, artifacts):
    """Score admitted test context using frozen bytes; never fit or recalibrate."""
    roles = _roles(refs, partition)
    artifacts = validate_artifacts(artifacts)
    contexts = _contexts(refs, roles["test"])
    predictions = {}
    for name, network in VARIANTS.items():
        variant = artifacts["variants"][name]
        model = mdl.LogisticModel.from_dict(variant["model"]) if variant["model"] else None
        predictions[name] = {}
        for key in roles["test"]:
            if refs.unavailable_fields[key]:
                prediction = {"status": "missing_evidence", "label": None, "score": None}
            else:
                verdict = score(refs.sessions[key], None, contexts.get(key) if network else None,
                                traps=frozenset(), model=model)
                prediction = {"status": "available", "score": verdict.score,
                              "label": verdict.label}
            predictions[name][key] = prediction
    return validate_report(refs, partition, artifacts, _report(refs, roles, artifacts, predictions))


def validate_report(refs, partition, artifacts, report):
    """Check exact prediction ownership; recompute aggregates from parent references."""
    roles = _roles(refs, partition)
    artifacts = validate_artifacts(artifacts)
    _keys(report, {"schema_version", "detector", "variants", "public_robot",
                   "genuinely_hidden_attack", "production_quality"})
    if (report["schema_version"] != "frozen-native-report-v1"
            or report["detector"] != artifacts["detector"]
            or report["public_robot"] != {"status": "unavailable"}
            or report["genuinely_hidden_attack"] != {"status": "unavailable"}
            or report["production_quality"] is not None):
        raise ValueError("Invalid frozen native report")
    _keys(report["variants"], VARIANTS)
    predictions = {}
    for name in VARIANTS:
        variant = report["variants"][name]
        _keys(variant, {"predictions", "cohorts"})
        _keys(variant["predictions"], roles["test"])
        predictions[name] = variant["predictions"]
        frozen = artifacts["variants"][name]
        for key, prediction in predictions[name].items():
            _keys(prediction, {"status", "label", "score"})
            if refs.unavailable_fields[key]:
                if prediction != {"status": "missing_evidence", "label": None, "score": None}:
                    raise ValueError("Invalid frozen native missing evidence prediction")
            else:
                if prediction["status"] != "available" or prediction["label"] not in LABELS:
                    raise ValueError("Invalid frozen native prediction")
                _number(prediction["score"], probability=True)
                if frozen["thresholds"] is not None:
                    expected = apply_thresholds(
                        Verdict("uncertain", prediction["score"], (), mdl.MODEL_VERSION),
                        Thresholds(**frozen["thresholds"]))
                    if (prediction["label"] != expected
                            and (prediction["label"], prediction["score"]) != ("bad_bot", 1.0)):
                        raise ValueError("Frozen native label disagrees with thresholds")
                elif (prediction["label"], prediction["score"]) not in {
                        ("bad_bot", 1.0), ("uncertain", .5)}:
                    raise ValueError("Frozen native label disagrees with offline rules")
    return _decode(_encode(_report(refs, roles, artifacts, predictions)))


def _packet(refs, partition, *, operation, detector, artifacts):
    roles = _roles(refs, partition)
    selected_roles = ("fit", "calibration") if operation == "prepare" else ("test",)
    selected = [k for role in selected_roles for k in roles[role]]
    fields = {"cohort", "truth", "actor_id", "run_id", "intent", "behavior"}
    return {"operation": operation, "detector": detector, "artifacts": artifacts,
            "roles": {r: roles[r] if r in selected_roles else [] for r in ROLES},
            "sessions": {k: _Session.model_validate(asdict(refs.sessions[k]) | {
                "requests": [asdict(r) for r in refs.sessions[k].requests]}).model_dump(mode="json")
                         for k in selected},
            "metadata": {k: {f: v for f, v in refs.metadata[k].items() if f in fields}
                         for k in selected},
            "unavailable_fields": {k: list(refs.unavailable_fields[k]) for k in selected}}


def _execute(packet):
    _keys(packet, {"operation", "detector", "artifacts", "roles", "sessions", "metadata",
                   "unavailable_fields"})
    if packet["operation"] not in {"prepare", "evaluate"}:
        raise ValueError("Invalid frozen native operation")
    sessions = {}
    if type(packet["sessions"]) is not dict or len(packet["sessions"]) > MAX_SESSIONS:
        raise ValueError("Invalid frozen native sessions")
    for key, value in packet["sessions"].items():
        dto = _Session.model_validate_json(_encode(value))
        if (dto.ended_at < dto.started_at or dto.id != key
                or any(r.ip != dto.ip or r.user_agent != dto.user_agent
                       or not dto.started_at <= r.ts <= dto.ended_at
                       or any(h.lower() in {"x-sim-run", "x-sim-sig"} for h in r.headers)
                       for r in dto.requests)):
            raise ValueError("Invalid frozen native session")
        sessions[key] = Session(dto.id, dto.ip, dto.user_agent, dto.started_at, dto.ended_at,
                                tuple(Request(**r.model_dump()) for r in dto.requests))
    _keys(packet["metadata"], sessions)
    _keys(packet["unavailable_fields"], sessions)
    for md in packet["metadata"].values():
        if (type(md) is not dict or not {"cohort", "truth", "actor_id", "run_id"} <= md.keys()
                or not md.keys() <= {"cohort", "truth", "actor_id", "run_id",
                                     "intent", "behavior"}):
            raise ValueError("Invalid frozen native metadata DTO")
    refs = SimpleNamespace(sessions=sessions, metadata=packet["metadata"],
                           unavailable_fields=packet["unavailable_fields"])
    partition = {"roles": packet["roles"]}
    roles = _roles(refs, partition)
    if set(sessions) != {k for keys in roles.values() for k in keys}:
        raise ValueError("Unassigned frozen native worker session")
    if packet["operation"] == "prepare":
        if roles["test"] or packet["artifacts"] is not None:
            raise ValueError("Preparation cannot receive holdout data")
        return prepare_artifacts(refs, partition, detector=packet["detector"])
    if roles["fit"] or roles["calibration"] or packet["detector"] is not None:
        raise ValueError("Evaluation cannot receive development data")
    return evaluate_artifacts(refs, partition, packet["artifacts"])


def _in_worker(refs, partition, *, operation, detector=None, artifacts=None, timeout=30):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("Frozen native timeout must be between zero and 30 seconds")
    started = time.monotonic()
    _verify_partition(refs, partition)
    if operation == "evaluate":
        artifacts = validate_artifacts(artifacts)
    data = _encode(_packet(refs, partition, operation=operation, detector=detector,
                           artifacts=artifacts))
    try:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired("frozen native", timeout)
        output = _decode(run_analysis(data, remaining,
                                      worker_module="bouncer.eval.frozen_analysis"))
        result = (validate_artifacts(output) if operation == "prepare"
                  else validate_report(refs, partition, artifacts, output))
        if operation == "prepare" and result["detector"] != detector:
            raise ValueError("Wrong frozen native detector")
        if time.monotonic() - started > timeout:
            raise subprocess.TimeoutExpired("frozen native", timeout)
        return result
    except subprocess.TimeoutExpired:
        raise ValueError("Frozen native analysis timed out") from None
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError("Frozen native analysis failed") from None


def prepare_in_worker(refs, partition, *, detector, timeout=30):
    return _in_worker(refs, partition, operation="prepare", detector=detector, timeout=timeout)


def evaluate_in_worker(refs, partition, artifacts, *, timeout=30):
    return _in_worker(refs, partition, operation="evaluate", artifacts=artifacts, timeout=timeout)


def main():
    try:
        if len(sys.argv) != 1:
            return 2
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        output = _encode(_execute(_decode(data)))
        sys.stdout.buffer.write(output)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
