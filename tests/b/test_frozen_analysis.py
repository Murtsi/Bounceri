"""Frozen CPU boundary: role ownership, unavailable evidence and strict IPC."""

import copy
import importlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bouncer.contracts import Request, Session
from bouncer.eval.partition import GroupedExample, partition_examples


def module():
    return importlib.import_module("bouncer.eval.frozen_analysis")


def fixture():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    refs = SimpleNamespace(
        examples=[], sessions={}, rows=[], metadata={}, unavailable_fields={}, source_ids=()
    )
    for index, role in enumerate(("fit", "calibration", "test")):
        for label in ("human", "bad_bot", None):
            native = f"{role}-{label}"
            digest = sha256(native.encode()).hexdigest()
            key = sha256(
                json.dumps(["source", native, digest], separators=(",", ":")).encode()
            ).hexdigest()
            ts = start + timedelta(days=index, hours=1)
            paths = ("/.env", "/wp-login.php") if label != "human" else ("/", "/home")
            requests = tuple(
                Request(
                    ts + timedelta(seconds=i),
                    "198.51.100.1",
                    "GET",
                    p,
                    200,
                    "Mozilla/5.0",
                    content_type="text/html",
                )
                for i, p in enumerate(paths)
            )
            refs.sessions[key] = Session(
                key, "198.51.100.1", "Mozilla/5.0", ts, requests[-1].ts, requests
            )
            refs.examples.append(
                GroupedExample("source", native, digest, ts, requests[-1].ts, native, role, ())
            )
            refs.metadata[key] = {
                "cohort": "human_study" if label is None else "simulation",
                "truth": label,
                "run_id": role,
                "actor_id": native,
                "intent": "unknown",
                "behavior": "automated",
            }
            refs.unavailable_fields[key] = ()
    windows = {
        role: (start + timedelta(days=i), start + timedelta(days=i + 1))
        for i, role in enumerate(("fit", "calibration", "test"))
    }
    return refs, partition_examples(refs.examples, windows)


def test_rules_prepare_never_scores_or_fits_and_test_reports_unknown_truth():
    m = module()
    refs, part = fixture()
    before = copy.deepcopy(refs)
    with (
        patch.object(m, "score", side_effect=AssertionError("prepare cannot score")),
        patch.object(m.mdl, "fit", side_effect=AssertionError("rules cannot fit")),
        patch.object(m, "find_campaigns", side_effect=AssertionError("no prepare contexts")),
    ):
        artifact = m.prepare_artifacts(refs, part, detector="rules")
    assert refs.__dict__ == before.__dict__
    with (
        patch("socket.getaddrinfo", side_effect=AssertionError("offline")),
        patch("bouncer.session.rules.load_traps", side_effect=AssertionError("no traps")),
        patch("bouncer.session.score._default_model", side_effect=AssertionError("no model")),
    ):
        report = m.evaluate_artifacts(refs, part, artifact)
    variant = report["variants"]["without_network"]
    assert set(variant["predictions"]) == set(part["roles"]["test"])
    study = variant["cohorts"]["human_study"]
    assert study["unknown_truth"] == 1 and study["human_fpr_denominator"] == 0
    assert study["unknown_intent_bad_flags"] == 1
    assert report["production_quality"] is None


def test_logistic_fits_only_fit_and_thresholds_only_calibration_twice():
    m = module()
    refs, part = fixture()
    vectors, fits, calibrations = [], [], []
    original_features = m.compute_features
    original_fit, original_choose = m.mdl.fit, m.choose_thresholds

    def features(session):
        assert session.id in part["roles"]["fit"] + part["roles"]["calibration"]
        vectors.append(session.id)
        return original_features(session)

    def fit(xs, ys, **kwargs):
        fits.append((copy.deepcopy(xs), ys, kwargs))
        assert len(xs) == 2 and set(ys) == {0, 1}
        return original_fit(xs, ys, **kwargs)

    def choose(humans, bots):
        calibrations.append((humans, bots))
        assert len(humans) == len(bots) == 1
        return original_choose(humans, bots)

    with (
        patch.object(m, "compute_features", side_effect=features),
        patch.object(m.mdl, "fit", side_effect=fit),
        patch.object(m, "choose_thresholds", side_effect=choose),
    ):
        artifacts = m.prepare_artifacts(refs, part, detector="logistic")
    assert len(fits) == len(calibrations) == 2
    assert {x[2]["network"] for x in fits} == {True, False}
    assert len(fits[0][0][0]) != len(fits[1][0][0])
    assert set(vectors) <= set(part["roles"]["fit"] + part["roles"]["calibration"])
    with patch.object(m.mdl, "fit", side_effect=AssertionError("frozen")):
        assert m.evaluate_artifacts(refs, part, artifacts)["variants"]


