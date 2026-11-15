import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from bouncer.db.participants import StudyStore
from tests.a.test_migrations import engine, postgres_url  # noqa: F401
from tests.a.test_participants import enroll, review, source
from tools.datasets.native import generate_bundle


@pytest.fixture(params=["sqlite", "postgres"])
def evaluation(tmp_path, monkeypatch, request):
    from bouncer.eval import frozen
    from bouncer.eval.frozen_analysis import evaluate_artifacts, prepare_artifacts

    database = (request.getfixturevalue("engine") if request.param == "postgres"
                else f"sqlite:///{tmp_path / 'evaluation.db'}")
    study = StudyStore(database)
    source(study.traffic)
    enrolled = enroll(study)
    review(study, enrolled)
    manifest = generate_bundle(tmp_path / "native", seed=101, runs_per_partition=1)
    monkeypatch.setattr(frozen, "fingerprint", lambda: {"code": "test-code-v1"})
    monkeypatch.setattr(frozen, "prepare_in_worker", prepare_artifacts)
    monkeypatch.setattr(frozen, "evaluate_in_worker", evaluate_artifacts)
    plan = {
        "schema_version": "frozen-native-plan-v1", "detector": "rules",
        "collections": [{"source_key": "collection-a", "run_id": "study-run",
                         "campaign_ids": []}],
        "synthetic_manifests": [str(manifest)],
        "windows": {
            "fit": {"from": "2026-01-01T00:00:00Z", "until": "2026-01-01T01:00:00Z"},
            "calibration": {"from": "2026-01-01T01:00:00Z", "until": "2026-01-01T02:00:00Z"},
            "test": {"from": "2026-01-01T02:00:00Z", "until": "2026-11-16T00:00:00Z"},
        },
    }
    evaluation_engine = study.engine
    yield frozen.FrozenEvaluator(study), plan, enrolled
    evaluation_engine.dispose()


def test_prepare_freezes_before_test_and_exact_evaluation_replay_is_cached(
    evaluation, monkeypatch,
):
    from bouncer.eval import frozen

    evaluator, plan, _ = evaluation
    prepared = evaluator.prepare(plan)
    identifier = prepared["preparation_id"]
    assert prepared["state"] == "frozen" and prepared["artifact_digest"]
    assert evaluator.ledger.get(identifier)["report"] == {}
    first = evaluator.evaluate(identifier)
    assert first["cached"] is False and first["report"]["production_quality"] is None
    assert first["report_digest"] == frozen.digest(first["report"])
    monkeypatch.setattr(frozen, "evaluate_in_worker", lambda *args: pytest.fail("rescored"))
    second = evaluator.evaluate(identifier)
    assert second["cached"] is True and second["report"] == first["report"]


def test_captured_plan_replays_bound_context_and_revalidates_cached_results(
    evaluation, monkeypatch,
):
    from bouncer.eval import frozen
    from tests.b.test_native_references import runtime_wrapper

    evaluator, plan, _ = evaluation
    plan["evidence_profile"] = "captured"
    load = evaluator.study._load_approved_connection
    changed = False

    def captured(conn, sources):
        rows = load(conn, sources)
        return [replace(row, provenance=row.provenance | {
            "source": row.provenance["source"] | {
                "runtime_context": runtime_wrapper(
                    row.session, traps=("/changed-private-trap" if changed else "/private-trap",),
                ),
            },
        }) for row in rows]

    monkeypatch.setattr(evaluator.study, "_load_approved_connection", captured)
    prepared = evaluator.prepare(plan)
    assert prepared["descriptor"]["plan"]["evidence_profile"] == "captured"
    analysis = prepared["artifacts"]["analysis"]
    assert analysis["config"]["evidence_profile"] == "captured"
    assert len(analysis["variants"]) == 4
    first = evaluator.evaluate(prepared["preparation_id"])
    assert first["report"]["production_quality"] is None
    assert len(first["report"]["variants"]) == 4
    monkeypatch.setattr(frozen, "evaluate_in_worker", lambda *args: pytest.fail("rescored"))
    assert evaluator.evaluate(prepared["preparation_id"])["cached"] is True
    changed = True
    with pytest.raises(ValueError, match="references changed"):
        evaluator.evaluate(prepared["preparation_id"])


def test_captured_plan_rejects_worker_profile_downgrade(evaluation, monkeypatch):
    from bouncer.eval import frozen
    from bouncer.eval.frozen_analysis import prepare_artifacts

    evaluator, plan, _ = evaluation
    plan["evidence_profile"] = "captured"
    monkeypatch.setattr(frozen, "prepare_in_worker", lambda refs, part, **kwargs:
                        prepare_artifacts(refs, part, detector=kwargs["detector"]))
    with pytest.raises(ValueError, match="profile"):
        evaluator.prepare(plan)


