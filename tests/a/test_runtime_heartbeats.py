import importlib
import importlib.util
import json
from datetime import UTC, datetime

from sqlalchemy import select

from bouncer.investigations import InvestigationStore
from tests.a.test_worker import _rec, _write
from tests.a.test_worker_durability import worker


def health():
    assert importlib.util.find_spec("bouncer.db.health") is not None, "heartbeat store missing"
    return importlib.import_module("bouncer.db.health")


def test_worker_json_sidecar_matches_successful_committed_snapshot(tmp_path):
    _write(tmp_path / "access.log", [_rec(1000, "192.0.2.1")], "w")
    result = worker(tmp_path, None).cycle()
    snapshot = tmp_path / "offline.json"
    metadata = json.loads((tmp_path / "offline.json.health.json").read_text())
    assert metadata["source_updated_at"] == result["ingest"]["updated_at"]
    assert metadata["snapshot_size"] == snapshot.stat().st_size
    assert metadata["snapshot_mtime_ns"] == snapshot.stat().st_mtime_ns


def test_review_worker_records_disabled_state_without_provider_calls(tmp_path, monkeypatch):
    from bouncer.review.worker import main
    module = health()
    url = f"sqlite:///{tmp_path / 'health.db'}"
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "test")
    assert main(["--once", "--database-url", url]) == 0
    store = InvestigationStore(url)
    try:
        with store.engine.connect() as conn:
            row = conn.execute(select(module.components)).mappings().one()
        assert row["source_id"] == "test" and row["component"] == "review"
        assert row["state"] == "disabled" and row["config_key"]
        assert store.usage()["requests"] == 0
    finally:
        store.engine.dispose()


def test_heartbeat_replaces_only_its_source_component(tmp_path):
    module = health()
    store = InvestigationStore(f"sqlite:///{tmp_path / 'health.db'}")
    now = datetime(2026, 11, 15, tzinfo=UTC)
    try:
        module.record_heartbeat(store.engine, "a", "review", state="ready",
                                config_key="one", now=now)
        module.record_heartbeat(store.engine, "b", "review", state="disabled", now=now)
        module.record_heartbeat(store.engine, "a", "review", state="unavailable", now=now)
        with store.engine.connect() as conn:
            rows = list(conn.execute(select(module.components)).mappings())
        assert len(rows) == 2
        assert next(r for r in rows if r["source_id"] == "a")["state"] == "unavailable"
    finally:
        store.engine.dispose()
