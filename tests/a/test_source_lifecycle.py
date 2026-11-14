"""Source deletion uses only disposable SQLite/opt-in PostgreSQL databases."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, select, text, update

from bouncer.db.__main__ import main
from bouncer.db.health import components, record_heartbeat
from bouncer.db.traffic import CheckpointConflict, TrafficRepository, sources
from bouncer.ingest.worker import Worker
from bouncer.investigations.store import (
    InvestigationStore,
    budget,
    cases,
    jobs,
    reservations,
)
from tests.a import test_traffic_repository as traffic_fixtures
from tests.a.test_investigations_store import snapshot
from tests.a.test_migrations import engine, postgres_url  # noqa: F401
from tests.a.test_traffic_repository import batch, fixture_payload

repository = traffic_fixtures.repository

CANARY = "private-source-deletion-canary"


def case_store(repo):
    return InvestigationStore(repo.engine.url.render_as_string(hide_password=False))


def test_purge_erases_native_and_private_payloads_and_prevents_resurrection(repository):
    repo = repository
    cp = batch(repo)
    _, session, label, payload = fixture_payload()
    repo.save_snapshot(payload, source_key="other")
    with repo.engine.begin() as conn:
        conn.execute(update(sources).where(sources.c.source_key == "source-a").values(
            snapshot={"synthetic": True, "import_report": CANARY,
                      "source_provenance": CANARY, "verdicts": CANARY},
            resume_state={"partial": CANARY},
        ))

    report = repo.delete_source("source-a", expected_checkpoint=cp)

    assert report["requests_deleted"] == 2
    assert report["sessions_deleted"] == report["labels_deleted"] == 1
    assert report["revision"] == cp.revision + 1
    assert "backups" in report["scope"] and "files" in report["scope"]
    assert repo.load_sessions(source_key="source-a") == []
    assert repo.load_labels(source_key="source-a") == []
    assert repo.load_checkpoint("source-a") is None
    assert repo.load_snapshot("source-a") == {
        "source_deleted": True, "synthetic": True, "sessions": [], "labels": [],
    }
    assert repo.load_resume_state("source-a") == {"deleted": True}
    with repo.engine.connect() as conn:
        tombstone = dict(conn.execute(select(sources).where(
            sources.c.source_key == "source-a"
        )).mappings().one())
    assert tombstone["read_only"] is True and CANARY not in json.dumps(tombstone)
    assert repo.load_sessions(source_key="other") == [session]
    assert repo.load_labels(source_key="other") == [label]
    with pytest.raises(ValueError, match="read-only"):
        batch(repo, expected=cp)
    with pytest.raises(ValueError, match="immutable|deleted"):
        repo.save_snapshot(payload, source_key="source-a")


def test_purge_cas_and_unknown_source_have_no_side_effects(repository):
    repo = repository
    cp = batch(repo)
    before = repo.load_snapshot("source-a")
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(repo.engine, "before_cursor_execute", observe)
    try:
        with pytest.raises(ValueError, match="unknown source"):
            repo.delete_source("missing", expected_checkpoint=None)
        with pytest.raises(CheckpointConflict):
            repo.delete_source("source-a", expected_checkpoint=replace(cp, revision=0))
    finally:
        event.remove(repo.engine, "before_cursor_execute", observe)
    assert not any(sql.lstrip().upper().startswith(("CREATE", "INSERT")) for sql in statements)
    assert repo.load_snapshot("source-a") == before
    assert repo.load_checkpoint("source-a") == cp


def test_purge_clears_only_source_heartbeats_and_stale_worker_cannot_recreate(repository):
    repo = repository
    cp = batch(repo)
    _, _, _, payload = fixture_payload()
    repo.save_snapshot(payload, source_key="other")
    assert record_heartbeat(repo.engine, "source-a", "review", state="ready", config_key=CANARY)
    assert record_heartbeat(repo.engine, "other", "review", state="ready", config_key="other")
    with repo.engine.connect() as conn:
        other = dict(conn.execute(select(components).where(
            components.c.source_id == "other"
        )).mappings().one())
        source_count = len(list(conn.execute(select(components).where(
            components.c.source_id == "source-a"
        ))))

    report = repo.delete_source("source-a", expected_checkpoint=cp)

    assert report["heartbeats_deleted"] == source_count
    for component in ("ingest", "review"):
        assert record_heartbeat(repo.engine, "source-a", component, state="ready",
                                config_key=CANARY) is False
    with repo.engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(select(components)).mappings()]
    assert rows == [other]
    assert CANARY not in json.dumps(rows, default=str)


def test_purge_tombstones_cases_and_preserves_unknown_charge_audit(repository):
    repo = repository
    cp = batch(repo)
    store = case_store(repo)
    try:
        case = store.create_from_legacy(snapshot(), "source-a", public_demo=True)
        other = store.create_from_legacy(snapshot(), "other", public_demo=True, source_id="other")
        job = store.enqueue_review(case["id"], "config", 100)
        store.claim_job("worker")
        reservation = store.start_request(job["id"], "reviewer", "fixture", "model", 80, "v1")
        store.settle_request(reservation["id"], None, {}, None)
        store.append_assessment(job["id"], "reviewer", {"private": CANARY}, {"private": CANARY})
        store.finish_job(job["id"], "unavailable", "timeout")
        with repo.engine.begin() as conn:
            payload = conn.scalar(select(cases.c.payload).where(cases.c.id == case["id"]))
            conn.execute(update(cases).where(cases.c.id == case["id"]).values(
                payload=payload | {"private": CANARY},
            ))
            audit = {table.name: [dict(row) for row in conn.execute(select(table)).mappings()]
                     for table in (jobs, reservations, budget)}

        report = repo.delete_source("source-a", expected_checkpoint=cp)

        assert report["cases_tombstoned"] == 1
        assert report["assessments_deleted"] == 2
        deleted = store.get_case(case["id"], False)
        assert deleted["source"]["kind"] == "deleted"
        assert deleted["complete"] is False and deleted["evidence"] == []
        assert deleted["local_assessment"] is None
        assert deleted["review_eligibility"]["eligible"] is False
        assert CANARY not in json.dumps(deleted)
        assert store.get_case(case["id"]) is None
        assert store.list_assessments(case["id"]) == []
        assert len(store.list_cases(False)) == 2
        assert store.get_case(other["id"]) == other
        with repo.engine.connect() as conn:
            after = {table.name: [dict(row) for row in conn.execute(select(table)).mappings()]
                     for table in (jobs, reservations, budget)}
        assert audit == after
        with pytest.raises(ValueError, match="ineligible"):
            store.enqueue_review(case["id"], "new-config", 100)
        with pytest.raises(ValueError, match="deleted"):
            store.create_from_legacy(snapshot(), "source-a")
    finally:
        store.engine.dispose()


@pytest.mark.parametrize("status", ["queued", "running"])
def test_purge_refuses_active_review_without_releasing_money(repository, status):
    repo = repository
    cp = batch(repo)
    store = case_store(repo)
    try:
        case = store.create_from_legacy(snapshot(), "private-review-scope", source_id="source-a")
        store.enqueue_review(case["id"], "config", 100)
        if status == "running":
            store.claim_job("worker")
        usage = store.usage()
        with pytest.raises(ValueError, match="queued|running|active review"):
            repo.delete_source("source-a", expected_checkpoint=cp)
        assert repo.load_checkpoint("source-a") == cp
        assert store.usage() == usage
        assert store.get_case(case["id"], False)["source"]["kind"] != "deleted"
    finally:
        store.engine.dispose()


def test_purge_failure_rolls_back_cases_assessments_and_native_payloads(repository):
    repo = repository
    cp = batch(repo)
    store = case_store(repo)
    case = store.create_from_legacy(snapshot(), "source-a", public_demo=True)

    def fail_delete(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("DELETE FROM requests"):
            raise RuntimeError("injected failure")

    event.listen(repo.engine, "before_cursor_execute", fail_delete)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            repo.delete_source("source-a", expected_checkpoint=cp)
    finally:
        event.remove(repo.engine, "before_cursor_execute", fail_delete)
    try:
        assert store.get_case(case["id"]) == case
        assert len(store.list_assessments(case["id"])) == 1
        assert repo.load_checkpoint("source-a") == cp
        assert len(repo.load_sessions(source_key="source-a")[0].requests) == 2
    finally:
        store.engine.dispose()


def test_deleted_source_worker_fails_before_private_resume(tmp_path):
    repo = TrafficRepository("sqlite:///" + str(tmp_path / "worker.db"))
    cp = batch(repo)
    repo.delete_source("source-a", expected_checkpoint=cp)
    with pytest.raises(ValueError, match="deleted"):
        Worker(tmp_path / "access.log", store=tmp_path / "absent.json",
               repository=repo, source_key="source-a", secret="", intel_fn=None,
               campaigns_fn=lambda sessions: [], synthetic=True)


def test_uploaded_archive_private_reports_and_cases_are_deleted_together(repository):
    repo = repository
    store = case_store(repo)
    _, _, _, payload = fixture_payload()
    payload["labels"] = []
    try:
        case = store.create_traffic_import(
            payload, source_key="upload", report={"private": CANARY},
            provenance={"private": CANARY},
        )
        assert CANARY in json.dumps(repo.load_snapshot("upload"))
        report = repo.delete_source("upload", expected_checkpoint=None)
        assert report["requests_deleted"] == 2 and report["cases_tombstoned"] == 1
        assert CANARY not in json.dumps(repo.load_snapshot("upload"))
        assert store.get_case(case["id"], False)["source"]["kind"] == "deleted"
        with pytest.raises(ValueError, match="immutable|deleted"):
            store.create_traffic_import(payload, source_key="upload", report={}, provenance={})
    finally:
        store.engine.dispose()


@pytest.mark.parametrize("confirmation", [[], ["--confirm-source", "other"],
                                         ["--confirm-source", "source-a"]])
def test_cli_purge_requires_matching_source_and_stopped_writer(tmp_path, monkeypatch, confirmation):
    path = tmp_path / "never-created.db"
    monkeypatch.delenv("BOUNCER_DATABASE_URL", raising=False)
    assert main(["purge-source", "--source", "source-a", "--database-url",
                 "sqlite:///" + str(path), *confirmation]) == 2
    assert not path.exists()


def test_cli_purge_checks_cross_database_before_connecting(tmp_path, monkeypatch):
    path = tmp_path / "never-created.db"
    monkeypatch.setenv("BOUNCER_DATABASE_URL", "sqlite:///different.db")
    assert main(["purge-source", "--source", "source-a", "--database-url",
                 "sqlite:///" + str(path), "--confirm-source", "source-a",
                 "--confirm-writer-stopped"]) == 2
    assert not path.exists()


def test_cli_purge_uses_selected_database_and_preserves_files(tmp_path, monkeypatch, capsys):
    url = "sqlite:///" + str(tmp_path / "selected.db")
    repo = TrafficRepository(url)
    batch(repo)
    original = tmp_path / "original.json"
    original.write_text(CANARY)
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    assert main(["purge-source", "--source", "source-a", "--confirm-source", "source-a",
                 "--confirm-writer-stopped"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["requests_deleted"] == 2
    assert original.read_text() == CANARY
    assert repo.load_resume_state("source-a") == {"deleted": True}


def test_cli_purge_rejects_writer_that_commits_after_confirmation_read(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "racing.db")
    repo = TrafficRepository(url)
    batch(repo)
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    delete_source = TrafficRepository.delete_source

    def advance_then_delete(self, source_key, *, expected_checkpoint):
        batch(self, expected=expected_checkpoint)
        return delete_source(self, source_key, expected_checkpoint=expected_checkpoint)

    monkeypatch.setattr(TrafficRepository, "delete_source", advance_then_delete)
    assert main(["purge-source", "--source", "source-a", "--database-url", url,
                 "--confirm-source", "source-a", "--confirm-writer-stopped"]) == 2
    assert repo.load_resume_state("source-a") != {"deleted": True}
    assert len(repo.load_sessions(source_key="source-a")) == 1


@pytest.mark.parametrize("binding", ["explicit", "snapshot"])
def test_scoped_case_binds_actual_origin_and_purge_blocks_scoped_recreation(repository, binding):
    repo = repository
    cp = batch(repo)
    store = case_store(repo)
    raw = snapshot()
    kwargs = {"source_id": "source-a"} if binding == "explicit" else {}
    if binding == "snapshot":
        raw["traffic_source_id"] = "source-a"
    try:
        case = store.create_from_legacy(raw, "private-review-scope", **kwargs)
        with repo.engine.connect() as conn:
            stored_source = conn.scalar(select(cases.c.source_id).where(cases.c.id == case["id"]))
            assert stored_source == "source-a"
        report = repo.delete_source("source-a", expected_checkpoint=cp)
        assert report["cases_tombstoned"] == 1
        assert store.get_case(case["id"], False)["source"]["kind"] == "deleted"
        with pytest.raises(ValueError, match="deleted"):
            store.create_from_legacy(raw, "another-scope", **kwargs)
    finally:
        store.engine.dispose()


def test_origin_binding_distinguishes_identical_cases_in_same_scope(repository):
    repo = repository
    cp = batch(repo)
    store = case_store(repo)
    try:
        first = store.create_from_legacy(snapshot(), source_id="source-a")
        second = store.create_from_legacy(snapshot(), source_id="other")
        assert first["id"] != second["id"]
        assert first == store.create_from_legacy(snapshot(), source_id="source-a")
        assert repo.delete_source("source-a", expected_checkpoint=cp)["cases_tombstoned"] == 1
        assert store.get_case(second["id"], False) == second
    finally:
        store.engine.dispose()


def test_explicit_origin_wins_over_a_scope_that_matches_another_source(repository):
    repo = repository
    cp = batch(repo)
    store = case_store(repo)
    try:
        case = store.create_from_legacy(snapshot(), "source-a", source_id="other")
        assert repo.delete_source("source-a", expected_checkpoint=cp)["cases_tombstoned"] == 0
        assert store.get_case(case["id"], False) == case
        with pytest.raises(ValueError, match="does not match"):
            store.create_from_legacy(snapshot() | {"traffic_source_id": "source-a"},
                                     source_id="other")
    finally:
        store.engine.dispose()


def test_purge_refuses_unbound_monitored_cases_without_erasing_anything(repository):
    repo = repository
    cp = batch(repo)
    store = case_store(repo)
    try:
        legacy = store.create_from_legacy(snapshot(), "legacy-review-scope")
        with pytest.raises(ValueError, match="unbound.*monitored|monitored.*source identity"):
            repo.delete_source("source-a", expected_checkpoint=cp)
        assert repo.load_checkpoint("source-a") == cp
        assert store.get_case(legacy["id"], False) == legacy
        assert repo.load_sessions(source_key="source-a")
    finally:
        store.engine.dispose()


def test_cli_refuses_unconfigured_investigation_database_before_connecting(tmp_path, monkeypatch,
                                                                         capsys):
    path = tmp_path / "never-created.db"
    monkeypatch.delenv("BOUNCER_DATABASE_URL", raising=False)
    assert main(["purge-source", "--source", "source-a", "--database-url",
                 "sqlite:///" + str(path), "--confirm-source", "source-a",
                 "--confirm-writer-stopped"]) == 2
    assert "BOUNCER_DATABASE_URL" in capsys.readouterr().err
    assert not path.exists()


def test_cli_reports_action_needed_for_unbound_legacy_cases(tmp_path, monkeypatch, capsys):
    url = "sqlite:///" + str(tmp_path / "unbound.db")
    repo = TrafficRepository(url)
    cp = batch(repo)
    store = case_store(repo)
    try:
        store.create_from_legacy(snapshot(), "private-unbound-scope")
        monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
        assert main(["purge-source", "--source", "source-a", "--database-url", url,
                     "--confirm-source", "source-a", "--confirm-writer-stopped"]) == 2
        error = capsys.readouterr().err
        assert "bind verified source_id" in error
        assert "private-unbound-scope" not in error
        assert repo.load_checkpoint("source-a") == cp
    finally:
        store.engine.dispose()


def test_api_default_scope_case_is_erased_with_selected_source(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from bouncer.api.app import app

    url = "sqlite:///" + str(tmp_path / "api.db")
    repo = TrafficRepository(url)
    cp = batch(repo)
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "source-a")
    monkeypatch.setenv("BOUNCER_ADMIN_TOKEN", "test-admin")
    headers = {"Authorization": "Bearer test-admin"}
    with TestClient(app) as client:
        response = client.post("/api/investigations", headers=headers,
                               json={"source": "monitored_traffic"})
        assert response.status_code == 201, response.text
        case_id = response.json()["id"]
        assert repo.delete_source("source-a", expected_checkpoint=cp)["cases_tombstoned"] == 1
        deleted = client.get(f"/api/investigations/{case_id}", headers=headers).json()
        assert deleted["source"]["kind"] == "deleted"
        assert client.post("/api/investigations", headers=headers,
                           json={"source": "monitored_traffic"}).status_code == 422


@pytest.mark.parametrize("adapter", ["sqlite", "postgres"])
def test_origin_upgrade_binds_only_exact_existing_sources(request, tmp_path, adapter):
    database = (request.getfixturevalue("engine") if adapter == "postgres"
                else create_engine("sqlite:///" + str(tmp_path / "old-cases.db")))
    if adapter == "sqlite":
        TrafficRepository(database)
    with database.begin() as conn:
        if adapter == "postgres":
            conn.exec_driver_sql(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                "checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            for path in sorted(Path("src/bouncer/db/migrations").glob("00[1-5]_*.sql")):
                content = path.read_text(encoding="utf-8-sig")
                conn.exec_driver_sql(content)
                conn.execute(text("INSERT INTO schema_migrations (version, name, checksum) "
                                  "VALUES (:version, :name, :checksum)"), {
                    "version": int(path.name[:3]), "name": path.name,
                    "checksum": hashlib.sha256(content.encode()).hexdigest(),
                })
        else:
            conn.exec_driver_sql(
                "CREATE TABLE investigation_cases (id VARCHAR PRIMARY KEY, source_key VARCHAR "
                "NOT NULL, evidence_hash VARCHAR NOT NULL, public BOOLEAN NOT NULL, payload JSON "
                "NOT NULL, created_at VARCHAR NOT NULL, UNIQUE(source_key, evidence_hash))"
            )
        conn.exec_driver_sql(
            "INSERT INTO traffic_sources (source_key, generation, byte_offset, revision, snapshot, "
            "resume_state, read_only) VALUES ('source-a', NULL, 0, 0, '{}', '{}', false)"
        )
        for case_id, scope in (("bound", "source-a"), ("unbound", "overview")):
            conn.execute(text(
                "INSERT INTO investigation_cases (id, source_key, evidence_hash, public, payload, "
                "created_at) VALUES (:id, :scope, :id, false, '{}', '2026-11-14')"
            ), {"id": case_id, "scope": scope})
    store = InvestigationStore(database.url.render_as_string(hide_password=False))
    try:
        assert "source_id" in {column["name"] for column in inspect(database).get_columns(
            "investigation_cases"
        )}
        assert ["source_id"] in [index["column_names"] for index in inspect(database).get_indexes(
            "investigation_cases"
        )]
        with database.connect() as conn:
            assert dict(conn.execute(select(cases.c.id, cases.c.source_id)).all()) == {
                "bound": "source-a", "unbound": None,
            }
    finally:
        store.engine.dispose()
        if adapter == "sqlite":
            database.dispose()


def test_postgres_purge_and_batch_cannot_repopulate_source(engine):  # noqa: F811
    repo = TrafficRepository(engine)
    cp = batch(repo)

    def writer():
        try:
            return batch(repo, expected=cp)
        except (CheckpointConflict, ValueError):
            return None

    def purge():
        try:
            return repo.delete_source("source-a", expected_checkpoint=cp)
        except CheckpointConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        write, deletion = pool.submit(writer), pool.submit(purge)
        results = write.result(), deletion.result()
    if results[1] is None:
        repo.delete_source("source-a", expected_checkpoint=repo.load_checkpoint("source-a"))
    assert repo.load_sessions(source_key="source-a") == []
    assert repo.load_resume_state("source-a") == {"deleted": True}


def test_api_binds_copied_archive_to_selected_database_source(repository, monkeypatch):
    from fastapi.testclient import TestClient

    from bouncer.api.app import app
    repo = repository
    payload = fixture_payload()[3] | {"traffic_source_id": "original-live-source"}
    repo.save_snapshot(payload, source_key="copied-archive")
    url = repo.engine.url.render_as_string(hide_password=False)
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "copied-archive")
    monkeypatch.setenv("BOUNCER_ADMIN_TOKEN", "test-admin")
    with TestClient(app) as client:
        response = client.post("/api/investigations", headers={
            "Authorization": "Bearer test-admin",
        }, json={"source": "monitored_traffic"})
        assert response.status_code == 201, response.text
        report = repo.delete_source("copied-archive", expected_checkpoint=None)
        assert report["cases_tombstoned"] == 1
