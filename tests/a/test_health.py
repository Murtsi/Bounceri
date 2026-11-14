"""Public health probes remain cheap, read-only and honest about unknown state."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from bouncer.api.app import app

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)


@pytest.fixture
def sql_health(monkeypatch, tmp_path):
    from bouncer.api import health

    monkeypatch.setattr(health, "utc_now", lambda: NOW)
    monkeypatch.setenv("BOUNCER_TRAFFIC_SOURCE", "monitored")
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    url = f"sqlite:///{tmp_path / 'health.sqlite3'}"
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE traffic_sources "
                "(source_key TEXT PRIMARY KEY, revision INTEGER, snapshot JSON, "
                "read_only BOOLEAN DEFAULT FALSE, resume_state JSON DEFAULT '{}')"
            )
        )

    def source(
        timestamp=NOW,
        *,
        key="monitored",
        revision=1,
        deleted=False,
        last_event_at=NOW,
        read_only=False,
    ):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM traffic_sources WHERE source_key = :key"), {"key": key})
            conn.execute(
                text(
                    "INSERT INTO traffic_sources "
                    "(source_key, revision, snapshot, read_only) "
                    "VALUES (:key, :revision, :snapshot, :read_only)"
                ),
                {
                    "key": key,
                    "revision": revision,
                    "read_only": read_only,
                    "snapshot": json.dumps(
                        {
                            "ingest": {
                                "updated_at": timestamp.isoformat(),
                                "last_event_at": last_event_at.isoformat()
                                if isinstance(last_event_at, datetime)
                                else last_event_at,
                            }
                            if isinstance(timestamp, datetime)
                            else timestamp,
                            "sessions": [],
                            "source_deleted": deleted,
                        }
                    ),
                },
            )

    yield TestClient(app), source, engine
    engine.dispose()


def test_json_mode_is_explicitly_offline(monkeypatch, tmp_path):
    monkeypatch.delenv("BOUNCER_TRAFFIC_DATABASE_URL", raising=False)
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(tmp_path / "private-traffic.json"))
    response = TestClient(app).get("/api/readyz")
    assert response.status_code == 503
    payload = response.json()
    assert payload["mode"] == "json"
    assert payload["ready"] is False
    assert payload["components"]["ingest"]["reason"] == "json_health_missing"
    assert "private-traffic" not in response.text


def test_json_sidecar_is_bounded_and_matches_committed_file(monkeypatch, tmp_path):
    from bouncer.api import health

    monkeypatch.setattr(health, "utc_now", lambda: NOW)
    monkeypatch.delenv("BOUNCER_TRAFFIC_DATABASE_URL", raising=False)
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    snapshot = tmp_path / "store.json"
    snapshot.write_text("private traffic", encoding="utf-8")
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(snapshot))
    stat = snapshot.stat()
    sidecar = snapshot.with_name(snapshot.name + ".health.json")
    metadata = {
        "updated_at": NOW.isoformat(),
        "source_updated_at": NOW.isoformat(),
        "snapshot_mtime_ns": stat.st_mtime_ns,
        "snapshot_size": stat.st_size,
    }
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    client = TestClient(app)
    assert client.get("/api/readyz").status_code == 200
    snapshot.write_text("a different committed snapshot", encoding="utf-8")
    response = client.get("/api/readyz")
    assert response.status_code == 503
    assert response.json()["components"]["ingest"]["reason"] == "json_snapshot_changed"
    sidecar.write_text("x" * 16_385, encoding="utf-8")
    response = client.get("/api/readyz")
    assert response.status_code == 503
    assert response.json()["components"]["ingest"]["reason"] == "json_health_invalid"


@pytest.mark.parametrize("field", ["updated_at", "source_updated_at"])
def test_json_sidecar_requires_fresh_worker_and_source(monkeypatch, tmp_path, field):
    from bouncer.api import health

    monkeypatch.setattr(health, "utc_now", lambda: NOW)
    monkeypatch.delenv("BOUNCER_TRAFFIC_DATABASE_URL", raising=False)
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    path = tmp_path / "store.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(path))
    stat = path.stat()
    metadata = {
        "updated_at": NOW.isoformat(),
        "source_updated_at": NOW.isoformat(),
        "snapshot_mtime_ns": stat.st_mtime_ns,
        "snapshot_size": stat.st_size,
    }
    metadata[field] = (NOW - timedelta(seconds=121)).isoformat()
    path.with_name(path.name + ".health.json").write_text(json.dumps(metadata), encoding="utf-8")
    response = TestClient(app).get("/api/readyz")
    assert response.status_code == 503
    assert response.json()["components"]["ingest"]["state"] == "stale"


@pytest.mark.parametrize(
    ("last_event_at", "data_state", "status"),
    [
        (NOW.isoformat(), "healthy", "healthy"),
        ((NOW - timedelta(seconds=300)).isoformat(), "stale", "degraded"),
        (None, "unknown", "degraded"),
        ((NOW + timedelta(seconds=1)).isoformat(), "unknown", "degraded"),
    ],
)
def test_json_data_freshness_is_independent_from_worker(
    monkeypatch, tmp_path, last_event_at, data_state, status
):
    from bouncer.api import health

    monkeypatch.setattr(health, "utc_now", lambda: NOW)
    monkeypatch.delenv("BOUNCER_TRAFFIC_DATABASE_URL", raising=False)
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    path = tmp_path / "store.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(path))
    stat = path.stat()
    metadata = {
        "updated_at": NOW.isoformat(),
        "source_updated_at": NOW.isoformat(),
        "last_event_at": last_event_at,
        "snapshot_mtime_ns": stat.st_mtime_ns,
        "snapshot_size": stat.st_size,
    }
    path.with_name(path.name + ".health.json").write_text(json.dumps(metadata), encoding="utf-8")
    response = TestClient(app).get("/api/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == status
    assert payload["components"]["ingest"]["state"] == "healthy"
    assert payload["components"]["data"]["state"] == data_state


def test_postgres_health_connections_are_short_lived_read_only_and_bounded(monkeypatch):
    from bouncer.api import health

    calls = []
    marker = object()

    def capture(url, **kwargs):
        calls.append(kwargs)
        return marker

    monkeypatch.setattr(health, "create_engine", capture)
    assert health._engine("postgresql+psycopg://user:secret@db/traffic") is marker
    assert calls[0]["poolclass"].__name__ == "NullPool"
    assert calls[0]["connect_args"]["connect_timeout"] == 2
    assert "statement_timeout=1000" in calls[0]["connect_args"]["options"]
    assert "default_transaction_read_only=on" in calls[0]["connect_args"]["options"]


def test_missing_sqlite_database_is_not_created(monkeypatch, tmp_path):
    path = tmp_path / "missing.sqlite3"
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    assert TestClient(app).get("/api/readyz").status_code == 503
    assert not path.exists()


def test_liveness_has_no_database_or_provider_calls(monkeypatch):
    from bouncer.api import health

    def forbidden(*args, **kwargs):
        raise AssertionError("Liveness must not access a dependency")

    monkeypatch.setattr(health, "create_engine", forbidden)
    monkeypatch.setattr(health.ReviewSettings, "from_env", forbidden)
    assert TestClient(app).get("/api/healthz").json() == {"status": "ok"}


def test_fresh_source_is_ready_with_review_disabled(sql_health):
    client, source, _ = sql_health
    source()
    response = client.get("/api/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "healthy"
    assert payload["components"]["database"]["state"] == "healthy"
    ingest = payload["components"]["ingest"]
    assert ingest["source_present"] is True
    assert ingest["state"] == "healthy"
    assert ingest["age_seconds"] == 0
    assert ingest["revision"] == 1
    assert payload["components"]["review"]["state"] == "disabled"


@pytest.mark.parametrize(
    ("last_event_at", "state", "reason"),
    [
        (NOW - timedelta(seconds=300), "stale", "data_stale"),
        (None, "unknown", "no_observed_data"),
        (NOW + timedelta(seconds=1), "unknown", "clock_skew"),
    ],
)
def test_data_age_does_not_claim_worker_failure(sql_health, last_event_at, state, reason):
    client, source, _ = sql_health
    source(last_event_at=last_event_at)
    response = client.get("/api/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["ready"] is True
    assert payload["components"]["ingest"]["state"] == "healthy"
    assert payload["components"]["data"]["state"] == state
    assert payload["components"]["data"]["reason"] == reason


def test_fresh_data_does_not_hide_stopped_worker(sql_health):
    client, source, _ = sql_health
    source(timestamp=NOW - timedelta(seconds=300), last_event_at=NOW)
    response = client.get("/api/readyz")
    assert response.status_code == 503
    assert response.json()["components"]["ingest"]["state"] == "stale"
    assert response.json()["components"]["data"]["state"] == "healthy"


def test_read_only_historical_source_is_ready_without_live_worker(sql_health):
    client, source, _ = sql_health
    source(timestamp=NOW - timedelta(days=1), last_event_at=NOW - timedelta(days=1), read_only=True)
    response = client.get("/api/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "degraded"
    assert payload["components"]["ingest"]["state"] == "disabled"
    assert payload["components"]["ingest"]["reason"] == "read_only_source"
    assert payload["components"]["data"]["state"] == "stale"


def test_missing_source_is_unavailable(sql_health):
    client, _, _ = sql_health
    response = client.get("/api/readyz")
    assert response.status_code == 503
    ingest = response.json()["components"]["ingest"]
    assert ingest["state"] == "unavailable"
    assert ingest["source_present"] is False
    assert ingest["reason"] == "source_missing"


def test_deleted_source_tombstone_is_unavailable(sql_health):
    client, source, _ = sql_health
    source(deleted=True)
    response = client.get("/api/readyz")
    assert response.status_code == 503
    ingest = response.json()["components"]["ingest"]
    assert ingest["state"] == "unavailable"
    assert ingest["reason"] == "source_deleted"


@pytest.mark.parametrize(
    ("timestamp", "state", "reason"),
    [
        (None, "unknown", "timestamp_missing"),
        ({"updated_at": "garbage"}, "unknown", "timestamp_invalid"),
        (NOW + timedelta(seconds=10), "unknown", "clock_skew"),
        ({"updated_at": NOW.replace(tzinfo=None).isoformat()}, "unknown", "timestamp_invalid"),
        (NOW - timedelta(seconds=121), "stale", "heartbeat_stale"),
    ],
)
def test_untrusted_or_stale_ingest_timestamps_fail_readiness(sql_health, timestamp, state, reason):
    client, source, _ = sql_health
    source(timestamp)
    response = client.get("/api/readyz")
    assert response.status_code == 503
    ingest = response.json()["components"]["ingest"]
    assert ingest["state"] == state
    assert ingest["reason"] == reason
    assert ingest["age_seconds"] is None or ingest["age_seconds"] >= 0


def test_database_failure_is_sanitized_and_does_not_fall_back_to_json(monkeypatch):
    from bouncer.api import health

    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", "postgresql+psycopg://user:SECRET@db/db")
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")

    def fail(*args, **kwargs):
        raise RuntimeError("SECRET 192.0.2.1 /private/traffic provider-key")

    monkeypatch.setattr(health, "create_engine", fail)
    response = TestClient(app).get("/api/readyz")
    assert response.status_code == 503
    assert response.json()["components"]["database"]["state"] == "unavailable"
    for secret in ("SECRET", "192.0.2.1", "/private/traffic", "provider-key", "postgresql"):
        assert secret not in response.text


def test_health_does_not_initialize_schema(sql_health):
    client, _, engine = sql_health
    client.get("/api/readyz")
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).scalars().all() == ["traffic_sources"]


def test_enabled_provider_configuration_does_not_prove_worker_available(sql_health, monkeypatch):
    client, source, _ = sql_health
    source()
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "true")
    response = client.get("/api/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    review = response.json()["components"]["review"]
    assert review["configured"] is True
    assert review["state"] == "unavailable"
    assert review["reason"] == "configuration_unavailable"


@pytest.fixture
def configured_review(sql_health, monkeypatch):
    from bouncer.api import health

    client, source, engine = sql_health
    source()
    provider = health.ReviewSettings().reviewer
    provider = replace(
        provider,
        enabled=True,
        api_key="private-provider-key",
        model="approved",
        expected_model="approved",
        endpoint="https://api.featherless.ai/v1/chat/completions",
        contract_verified=True,
        identity_verified=True,
        no_fallback_verified=True,
        pricing_verified=True,
        limits_verified=True,
        maximum_cost_microusd=1,
        pricing_version="test",
    )
    settings = health.ReviewSettings(enabled=True, decision=provider, reviewer=provider)
    monkeypatch.setattr(health.ReviewSettings, "from_env", lambda: settings)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE runtime_component_health ("
                "source_id TEXT, component TEXT, heartbeat_at TEXT, "
                "state TEXT, config_key TEXT, PRIMARY KEY(source_id, component))"
            )
        )

    def heartbeat(*, age=0, state="ready", key=settings.config_key, source_id="monitored"):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM runtime_component_health"))
            conn.execute(
                text(
                    "INSERT INTO runtime_component_health VALUES "
                    "(:source, 'review', :at, :state, :key)"
                ),
                {
                    "source": source_id,
                    "at": (NOW - timedelta(seconds=age)).isoformat(),
                    "state": state,
                    "key": key,
                },
            )

    return client, heartbeat, engine, settings


@pytest.mark.parametrize(
    ("kwargs", "state", "reason"),
    [
        ({}, "healthy", "worker_fresh_provider_declared"),
        ({"age": 121}, "stale", "heartbeat_stale"),
        ({"key": "previous-configuration"}, "unknown", "configuration_changed"),
        ({"state": "unavailable"}, "unavailable", "worker_unavailable"),
        ({"state": "disabled"}, "unavailable", "worker_disabled"),
        ({"source_id": "other-private-source"}, "unknown", "worker_unverified"),
    ],
)
def test_review_worker_heartbeat_never_pings_providers(configured_review, kwargs, state, reason):
    client, heartbeat, _, _ = configured_review
    heartbeat(**kwargs)
    response = client.get("/api/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == ("healthy" if state == "healthy" else "degraded")
    review = payload["components"]["review"]
    assert review["state"] == state
    assert review["reason"] == reason
    assert review["provider_live_verified"] is False
    for private in ("private-provider-key", "previous-configuration", "other-private-source"):
        assert private not in response.text


def test_review_enabled_without_heartbeat_is_unknown(configured_review):
    client, _, _, _ = configured_review
    response = client.get("/api/readyz")
    assert response.status_code == 200
    assert response.json()["components"]["review"]["state"] == "unknown"


def test_real_sqlite_heartbeat_uses_database_utc_contract(configured_review):
    from bouncer.db.health import record_heartbeat

    client, _, engine, settings = configured_review
    record_heartbeat(
        engine, "monitored", "review", state="ready", config_key=settings.config_key, now=NOW
    )
    response = client.get("/api/readyz")
    assert response.status_code == 200
    review = response.json()["components"]["review"]
    assert review["state"] == "healthy"
    assert review["age_seconds"] == 0


def test_review_does_not_assume_traffic_database_is_its_job_store(configured_review, monkeypatch):
    client, heartbeat, _, _ = configured_review
    heartbeat()
    monkeypatch.delenv("BOUNCER_DATABASE_URL", raising=False)
    monkeypatch.delenv("BOUNCERI_DATABASE_URL", raising=False)
    response = client.get("/api/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["components"]["review"]["state"] == "unknown"
    assert payload["components"]["review"]["reason"] == "worker_unverified"
