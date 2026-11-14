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