@pytest.mark.parametrize("profile", [None, True, 1, [], {}, "live", "CAPTURED"])
def test_invalid_evidence_profile_rejected_before_sources(evaluation, profile, monkeypatch):
    evaluator, plan, _ = evaluation
    plan["evidence_profile"] = profile
    monkeypatch.setattr(evaluator, "_references", lambda *args: pytest.fail("loaded sources"))
    with pytest.raises(ValueError, match="plan"):
        evaluator.prepare(plan)


def test_fingerprint_changes_refuse_test_before_consumption(evaluation, monkeypatch):
    from bouncer.eval import frozen

    evaluator, plan, _ = evaluation
    prepared = evaluator.prepare(plan)
    monkeypatch.setattr(frozen, "fingerprint", lambda: {"code": "changed"})
    with pytest.raises(ValueError, match="fingerprint"):
        evaluator.evaluate(prepared["preparation_id"])
    assert evaluator.ledger.get(prepared["preparation_id"])["state"] == "frozen"


def test_claim_is_durable_before_analysis_and_failure_cannot_be_retried(evaluation, monkeypatch):
    from bouncer.eval import frozen

    evaluator, plan, _ = evaluation
    prepared = evaluator.prepare(plan)
    identifier = prepared["preparation_id"]

    def failed_analysis(*args):
        assert evaluator.ledger.get(identifier)["state"] == "claimed"
        raise ValueError("private-failure-canary")

    monkeypatch.setattr(frozen, "evaluate_in_worker", failed_analysis)
    with pytest.raises(ValueError, match="analysis failed") as failure:
        evaluator.evaluate(identifier)
    assert "private-failure-canary" not in str(failure.value)
    record = evaluator.ledger.get(identifier)
    assert record["state"] == "unavailable" and record["failure_code"] == "analysis_failed"
    with pytest.raises(ValueError):
        evaluator.evaluate(identifier)


def test_claim_blocks_withdrawal_then_completed_source_purge_revokes_cached_report(
    evaluation, monkeypatch,
):
    from bouncer.eval import frozen
    from bouncer.eval.frozen_analysis import evaluate_artifacts

    evaluator, plan, enrolled = evaluation
    identifier = evaluator.prepare(plan)["preparation_id"]

    def during_analysis(*args):
        with pytest.raises(ValueError, match="evaluation in progress"):
            evaluator.study.withdraw(enrolled["subject_id"], confirm_subject=enrolled["subject_id"],
                                     writer_stopped=True)
        return evaluate_artifacts(*args)

    monkeypatch.setattr(frozen, "evaluate_in_worker", during_analysis)
    evaluator.evaluate(identifier)
    evaluator.study.withdraw(enrolled["subject_id"], confirm_subject=enrolled["subject_id"],
                             writer_stopped=True)
    record = evaluator.ledger.get(identifier)
    assert record["state"] == "revoked" and record["report"] == record["descriptor"] == {}
    with pytest.raises(ValueError, match="revoked"):
        evaluator.evaluate(identifier)


def test_post_claim_data_change_consumes_without_publishing_old_review(evaluation, monkeypatch):
    from bouncer.eval import frozen
    from bouncer.eval.frozen_analysis import evaluate_artifacts

    evaluator, plan, _ = evaluation
    identifier = evaluator.prepare(plan)["preparation_id"]

    def changed_data(*args):
        result = evaluate_artifacts(*args)
        source(evaluator.study.traffic, count=2,
               expected=evaluator.study.traffic.load_checkpoint("collection-a"))
        return result

    monkeypatch.setattr(frozen, "evaluate_in_worker", changed_data)
    with pytest.raises(ValueError, match="validation failed"):
        evaluator.evaluate(identifier)
    record = evaluator.ledger.get(identifier)
    assert record["state"] == "unavailable" and record["failure_code"] == "validation_failed"
    assert record["report"] == {}


def test_interrupted_receipt_requires_confirmation_and_never_restores_independence(evaluation):
    evaluator, plan, _ = evaluation
    prepared = evaluator.prepare(plan)
    identifier = prepared["preparation_id"]
    evaluator.ledger.claim(identifier, artifact_digest=prepared["artifact_digest"])
    with pytest.raises(ValueError, match="stopped"):
        evaluator.close_interrupted(identifier, confirm_worker_stopped=False)
    evaluator.close_interrupted(identifier, confirm_worker_stopped=True)
    assert evaluator.ledger.get(identifier)["state"] == "unavailable"
    with pytest.raises(ValueError):
        evaluator.evaluate(identifier)
    with pytest.raises(ValueError):
        evaluator.prepare(plan | {"detector": "logistic"})


