"""Durable normalized traffic; PostgreSQL fixtures own only disposable databases."""

from __future__ import annotations

import importlib
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, func, select

from bouncer.contracts import Request, Session, SessionLabel
from bouncer.db.store import _serialize_label, _serialize_session
from tests.a.test_migrations import engine, postgres_url  # noqa: F401


def api():
    assert importlib.util.find_spec("bouncer.db.traffic") is not None, "traffic repository missing"
    return importlib.import_module("bouncer.db.traffic")


def fixture_payload(count=2):
    request = Request(
        datetime(2026, 11, 14, tzinfo=UTC),
        "192.0.2.1",
        "POST",
        "/login",
        401,
        "fixture",
        "a=one&a=two",
        123,
        {"accept": "text/html"},
        "text/html",
        "alice",
    )
    session = Session(
        "opaque/session-one",
        request.ip,
        request.user_agent,
        request.ts,
        request.ts,
        (request,) * count,
    )
    label = SessionLabel(session.id, "signed-run", "human", "trusted-campaign")
    payload = {
        "sessions": [_serialize_session(session)],
        "labels": [_serialize_label(label)],
        "synthetic": True,
        "source": "fixture",
        "verdicts": {session.id: {"label": "uncertain"}},
        "campaigns": [{"id": "observed-campaign", "session_ids": [session.id]}],
        "ingest": {"retained_records": count},
    }
    return request, session, label, payload


@pytest.fixture(params=["sqlite", "postgres"])
def repository(request, tmp_path):
    module = api()
    if request.param == "postgres":
        database = request.getfixturevalue("engine")
    else:
        database = create_engine("sqlite:///" + str(tmp_path / "traffic.db"))
    repo = module.TrafficRepository(database)
    yield repo
    if request.param == "sqlite":
        database.dispose()


def batch(repo, *, expected=None, generation="generation-a", offset=200, count=2):
    module = api()
    request, session, _, payload = fixture_payload(count)
    events = [
        module.SourceEvent(generation, index * 100, request, session.id) for index in range(count)
    ]
    checkpoint = module.Checkpoint(generation, offset)
    return repo.apply_batch(
        "source-a",
        events=events,
        snapshot=payload,
        checkpoint=checkpoint,
        expected_checkpoint=expected,
        resume_state={"partial": "private", "records": []},
    )


def test_duplicate_identical_requests_and_replay_keep_exact_source_identity(repository):
    repo = repository
    batch(repo)
    result = repo.load_snapshot("source-a")
    expected = repo.load_checkpoint("source-a")
    batch(repo, expected=expected)
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().requests)) == 2
    assert len(result["sessions"][0]["requests"]) == 2
    assert "resume_state" not in result and "partial" not in str(result)


def test_roundtrip_reopen_and_source_scoped_readers(repository):
    repo = repository
    batch(repo)
    module = api()
    reopened = module.TrafficRepository(repo.engine)
    request, session, label, payload = fixture_payload()
    assert reopened.load_sessions(source_key="source-a") == [session]
    assert reopened.load_labels(source_key="source-a") == [label]
    assert reopened.load_sessions(request.ts + timedelta(seconds=1), source_key="source-a") == []
    assert reopened.load_sessions(source_key="other") == []
    assert reopened.load_labels(source_key="other") == []
    assert reopened.load_snapshot("source-a") == payload
    assert reopened.load_resume_state("source-a") == {"partial": "private", "records": []}


@pytest.mark.parametrize("reader", ["history", "snapshot"])
def test_multi_query_reads_keep_one_batch_during_concurrent_commit(repository, reader):
    repo = repository
    module = api()
    if repo.engine.dialect.name == "sqlite":
        with repo.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    checkpoint = batch(repo, count=1)
    request, original, _, payload = fixture_payload(count=1)
    later = replace(request, ts=request.ts + timedelta(seconds=1))
    updated = replace(original, ended_at=later.ts, requests=(request, later))
    next_payload = payload | {"sessions": [_serialize_session(updated)]}
    advanced = False

    def commit_before_request_query(conn, cursor, statement, parameters, context, executemany):
        nonlocal advanced
        if advanced or not statement.startswith("SELECT requests."):
            return
        advanced = True
        repo.apply_batch(
            "source-a",
            events=[module.SourceEvent("generation-a", 0, request, original.id),
                    module.SourceEvent("generation-a", 100, later, original.id)],
            snapshot=next_payload,
            checkpoint=module.Checkpoint("generation-a", 300),
            expected_checkpoint=checkpoint,
        )

    event.listen(repo.engine, "before_cursor_execute", commit_before_request_query)
    try:
        if reader == "history":
            assert repo.load_sessions(source_key="source-a") == [original]
        else:
            assert repo.load_snapshot("source-a") == payload
    finally:
        event.remove(repo.engine, "before_cursor_execute", commit_before_request_query)
    assert advanced
    assert repo.load_sessions(source_key="source-a") == [updated]