@pytest.mark.parametrize("role", ["fit", "calibration"])
def test_incomplete_labeled_development_rows_refused_before_any_fit(role):
    m = module()
    refs, part = fixture()
    key = next(k for k in part["roles"][role] if refs.metadata[k]["truth"] == "human")
    refs.unavailable_fields[key] = ("headers",)
    with (
        patch.object(m.mdl, "fit", side_effect=AssertionError("must validate first")),
        pytest.raises(ValueError, match="missing|incomplete"),
    ):
        m.prepare_artifacts(refs, part, detector="logistic")


def test_missing_test_evidence_unavailable_and_never_enters_context():
    m = module()
    refs, part = fixture()
    artifact = m.prepare_artifacts(refs, part, detector="rules")
    key = part["roles"]["test"][0]
    refs.unavailable_fields[key] = ("headers",)
    calls = []

    def campaigns(sessions):
        calls.append([s.id for s in sessions])
        assert key not in calls[-1]
        assert set(calls[-1]) <= set(part["roles"]["test"])
        return []

    with patch.object(m, "find_campaigns", side_effect=campaigns):
        report = m.evaluate_artifacts(refs, part, artifact)
    assert calls
    for variant in report["variants"].values():
        assert variant["predictions"][key] == {
            "status": "missing_evidence",
            "score": None,
            "label": None,
        }


@pytest.mark.parametrize("mutation", ["coefficient", "names", "network", "threshold", "extra"])
def test_artifact_mutations_refused(mutation):
    m = module()
    refs, part = fixture()
    artifact = m.prepare_artifacts(refs, part, detector="logistic")
    variant = artifact["variants"]["with_network"]
    if mutation == "coefficient":
        variant["model"]["weights"][0] = float("nan")
    elif mutation == "names":
        variant["model"]["names"].pop()
    elif mutation == "network":
        variant["network"] = False
    elif mutation == "threshold":
        variant["thresholds"]["calibrated"] = False
    else:
        artifact["extra"] = True
    with pytest.raises(ValueError):
        m.evaluate_artifacts(refs, part, artifact)


def test_prepare_ipc_physically_omits_test_and_excluded_observations():
    m = module()
    refs, part = fixture()
    secret_key = part["roles"]["test"][0]
    expected = m.prepare_artifacts(refs, part, detector="rules")

    def runner(data, timeout, **kwargs):
        packet = json.loads(data)
        assert secret_key not in data.decode()
        assert packet["roles"]["test"] == []
        assert set(packet["sessions"]) == set(part["roles"]["fit"] + part["roles"]["calibration"])
        assert all("source_id" not in md for md in packet["metadata"].values())
        assert kwargs == {"worker_module": "bouncer.eval.frozen_analysis"}
        return json.dumps(expected).encode()

    with patch.object(m, "run_analysis", side_effect=runner):
        assert m.prepare_in_worker(refs, part, detector="rules") == expected


def test_worker_roundtrip_and_parent_recomputes_aggregates():
    m = module()
    refs, part = fixture()
    artifact = m.prepare_in_worker(refs, part, detector="logistic")
    report = m.evaluate_in_worker(refs, part, artifact)
    assert report == m.evaluate_artifacts(refs, part, artifact)
    corrupted = copy.deepcopy(report)
    corrupted["variants"]["with_network"]["cohorts"]["simulation"]["n"] = 999
    with patch.object(m, "run_analysis", return_value=json.dumps(corrupted).encode()):
        assert m.evaluate_in_worker(refs, part, artifact) == report


@pytest.mark.parametrize("fault", ["missing", "extra", "nan", "availability"])
def test_worker_prediction_coverage_and_schema_strict(fault):
    m = module()
    refs, part = fixture()
    artifact = m.prepare_artifacts(refs, part, detector="rules")
    report = m.evaluate_artifacts(refs, part, artifact)
    predictions = report["variants"]["with_network"]["predictions"]
    key = next(iter(predictions))
    if fault == "missing":
        predictions.pop(key)
    elif fault == "extra":
        predictions["unexpected"] = predictions[key]
    elif fault == "nan":
        predictions[key]["score"] = float("nan")
    else:
        predictions[key] = {"status": "missing_evidence", "score": None, "label": None}
    with (
        patch.object(m, "run_analysis", return_value=json.dumps(report).encode()),
        pytest.raises(ValueError),
    ):
        m.evaluate_in_worker(refs, part, artifact)


def test_timeout_and_protocol_failures_sanitized():
    m = module()
    refs, part = fixture()
    for failure in (subprocess.TimeoutExpired("private", 1), OSError("private")):
        with (
            patch.object(m, "run_analysis", side_effect=failure),
            pytest.raises(ValueError, match="Frozen native") as exc,
        ):
            m.prepare_in_worker(refs, part, detector="rules")
        assert "private" not in str(exc.value)
    with (
        patch.object(m, "run_analysis", return_value=b"x" * (16 * 1024**2 + 1)),
        pytest.raises(ValueError),
    ):
        m.prepare_in_worker(refs, part, detector="rules")


