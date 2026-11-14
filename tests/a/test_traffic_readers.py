from bouncer.db import store
from bouncer.db.traffic import TrafficRepository
from tests.a.test_investigations_store import snapshot


def traffic_snapshot(synthetic=True):
    value = snapshot(synthetic)
    session = value["sessions"][0]
    session["requests"][0].update(ts=session["started_at"], ip=session["ip"],
                                   user_agent=session["user_agent"])
    value["labels"][0]["run_id"] = "fixture-run"
    return value


def test_sql_readers_keep_explicit_json_offline(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'traffic.db'}"
    repository = TrafficRepository(url)
    try:
        repository.save_snapshot(traffic_snapshot(), source_key="test")
        monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
        monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "test")
        monkeypatch.setenv("BOUNCER_STORE_PATH", str(tmp_path / "absent.json"))
        assert store.read_snapshot()["sessions"][0]["id"] == "s1"
        assert store.load_sessions()[0].id == "s1"
        assert store.is_synthetic() is True
        assert store.read_snapshot(path=tmp_path / "absent.json")["sessions"] == []
        assert store.load_sessions(path=tmp_path / "absent.json") == []
    finally:
        repository.engine.dispose()


def test_api_uses_sql_and_keeps_non_synthetic_private(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from bouncer.api.app import app
    url = f"sqlite:///{tmp_path / 'traffic.db'}"
    repository = TrafficRepository(url)
    try:
        repository.save_snapshot(traffic_snapshot(False), source_key="private")
        monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
        monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "private")
        monkeypatch.setenv("BOUNCER_ADMIN_TOKEN", "audit-admin")
        monkeypatch.setenv("BOUNCER_STORE_PATH", str(tmp_path / "absent.json"))
        client = TestClient(app)
        assert client.get("/api/sessions").json() == []
        response = client.get("/api/sessions", headers={"Authorization": "Bearer audit-admin"})
        assert response.json()[0]["id"] == "s1"
        assert "192.0.2.1" in response.text
    finally:
        repository.engine.dispose()


def test_unknown_legacy_origin_cannot_be_reported_as_real(tmp_path, monkeypatch):
    import pytest
    from sqlalchemy import update

    from bouncer.db.traffic import sources
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    repository = TrafficRepository(url)
    try:
        repository.save_snapshot(traffic_snapshot(), source_key="legacy")
        with repository.engine.begin() as conn:
            conn.execute(
                update(sources).where(sources.c.source_key == "legacy").values(snapshot={})
            )
        monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
        monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "legacy")
        with pytest.raises(ValueError, match="provenance"):
            store.is_synthetic()
    finally:
        repository.engine.dispose()


def test_retention_configuration_rejects_invalid_ages(monkeypatch):
    import pytest
    monkeypatch.delenv("BOUNCER_TRAFFIC_RETENTION_SECONDS", raising=False)
    assert store.traffic_retention() == 86400
    for value in ("0", "-1", "nan", "inf", "broken"):
        monkeypatch.setenv("BOUNCER_TRAFFIC_RETENTION_SECONDS", value)
        with pytest.raises(ValueError):
            store.traffic_retention()
