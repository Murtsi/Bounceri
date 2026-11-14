import copy

import pytest

from bouncer.ingest.worker import Worker
from tests.a.test_worker import SECRET, _rec, _write


class Repository:
    def __init__(self):
        self.snapshot = {}
        self.resume = None
        self.position = None
        self.fail = False
        self.events = []

    def load_snapshot(self, source_key):
        return copy.deepcopy(self.snapshot)

    def load_resume_state(self, source_key):
        return copy.deepcopy(self.resume)

    def load_checkpoint(self, source_key):
        return self.position

    def apply_batch(self, source_key, *, events, snapshot, checkpoint,
                    expected_checkpoint, resume_state, history_sessions=(), history_labels=(),
                    visible_events=None, retention_before=None):
        assert expected_checkpoint == self.position
        if self.fail:
            raise OSError("transaction failed")
        self.events.extend(events)
        self.snapshot = copy.deepcopy(snapshot)
        self.resume = copy.deepcopy(resume_state)
        self.position = checkpoint
        return checkpoint


def worker(tmp_path, repository):
    return Worker(tmp_path / "access.log", tmp_path / "offline.json", secret=SECRET,
                  intel_fn=None, campaigns_fn=None, synthetic=True,
                  repository=repository, source_key="test")


def test_failed_commit_retries_same_bytes_without_json_write(tmp_path):
    repository = Repository()
    _write(tmp_path / "access.log", [_rec(1000, "192.0.2.1")], "w")
    w = worker(tmp_path, repository)
    repository.fail = True
    with pytest.raises(OSError):
        w.cycle()
    assert w.tail.offset == 0
    assert w.records == []
    repository.fail = False
    snapshot = w.cycle()
    assert len(snapshot["sessions"][0]["requests"]) == 1
    assert len(repository.events) == 1
    assert not (tmp_path / "offline.json").exists()


def test_restart_restores_retained_records_and_partial_line(tmp_path):
    repository = Repository()
    log = tmp_path / "access.log"
    _write(log, [_rec(1000, "192.0.2.1")], "w")
    first = worker(tmp_path, repository).cycle()
    _write(log, [_rec(1001, "192.0.2.1")])
    resumed = worker(tmp_path, repository)
    second = resumed.cycle()
    assert second["sessions"][0]["id"] == first["sessions"][0]["id"]
    assert len(second["sessions"][0]["requests"]) == 2
    assert resumed.tail.offset == log.stat().st_size


def test_real_repository_preserves_identical_requests_across_restart(tmp_path):
    from bouncer.db.traffic import TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        log = tmp_path / "access.log"
        _write(log, [_rec(1000, "192.0.2.1"), _rec(1000, "192.0.2.1")], "w")
        first = worker(tmp_path, repository).cycle()
        second = worker(tmp_path, repository).cycle()
        assert first["sessions"] == second["sessions"]
        history = repository.load_sessions(source_key="test")
        assert len(history) == 1
        assert len(history[0].requests) == 2
        assert len(repository.load_snapshot("test")["sessions"][0]["requests"]) == 2
    finally:
        repository.engine.dispose()


def test_real_failed_write_rolls_back_requests_checkpoint_and_window(tmp_path, monkeypatch):
    from bouncer.db.traffic import TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        _write(tmp_path / "access.log", [_rec(1000, "192.0.2.1")], "w")
        w = worker(tmp_path, repository)
        save = repository._save
        def fail_after_writes(*args, **kwargs):
            save(*args, **kwargs)
            raise RuntimeError("forced rollback")
        with monkeypatch.context() as m:
            m.setattr(repository, "_save", fail_after_writes)
            with pytest.raises(RuntimeError, match="forced rollback"):
                w.cycle()
        assert repository.load_checkpoint("test") is None
        assert repository.load_sessions(source_key="test") == []
        assert w.tail.offset == 0
        assert len(w.cycle()["sessions"]) == 1
    finally:
        repository.engine.dispose()


def test_second_writer_cannot_acknowledge_first_writers_bytes(tmp_path):
    from bouncer.db.traffic import CheckpointConflict, TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        _write(tmp_path / "access.log", [_rec(1000, "192.0.2.1")], "w")
        first, second = worker(tmp_path, repository), worker(tmp_path, repository)
        first.cycle()
        with pytest.raises(CheckpointConflict):
            second.cycle()
        assert second.tail.offset == 0
        assert second.records == []
        assert len(worker(tmp_path, repository).cycle()["sessions"][0]["requests"]) == 1
    finally:
        repository.engine.dispose()


def test_fresh_overflow_is_durable_before_view_retention(tmp_path):
    from bouncer.db.traffic import TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        log = tmp_path / "access.log"
        _write(log, [_rec(1000, "192.0.2.1", uri="/first"),
                     _rec(1001, "192.0.2.1", uri="/last")], "w")
        w = worker(tmp_path, repository)
        w.max_records = 1
        visible = w.cycle()
        assert len(visible["sessions"][0]["requests"]) == 1
        assert len(repository.load_sessions(source_key="test")[0].requests) == 2
        assert repository.load_checkpoint("test").byte_offset == log.stat().st_size
    finally:
        repository.engine.dispose()