def test_failed_batch_rolls_back_checkpoint_requests_labels_and_snapshot(repository):
    repo = repository
    batch(repo)
    original = repo.load_snapshot("source-a")
    checkpoint = repo.load_checkpoint("source-a")

    def fail_labels(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO labels"):
            raise RuntimeError("injected failure")

    event.listen(repo.engine, "before_cursor_execute", fail_labels)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            batch(repo, expected=checkpoint, offset=300, count=1)
    finally:
        event.remove(repo.engine, "before_cursor_execute", fail_labels)
    assert repo.load_checkpoint("source-a") == checkpoint
    assert repo.load_snapshot("source-a") == original


def test_stale_checkpoint_is_rejected_and_retention_is_explicit(repository):
    repo = repository
    batch(repo)
    checkpoint = repo.load_checkpoint("source-a")
    batch(repo, expected=checkpoint, offset=300, count=1)
    with pytest.raises(api().CheckpointConflict):
        batch(repo, expected=checkpoint, offset=400)
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().requests)) == 2
    assert len(repo.load_snapshot("source-a")["sessions"][0]["requests"]) == 1
    assert repo.prune_before("source-a", fixture_payload()[0].ts + timedelta(seconds=1)) == 1
    assert len(repo.load_sessions(source_key="source-a")[0].requests) == 1


def test_snapshot_backfill_preserves_external_ids_and_labels(repository):
    repo = repository
    _, session, label, payload = fixture_payload()
    repo.save_snapshot(payload, source_key="backfill")
    repo.save_snapshot(payload, source_key="backfill")
    assert repo.load_sessions(source_key="backfill") == [session]
    assert repo.load_labels(source_key="backfill") == [label]
    assert repo.load_snapshot("backfill") == payload


def test_private_continuity_state_is_never_part_of_normalized_snapshot(repository):
    _, _, _, payload = fixture_payload()
    repository.save_snapshot(
        payload
        | {
            "session_identity_state": ["private-id"],
            "session_label_state": {"private-marker": "human"},
            "worker_resume_state": {"private": "tail-and-record-cache"},
        },
        source_key="backfill",
    )
    assert repository.load_snapshot("backfill") == payload


def test_atomic_retention_expires_only_hidden_history_and_keeps_old_visible_requests(repository):
    request, history, label, payload = fixture_payload(3)
    payload["sessions"] = [_serialize_session(replace(history, requests=(request,)))]
    events = [
        api().SourceEvent("generation-a", offset, request, history.id) for offset in (0, 100, 200)
    ]
    repository.apply_batch(
        "source-a",
        events=events,
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 300),
        expected_checkpoint=None,
        history_sessions=[history],
        history_labels=[label],
        visible_events=[events[-1]],
        retention_before=request.ts + timedelta(seconds=1),
    )
    assert repository.load_sessions(source_key="source-a")[0].requests == (request,)
    assert repository.load_labels(source_key="source-a") == [label]
    assert repository.load_snapshot("source-a") == payload


