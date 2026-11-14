import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.datasets.__main__ import main


@pytest.fixture
def command(monkeypatch):
    from tools.datasets import participants

    calls = []
    store = SimpleNamespace(
        enroll=lambda **values: calls.append(values) or {
            "enrollment_id": "enrollment-one", "subject_id": "subject-one",
            "source_key": "private-source", "consent_ref": "private-canary",
        },
        review_session=lambda **values: calls.append(values) or {
            "review_id": "review-one", "revision": 1, "status": "approved",
            "behavior": "manual", "intent": "benign", "evidence_ref": "private-canary",
        },
        inspect_session=lambda **values: {
            "digest": "a" * 64, "expected_revision": 0,
            "session": {"user_agent": "private-inspection-canary"},
        },
        load_approved=lambda sources: [SimpleNamespace(
            subject_id="one", behavior="manual", intent="benign",
        ), SimpleNamespace(subject_id="one", behavior="automated", intent="unknown")],
        withdraw=lambda subject, **values: calls.append(values) or {
            "status": "withdrawn", "sources_deleted": 1,
        },
        engine=SimpleNamespace(dispose=lambda: None),
    )
    monkeypatch.setenv("BOUNCER_DATABASE_URL", "sqlite:///private.db")
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", "sqlite:///private.db")
    monkeypatch.setattr(participants, "StudyStore", lambda url: store)
    return calls


def test_enrollment_dispatch_parses_dates_and_omits_private_references(command, tmp_path, capsys):
    path = tmp_path / "enrollment.json"
    path.write_text(json.dumps({
        "source_key": "private-source", "consent_ref": "private-canary",
        "consent_granted_at": "2026-11-13T00:00:00+00:00",
        "collection_from": "2026-11-14T00:00:00+00:00",
        "collection_until": "2026-11-15T00:00:00+00:00",
    }), encoding="utf-8")
    assert main(["participants", "enroll", "--input", str(path)]) == 0
    result = capsys.readouterr()
    assert json.loads(result.out)["enrollment_id"] == "enrollment-one"
    assert "private-canary" not in result.out + result.err
    assert isinstance(command[0]["collection_from"], datetime)


def test_approval_summary_distinguishes_human_operation_and_automation(command, capsys):
    assert main(["participants", "approved", "--source", "private-source"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "approved_observations": 2, "subjects": 1, "human_reference_sessions": 1,
        "automated_observations": 1, "other_observations": 0,
        "release_evaluation_available": False,
    }
    assert command == []


def test_participants_refuses_implicit_or_different_case_database_before_connect(
    command, monkeypatch, capsys,
):
    from tools.datasets import participants

    monkeypatch.setattr(participants, "StudyStore", lambda url: pytest.fail("connected"))
    for case_url in (None, "sqlite:///other.db"):
        if case_url is None:
            monkeypatch.delenv("BOUNCER_DATABASE_URL", raising=False)
        else:
            monkeypatch.setenv("BOUNCER_DATABASE_URL", case_url)
        assert main(["participants", "approved", "--source", "private-source"]) == 2
    assert "sqlite" not in capsys.readouterr().err


def test_participants_input_is_bounded_and_errors_hide_content(command, tmp_path, capsys):
    path = tmp_path / "input.json"
    for content in ("private-canary", json.dumps(["private-canary"]), "x" * 16_385):
        path.write_text(content, encoding="utf-8")
        assert main(["participants", "enroll", "--input", str(path)]) == 2
    assert command == []
    assert "private-canary" not in capsys.readouterr().err


def test_review_and_withdraw_require_explicit_operator_inputs(command, tmp_path, capsys):
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"status": "approved"}), encoding="utf-8")
    assert main(["participants", "review-session", "--input", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["revision"] == 1 and "evidence_ref" not in result
    assert main(["participants", "withdraw", "--subject", "subject-one",
                 "--confirm-subject", "subject-one", "--confirm-writer-stopped"]) == 0
    assert command[-1] == {"confirm_subject": "subject-one", "writer_stopped": True}


def test_private_cli_roundtrip_records_reviews_and_erases_collection(tmp_path, monkeypatch, capsys):
    from bouncer.db.traffic import TrafficRepository
    from tests.a.test_traffic_repository import fixture_payload

    url = f"sqlite:///{tmp_path / 'study.db'}"
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    repository = TrafficRepository(url)
    payload = fixture_payload()[3] | {"synthetic": False, "labels": []}
    repository.save_snapshot(payload, source_key="private-study")
    path = tmp_path / "private-input.json"

    def record(command, values):
        path.write_text(json.dumps(values), encoding="utf-8")
        assert main(["participants", command, "--input", str(path)]) == 0
        output = capsys.readouterr()
        assert "consent-canary" not in output.out + output.err
        return json.loads(output.out)

    enrollment = record("enroll", {
        "source_key": "private-study", "consent_ref": "consent-canary",
        "consent_version": "study-v1", "consent_granted_at": "2026-11-13T00:00:00Z",
        "collection_from": "2026-11-14T00:00:00Z",
        "collection_until": "2026-11-15T00:00:00Z", "evaluation_allowed": True,
        "exclusive_source": True, "operator_ref": "operator-one",
    })
    inspection = tmp_path / "inspection.json"
    assert main(["participants", "inspect-session", "--enrollment", enrollment["enrollment_id"],
                 "--session", payload["sessions"][0]["id"], "--output", str(inspection)]) == 0
    capsys.readouterr()
    inspected = json.loads(inspection.read_text(encoding="utf-8"))
    record("review-session", {
        "enrollment_id": enrollment["enrollment_id"],
        "external_session_id": payload["sessions"][0]["id"], "expected_revision": 0,
        "expected_session_digest": inspected["digest"],
        "status": "approved", "behavior": "manual", "intent": "benign",
        "mapping_ref": "mapping-one", "evidence_ref": "observation-one",
        "reviewer_ref": "reviewer-one",
    })
    assert main(["participants", "approved", "--source", "private-study"]) == 0
    assert json.loads(capsys.readouterr().out)["human_reference_sessions"] == 1
    subject_id = enrollment["subject_id"]
    assert main(["participants", "withdraw", "--subject", subject_id,
                 "--confirm-subject", subject_id, "--confirm-writer-stopped"]) == 0
    capsys.readouterr()
    assert repository.load_sessions(source_key="private-study") == []
    assert main(["participants", "approved", "--source", "private-study"]) == 0
    assert json.loads(capsys.readouterr().out)["human_reference_sessions"] == 0
    repository.engine.dispose()


def test_inspection_is_private_bounded_and_refuses_overwrite_or_repo_output(
    command, tmp_path, monkeypatch, capsys,
):
    from tools.datasets import participants

    path = tmp_path / "inspection.json"
    args = ["participants", "inspect-session", "--enrollment", "enrollment-one",
            "--session", "native-session", "--output"]
    assert main(args + [str(path)]) == 0
    before = path.read_bytes()
    assert b"private-inspection-canary" in before
    assert main(args + [str(path)]) == 2
    assert path.read_bytes() == before
    assert main(args + [str(Path(__file__).resolve().parents[2] / "inspection.json")]) == 2
    output = capsys.readouterr()
    assert "private-inspection-canary" not in output.out + output.err
    giant = SimpleNamespace(
        inspect_session=lambda **values: {"session": "x" * (8 * 1024 * 1024 + 1)},
        engine=SimpleNamespace(dispose=lambda: None),
    )
    monkeypatch.setattr(participants, "StudyStore", lambda url: giant)
    oversized = tmp_path / "too-big.json"
    assert main(args + [str(oversized)]) == 2
    assert not oversized.exists()
