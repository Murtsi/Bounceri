"""Cheap liveness and read-only readiness; configuration never proves worker health."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from bouncer.db.store import store_path, traffic_source
from bouncer.db.traffic import sources
from bouncer.review.config import ReviewSettings, capabilities

router = APIRouter()
STALE_SECONDS = 120
State = Literal["healthy", "stale", "unavailable", "disabled", "unknown"]


class ComponentHealth(BaseModel):
    state: State
    configured: bool
    reason: str
    age_seconds: float | None = None
    source_present: bool | None = None
    revision: int | None = None
    provider_live_verified: bool = False


class Readiness(BaseModel):
    status: Literal["healthy", "degraded", "stale", "unavailable", "unknown"]
    ready: bool
    mode: Literal["sql", "json"]
    components: dict[str, ComponentHealth]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _age(timestamp, now: datetime) -> ComponentHealth:
    if timestamp is None:
        return ComponentHealth(state="unknown", configured=True, reason="timestamp_missing")
    try:
        updated = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if updated.tzinfo is None:
            raise ValueError("timezone required")
        age = (now - updated).total_seconds()
    except (ValueError, TypeError, OverflowError):
        return ComponentHealth(state="unknown", configured=True, reason="timestamp_invalid")
    if age < 0:
        return ComponentHealth(state="unknown", configured=True, reason="clock_skew")
    return ComponentHealth(
        state="stale" if age > STALE_SECONDS else "healthy",
        configured=True,
        reason="heartbeat_stale" if age > STALE_SECONDS else "heartbeat_fresh",
        age_seconds=round(age, 3),
    )


def _data(timestamp, now: datetime) -> ComponentHealth:
    data = _age(timestamp, now)
    if timestamp is None:
        data.reason = "no_observed_data"
    elif data.state in ("healthy", "stale"):
        data.reason = "data_fresh" if data.state == "healthy" else "data_stale"
    return data


def _engine(url: str):
    parsed = make_url(url)
    if parsed.get_backend_name() == "postgresql":
        return create_engine(
            parsed,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 2,
                "options": "-c statement_timeout=1000 -c default_transaction_read_only=on",
            },
        )
    if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, "", ":memory:"):
        # Read-only URI avoids creating a missing compatibility database during a probe.
        parsed = parsed.set(database="file:" + parsed.database, query={"mode": "ro", "uri": "true"})
        return create_engine(parsed, poolclass=NullPool, connect_args={"timeout": 1})
    raise ValueError("unsupported health database")


def _ingest(url: str, now: datetime) -> tuple[ComponentHealth, ComponentHealth, ComponentHealth]:
    engine = None
    data = ComponentHealth(state="unknown", configured=True, reason="data_unavailable")
    try:
        engine = _engine(url)
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        sources.c.revision,
                        sources.c.read_only,
                        sources.c.snapshot["ingest"]["updated_at"].as_string().label("updated_at"),
                        sources.c.snapshot["ingest"]["last_event_at"]
                        .as_string()
                        .label("last_event_at"),
                        sources.c.snapshot["source_deleted"].as_boolean().label("source_deleted"),
                    ).where(sources.c.source_key == traffic_source())
                )
                .mappings()
                .first()
            )
        database = ComponentHealth(state="healthy", configured=True, reason="read_available")
        if row is None:
            return (
                database,
                ComponentHealth(
                    state="unavailable",
                    configured=True,
                    reason="source_missing",
                    source_present=False,
                ),
                data,
            )
        if row["source_deleted"] is True:
            return (
                database,
                ComponentHealth(
                    state="unavailable",
                    configured=True,
                    reason="source_deleted",
                    source_present=True,
                    revision=row["revision"],
                ),
                data,
            )
        data = _data(row["last_event_at"], now)
        ingest = (
            ComponentHealth(state="disabled", configured=True, reason="read_only_source")
            if row["read_only"]
            else _age(row["updated_at"], now)
        )
        ingest.source_present = True
        ingest.revision = row["revision"]
        return database, ingest, data
    except Exception:
        # Driver diagnostics can contain connection credentials and private source details.
        return (
            ComponentHealth(state="unavailable", configured=True, reason="read_unavailable"),
            ComponentHealth(state="unknown", configured=True, reason="database_unavailable"),
            data,
        )
    finally:
        if engine is not None:
            engine.dispose()


def _json_ingest(now: datetime) -> tuple[ComponentHealth, ComponentHealth]:
    path = store_path()
    data = ComponentHealth(state="unknown", configured=True, reason="data_unavailable")
    try:
        with path.with_name(path.name + ".health.json").open("rb") as stream:
            raw = stream.read(16_385)
        if len(raw) > 16_384:
            raise ValueError("health metadata too large")
        metadata = json.loads(raw)
        stat = path.stat()
        if (metadata["snapshot_mtime_ns"], metadata["snapshot_size"]) != (
            stat.st_mtime_ns,
            stat.st_size,
        ):
            return ComponentHealth(
                state="unknown", configured=True, reason="json_snapshot_changed"
            ), data
        worker = _age(metadata.get("updated_at"), now)
        source = _age(metadata.get("source_updated_at"), now)
        return (source if worker.state == "healthy" else worker), _data(
            metadata.get("last_event_at"), now
        )
    except FileNotFoundError:
        return ComponentHealth(
            state="unknown", configured=False, reason="json_health_missing"
        ), data
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return ComponentHealth(state="unknown", configured=True, reason="json_health_invalid"), data


def _review(now: datetime) -> ComponentHealth:
    settings = ReviewSettings.from_env()
    if not settings.enabled:
        return ComponentHealth(state="disabled", configured=False, reason="review_disabled")
    if not capabilities(settings)["enabled"]:
        return ComponentHealth(
            state="unavailable", configured=True, reason="configuration_unavailable"
        )
    url = os.getenv("BOUNCER_DATABASE_URL", os.getenv("BOUNCERI_DATABASE_URL", "")).strip()
    if not url:
        return ComponentHealth(state="unknown", configured=True, reason="worker_unverified")
    engine = None
    try:
        engine = _engine(url)
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT heartbeat_at, state, config_key FROM runtime_component_health "
                        "WHERE source_id = :source AND component = 'review'"
                    ),
                    {"source": traffic_source()},
                )
                .mappings()
                .first()
            )
        if row is None:
            return ComponentHealth(state="unknown", configured=True, reason="worker_unverified")
        timestamp = row["heartbeat_at"]
        if engine.dialect.name == "sqlite" and timestamp is not None:
            # SQLite drops the zone from the heartbeat writer's UTC-only database contract.
            timestamp = datetime.fromisoformat(str(timestamp))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        heartbeat = _age(timestamp, now)
        if heartbeat.state != "healthy":
            return heartbeat
        if row["config_key"] != settings.config_key:
            heartbeat.state, heartbeat.reason = "unknown", "configuration_changed"
        elif row["state"] != "ready":
            heartbeat.state = "unavailable"
            heartbeat.reason = (
                "worker_disabled" if row["state"] == "disabled" else "worker_unavailable"
            )
        else:
            heartbeat.reason = "worker_fresh_provider_declared"
        return heartbeat
    except Exception:
        return ComponentHealth(state="unknown", configured=True, reason="worker_unverified")
    finally:
        if engine is not None:
            engine.dispose()


@router.get("/api/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/readyz", response_model=Readiness)
def readyz(response: Response) -> Readiness:
    url = os.getenv("BOUNCER_TRAFFIC_DATABASE_URL", "").strip()
    now = utc_now()
    if url:
        database, ingest, data = _ingest(url, now)
    else:
        database = ComponentHealth(state="disabled", configured=False, reason="sql_not_selected")
        ingest, data = _json_ingest(now)
    review = _review(now)
    components = {"database": database, "ingest": ingest, "data": data, "review": review}
    ready = database.state in ("healthy", "disabled") and ingest.state in ("healthy", "disabled")
    status = (
        "healthy"
        if review.state in ("healthy", "disabled") and data.state == "healthy"
        else "degraded"
    )
    if not ready:
        status = next(
            state
            for state in ("unavailable", "stale", "unknown")
            if any(component.state == state for component in (database, ingest))
        )
        response.status_code = 503
    return Readiness(
        status=status, ready=ready, mode="sql" if url else "json", components=components
    )
