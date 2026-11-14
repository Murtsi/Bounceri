"""Normalized private traffic and atomically committed source checkpoints."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    bindparam,
    create_engine,
    delete,
    insert,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from bouncer.contracts import Request, Session, SessionLabel
from bouncer.db.store import (
    _dt,
    _label_from_dict,
    _request_from_dict,
    _serialize_label,
    _serialize_session,
    _session_from_dict,
)

metadata = MetaData()
BIGINT = BigInteger().with_variant(Integer, "sqlite")
ADDRESS = Text().with_variant(INET, "postgresql")
DOCUMENT = JSON().with_variant(JSONB, "postgresql")
sources = Table(
    "traffic_sources",
    metadata,
    Column("source_key", Text, primary_key=True),
    Column("generation", Text),
    Column("byte_offset", BIGINT, nullable=False),
    Column("revision", BIGINT, nullable=False),
    Column("snapshot", DOCUMENT, nullable=False),
    Column("resume_state", DOCUMENT, nullable=False),
    Column("read_only", Boolean, nullable=False, server_default=text("false")),
)
sessions = Table(
    "sessions",
    metadata,
    Column("id", BIGINT, primary_key=True),
    Column("ip", ADDRESS, nullable=False),
    Column("user_agent", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True), nullable=False),
    Column("source_key", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("visible", Boolean, nullable=False),
    Column("view_started_at", DateTime(timezone=True), nullable=False),
    Column("view_ended_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_key", "external_id"),
)
Index("sessions_started_at_idx", sessions.c.started_at)
requests = Table(
    "requests",
    metadata,
    Column("id", BIGINT, primary_key=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("ip", ADDRESS, nullable=False),
    Column("method", Text, nullable=False),
    Column("path", Text, nullable=False),
    Column("status", Integer, nullable=False),
    Column("user_agent", Text, nullable=False, server_default=""),
    Column("query", Text, nullable=False, server_default=""),
    Column("bytes", Integer, nullable=False, server_default=text("0")),
    Column("headers", DOCUMENT, nullable=False, server_default=text("'{}'")),
    Column("content_type", Text),
    Column("username", Text),
    Column("session_id", BIGINT, ForeignKey("sessions.id", ondelete="SET NULL")),
    Column("source_key", Text, nullable=False),
    Column("generation", Text, nullable=False),
    Column("byte_offset", BIGINT, nullable=False),
    Column("visible", Boolean, nullable=False),
    Column("position", BIGINT, nullable=False),
    UniqueConstraint("source_key", "generation", "byte_offset"),
)
Index("requests_source_ts_idx", requests.c.source_key, requests.c.ts)
labels = Table(
    "labels",
    metadata,
    Column("session_id", BIGINT, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("run_id", Text, nullable=False),
    Column("sim_class", Text, nullable=False),
    Column("campaign_id", Text),
    Column("visible", Boolean, nullable=False),
)


@dataclass(frozen=True)
class Checkpoint:
    generation: str
    byte_offset: int
    revision: int = 0


@dataclass(frozen=True)
class SourceEvent:
    generation: str
    byte_offset: int
    request: Request
    session_id: str


class CheckpointConflict(RuntimeError):
    """The source advanced since the caller read its state."""


def _checkpoint(row) -> Checkpoint | None:
    if row is None or row["generation"] is None:
        return None
    return Checkpoint(row["generation"], row["byte_offset"], row["revision"])


def _request(row) -> Request:
    return _request_from_dict(dict(row) | {"ip": str(row["ip"])})


def _request_key(request: Request) -> tuple:
    return tuple(
        tuple(sorted(value.items())) if name == "headers" else value
        for name, value in asdict(request).items()
    )


def _update_rows(conn, table, values):
    if values:
        conn.execute(
            update(table)
            .where(table.c.id == bindparam("_row_id"))
            .values(**{key: bindparam(key) for key in values[0] if key != "_row_id"}),
            values,
        )


class TrafficRepository:
    def __init__(self, database: str | Engine):
        if isinstance(database, Engine):
            self.engine = database
        else:
            options = {}
            if database in {"sqlite://", "sqlite:///:memory:"}:
                options = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
            self.engine = create_engine(database, **options)
        if self.engine.dialect.name == "postgresql":
            from bouncer.db.migrate import run_migrations

            run_migrations(self.engine)
        else:
            metadata.create_all(self.engine)

    def load_checkpoint(self, source_key: str) -> Checkpoint | None:
        with self.engine.connect() as conn:
            return _checkpoint(
                conn.execute(select(sources).where(sources.c.source_key == source_key))
                .mappings()
                .first()
            )

    def load_resume_state(self, source_key: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            return (
                conn.scalar(
                    select(sources.c.resume_state).where(sources.c.source_key == source_key)
                )
                or {}
            )

    def _lock_source(self, conn, source_key):
        # The unique insert serializes first initialization as well as existing-row writers.
        if conn.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        conn.execute(
            upsert(sources)
            .values(
                source_key=source_key,
                generation=None,
                byte_offset=0,
                revision=0,
                snapshot={},
                resume_state={},
            )
            .on_conflict_do_nothing(index_elements=["source_key"])
        )
        return (
            conn.execute(
                select(sources).where(sources.c.source_key == source_key).with_for_update()
            )
            .mappings()
            .one()
        )

    def apply_batch(
        self,
        source_key: str,
        *,
        events: Sequence[SourceEvent],
        snapshot: dict[str, Any],
        checkpoint: Checkpoint,
        expected_checkpoint: Checkpoint | None,
        resume_state: dict[str, Any] | None = None,
        history_sessions: Sequence[Session] = (),
        history_labels: Sequence[SessionLabel] = (),
        visible_events: Sequence[SourceEvent] | None = None,
        retention_before: datetime | None = None,
    ) -> Checkpoint:
        if not checkpoint.generation or checkpoint.byte_offset < 0:
            raise ValueError("invalid source checkpoint")
        with self.engine.begin() as conn:
            current = self._lock_source(conn, source_key)
            if current["read_only"]:
                raise ValueError(
                    "read-only archive cannot accept live batches; use a new source key"
                )
            if _checkpoint(current) != expected_checkpoint:
                raise CheckpointConflict("source checkpoint changed")
            if (
                expected_checkpoint is not None
                and expected_checkpoint.generation == checkpoint.generation
                and checkpoint.byte_offset < expected_checkpoint.byte_offset
            ):
                raise ValueError("source checkpoint cannot move backwards")
            self._save(
                conn,
                source_key,
                events,
                snapshot,
                history_sessions=history_sessions,
                history_labels=history_labels,
                visible_events=visible_events,
            )
            if retention_before is not None:
                self._prune(conn, source_key, retention_before)
            committed = Checkpoint(
                checkpoint.generation, checkpoint.byte_offset, current["revision"] + 1
            )
            conn.execute(
                update(sources)
                .where(sources.c.source_key == source_key)
                .values(
                    generation=committed.generation,
                    byte_offset=committed.byte_offset,
                    revision=committed.revision,
                    resume_state=resume_state or {},
                )
            )
        return committed

    def save_snapshot(self, snapshot: dict[str, Any], *, source_key: str) -> None:
        """Freeze an immutable compatibility archive while preserving external session IDs."""
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, default=str).encode()
        ).hexdigest()
        events = []
        for session in snapshot.get("sessions", []):
            for request in session.get("requests", []):
                events.append(
                    SourceEvent(
                        "snapshot-backfill",
                        len(events),
                        _request_from_dict(request),
                        str(session["id"]),
                    )
                )
        with self.engine.begin() as conn:
            current = self._lock_source(conn, source_key)
            if current["generation"] is not None:
                raise ValueError(
                    "cannot backfill a source with a live checkpoint; use a new source key"
                )
            if current["read_only"]:
                if current["resume_state"].get("archive_digest") != digest:
                    raise ValueError("cannot replace an immutable archive; use a new source key")
                return
            self._save(conn, source_key, events, snapshot)
            conn.execute(
                update(sources)
                .where(sources.c.source_key == source_key)
                .values(read_only=True, resume_state={"archive_digest": digest})
            )

    def _save(
        self,
        conn,
        source_key,
        events,
        snapshot,
        *,
        history_sessions=(),
        history_labels=(),
        visible_events=None,
    ):
        if type(snapshot.get("synthetic")) is not bool:
            raise ValueError("traffic source synthetic provenance must be a boolean")
        previous = conn.scalar(select(sources.c.snapshot).where(sources.c.source_key == source_key))
        if "synthetic" in previous and previous["synthetic"] != snapshot["synthetic"]:
            raise ValueError("traffic source provenance cannot change; use a new source key")
        view_sessions = [_session_from_dict(row) for row in snapshot.get("sessions", [])]
        view_by_id = {session.id: session for session in view_sessions}
        history_by_id = {session.id: session for session in history_sessions}
        if len(view_by_id) != len(view_sessions) or len(history_by_id) != len(history_sessions):
            raise ValueError("duplicate external session ID")
        for session in view_sessions:
            history = history_by_id.setdefault(session.id, session)
            if (history.ip, history.user_agent) != (session.ip, session.user_agent):
                raise ValueError("historical and visible session identity differ")
        parsed_sessions = list(history_by_id.values())
        conn.execute(
            update(sessions).where(sessions.c.source_key == source_key).values(visible=False)
        )
        conn.execute(
            update(requests).where(requests.c.source_key == source_key).values(visible=False)
        )
        source_ids = select(sessions.c.id).where(sessions.c.source_key == source_key)
        conn.execute(
            update(labels).where(labels.c.session_id.in_(source_ids)).values(visible=False)
        )
        mapping = {}
        wanted = {}
        existing_sessions = {}
        external_ids = [session.id for session in parsed_sessions]
        for start in range(0, len(external_ids), 1000):
            for row in conn.execute(
                select(sessions).where(
                    sessions.c.source_key == source_key,
                    sessions.c.external_id.in_(external_ids[start : start + 1000]),
                )
            ).mappings():
                existing_sessions[row["external_id"]] = row
        new_sessions, changed_sessions = [], []
        for session in parsed_sessions:
            old = existing_sessions.get(session.id)
            view = view_by_id.get(session.id, session)
            if old and (str(old["ip"]), old["user_agent"]) != (session.ip, session.user_agent):
                raise ValueError("external session identity cannot change client")
            values = {
                "ip": session.ip,
                "user_agent": session.user_agent,
                "started_at": min(_dt(old["started_at"]), session.started_at)
                if old
                else session.started_at,
                "ended_at": max(_dt(old["ended_at"]), session.ended_at)
                if old
                else session.ended_at,
                "source_key": source_key,
                "external_id": session.id,
                "visible": session.id in view_by_id,
                "view_started_at": view.started_at,
                "view_ended_at": view.ended_at,
            }
            if old:
                changed_sessions.append(values | {"_row_id": old["id"]})
                mapping[session.id] = old["id"]
            else:
                new_sessions.append(values)
            wanted[session.id] = defaultdict(deque)
            for position, request in enumerate(session.requests):
                wanted[session.id][_request_key(request)].append(position)
        _update_rows(conn, sessions, changed_sessions)
        if new_sessions:
            for row in conn.execute(
                insert(sessions).returning(sessions.c.id, sessions.c.external_id), new_sessions
            ):
                mapping[row.external_id] = row.id
        existing_events = {}
        event_keys = [(event.generation, event.byte_offset) for event in events]
        by_identity = dict(zip(event_keys, events, strict=True))
        if len(by_identity) != len(events):
            raise ValueError("duplicate source event identity in batch")
        view_wanted = {}
        for session in view_sessions:
            view_wanted[session.id] = defaultdict(deque)
            for position, request in enumerate(session.requests):
                view_wanted[session.id][_request_key(request)].append(position)
        visible_positions = {}
        for event in events if visible_events is None else visible_events:
            key = (event.generation, event.byte_offset)
            if key in visible_positions:
                raise ValueError("duplicate visible source event identity")
            if by_identity.get(key) != event:
                raise ValueError("visible source event is absent or changed in history")
            try:
                visible_positions[key] = view_wanted[event.session_id][
                    _request_key(event.request)
                ].popleft()
            except (KeyError, IndexError) as exc:
                raise ValueError("visible source events differ from snapshot requests") from exc
        if any(positions for session in view_wanted.values() for positions in session.values()):
            raise ValueError("snapshot requests are missing visible source events")
        for start in range(0, len(event_keys), 1000):
            for row in conn.execute(
                select(requests).where(
                    requests.c.source_key == source_key,
                    tuple_(requests.c.generation, requests.c.byte_offset).in_(
                        event_keys[start : start + 1000]
                    ),
                )
            ).mappings():
                existing_events[(row["generation"], row["byte_offset"])] = row
        new_events, changed_events = [], []
        for event in events:
            key = (event.generation, event.byte_offset)
            if not event.generation or event.byte_offset < 0 or event.session_id not in mapping:
                raise ValueError("invalid source event")
            # Match multiplicity and snapshot order without depending on log timestamp order.
            try:
                position = wanted[event.session_id][_request_key(event.request)].popleft()
            except IndexError as exc:
                raise ValueError("source events differ from historical session requests") from exc
            position = visible_positions.get(key, position)
            visible = key in visible_positions
            old = existing_events.get(key)
            values = asdict(event.request) | {
                "session_id": mapping[event.session_id],
                "source_key": source_key,
                "generation": event.generation,
                "byte_offset": event.byte_offset,
                "visible": visible,
                "position": position,
            }
            if old:
                if _request(old) != event.request or old["session_id"] != mapping[event.session_id]:
                    raise ValueError("source event identity collision")
                changed_events.append(
                    {"_row_id": old["id"], "visible": visible, "position": position}
                )
            else:
                new_events.append(values)
        if any(positions for session in wanted.values() for positions in session.values()):
            raise ValueError("historical session requests are missing source events")
        _update_rows(conn, requests, changed_events)
        if new_events:
            conn.execute(insert(requests), new_events)
        accepted_labels = {}
        for label in history_labels:
            if label.session_id in accepted_labels:
                raise ValueError("duplicate historical session label")
            accepted_labels[label.session_id] = label
        visible_label_ids = set()
        for row in snapshot.get("labels", []):
            label = _label_from_dict(row)
            if label.session_id in visible_label_ids:
                raise ValueError("duplicate session label")
            visible_label_ids.add(label.session_id)
            old_label = accepted_labels.setdefault(label.session_id, label)
            if old_label != label:
                raise ValueError("historical and visible session labels conflict")
            if label.session_id not in view_by_id:
                raise ValueError("visible label refers to unknown visible session")
        new_labels = []
        for label in accepted_labels.values():
            if label.session_id not in mapping:
                raise ValueError("label refers to unknown session")
            new_labels.append(
                asdict(label)
                | {
                    "session_id": mapping[label.session_id],
                    "visible": label.session_id in visible_label_ids,
                }
            )
        processed_ids = list(mapping.values())
        for start in range(0, len(processed_ids), 1000):
            conn.execute(
                delete(labels).where(labels.c.session_id.in_(processed_ids[start : start + 1000]))
            )
        if new_labels:
            conn.execute(insert(labels), new_labels)
        excluded = {
            "sessions",
            "labels",
            "session_identity_state",
            "session_label_state",
            "worker_resume_state",
        }
        conn.execute(
            update(sources)
            .where(sources.c.source_key == source_key)
            .values(snapshot={key: value for key, value in snapshot.items() if key not in excluded})
        )

    def _sessions(self, conn, source_key, since=None, *, visible=False):
        query = select(sessions).where(sessions.c.source_key == source_key)
        if since is not None:
            query = query.where(sessions.c.started_at >= _dt(since))
        if visible:
            query = query.where(sessions.c.visible.is_(True))
        rows = (
            conn.execute(query.order_by(sessions.c.started_at, sessions.c.external_id))
            .mappings()
            .all()
        )
        grouped = defaultdict(list)
        if rows:
            query = select(requests).where(requests.c.session_id.in_([row["id"] for row in rows]))
            if visible:
                query = query.where(requests.c.visible.is_(True))
            ordering = (
                (requests.c.position, requests.c.id) if visible else (requests.c.ts, requests.c.id)
            )
            for request in conn.execute(query.order_by(*ordering)).mappings():
                grouped[request["session_id"]].append(_request(request))
        return [
            Session(
                row["external_id"],
                str(row["ip"]),
                row["user_agent"],
                _dt(row["view_started_at"] if visible else row["started_at"]),
                _dt(row["view_ended_at"] if visible else row["ended_at"]),
                tuple(grouped[row["id"]]),
            )
            for row in rows
        ]

    @contextmanager
    def _read_transaction(self):
        with self.engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            elif conn.dialect.name == "sqlite":
                # SQLite's legacy driver does not start a transaction for SELECT statements.
                conn.exec_driver_sql("BEGIN")
            yield conn

    def load_sessions(self, since: datetime | None = None, *, source_key: str) -> list[Session]:
        with self._read_transaction() as conn:
            return self._sessions(conn, source_key, since)

    def _labels(self, conn, source_key, *, visible=False):
        query = (
            select(labels, sessions.c.external_id)
            .join(sessions)
            .where(sessions.c.source_key == source_key)
        )
        if visible:
            query = query.where(sessions.c.visible.is_(True), labels.c.visible.is_(True))
        return [
            SessionLabel(row.external_id, row.run_id, row.sim_class, row.campaign_id)
            for row in conn.execute(query.order_by(sessions.c.external_id))
        ]

    def load_labels(self, *, source_key: str) -> list[SessionLabel]:
        with self.engine.connect() as conn:
            return self._labels(conn, source_key)

    def load_snapshot(self, source_key: str) -> dict[str, Any]:
        # One transaction prevents pairing one checkpoint's metadata with another batch's rows.
        with self._read_transaction() as conn:
            saved = conn.scalar(
                select(sources.c.snapshot).where(sources.c.source_key == source_key)
            )
            return ({"synthetic": False} if saved is None else saved) | {
                "sessions": [
                    _serialize_session(s) for s in self._sessions(conn, source_key, visible=True)
                ],
                "labels": [
                    _serialize_label(label)
                    for label in self._labels(conn, source_key, visible=True)
                ],
            }

    def prune_before(self, source_key: str, cutoff: datetime) -> int:
        """Explicit private retention; never remove records still in the current read model."""
        with self.engine.begin() as conn:
            self._lock_source(conn, source_key)
            return self._prune(conn, source_key, cutoff)

    def _prune(self, conn, source_key: str, cutoff: datetime) -> int:
        result = conn.execute(
            delete(requests).where(
                requests.c.source_key == source_key,
                requests.c.ts < _dt(cutoff),
                requests.c.visible.is_(False),
            )
        )
        empty = ~select(requests.c.id).where(requests.c.session_id == sessions.c.id).exists()
        expired = select(sessions.c.id).where(
            sessions.c.source_key == source_key, sessions.c.visible.is_(False), empty
        )
        conn.execute(delete(labels).where(labels.c.session_id.in_(expired)))
        conn.execute(delete(sessions).where(sessions.c.id.in_(expired)))
        return result.rowcount