def test_strict_worker_rejects_extra_fields_and_duplicate_json_keys():
    m = module()
    refs, part = fixture()
    packet = m._packet(refs, part, operation="prepare", detector="rules", artifacts=None)
    packet["ambient_model"] = "models/model.json"
    with pytest.raises(ValueError):
        m._execute(packet)
    with (
        patch.object(m, "run_analysis", return_value=b'{"schema_version":1,"schema_version":2}'),
        pytest.raises(ValueError),
    ):
        m.prepare_in_worker(refs, part, detector="rules")


def test_contexts_are_separate_for_every_role_and_declared_run_and_exclude_unknown_groups():
    m = module()
    refs, part = fixture()
    for index, md in enumerate(refs.metadata.values()):
        if md["truth"] is None:
            refs.examples[index] = replace(refs.examples[index], actor_id=None)
        else:
            md["run_id"] += "-" + md["truth"]
            refs.examples[index] = replace(refs.examples[index], run_id=md["run_id"])
    part = partition_examples(
        refs.examples,
        {
            r: (datetime.fromisoformat(w["from"]), datetime.fromisoformat(w["until"]))
            for r, w in part["windows"].items()
        },
    )
    calls = []

    def campaigns(sessions):
        calls.append({s.id for s in sessions})
        assert not calls[-1].intersection(part["exclusions"])
        assert len({refs.metadata[s.id]["run_id"] for s in sessions}) == 1
        return []

    with patch.object(m, "find_campaigns", side_effect=campaigns):
        artifact = m.prepare_artifacts(refs, part, detector="logistic")
        assert len(calls) == 4
        assert set.union(*calls) == set(part["roles"]["fit"] + part["roles"]["calibration"])
        calls.clear()
        m.evaluate_artifacts(refs, part, artifact)
        assert len(calls) == 2 and set.union(*calls) == set(part["roles"]["test"])


@pytest.mark.parametrize("role", ["fit", "calibration"])
def test_missing_class_never_fits_or_manufactures_thresholds(role):
    m = module()
    refs, part = fixture()
    for key in part["roles"][role]:
        if refs.metadata[key]["truth"] != "human":
            refs.metadata[key]["truth"] = None
    with (
        patch.object(m.mdl, "fit", side_effect=AssertionError("validate first")),
        pytest.raises(ValueError, match="classes"),
    ):
        m.prepare_artifacts(refs, part, detector="logistic")


def test_subject_false_alarm_denominator_uses_unique_actual_humans():
    m = module()
    refs, part = fixture()
    artifact = m.prepare_artifacts(refs, part, detector="rules")
    for key in part["roles"]["test"]:
        refs.metadata[key].update(cohort="human_study", truth="human", actor_id="same-subject")
    report = m.evaluate_artifacts(refs, part, artifact)
    cohort = report["variants"]["without_network"]["cohorts"]["human_study"]
    assert cohort["human_fpr_denominator"] == 3
    assert cohort["human_fpr_numerator"] == 2
    assert cohort["human_subject_any_bot_false_alarm_denominator"] == 1
    assert cohort["human_subject_any_bot_false_alarm_numerator"] == 1
    assert "same-subject" not in json.dumps(report)


def test_partition_mutation_and_metadata_group_mismatch_rejected_before_launch():
    m = module()
    refs, part = fixture()
    key = part["roles"]["test"].pop()
    part["roles"]["fit"].append(key)
    with (
        patch.object(m, "run_analysis", side_effect=AssertionError("invalid partition")),
        pytest.raises(ValueError),
    ):
        m.prepare_in_worker(refs, part, detector="rules")
    refs, part = fixture()
    refs.metadata[part["roles"]["test"][0]]["run_id"] = "cross-run"
    with pytest.raises(ValueError, match="metadata|reference"):
        m.prepare_in_worker(refs, part, detector="rules")


def test_worker_timeout_secret_environment_and_cancel_cleanup():
    from pathlib import Path

    import bouncer.ingest.import_analysis as transport

    roots = []
    with (
        patch.dict(
            transport.os.environ, {"BOUNCERI_DECISION_API_KEY": "secret", "DATABASE_URL": "private"}
        ),
        patch.object(transport.subprocess, "Popen") as popen,
    ):
        process = popen.return_value

        def start(*args, **kwargs):
            env = kwargs["env"]
            assert "BOUNCERI_DECISION_API_KEY" not in env and "DATABASE_URL" not in env
            assert env["PYTHONPATH"] == str(Path(transport.__file__).resolve().parents[2])
            root = Path(env["TMPDIR"])
            roots.append(root)
            (root / "private").write_text("secret")
            assert args[0][1:] == ["-m", "bouncer.eval.frozen_analysis"]
            return process

        popen.side_effect = start
        process.wait.side_effect = [KeyboardInterrupt(), 0]
        with pytest.raises(KeyboardInterrupt):
            transport.run_analysis(b"{}", 1, worker_module="bouncer.eval.frozen_analysis")
        process.kill.assert_called_once()
    assert roots and all(not root.exists() for root in roots)
    with (
        patch.object(transport.subprocess, "Popen", side_effect=AssertionError("fixed workers")),
        pytest.raises(ValueError),
    ):
        transport.run_analysis(b"{}", 1, worker_module="tools.anything")


