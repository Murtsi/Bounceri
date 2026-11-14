"""Retention applies to freshly read logs before any session/detector work."""

from bouncer.ingest.worker import Worker
from tests.a.test_worker import SECRET, _rec, _write


def test_restart_large_log_is_pruned_before_parsing_and_scoring(tmp_path, monkeypatch):
    monkeypatch.setattr("bouncer.ingest.worker._retention_now", lambda: 2000.0, raising=False)
    log = tmp_path / "access.log"
    rows = [_rec(1000 + i, f"192.0.2.{i + 1}") for i in range(10)]
    rows += [_rec(1990 + i, "198.51.100.1") for i in range(5)]
    _write(log, rows, "w")
    calls = []
    from bouncer.contracts import IpIntel

    def intel(ip):
        calls.append(ip)
        return IpIntel()

    worker = Worker(
        log,
        tmp_path / "store.json",
        secret=SECRET,
        intel_fn=intel,
        campaigns_fn=None,
        synthetic=True,
        max_records=3,
        window_seconds=60,
    )
    snapshot = worker.cycle()
    assert len(worker.records) == 3
    assert len(snapshot["sessions"]) == 1
    assert len(snapshot["sessions"][0]["requests"]) == 3
    assert calls == ["198.51.100.1"]
    assert snapshot["ingest"]["discarded_by_retention"] == 12


def test_window_prunes_on_quiet_cycle_and_accepts_iso_timestamp(tmp_path, monkeypatch):
    clock = [2000.0]
    monkeypatch.setattr("bouncer.ingest.worker._retention_now", lambda: clock[0], raising=False)
    log = tmp_path / "access.log"
    from datetime import UTC, datetime

    timestamp = datetime.fromtimestamp(1999, tz=UTC).isoformat()
    _write(log, [_rec(timestamp, "192.0.2.1")], "w")
    worker = Worker(
        log,
        tmp_path / "store.json",
        secret=SECRET,
        intel_fn=None,
        campaigns_fn=None,
        synthetic=True,
        max_records=10,
        window_seconds=60,
    )
    assert len(worker.cycle()["sessions"]) == 1
    clock[0] = 2060
    assert worker.cycle()["sessions"] == []
    assert worker.records == [] and worker.intel_cache == {}


def test_identity_survives_time_window_eviction(tmp_path, monkeypatch):
    clock = [2000.0]
    monkeypatch.setattr("bouncer.ingest.worker._retention_now", lambda: clock[0])
    log = tmp_path / "access.log"
    _write(log, [_rec(1941, "192.0.2.1"), _rec(1999, "192.0.2.1")], "w")
    w = Worker(log, tmp_path / "store.json", secret=SECRET, intel_fn=None,
               campaigns_fn=None, synthetic=True, window_seconds=60)
    original = w.cycle()["sessions"][0]["id"]
    clock[0] = 2002
    _write(log, [_rec(2001, "192.0.2.1")])
    assert w.cycle()["sessions"][0]["id"] == original


def test_identity_survives_empty_window_and_restart(tmp_path, monkeypatch):
    clock = [2000.0]
    monkeypatch.setattr("bouncer.ingest.worker._retention_now", lambda: clock[0])
    log = tmp_path / "access.log"
    _write(log, [_rec(1999, "192.0.2.1")], "w")
    def worker():
        return Worker(log, tmp_path / "store.json", secret=SECRET, intel_fn=None,
                      campaigns_fn=None, synthetic=True, window_seconds=60)
    w = worker()
    original = w.cycle()["sessions"][0]["id"]
    clock[0] = 2061
    assert w.cycle()["sessions"] == []
    w = worker()
    clock[0] = 2070
    _write(log, [_rec(2070, "192.0.2.1")])
    assert w.cycle()["sessions"][0]["id"] == original
    clock[0] = 2400
    _write(log, [_rec(2400, "192.0.2.1")])
    assert w.cycle()["sessions"][0]["id"] != original


def test_visible_old_session_identity_survives_partial_eviction(tmp_path):
    log = tmp_path / "access.log"
    def worker():
        return Worker(log, tmp_path / "store.json", secret=SECRET, intel_fn=None,
                      campaigns_fn=None, synthetic=True, max_records=4)
    _write(log, [_rec(t, "192.0.2.1") for t in (1000, 1100, 1200)], "w")
    w = worker()
    original = w.cycle()["sessions"][0]["id"]
    _write(log, [_rec(1600, "192.0.2.2")])
    w.cycle()
    w = worker()
    _write(log, [_rec(1601, "192.0.2.2")])
    result = w.cycle()["sessions"]
    assert next(s for s in result if s["ip"] == "192.0.2.1")["id"] == original