def test_atomic_retention_failure_rolls_back_history_snapshot_and_checkpoint(repository):
    repo = repository
    previous = batch(repo)
    original = repo.load_snapshot("source-a")
    request, history, label, payload = fixture_payload(3)
    payload["sessions"] = [_serialize_session(replace(history, requests=(request,)))]
    events = [
        api().SourceEvent("generation-a", offset, request, history.id) for offset in (0, 100, 200)
    ]

    def fail_prune(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("DELETE FROM requests"):
            raise RuntimeError("injected prune failure")

    event.listen(repo.engine, "before_cursor_execute", fail_prune)
    try:
        with pytest.raises(RuntimeError, match="injected prune failure"):
            repo.apply_batch(
                "source-a",
                events=events,
                snapshot=payload,
                checkpoint=api().Checkpoint("generation-a", 300),
                expected_checkpoint=previous,
                history_sessions=[history],
                history_labels=[label],
                visible_events=[events[-1]],
                retention_before=request.ts + timedelta(seconds=1),
            )
    finally:
        event.remove(repo.engine, "before_cursor_execute", fail_prune)
    assert repo.load_checkpoint("source-a") == previous
    assert repo.load_snapshot("source-a") == original
    assert len(repo.load_sessions(source_key="source-a")[0].requests) == 2


def test_backfill_archive_rejects_changed_replacement(repository):
    _, _, _, payload = fixture_payload()
    repository.save_snapshot(payload, source_key="archive")
    with pytest.raises(ValueError, match="immutable archive"):
        repository.save_snapshot(payload | {"source": "changed"}, source_key="archive")
    assert repository.load_snapshot("archive") == payload


def test_backfill_archive_cannot_become_a_live_writer_source(repository):
    request, session, _, payload = fixture_payload(1)
    repository.save_snapshot(payload, source_key="archive")
    with pytest.raises(ValueError, match="read-only archive"):
        repository.apply_batch(
            "archive",
            events=[api().SourceEvent("generation-a", 0, request, session.id)],
            snapshot=payload,
            checkpoint=api().Checkpoint("generation-a", 100),
            expected_checkpoint=None,
        )
    assert repository.load_checkpoint("archive") is None
    assert repository.load_sessions(source_key="archive") == [session]


def test_backfill_cannot_bypass_an_existing_live_checkpoint(repository):
    batch(repository)
    _, _, _, payload = fixture_payload()
    previous = repository.load_checkpoint("source-a")
    with pytest.raises(ValueError, match="live checkpoint"):
        repository.save_snapshot(payload, source_key="source-a")
    assert repository.load_checkpoint("source-a") == previous


def test_existing_source_with_unknown_provenance_does_not_become_real(repository):
    from sqlalchemy import update

    batch(repository)
    with repository.engine.begin() as conn:
        conn.execute(update(api().sources).values(snapshot={}))
    assert "synthetic" not in repository.load_snapshot("source-a")


def test_identity_collision_rejects_changed_request_and_rolls_back(repository):
    repo = repository
    batch(repo)
    checkpoint = repo.load_checkpoint("source-a")
    request, session, _, payload = fixture_payload(1)
    altered = replace(request, query="changed")
    payload["sessions"][0]["requests"][0]["query"] = "changed"
    with pytest.raises(ValueError, match="identity collision"):
        repo.apply_batch(
            "source-a",
            events=[api().SourceEvent("generation-a", 0, altered, session.id)],
            snapshot=payload,
            checkpoint=api().Checkpoint("generation-a", 300),
            expected_checkpoint=checkpoint,
        )
    assert repo.load_checkpoint("source-a") == checkpoint
    assert repo.load_sessions(source_key="source-a")[0].requests == (request, request)


def test_external_session_id_cannot_be_reassigned_to_another_client(repository):
    repo = repository
    batch(repo)
    request, session, _, payload = fixture_payload(1)
    changed = replace(request, ip="192.0.2.2")
    payload["sessions"] = [_serialize_session(replace(session, ip=changed.ip, requests=(changed,)))]
    with pytest.raises(ValueError, match="session identity"):
        repo.apply_batch(
            "source-a",
            events=[api().SourceEvent("generation-b", 0, changed, session.id)],
            snapshot=payload,
            checkpoint=api().Checkpoint("generation-b", 100),
            expected_checkpoint=repo.load_checkpoint("source-a"),
        )


def test_rotation_reuses_offsets_without_collapsing_distinct_events(repository):
    repo = repository
    first = batch(repo)
    assert first == api().Checkpoint("generation-a", 200, 1)
    second = batch(repo, expected=first, generation="generation-b")
    assert second == api().Checkpoint("generation-b", 200, 2)
    assert len(repo.load_sessions(source_key="source-a")[0].requests) == 4
    assert len(repo.load_snapshot("source-a")["sessions"][0]["requests"]) == 2


def test_fresh_history_survives_view_retention_and_marks_exact_duplicate_visible(repository):
    repo = repository
    request, history, label, payload = fixture_payload(3)
    visible = replace(history, requests=(request,))
    payload["sessions"] = [_serialize_session(visible)]
    events = [
        api().SourceEvent("generation-a", offset, request, history.id) for offset in (0, 100, 200)
    ]
    checkpoint = repo.apply_batch(
        "source-a",
        events=events,
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 300),
        expected_checkpoint=None,
        history_sessions=[history],
        history_labels=[label],
        visible_events=[events[-1]],
    )
    assert checkpoint == repo.load_checkpoint("source-a")
    assert repo.load_sessions(source_key="source-a") == [history]
    assert repo.load_snapshot("source-a") == payload
    with repo.engine.connect() as conn:
        assert conn.scalars(
            select(api().requests.c.byte_offset).where(api().requests.c.visible.is_(True))
        ).all() == [200]