def test_real_worker_short_deadline_is_sanitized():
    m = module()
    refs, part = fixture()
    with pytest.raises(ValueError, match="timed out"):
        m.prepare_in_worker(refs, part, detector="rules", timeout=0.00001)


def test_config_boolean_types_cannot_be_replaced_with_numeric_zero():
    m = module()
    refs, part = fixture()
    artifact = m.prepare_artifacts(refs, part, detector="rules")
    artifact["config"]["dns"] = 0
    with pytest.raises(ValueError):
        m.validate_artifacts(artifact)


def test_verified_native_bundle_runs_through_real_worker(tmp_path):
    from bouncer.eval.reference import build_references
    from tools.datasets.native import generate_bundle

    m = module()
    manifest = generate_bundle(tmp_path / "native", seed=53, runs_per_partition=1)
    refs = build_references([], [], [manifest])
    starts = sorted(
        min(refs.sessions[k].started_at for k, md in refs.metadata.items() if md["run_id"] == run)
        for run in {md["run_id"] for md in refs.metadata.values()}
    )
    assert len(starts) == 4
    part = partition_examples(
        refs.examples,
        {
            "fit": (starts[0], starts[1]),
            "calibration": (starts[1], starts[2]),
            "test": (starts[2], starts[-1] + timedelta(days=1)),
        },
    )
    artifact = m.prepare_in_worker(refs, part, detector="logistic")
    report = m.evaluate_in_worker(refs, part, artifact)
    for variant in report["variants"].values():
        assert set(variant["predictions"]) == set(part["roles"]["test"])
        assert variant["cohorts"]["simulation"]["n"] > 0
        assert variant["cohorts"]["human_study"]["n"] == 0


@pytest.mark.parametrize("detector", ["rules", "logistic"])
def test_parent_rejects_score_label_disagreement(detector):
    m = module()
    refs, part = fixture()
    artifact = m.prepare_artifacts(refs, part, detector=detector)
    report = m.evaluate_artifacts(refs, part, artifact)
    predictions = report["variants"]["with_network"]["predictions"]
    prediction = next(p for p in predictions.values() if p["label"] == "bad_bot")
    prediction["label"] = "human"
    with (
        patch.object(m, "run_analysis", return_value=json.dumps(report).encode()),
        pytest.raises(ValueError),
    ):
        m.evaluate_in_worker(refs, part, artifact)


def test_cohort_reports_missed_bots_and_unknown_predictions_do_not_boost_precision():
    m = module()
    cases = {
        "human": ("human", "human", "available", None, None),
        "missed-bad": ("bad_bot", "human", "available", None, None),
        "wrong-good": ("good_bot", "bad_bot", "available", None, None),
        "unknown-bad": (None, "bad_bot", "available", "automated", "unknown"),
        "unknown-good": (None, "good_bot", "available", "unknown", "unknown"),
        "unknown-uncertain": (None, "uncertain", "available", "unknown", "unknown"),
        "benign-automation": (None, "bad_bot", "available", "automated", "benign"),
        "missing-bad": ("bad_bot", None, "missing_evidence", None, None),
        "missing-human": ("human", None, "missing_evidence", None, None),
    }
    refs = SimpleNamespace(
        metadata={
            k: {
                "truth": truth,
                "actor_id": k,
                "run_id": "run",
                "behavior": behavior,
                "intent": intent,
            }
            for k, (truth, _, _, behavior, intent) in cases.items()
        }
    )
    predictions = {
        k: {"label": label, "status": status} for k, (_, label, status, _, _) in cases.items()
    }
    cohort = m._cohort(refs, list(cases), predictions)
    assert cohort["human_fpr"] == 0
    assert cohort["known_reference_available"] == 3
    assert cohort["known_reference_coverage"] == 3 / 5
    assert cohort["unknown_truth"] == cohort["unknown_truth_available"] == 4
    assert cohort["unknown_truth_coverage"] == 1
    confusion = cohort["confusion"]
    assert sum(sum(row.values()) for row in confusion.values()) == 3
    assert confusion["human"]["human"] == confusion["bad_bot"]["human"] == 1
    assert confusion["good_bot"]["bad_bot"] == 1
    precision = cohort["per_class"]["bad_bot"]["precision"]
    assert (precision["numerator"], precision["denominator"], precision["value"]) == (0, 1, 0)
    for label in ("bad_bot", "good_bot"):
        recall = cohort["per_class"][label]["recall"]
        assert (recall["numerator"], recall["denominator"], recall["value"]) == (0, 1, 0)
        assert recall["ci95_lower"] == 0 and 0 < recall["ci95_upper"] < 1
    human_precision = cohort["per_class"]["human"]["precision"]
    assert human_precision["numerator"] == 1 and human_precision["denominator"] == 2
    assert human_precision["value"] == 0.5
    good_precision = cohort["per_class"]["good_bot"]["precision"]
    assert good_precision["denominator"] == 0
    assert good_precision["value"] is good_precision["ci95_lower"] is None
    uncertain = cohort["uncertain_share"]
    assert (uncertain["numerator"], uncertain["denominator"], uncertain["value"]) == (1, 7, 1 / 7)
    benign = cohort["known_benign_automated_bad_flags"]
    assert (benign["numerator"], benign["denominator"], benign["value"]) == (1, 1, 1)
    assert cohort["unknown_intent_bad_flags"] == 1