def test_invalid_plans_fail_before_source_reads_or_reservations(evaluation, monkeypatch):
    evaluator, plan, _ = evaluation
    monkeypatch.setattr(evaluator.study, "_load_approved_connection",
                        lambda *args: pytest.fail("source read before plan validation"))
    for patch in (
        {"detector": []}, {"collections": None}, {"collections": [{}]},
        {"collections": plan["collections"] * 1001},
        {"synthetic_manifests": "private-canary"}, {"synthetic_manifests": ["x"] * 11},
        {"windows": []}, {"detector": float("nan")},
    ):
        with pytest.raises(ValueError):
            evaluator.prepare(plan | patch)


def test_equivalent_utc_plan_replay_reuses_the_frozen_artifact(evaluation, monkeypatch):
    from bouncer.eval import frozen

    evaluator, plan, _ = evaluation
    prepared = evaluator.prepare(plan)
    changed = plan | {"windows": {role: {name: value.replace("Z", "+00:00")
                                         for name, value in window.items()}
                                  for role, window in plan["windows"].items()}}
    monkeypatch.setattr(frozen, "prepare_in_worker", lambda *args, **kwargs: pytest.fail("refit"))
    assert evaluator.prepare(changed)["preparation_id"] == prepared["preparation_id"]


def test_valid_shaped_cached_prediction_corruption_cannot_change_exact_replay(
    evaluation, monkeypatch,
):
    from bouncer.db.evaluations import preparations
    from bouncer.eval import frozen

    evaluator, plan, _ = evaluation
    identifier = evaluator.prepare(plan)["preparation_id"]
    evaluator.evaluate(identifier)
    record = evaluator.ledger.get(identifier)
    changed = json.loads(json.dumps(record["report"]))
    predictions = changed["variants"]["with_network"]["predictions"]
    key = next(key for key, row in predictions.items() if row["label"] == "uncertain")
    predictions[key] = {"label": "bad_bot", "score": 1.0, "status": "available"}
    with evaluator.study.engine.begin() as conn:
        conn.execute(preparations.update().where(preparations.c.preparation_id == identifier)
                     .values(report=changed))
    monkeypatch.setattr(frozen, "evaluate_in_worker", lambda *args: pytest.fail("rescored"))
    with pytest.raises(ValueError, match="report"):
        evaluator.evaluate(identifier)
    with evaluator.study.engine.connect() as conn:
        assert conn.scalar(select(preparations.c.state).where(
            preparations.c.preparation_id == identifier
        )) == "complete"


def test_dependency_bytes_are_fingerprinted_even_without_a_version_change(tmp_path, monkeypatch):
    from bouncer.eval import frozen

    dependency = tmp_path / "library"
    dependency.mkdir()
    module = dependency / "runtime.py"
    module.write_text("COEFFICIENT = 1\n", encoding="utf-8")
    distribution = SimpleNamespace(version="1.0", files=[Path("runtime.py")],
                                   locate_file=lambda name: dependency / name)
    monkeypatch.setattr(frozen.importlib.metadata, "distribution", lambda name: distribution)
    before = frozen._dependency_fingerprint("fixture")
    module.write_text("COEFFICIENT = 2\n", encoding="utf-8")
    after = frozen._dependency_fingerprint("fixture")
    assert before["version"] == after["version"] == "1.0"
    assert before["files"] != after["files"]


def test_fingerprint_includes_installed_transitive_typing_inspection(monkeypatch):
    from bouncer.eval import frozen

    seen = set()

    def dependency(name):
        seen.add(name.replace("_", "-"))
        return {"version": "fixture", "files": {}}

    monkeypatch.setattr(frozen, "_dependency_fingerprint", dependency)
    result = frozen.fingerprint()
    assert "typing-inspection" in seen
    assert "typing-inspection" in {name.replace("_", "-") for name in result["dependencies"]}


def test_large_bounded_plan_can_support_more_than_three_hundred_subject_sources():
    from bouncer.eval.frozen import _plan

    plan = {
        "schema_version": "frozen-native-plan-v1", "detector": "rules",
        "collections": [{"source_key": f"study-{index}-" + "s" * 100,
                         "run_id": "r" * 100, "campaign_ids": []} for index in range(351)],
        "synthetic_manifests": [], "windows": {
            role: {"from": f"2026-01-01T0{index}:00:00Z",
                   "until": f"2026-01-01T0{index + 1}:00:00Z"}
            for index, role in enumerate(("fit", "calibration", "test"))
        },
    }
    assert len(json.dumps(plan).encode()) > 64 * 1024
    normalized, _ = _plan(plan)
    assert len(normalized["collections"]) == 351