def test_fresh_entirely_evicted_session_and_truth_are_persisted_before_checkpoint(repository):
    repo = repository
    request, history, label, _ = fixture_payload(1)
    payload = {"sessions": [], "labels": [], "synthetic": True}
    repo.apply_batch(
        "source-a",
        events=[api().SourceEvent("generation-a", 0, request, history.id)],
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 100),
        expected_checkpoint=None,
        history_sessions=[history],
        history_labels=[label],
        visible_events=[],
    )
    assert repo.load_sessions(source_key="source-a") == [history]
    assert repo.load_labels(source_key="source-a") == [label]
    assert repo.load_snapshot("source-a") == payload


def test_processed_session_without_accepted_truth_removes_stale_historical_label(repository):
    repo = repository
    batch(repo)
    request, session, _, payload = fixture_payload()
    payload["labels"] = []
    repo.apply_batch(
        "source-a",
        events=[
            api().SourceEvent("generation-a", index * 100, request, session.id)
            for index in range(2)
        ],
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 300),
        expected_checkpoint=repo.load_checkpoint("source-a"),
    )
    assert repo.load_labels(source_key="source-a") == []


def test_unprocessed_evicted_session_keeps_truth_until_explicitly_reprocessed(repository):
    repo = repository
    batch(repo)
    request, history, label, _ = fixture_payload()
    payload = {"sessions": [], "labels": [], "synthetic": True}
    previous = repo.apply_batch(
        "source-a",
        events=[],
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 300),
        expected_checkpoint=repo.load_checkpoint("source-a"),
    )
    assert repo.load_labels(source_key="source-a") == [label]
    repo.apply_batch(
        "source-a",
        events=[
            api().SourceEvent("generation-a", index * 100, request, history.id)
            for index in range(2)
        ],
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 400),
        expected_checkpoint=previous,
        history_sessions=[history],
        visible_events=[],
    )
    assert repo.load_labels(source_key="source-a") == []


@pytest.mark.parametrize("original", [False, True])
def test_source_provenance_cannot_change_with_a_later_snapshot(repository, original):
    repo = repository
    request, session, _, payload = fixture_payload(1)
    payload["synthetic"] = original
    events = [api().SourceEvent("generation-a", 0, request, session.id)]
    first = repo.apply_batch(
        "source-a",
        events=events,
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 100),
        expected_checkpoint=None,
    )
    changed = {"sessions": [], "labels": [], "synthetic": not original}
    with pytest.raises(ValueError, match="new source key"):
        repo.apply_batch(
            "source-a",
            events=[],
            snapshot=changed,
            checkpoint=api().Checkpoint("generation-a", 200),
            expected_checkpoint=first,
        )
    assert repo.load_checkpoint("source-a") == first
    assert repo.load_snapshot("source-a") == payload
    repo.save_snapshot(changed, source_key="different-provenance")
    assert repo.load_snapshot("different-provenance") == changed


def test_snapshot_preserves_request_order_when_events_arrive_out_of_order(repository):
    repo = repository
    request, session, _, payload = fixture_payload(1)
    later = replace(request, ts=request.ts + timedelta(seconds=1), query="later")
    session = replace(session, ended_at=later.ts, requests=(request, later))
    payload["sessions"] = [_serialize_session(session)]
    repo.apply_batch(
        "source-a",
        events=[
            api().SourceEvent("generation-a", 0, later, session.id),
            api().SourceEvent("generation-a", 100, request, session.id),
        ],
        snapshot=payload,
        checkpoint=api().Checkpoint("generation-a", 200),
        expected_checkpoint=None,
    )
    assert repo.load_snapshot("source-a") == payload