def test_frozen_logistic_preserves_shared_hard_rules_when_model_thresholds_abstain():
    m = module()
    refs, part = fixture()
    artifact = m.prepare_artifacts(refs, part, detector="logistic")
    for variant in artifact["variants"].values():
        variant["thresholds"].update(bot=None, human=None)
        variant["model"]["thresholds"].update(bot=None, human=None)
    for key in part["roles"]["test"]:
        refs.metadata[key].update(cohort="human_study", truth="human")
    report = m.evaluate_artifacts(refs, part, artifact)
    context = m._contexts(refs, part["roles"]["test"])
    for name, network in m.VARIANTS.items():
        model = m.mdl.LogisticModel.from_dict(artifact["variants"][name]["model"])
        for key, prediction in report["variants"][name]["predictions"].items():
            native = m.score(
                refs.sessions[key],
                None,
                context.get(key) if network else None,
                traps=frozenset(),
                model=model,
            )
            assert prediction["label"] == native.label
            assert prediction["score"] == native.score
        cohort = report["variants"][name]["cohorts"]["human_study"]
        assert cohort["human_fpr_numerator"] == 2
        assert cohort["human_fpr_denominator"] == 3
        assert cohort["uncertain"] == 1


def test_calibration_thresholds_use_model_probabilities_without_hard_rule_scores():
    m = module()
    refs, part = fixture()
    original_predict = m.mdl.LogisticModel.predict_proba
    original_choose = m.choose_thresholds
    original_features = m.compute_features
    probabilities, threshold_inputs = [], []
    current = {}

    def features(session):
        current["key"] = session.id
        assert session.id in part["roles"]["fit"] + part["roles"]["calibration"]
        return original_features(session)

    def predict(model, vector):
        assert current["key"] in part["roles"]["calibration"]
        probability = original_predict(model, vector)
        probabilities.append(probability)
        return probability

    def choose(humans, bots):
        threshold_inputs.extend([*humans, *bots])
        return original_choose(humans, bots)

    with (
        patch.object(m, "score", side_effect=AssertionError("calibration is model-only")),
        patch.object(m, "compute_features", side_effect=features),
        patch.object(m.mdl.LogisticModel, "predict_proba", autospec=True, side_effect=predict),
        patch.object(m, "choose_thresholds", side_effect=choose),
    ):
        m.prepare_artifacts(refs, part, detector="logistic")
    assert len(probabilities) == len(threshold_inputs) == 4
    assert sorted(probabilities) == sorted(threshold_inputs)
    assert all(0 < probability < 1 for probability in threshold_inputs)


def captured_fixture():
    from bouncer.db.participants import session_digest
    from bouncer.eval.reference import _digest
    from tests.b.test_native_references import runtime_wrapper

    refs, old = fixture()
    refs.runtime_contexts, refs.runtime_configurations = {}, {}
    for key, session in refs.sessions.items():
        native = refs.metadata[key]["actor_id"]
        original = replace(session, id=native)
        wrapper = runtime_wrapper(original, traps=("/home",))
        refs.runtime_contexts[key] = wrapper
        refs.metadata[key].update(
            external_session_id=native,
            digest=session_digest(original),
            runtime_context_status="available",
            runtime_context_digest=_digest(wrapper),
        )
    return refs, old


