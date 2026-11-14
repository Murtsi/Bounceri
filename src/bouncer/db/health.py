"""Source-scoped worker heartbeats; health probes never initialize this schema."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, MetaData, Table, Text, inspect, select

metadata = MetaData()
components = Table(
    "runtime_component_health", metadata,
    Column("source_id", Text, primary_key=True),
    Column("component", Text, primary_key=True),
    Column("heartbeat_at", DateTime(timezone=True), nullable=False),
    Column("state", Text, nullable=False),
    Column("config_key", Text),
)


def heartbeat_connection(conn, source_id, component, *, state, config_key=None, now=None):
    if component not in {"ingest", "review"} or state not in {"ready", "disabled", "unavailable"}:
        raise ValueError("invalid heartbeat component/state")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("source identity required")
    # Serialize against source purge; a stopped source must never recreate health payloads.
    if inspect(conn).has_table("traffic_sources"):
        from bouncer.db.traffic import sources
        source = conn.execute(select(sources.c.resume_state).where(
            sources.c.source_key == source_id
        ).with_for_update()).scalar()
        if source and source.get("deleted"):
            return False
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("heartbeat time must be UTC")
    values = {"heartbeat_at": timestamp, "state": state, "config_key": config_key}
    conn.execute(insert(components).values(source_id=source_id, component=component, **values)
                 .on_conflict_do_update(index_elements=["source_id", "component"], set_=values))
    return True


def record_heartbeat(engine, source_id, component, *, state, config_key=None, now=None):
    with engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        return heartbeat_connection(conn, source_id, component, state=state,
                                    config_key=config_key, now=now)
