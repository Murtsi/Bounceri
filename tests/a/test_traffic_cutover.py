"""Offline archive and retention commands use disposable databases only."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import stat
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from bouncer.db.__main__ import main
from bouncer.db.traffic import Checkpoint, SourceEvent, TrafficRepository, requests, sources
from bouncer.ingest.tail import LogTail
from tests.a.test_traffic_repository import fixture_payload


def cutover():
    assert importlib.util.find_spec("bouncer.db.cutover") is not None, "archive helper missing"
    return importlib.import_module("bouncer.db.cutover")


@pytest.fixture
def archive(tmp_path):
    _, session, label, payload = fixture_payload()
    payload["session_identity_state"] = {"private": "compatibility only"}
    payload["session_label_state"] = {"private": "compatibility only"}
    path = tmp_path / "snapshot.json"
    raw = json.dumps(payload).encode()
    path.write_bytes(raw)
    repo = TrafficRepository("sqlite:///" + str(tmp_path / "traffic.db"))
    yield path, raw, repo, session, label, payload
    repo.engine.dispose()


def test_backfill_is_verified_immutable_idempotent_archive_and_keeps_original(archive):
    path, raw, repo, session, label, payload = archive
    report = cutover().backfill_json(path, repo)
    digest = hashlib.sha256(raw).hexdigest()
    assert report == {
        "source_key": "archive/" + digest,
        "sha256": digest,
        "sessions": 1,
        "requests": 2,
        "labels": 1,
    }
    assert cutover().backfill_json(path, repo) == report
    assert path.read_bytes() == raw
    assert repo.load_sessions(source_key=report["source_key"]) == [session]
    assert repo.load_labels(source_key=report["source_key"]) == [label]
    assert repo.load_checkpoint(report["source_key"]) is None
    expected = {k: v for k, v in payload.items() if not k.startswith("session_")}
    assert repo.load_snapshot(report["source_key"]) == expected
    with pytest.raises(ValueError, match="immutable"):
        repo.save_snapshot(expected | {"synthetic": False}, source_key=report["source_key"])
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(requests)) == 2


@pytest.mark.parametrize("synthetic", [None, 0, 1, "false", [], {}])
def test_backfill_requires_explicit_boolean_provenance(archive, synthetic):
    path, _, repo, _, _, payload = archive
    payload["synthetic"] = synthetic
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic"):
        cutover().backfill_json(path, repo)
    assert repo.load_sessions(source_key="monitored") == []


def test_backfill_rejects_missing_provenance_and_oversized_input(archive, monkeypatch):
    path, _, repo, _, _, payload = archive
    del payload["synthetic"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic"):
        cutover().backfill_json(path, repo)
    monkeypatch.setattr(cutover(), "MAX_SNAPSHOT_BYTES", 10)
    with pytest.raises(ValueError, match="size"):
        cutover().backfill_json(path, repo)


@pytest.mark.parametrize(
    "field,value", [("headers", {"secret": ["bad"]}), ("headers", []), ("status", True)]
)
def test_backfill_validates_native_request_types_before_writing(archive, field, value):
    path, _, repo, _, _, payload = archive
    payload["sessions"][0]["requests"][0][field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot"):
        cutover().backfill_json(path, repo)


def test_backfill_rejects_nonfinite_metadata_before_writing(archive):
    path, _, repo, _, _, payload = archive
    payload["metadata"] = float("nan")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot"):
        cutover().backfill_json(path, repo)
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(requests)) == 0


def test_backfill_fails_verification_when_roundtrip_changes_metadata(archive, monkeypatch):
    path, _, repo, _, _, _ = archive
    load = repo.load_snapshot
    monkeypatch.setattr(repo, "load_snapshot", lambda key: load(key) | {"synthetic": False})
    with pytest.raises(ValueError, match="verification"):
        cutover().backfill_json(path, repo)


def test_cli_backfill_prints_only_safe_report(archive, capsys, monkeypatch):
    path, raw, repo, _, _, _ = archive
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", str(repo.engine.url))
    assert main(["backfill-json", "--snapshot", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result) == {"source_key", "sha256", "sessions", "requests", "labels"}
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()


def test_cli_suppresses_sensitive_database_errors(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("BOUNCER_TRAFFIC_DATABASE_URL", raising=False)
    path = tmp_path / "snapshot.json"
    path.write_text('{"synthetic": false, "sessions": [], "labels": []}')
    assert main(["backfill-json", "--snapshot", str(path)]) == 2
    assert "required" in capsys.readouterr().err
    secret_url = "unknown://private-user:private-password@192.0.2.99/secret"
    assert main(["backfill-json", "--snapshot", str(path), "--database-url", secret_url]) == 2
    output = capsys.readouterr()
    assert "failed" in output.err
    assert "private" not in output.err and "192.0.2.99" not in output.err


@pytest.mark.parametrize("command", ["seed", "clear"])
def test_cli_offline_commands_refuse_selected_sql_without_explicit_flag(
    tmp_path, monkeypatch, capsys, command
):
    path = tmp_path / "offline.json"
    path.write_text("unchanged")
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(path))
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", "sqlite://")
    assert main([command]) == 2
    assert "--offline" in capsys.readouterr().err
    assert path.read_text() == "unchanged"
    assert main([command, "--offline"]) == 0
    if command == "clear":
        assert not path.exists()
    else:
        assert json.loads(path.read_text())["synthetic"] is True


def test_cli_prune_is_explicit_source_scoped_and_requires_timezone(archive, monkeypatch, capsys):
    _, _, repo, session, _, payload = archive
    event = SourceEvent("live", 0, session.requests[0], session.id)
    for source in ("fixture-live", "other"):
        repo.apply_batch(
            source,
            events=[event],
            snapshot=payload
            | {
                "sessions": [
                    payload["sessions"][0] | {"requests": [payload["sessions"][0]["requests"][0]]}
                ]
            },
            checkpoint=Checkpoint("live", 100),
            expected_checkpoint=None,
        )
        repo.apply_batch(
            source,
            events=[],
            snapshot={"synthetic": True, "sessions": [], "labels": []},
            checkpoint=Checkpoint("live", 100),
            expected_checkpoint=repo.load_checkpoint(source),
        )
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", str(repo.engine.url))
    monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "fixture-live")
    assert main(["prune", "--before", "2026-11-15T00:00:00"]) == 2
    assert "timezone" in capsys.readouterr().err
    before = (session.ended_at + timedelta(days=1)).isoformat()
    assert main(["prune", "--before", before]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requests_deleted"] == 1
    assert repo.load_sessions(source_key="fixture-live") == []
    assert len(repo.load_sessions(source_key="other")) == 1


def export_api():
    function = getattr(cutover(), "export_json", None)
    assert function is not None, "rollback export missing"
    return function


def save_resumable_source(repo, payload, session, tmp_path):
    log = tmp_path / "access.jsonl"
    record = {
        "ts": session.started_at.timestamp(),
        "request": {"client_ip": session.ip, "method": "GET", "uri": "/", "headers": {}},
        "status": 200,
    }
    log.write_text(json.dumps(record) + "\n", encoding="utf-8")
    tail = LogTail(log)
    retained = tail.read_new()
    resumed = {
        "tail": tail.checkpoint(),
        "records": retained,
        "session_identity_state": [payload["sessions"][0] | {"requests": []}],
        "session_label_state": {session.id: {"marker": "private", "conflict": False}},
        "discarded_by_retention": 3,
    }
    events = [
        SourceEvent(tail.generation, i, request, session.id)
        for i, request in enumerate(session.requests)
    ]
    repo.apply_batch(
        "fixture-live",
        events=events,
        snapshot=payload,
        checkpoint=Checkpoint(tail.generation, tail.offset),
        expected_checkpoint=None,
        resume_state=resumed,
    )
    return log, resumed


def test_export_preserves_fresh_snapshot_and_private_resume_without_overwrite(archive, tmp_path):
    _, _, repo, session, _, payload = archive
    log, resumed = save_resumable_source(repo, payload, session, tmp_path)
    path = tmp_path / "rollback.json"
    report = export_api()(repo, "fixture-live", path)
    exported = json.loads(path.read_bytes())
    assert exported.pop("worker_resume_state") == resumed
    assert exported.pop("session_identity_state") == resumed["session_identity_state"]
    assert exported.pop("session_label_state") == resumed["session_label_state"]
    assert exported == {
        key: value
        for key, value in payload.items()
        if key not in {"session_identity_state", "session_label_state"}
    }
    assert report == {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sessions": 1,
        "requests": 2,
        "labels": 1,
    }
    restored = LogTail(log)
    restored.restore(resumed["tail"])
    assert restored.read_new() == []
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(resumed["records"][0]) + "\n")
    assert len(restored.read_new()) == 1
    assert len(resumed["records"]) == 1
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        export_api()(repo, "fixture-live", path)
    assert path.read_bytes() == original


def test_backfill_rollback_file_omits_all_private_worker_state(archive):
    path, _, repo, _, _, payload = archive
    payload["worker_resume_state"] = {"tail": {"private": "state"}, "records": []}
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = cutover().backfill_json(path, repo)
    assert "worker_resume_state" not in repo.load_snapshot(report["source_key"])


def test_export_archive_omits_nonworker_resume_and_rejects_missing_provenance(archive, tmp_path):
    _, _, repo, _, _, payload = archive
    repo.save_snapshot(payload, source_key="archive-fixture")
    output = tmp_path / "archive.json"
    export_api()(repo, "archive-fixture", output)
    assert "worker_resume_state" not in json.loads(output.read_bytes())
    missing = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="provenance"):
        export_api()(repo, "absent", missing)
    assert not missing.exists()
    with repo.engine.begin() as conn:
        conn.execute(
            update(sources).where(sources.c.source_key == "archive-fixture").values(snapshot={})
        )
    with pytest.raises(ValueError, match="provenance"):
        export_api()(repo, "archive-fixture", missing)
    assert not missing.exists()


def test_export_aborts_if_checkpoint_changes_and_cleans_failed_write(
    archive, tmp_path, monkeypatch
):
    _, _, repo, session, _, payload = archive
    save_resumable_source(repo, payload, session, tmp_path)
    output = tmp_path / "rollback.json"
    original = repo.load_checkpoint("fixture-live")
    reads = iter(
        [original, Checkpoint(original.generation, original.byte_offset, original.revision + 1)]
    )
    with monkeypatch.context() as patch:
        patch.setattr(repo, "load_checkpoint", lambda source: next(reads))
        with pytest.raises(ValueError, match="changed"):
            export_api()(repo, "fixture-live", output)
    assert not output.exists()
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("private failure")))
    with pytest.raises(OSError):
        export_api()(repo, "fixture-live", output)
    assert not output.exists()


def test_cli_export_uses_environment_source_and_prints_only_safe_report(
    archive, tmp_path, monkeypatch, capsys
):
    _, _, repo, session, _, payload = archive
    save_resumable_source(repo, payload, session, tmp_path)
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", str(repo.engine.url))
    monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "fixture-live")
    output = tmp_path / "rollback.json"
    assert main(["export-json", "--output", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report) == {"sha256", "sessions", "requests", "labels"}
    assert main(["export-json", "--output", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "failed" in captured.err and "private" not in captured.err