def test_captured_rules_replay_actual_network_and_traps_without_ambient_inputs():
    from bouncer.contracts import IpIntel
    from tests.b.test_native_references import runtime_wrapper

    m = module()
    refs, part = captured_fixture()
    human = next(k for k in part["roles"]["test"] if refs.metadata[k]["truth"] == "human")
    refs.metadata[human]["cohort"] = "human_study"
    crawler = next(k for k in part["roles"]["test"] if refs.metadata[k]["truth"] is None)
    original = replace(refs.sessions[crawler], id=refs.metadata[crawler]["external_session_id"])
    context = runtime_wrapper(original, intel=IpIntel(verified_bot=True), traps=("/home",))
    refs.runtime_contexts[crawler] = context
    refs.metadata[crawler]["runtime_context_digest"] = m._context_digest(context)
    artifact = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")
    assert artifact["config"]["evidence_profile"] == "captured"
    assert artifact["config"]["dns"] is False
    assert set(artifact["variants"]) == {
        "with_network_with_traps",
        "without_network_with_traps",
        "with_network_without_traps",
        "without_network_without_traps",
    }
    with (
        patch("socket.getaddrinfo", side_effect=AssertionError("no current DNS")),
        patch("bouncer.session.rules.load_traps", side_effect=AssertionError("no current traps")),
        patch(
            "bouncer.session.score._default_model", side_effect=AssertionError("no ambient model")
        ),
    ):
        report = m.evaluate_artifacts(refs, part, artifact)
    assert report["variants"]["with_network_with_traps"]["predictions"][human]["label"] == "bad_bot"
    assert (
        report["variants"]["with_network_without_traps"]["predictions"][human]["label"]
        == "uncertain"
    )
    assert (
        report["variants"]["with_network_without_traps"]["predictions"][crawler]["label"]
        == "good_bot"
    )
    assert (
        report["variants"]["without_network_without_traps"]["predictions"][crawler]["label"]
        == "bad_bot"
    )
    assert report["variants"]["with_network_with_traps"]["cohorts"]["human_study"]["human_fpr"] == 1
    assert (
        report["variants"]["with_network_without_traps"]["cohorts"]["human_study"]["human_fpr"] == 0
    )
    assert report["production_quality"] is None


@pytest.mark.parametrize("verified,expected", [(None, "uncertain"), (False, "bad_bot")])
def test_captured_unknown_lookup_failure_is_not_false(verified, expected):
    from bouncer.contracts import IpIntel
    from tests.b.test_native_references import runtime_wrapper

    m = module()
    refs, part = captured_fixture()
    key = next(k for k in part["roles"]["test"] if refs.metadata[k]["truth"] == "human")
    session = refs.sessions[key]
    session = replace(
        session,
        user_agent="Googlebot",
        requests=tuple(replace(r, user_agent="Googlebot") for r in session.requests),
    )
    refs.sessions[key] = session
    original = replace(session, id=refs.metadata[key]["external_session_id"])
    wrapper = runtime_wrapper(original, intel=IpIntel(verified_bot=verified))
    refs.metadata[key].update(
        digest=wrapper["session_digest"], runtime_context_digest=m._context_digest(wrapper)
    )
    refs.runtime_contexts[key] = wrapper
    artifacts = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")
    report = m.evaluate_artifacts(refs, part, artifacts)
    assert report["variants"]["with_network_with_traps"]["predictions"][key]["label"] == expected


@pytest.mark.parametrize("role", ["fit", "calibration"])
def test_captured_missing_labeled_context_refuses_fit(role):
    m = module()
    refs, part = captured_fixture()
    key = next(k for k in part["roles"][role] if refs.metadata[k]["truth"] is not None)
    del refs.runtime_contexts[key]
    with (
        patch.object(m.mdl, "fit", side_effect=AssertionError("validate first")),
        pytest.raises(ValueError, match="missing|incomplete"),
    ):
        m.prepare_artifacts(refs, part, detector="logistic", evidence_profile="captured")


def test_captured_missing_context_excluded_from_graph_and_all_predictions():
    m = module()
    refs, part = captured_fixture()
    key = part["roles"]["test"][0]
    del refs.runtime_contexts[key]
    artifacts = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")
    original = m.find_campaigns

    def find(sessions):
        assert key not in {s.id for s in sessions}
        return original(sessions)

    with patch.object(m, "find_campaigns", side_effect=find):
        report = m.evaluate_artifacts(refs, part, artifacts)
    for variant in report["variants"].values():
        assert variant["predictions"][key] == {
            "status": "missing_evidence",
            "label": None,
            "score": None,
        }


def test_captured_fits_two_network_models_and_shares_exact_trap_model_bytes():
    m = module()
    refs, part = captured_fixture()
    with patch.object(m.mdl, "fit", wraps=m.mdl.fit) as fit:
        artifacts = m.prepare_artifacts(
            refs, part, detector="logistic", evidence_profile="captured"
        )
    assert fit.call_count == 2
    assert {c.kwargs["network"] for c in fit.call_args_list} == {True, False}
    for prefix in ("with_network", "without_network"):
        with_traps = artifacts["variants"][prefix + "_with_traps"]
        without_traps = artifacts["variants"][prefix + "_without_traps"]
        assert with_traps["model"] == without_traps["model"]
        assert with_traps["thresholds"] == without_traps["thresholds"]
    corrupted = copy.deepcopy(artifacts)
    corrupted["variants"]["with_network_without_traps"]["model"]["weights"][0] += 1
    with pytest.raises(ValueError):
        m.validate_artifacts(corrupted)


