import pytest

from bouncer.db.cutover import backfill_json, export_json
from bouncer.db.traffic import TrafficRepository
from tests.a.test_migrations import engine, postgres_url  # noqa: F401
from tests.a.test_worker import _rec, _write
from tests.a.test_worker_durability import worker


def test_postgres_worker_cutover_restart_and_json_rollback(request, tmp_path):
    database = request.getfixturevalue("engine")
    log = tmp_path / "access.log"
    original_json = tmp_path / "offline.json"
    _write(log, [_rec(1000, "192.0.2.1", marker="run:human")], "w")
    original = worker(tmp_path, None).cycle()
    repo = TrafficRepository(database)
    backfill_json(original_json, repo)
    _write(log, [_rec(1001, "192.0.2.1", marker="run:human")])
    actual = worker(tmp_path, repo).cycle()
    assert actual["sessions"][0]["id"] == original["sessions"][0]["id"]
    assert len(actual["sessions"][0]["requests"]) == 2
    assert len(worker(tmp_path, repo).cycle()["sessions"][0]["requests"]) == 2
    rollback = tmp_path / "rollback.json"
    export_json(repo, "test", rollback)
    _write(log, [_rec(1002, "192.0.2.1", marker="run:human")])
    from bouncer.ingest.worker import Worker
    resumed = Worker(log, rollback, secret="test-secret", intel_fn=None,
                     campaigns_fn=None, synthetic=True)
    result = resumed.cycle()
    assert len(result["sessions"][0]["requests"]) == 3
    assert result["sessions"][0]["id"] == original["sessions"][0]["id"]
    assert result["labels"][0]["sim_class"] == "human"


def test_plain_postgres_url_uses_installed_psycopg3(request):
    database = request.getfixturevalue("engine")
    plain = database.url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    repository = TrafficRepository(plain)
    try:
        assert repository.engine.dialect.driver == "psycopg"
        assert repository.load_checkpoint("unused") is None
    finally:
        repository.engine.dispose()


@pytest.mark.parametrize("address", ["not-an-ip", "fe80::1%eth0", 123])
def test_invalid_log_address_cannot_wedge_postgres_ingestion(request, tmp_path, address):
    database = request.getfixturevalue("engine")
    repo = TrafficRepository(database)
    _write(tmp_path / "access.log", [_rec(1000, address), _rec(1001, "192.0.2.1")], "w")
    snapshot = worker(tmp_path, repo).cycle()
    assert snapshot["ingest"]["invalid_records"] == 1
    assert len(snapshot["sessions"]) == 1
    assert len(repo.load_sessions(source_key="test")) == 1


def test_ipv6_spelling_does_not_change_source_identity(request, tmp_path):
    database = request.getfixturevalue("engine")
    repo = TrafficRepository(database)
    log = tmp_path / "access.log"
    _write(log, [_rec(1000, "2001:0db8:0:0:0:0:0:1")], "w")
    active = worker(tmp_path, repo)
    active.cycle()
    _write(log, [_rec(1001, "2001:db8::1")])
    result = active.cycle()
    assert len(result["sessions"]) == 1
    assert len(repo.load_sessions(source_key="test")[0].requests) == 2
