import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from bouncer.eval import frozen_cli
from tools.datasets.__main__ import main as datasets_main

IDENTIFIER = "a" * 64
DIGEST = "b" * 64
CANARY = "private-source-evidence-canary"


@pytest.fixture
def command(monkeypatch):
    calls = []
    record = {
        "preparation_id": IDENTIFIER, "state": "frozen", "artifact_digest": DIGEST,
        "failure_code": None, "claimed_at": datetime(2026, 11, 15, tzinfo=UTC),
        "completed_at": None, "descriptor": {"source": CANARY}, "artifacts": CANARY,
        "report": {"production_quality": None, "source": CANARY},
    }
    store = SimpleNamespace(engine=SimpleNamespace(dispose=lambda: calls.append("disposed")))
    evaluator = SimpleNamespace(
        prepare=lambda plan: calls.append(("prepare", plan)) or record,
        evaluate=lambda identifier: calls.append(("evaluate", identifier)) or {
            "preparation_id": IDENTIFIER, "artifact_digest": DIGEST, "cached": False,
            "report": record["report"],
        },
        close_interrupted=lambda identifier, **kwargs:
            calls.append(("close", identifier, kwargs)) or record | {"state": "unavailable"},
        ledger=SimpleNamespace(
            get=lambda identifier: calls.append(("status", identifier)) or record,
        ),
    )
    monkeypatch.setenv("BOUNCER_DATABASE_URL", "sqlite:///private.db")
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", "sqlite:///private.db")
    monkeypatch.setattr(frozen_cli, "StudyStore", lambda url: calls.append("connected") or store)
    monkeypatch.setattr(frozen_cli, "FrozenEvaluator", lambda value: evaluator)
    return calls, evaluator, record


def test_prepare_dispatch_only_prints_safe_receipt(command, tmp_path, capsys):
    path = tmp_path / "plan.json"
    plan = {"source": CANARY}
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert datasets_main(["frozen-evaluation", "prepare", "--plan", str(path)]) == 0
    result = capsys.readouterr()
    assert json.loads(result.out) == {
        "preparation_id": IDENTIFIER, "state": "frozen", "artifact_digest": DIGEST,
    }
    assert CANARY not in result.out + result.err
    assert command[0] == ["connected", ("prepare", plan), "disposed"]


@pytest.mark.parametrize("raw", [
    b'{"source": "private-canary", "source": 2}', b'{"number": Infinity}',
    b'{"number": NaN}', b'{"number": -Infinity}', b'{"number": 1e999}',
    '{"source":"private-canary"}'.encode("utf-16"), b"[1]", b"x" * 65537,
    b'{"nested":{"key":1,"key":2}}',
], ids=["duplicate", "infinity", "nan", "negative-infinity", "overflow", "utf16", "array",
        "oversized", "nested-duplicate"])
def test_plan_rejects_ambiguous_or_oversized_input_before_connect(
    command, tmp_path, capsys, raw,
):
    path = tmp_path / "plan.json"
    path.write_bytes(raw)
    assert frozen_cli.main(["prepare", "--plan", str(path)]) == 2
    assert command[0] == []
    result = capsys.readouterr()
    assert not result.out and "private-canary" not in result.err
    assert str(path) not in result.err


def test_status_omits_all_private_record_payload_and_encodes_dates(command, capsys):
    assert frozen_cli.main(["status", "--preparation", IDENTIFIER]) == 0
    result = capsys.readouterr()
    assert json.loads(result.out) == {
        "preparation_id": IDENTIFIER, "state": "frozen", "artifact_digest": DIGEST,
        "failure_code": None, "claimed_at": "2026-11-15T00:00:00+00:00",
        "completed_at": None,
    }
    assert CANARY not in result.out + result.err
    assert command[0][-1] == "disposed"


def test_evaluate_writes_only_private_report_envelope(command, tmp_path, capsys):
    output = tmp_path / "report.json"
    assert frozen_cli.main([
        "evaluate", "--preparation", IDENTIFIER, "--output", str(output),
    ]) == 0
    result = capsys.readouterr()
    assert json.loads(result.out) == {
        "preparation_id": IDENTIFIER, "artifact_digest": DIGEST,
        "cached": False, "report_written": True,
    }
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "preparation_id": IDENTIFIER, "artifact_digest": DIGEST, "cached": False,
        "report": {"production_quality": None, "source": CANARY},
    }
    assert CANARY not in result.out + result.err and str(output) not in result.out
    assert command[0] == ["connected", ("evaluate", IDENTIFIER), "disposed"]


def test_output_refusal_precedes_connect_and_preserves_existing(command, tmp_path, capsys):
    existing = tmp_path / "existing.json"
    existing.write_text(CANARY)
    repository = Path(__file__).resolve().parents[2] / "private-report.json"
    for output in (existing, repository):
        assert frozen_cli.main([
            "evaluate", "--preparation", IDENTIFIER, "--output", str(output),
        ]) == 2
    assert existing.read_text() == CANARY
    assert not repository.exists() and command[0] == []
    result = capsys.readouterr()
    assert CANARY not in result.err and not result.out


def test_invalid_preparation_rejected_before_connect(command, capsys):
    for value in ("private-canary", "a" * 65, "A" * 64):
        assert frozen_cli.main(["status", "--preparation", value]) == 2
    assert command[0] == []
    assert "private-canary" not in capsys.readouterr().err