def test_captured_prepare_ipc_omits_holdout_runtime_configs_and_deduplicates_traps():
    from tests.b.test_native_references import runtime_wrapper

    m = module()
    refs, part = captured_fixture()
    for key in part["roles"]["test"]:
        session = replace(refs.sessions[key], id=refs.metadata[key]["external_session_id"])
        wrapper = runtime_wrapper(session, traps=("/holdout-config-canary",))
        refs.runtime_contexts[key] = wrapper
        refs.metadata[key]["runtime_context_digest"] = m._context_digest(wrapper)
    expected = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")

    def runner(data, timeout, **kwargs):
        packet = json.loads(data)
        assert "/holdout-config-canary" not in data.decode()
        assert set(packet["runtime_contexts"]) == set(
            part["roles"]["fit"] + part["roles"]["calibration"]
        )
        assert len(packet["runtime_configurations"]) == 1
        assert all("traps" not in c["effective"] for c in packet["runtime_contexts"].values())
        assert m._execute(packet) == expected
        return json.dumps(expected).encode()

    with patch.object(m, "run_analysis", side_effect=runner):
        assert (
            m.prepare_in_worker(refs, part, detector="rules", evidence_profile="captured")
            == expected
        )


@pytest.mark.parametrize(
    "fault",
    [
        "extra_context",
        "orphan_config",
        "missing_intel",
        "bad_hash",
        "oversize_traps",
        "wrong_digest",
        "provenance",
        "unknown_schema",
    ],
)
def test_captured_worker_rejects_unbound_or_invalid_runtime_packet(fault):
    m = module()
    refs, part = captured_fixture()
    packet = m._packet(
        refs,
        part,
        operation="prepare",
        detector="rules",
        artifacts=None,
        evidence_profile="captured",
    )
    key = next(iter(packet["runtime_contexts"]))
    context = packet["runtime_contexts"][key]
    digest = context["config_digest"]
    if fault == "extra_context":
        packet["runtime_contexts"][part["roles"]["test"][0]] = copy.deepcopy(context)
    elif fault == "orphan_config":
        packet["runtime_configurations"]["a" * 64] = packet["runtime_configurations"][digest]
    elif fault == "missing_intel":
        del context["effective"]["intel"]
    elif fault == "bad_hash":
        context["config_digest"] = "b" * 64
    elif fault == "oversize_traps":
        packet["runtime_configurations"][digest]["trap_paths"] = [
            "/trap" + str(i) for i in range(129)
        ]
    elif fault == "wrong_digest":
        context["session_digest"] = "c" * 64
    elif fault == "provenance":
        context["effective"]["provenance"]["availability"] = "available"
    else:
        context["ambient"] = True
    with pytest.raises(ValueError):
        m._execute(packet)


def test_captured_real_worker_roundtrip_and_exact_shared_score_parity():
    from bouncer.contracts import IpIntel

    m = module()
    refs, part = captured_fixture()
    artifacts = m.prepare_in_worker(refs, part, detector="logistic", evidence_profile="captured")
    report = m.evaluate_in_worker(refs, part, artifacts)
    assert report == m.evaluate_artifacts(refs, part, artifacts)
    campaigns = m._contexts(refs, part["roles"]["test"], "captured", refs.runtime_contexts)
    for name, variant in artifacts["variants"].items():
        model = m.mdl.LogisticModel.from_dict(variant["model"])
        for key in part["roles"]["test"]:
            effective = refs.runtime_contexts[key]["effective"]
            verdict = m.score(
                refs.sessions[key],
                IpIntel(**effective["intel"]) if variant["network"] else None,
                campaigns.get(key) if variant["network"] else None,
                traps=frozenset(effective["traps"]) if variant["traps"] else frozenset(),
                model=model,
            )
            assert report["variants"][name]["predictions"][key] == {
                "status": "available",
                "label": verdict.label,
                "score": verdict.score,
            }


@pytest.mark.parametrize("label,score", [("good_bot", 1.0), ("bad_bot", 1.0)])
def test_captured_parent_rejects_invented_hard_rule_without_actual_inputs(label, score):
    m = module()
    refs, part = captured_fixture()
    artifacts = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")
    report = m.evaluate_artifacts(refs, part, artifacts)
    key = next(k for k in part["roles"]["test"] if refs.metadata[k]["truth"] == "human")
    report["variants"]["with_network_without_traps"]["predictions"][key].update(
        label=label, score=score
    )
    with pytest.raises(ValueError):
        m.validate_report(refs, part, artifacts, report)