def test_late_event_and_bridge_preserve_committed_ownership(tmp_path):
    from bouncer.db.traffic import TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        log = tmp_path / "access.log"
        _write(log, [_rec(1000, "192.0.2.1"), _rec(1400, "192.0.2.1")], "w")
        w = worker(tmp_path, repository)
        original = {s["id"] for s in w.cycle()["sessions"]}
        _write(log, [_rec(1200, "192.0.2.1"), _rec(999, "192.0.2.1")])
        result = w.cycle()
        assert {s["id"] for s in result["sessions"]} == original
        assert sum(len(s.requests) for s in repository.load_sessions(source_key="test")) == 4
    finally:
        repository.engine.dispose()


def test_conflicting_truth_stays_invalid_after_eviction_and_restart(tmp_path):
    from bouncer.db.traffic import TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        log = tmp_path / "access.log"
        _write(log, [_rec(1000, "192.0.2.1", marker="one:human")], "w")
        w = worker(tmp_path, repository)
        w.max_records = 1
        assert w.cycle()["labels"][0]["sim_class"] == "human"
        _write(log, [_rec(1001, "192.0.2.1", marker="two:credential_stuffing")])
        assert w.cycle()["labels"] == []
        assert repository.load_labels(source_key="test") == []
        assert worker(tmp_path, repository).cycle()["labels"] == []
    finally:
        repository.engine.dispose()


def test_sql_cutover_requires_archiving_existing_json_and_keeps_it(tmp_path):
    from bouncer.db.cutover import backfill_json
    from bouncer.db.traffic import TrafficRepository
    log = tmp_path / "access.log"
    store = tmp_path / "offline.json"
    _write(log, [_rec(1000, "192.0.2.1")], "w")
    original = worker(tmp_path, None).cycle()
    saved = store.read_bytes()
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        with pytest.raises(ValueError, match="archive"):
            worker(tmp_path, repository)
        backfill_json(store, repository)
        _write(log, [_rec(1001, "192.0.2.1")])
        after = worker(tmp_path, repository).cycle()
        assert after["sessions"][0]["id"] == original["sessions"][0]["id"]
        assert len(after["sessions"][0]["requests"]) == 2
        assert store.read_bytes() == saved
    finally:
        repository.engine.dispose()


def test_exported_sql_snapshot_can_resume_json_without_losing_bytes(tmp_path):
    from bouncer.db.cutover import export_json
    from bouncer.db.traffic import TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        log = tmp_path / "access.log"
        _write(log, [_rec(1000, "192.0.2.1")], "w")
        first = worker(tmp_path, repository).cycle()
        export_json(repository, "test", tmp_path / "offline.json")
        _write(log, [_rec(1001, "192.0.2.1")])
        after = worker(tmp_path, None).cycle()
        assert after["sessions"][0]["id"] == first["sessions"][0]["id"]
        assert len(after["sessions"][0]["requests"]) == 2
    finally:
        repository.engine.dispose()


def test_explicit_history_retention_is_distinct_from_view_cap(tmp_path, monkeypatch):
    from bouncer.db.traffic import TrafficRepository
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        monkeypatch.setattr("bouncer.ingest.worker._retention_now", lambda: 2000)
        _write(tmp_path / "access.log", [_rec(1000, "192.0.2.1"),
                                        _rec(1500, "192.0.2.2")], "w")
        w = worker(tmp_path, repository)
        w.max_records = 1
        w.history_retention_seconds = 600
        w.cycle()
        history = repository.load_sessions(source_key="test")
        assert len(history) == 1 and history[0].ip == "192.0.2.2"
    finally:
        repository.engine.dispose()


def test_empty_json_view_still_requires_archive_and_restores_tail(tmp_path, monkeypatch):
    from bouncer.db.cutover import backfill_json
    from bouncer.db.traffic import TrafficRepository
    monkeypatch.setattr("bouncer.ingest.worker._retention_now", lambda: 2000)
    log = tmp_path / "access.log"
    _write(log, [_rec(1000, "192.0.2.1")], "w")
    old = worker(tmp_path, None)
    old.window_seconds = 1
    assert old.cycle()["sessions"] == []
    _write(log, [_rec(1001, "192.0.2.1")])
    log.rename(tmp_path / "access.log.1")
    _write(log, [_rec(1002, "192.0.2.1")], "w")
    repository = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    try:
        with pytest.raises(ValueError, match="archive"):
            worker(tmp_path, repository)
        backfill_json(tmp_path / "offline.json", repository)
        resumed = worker(tmp_path, repository)
        resumed.cycle()
        resumed.cycle()
        paths = [r.ts.timestamp() for s in repository.load_sessions(source_key="test")
                 for r in s.requests]
        assert paths == [1001, 1002]
    finally:
        repository.engine.dispose()