def test_replayed_event_sql_work_is_bounded_per_batch(repository):
    repo = repository
    request, session, label, payload = fixture_payload(1)
    payload["sessions"] = [
        _serialize_session(replace(session, id=f"session-{index}")) for index in range(40)
    ]
    payload["labels"] = [
        _serialize_label(replace(label, session_id=f"session-{index}")) for index in range(40)
    ]
    events = [
        api().SourceEvent("generation-a", index * 100, request, f"session-{index}")
        for index in range(40)
    ]

    def write(expected):
        return repo.apply_batch(
            "source-a",
            events=events,
            snapshot=payload,
            checkpoint=api().Checkpoint("generation-a", 4000),
            expected_checkpoint=expected,
        )

    checkpoint = write(None)
    statements = []

    def count_statements(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(repo.engine, "before_cursor_execute", count_statements)
    try:
        write(checkpoint)
    finally:
        event.remove(repo.engine, "before_cursor_execute", count_statements)
    # Three fixed statements publish the source-checked ingest heartbeat.
    assert len(statements) <= 19


def test_explicit_retention_removes_empty_history_and_labels_without_affecting_other_source(
    repository,
):
    repo = repository
    batch(repo)
    _, session, label, payload = fixture_payload()
    repo.save_snapshot(payload, source_key="other")
    empty = {"sessions": [], "labels": [], "synthetic": True}
    repo.apply_batch(
        "source-a",
        events=[],
        snapshot=empty,
        checkpoint=api().Checkpoint("generation-a", 300),
        expected_checkpoint=repo.load_checkpoint("source-a"),
    )
    assert repo.load_snapshot("source-a") == empty
    assert repo.load_sessions(source_key="source-a") == [session]
    assert repo.load_labels(source_key="source-a") == [label]
    assert repo.prune_before("source-a", session.ended_at + timedelta(seconds=1)) == 2
    assert repo.load_sessions(source_key="source-a") == []
    assert repo.load_labels(source_key="source-a") == []
    assert repo.load_sessions(source_key="other") == [session]


def test_postgres_concurrent_checkpoint_has_one_winner(engine):  # noqa: F811
    repo = api().TrafficRepository(engine)
    batch(repo)
    checkpoint = repo.load_checkpoint("source-a")

    def writer(_):
        try:
            batch(repo, expected=checkpoint, offset=300)
            return "committed"
        except api().CheckpointConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(writer, range(2))) == ["committed", "conflict"]


def test_populated_001_upgrade_preserves_traffic_and_old_external_id_mapping(engine):  # noqa: F811
    from pathlib import Path

    with engine.begin() as conn:
        conn.exec_driver_sql(Path("src/bouncer/db/migrations/001_init.sql").read_text())
        conn.exec_driver_sql(
            "INSERT INTO sessions (ip,user_agent,started_at,ended_at) "
            "VALUES ('192.0.2.1','fixture',now(),now())"
        )
        conn.exec_driver_sql(
            "INSERT INTO requests (ts,ip,method,path,status,session_id) "
            "VALUES (now(),'192.0.2.1','GET','/',200,1)"
        )
        conn.exec_driver_sql("INSERT INTO labels VALUES (1,'legacy-run','human',NULL)")
    repo = api().TrafficRepository(engine)
    assert repo.load_sessions(source_key="legacy")[0].id == "1"
    assert repo.load_labels(source_key="legacy") == [SessionLabel("1", "legacy-run", "human")]
    assert len(repo.load_sessions(source_key="legacy")[0].requests) == 1


def test_valid_large_response_size_round_trips(repository):
    module = api()
    request, session, _, payload = fixture_payload(count=1)
    request = replace(request, bytes=3_000_000_000)
    session = replace(session, requests=(request,))
    payload["sessions"] = [_serialize_session(session)]
    repository.apply_batch("large-response",
                           events=[module.SourceEvent("one", 0, request, session.id)],
                           snapshot=payload, checkpoint=module.Checkpoint("one", 100),
                           expected_checkpoint=None)
    stored = repository.load_sessions(source_key="large-response")[0].requests[0]
    assert stored.bytes == 3_000_000_000