def test_captured_manual_human_verified_input_is_false_alarm_not_ground_truth():
    from dataclasses import asdict

    from bouncer.contracts import IpIntel
    from tests.b.test_native_references import runtime_wrapper

    m = module()
    refs, part = captured_fixture()
    key = next(k for k in part["roles"]["test"] if refs.metadata[k]["truth"] == "human")
    refs.metadata[key].update(cohort="human_study", behavior="manual", intent="benign")
    original = replace(refs.sessions[key], id=refs.metadata[key]["external_session_id"])
    intel = IpIntel(verified_bot=True)
    observation = asdict(intel) | {
        "checked_at": original.ended_at.isoformat(),
        "resolver_outcome": "verified",
        "crawler": "googlebot",
        "asn_origin": "unknown",
    }
    wrapper = runtime_wrapper(original, intel=intel, observation=observation)
    refs.runtime_contexts[key] = wrapper
    refs.metadata[key]["runtime_context_digest"] = m._context_digest(wrapper)
    artifacts = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")
    report = m.evaluate_artifacts(refs, part, artifacts)
    with_network = report["variants"]["with_network_with_traps"]["cohorts"]["human_study"]
    without_network = report["variants"]["without_network_with_traps"]["cohorts"]["human_study"]
    assert with_network["truth_counts"]["human"] == 1
    assert with_network["human_fpr"] == 1 and without_network["human_fpr"] == 0
    assert with_network["runtime_evidence_coverage"]["numerator"] == 2
    assert with_network["runtime_provenance_coverage"]["numerator"] == 1
    assert with_network["runtime_provenance_unavailable"] == 1
    # The second study observation remains unknown, even with replayable inputs.
    assert with_network["unknown_truth"] == 1
    assert report["production_quality"] is None


def test_captured_replay_without_verification_provenance_does_not_claim_provenance_support():
    m = module()
    refs, part = captured_fixture()
    artifacts = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")
    report = m.evaluate_artifacts(refs, part, artifacts)
    for variant in report["variants"].values():
        for cohort in variant["cohorts"].values():
            assert cohort["runtime_provenance_coverage"]["numerator"] == 0
            assert cohort["runtime_provenance_unavailable"] == cohort["n"]


def test_captured_synthetic_context_is_replayable_but_never_actual_runtime_evidence(tmp_path):
    from bouncer.eval.reference import build_references
    from tools.datasets.native import generate_bundle

    m = module()
    refs = build_references(
        [],
        [],
        [generate_bundle(tmp_path / "native", seed=61, runs_per_partition=1)],
        evidence_profile="captured",
    )
    starts = sorted(
        min(refs.sessions[k].started_at for k, md in refs.metadata.items() if md["run_id"] == run)
        for run in {md["run_id"] for md in refs.metadata.values()}
    )
    part = partition_examples(
        refs.examples,
        {
            "fit": (starts[0], starts[1]),
            "calibration": (starts[1], starts[2]),
            "test": (starts[2], starts[-1] + timedelta(days=1)),
        },
    )
    artifacts = m.prepare_in_worker(refs, part, detector="logistic", evidence_profile="captured")
    report = m.evaluate_in_worker(refs, part, artifacts)
    for variant in report["variants"].values():
        cohort = variant["cohorts"]["simulation"]
        assert cohort["available"] == cohort["synthetic_offline_contexts"] == cohort["n"]
        assert cohort["runtime_evidence_coverage"]["numerator"] == 0
        assert cohort["runtime_provenance_coverage"]["numerator"] == 0


def test_captured_contexts_obey_role_run_and_missing_evidence_isolation():
    m = module()
    refs, part = captured_fixture()
    for md in refs.metadata.values():
        md["run_id"] += "-" + str(md["truth"])
    missing = next(k for k in part["roles"]["test"] if refs.metadata[k]["truth"] is None)
    del refs.runtime_contexts[missing]
    calls = []

    def find(sessions):
        keys = {s.id for s in sessions}
        assert missing not in keys
        assert len({refs.metadata[k]["run_id"] for k in keys}) == 1
        assert sum(bool(keys.intersection(part["roles"][role])) for role in part["roles"]) == 1
        calls.append(keys)
        return []

    with patch.object(m, "find_campaigns", side_effect=find):
        artifacts = m.prepare_artifacts(
            refs, part, detector="logistic", evidence_profile="captured"
        )
        assert set.union(*calls) == set(part["roles"]["fit"] + part["roles"]["calibration"])
        calls.clear()
        m.evaluate_artifacts(refs, part, artifacts)
        assert set.union(*calls) == set(part["roles"]["test"]) - {missing}


@pytest.mark.parametrize("fault", ["numeric_available", "numeric_traps", "list_label"])
def test_captured_protocol_rejects_equal_numeric_booleans_and_malformed_label(fault):
    m = module()
    refs, part = captured_fixture()
    if fault == "numeric_available":
        packet = m._packet(
            refs,
            part,
            operation="prepare",
            detector="rules",
            artifacts=None,
            evidence_profile="captured",
        )
        next(iter(packet["runtime_configurations"].values()))["available"] = 1
        with pytest.raises(ValueError):
            m._execute(packet)
    else:
        artifacts = m.prepare_artifacts(refs, part, detector="rules", evidence_profile="captured")
        if fault == "numeric_traps":
            artifacts["variants"]["with_network_with_traps"]["traps"] = 1
            with pytest.raises(ValueError):
                m.validate_artifacts(artifacts)
        else:
            report = m.evaluate_artifacts(refs, part, artifacts)
            predictions = report["variants"]["with_network_with_traps"]["predictions"]
            next(iter(predictions.values()))["label"] = []
            with pytest.raises(ValueError):
                m.validate_report(refs, part, artifacts, report)