def test_explicit_confirmation_required_and_close_has_no_retry(command, capsys):
    with pytest.raises(SystemExit) as error:
        frozen_cli.main(["close-interrupted", "--preparation", IDENTIFIER])
    assert error.value.code == 2 and command[0] == []
    capsys.readouterr()
    assert frozen_cli.main([
        "close-interrupted", "--preparation", IDENTIFIER, "--confirm-worker-stopped",
    ]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "preparation_id": IDENTIFIER, "state": "unavailable",
    }
    assert command[0] == [
        "connected", ("close", IDENTIFIER, {"confirm_worker_stopped": True}), "disposed",
    ]


def test_failure_disposes_engine_and_hides_exception_values(command, capsys):
    def fail(identifier):
        raise RuntimeError("SQL credentials " + CANARY)

    command[1].ledger.get = fail
    assert frozen_cli.main(["status", "--preparation", IDENTIFIER]) == 2
    result = capsys.readouterr()
    assert not result.out and CANARY not in result.err and "SQL" not in result.err
    assert command[0] == ["connected", "disposed"]


@pytest.mark.parametrize("report", [{"value": "x" * (8 * 1024 * 1024)}, {"bad": b"bytes"}])
def test_report_limit_or_serialization_failure_removes_only_owned_partial(
    command, tmp_path, capsys, report,
):
    output = tmp_path / "partial.json"
    command[2]["report"].clear()
    command[2]["report"].update(report)
    assert frozen_cli.main([
        "evaluate", "--preparation", IDENTIFIER, "--output", str(output),
    ]) == 2
    assert not output.exists() and command[0][-1] == "disposed"
    assert not capsys.readouterr().out


def test_symlink_output_is_rejected_before_connect(command, tmp_path):
    target = tmp_path / "preserved.json"
    target.write_text(CANARY)
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert frozen_cli.main([
        "evaluate", "--preparation", IDENTIFIER, "--output", str(link),
    ]) == 2
    assert command[0] == [] and target.read_text() == CANARY


@pytest.mark.parametrize("traffic,cases", [
    (None, "sqlite:///private.db"), ("sqlite:///private.db", None),
    ("sqlite:///private.db", "sqlite:///other.db"), ("bad-private-canary", "bad-private-canary"),
    ("sqlite://", "sqlite://"), ("sqlite:///:memory:", "sqlite:///:memory:"),
    ("postgresql://host", "postgresql://host"),
])
def test_shared_database_rejected_before_connect(command, monkeypatch, capsys, traffic, cases):
    for key, value in (("BOUNCER_TRAFFIC_DATABASE_URL", traffic), ("BOUNCER_DATABASE_URL", cases)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    assert frozen_cli.main(["status", "--preparation", IDENTIFIER]) == 2
    assert command[0] == []
    result = capsys.readouterr()
    assert not result.out and "private-canary" not in result.err


def test_output_race_preserves_file_not_owned_by_command(command, monkeypatch, tmp_path, capsys):
    output = tmp_path / "raced.json"
    original = command[1].evaluate

    def evaluate(identifier):
        output.write_text(CANARY)
        return original(identifier)

    command[1].evaluate = evaluate
    assert frozen_cli.main([
        "evaluate", "--preparation", IDENTIFIER, "--output", str(output),
    ]) == 2
    assert output.read_text() == CANARY and command[0][-1] == "disposed"
    assert not capsys.readouterr().out


@pytest.mark.parametrize("profile", [None, "captured"])
def test_cli_sqlite_native_fixture_roundtrip_is_private_and_cached(
    tmp_path, monkeypatch, capsys, profile,
):
    from bouncer.db.participants import StudyStore
    from bouncer.eval import frozen
    from bouncer.eval.frozen_analysis import evaluate_artifacts, prepare_artifacts
    from bouncer.eval.native_fixtures import generate_bundle
    from tests.a.test_participants import enroll, review, source

    url = f"sqlite:///{tmp_path / 'frozen.db'}"
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    monkeypatch.setattr(frozen, "fingerprint", lambda: {"code": "cli-test-v1"})
    monkeypatch.setattr(frozen, "prepare_in_worker", prepare_artifacts)
    monkeypatch.setattr(frozen, "evaluate_in_worker", evaluate_artifacts)
    study = StudyStore(url)
    try:
        source(study.traffic)
        review(study, enroll(study))
    finally:
        study.engine.dispose()
    manifest = generate_bundle(tmp_path / "native", seed=111, runs_per_partition=1)
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
    if profile is not None:
        plan["evidence_profile"] = profile
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert frozen_cli.main(["prepare", "--plan", str(path)]) == 0
    preparation = json.loads(capsys.readouterr().out)
    identifier = preparation["preparation_id"]
    assert preparation["state"] == "frozen"
    reports = []
    for index, cached in enumerate((False, True)):
        report_path = tmp_path / f"report-{index}.json"
        assert frozen_cli.main([
            "evaluate", "--preparation", identifier, "--output", str(report_path),
        ]) == 0
        printed = capsys.readouterr()
        receipt = json.loads(printed.out)
        assert receipt["cached"] is cached
        assert set(receipt) == {"preparation_id", "artifact_digest", "cached", "report_written"}
        assert "collection-a" not in printed.out + printed.err
        envelope = json.loads(report_path.read_text(encoding="utf-8"))
        assert envelope["report"]["production_quality"] is None
        assert len(envelope["report"]["variants"]) == (4 if profile == "captured" else 2)
        reports.append(envelope["report"])
    assert reports[0] == reports[1]
    assert frozen_cli.main(["status", "--preparation", identifier]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["state"] == "complete"
    assert status["claimed_at"] and status["completed_at"]
