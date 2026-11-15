"""Private durable reservations and one-shot frozen native evaluation receipts."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Table,
    Text,
    inspect,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from bouncer.db.store import _dt
from bouncer.db.traffic import DOCUMENT

metadata = MetaData()
preparations = Table(
    "evaluation_preparations",
    metadata,
    Column("preparation_id", Text, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("state", Text, nullable=False),
    Column("descriptor", DOCUMENT, nullable=False),
    Column("reservation_digest", Text, nullable=False),
    Column("artifact_digest", Text),
    Column("artifacts", DOCUMENT, nullable=False),
    Column("report", DOCUMENT, nullable=False),
    Column("report_digest", Text),
    Column("claimed_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    Column("failure_code", Text),
    CheckConstraint("state IN ('reserved','frozen','claimed','complete','unavailable','revoked')"),
)
units = Table(
    "evaluation_units",
    metadata,
    Column("unit_hash", Text, primary_key=True),
    Column("usage", Text, nullable=False),
    Column("preparation_id", Text, ForeignKey("evaluation_preparations.preparation_id")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("usage IN ('development','holdout')"),
    CheckConstraint(
        "(usage = 'development' AND preparation_id IS NULL) OR "
        "(usage = 'holdout' AND preparation_id IS NOT NULL)"
    ),
)
sources = Table(
    "evaluation_sources",
    metadata,
    Column(
        "preparation_id",
        Text,
        ForeignKey("evaluation_preparations.preparation_id"),
        primary_key=True,
    ),
    Column("source_key", Text, primary_key=True),
)
Index("evaluation_sources_source_idx", sources.c.source_key)

MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BINDINGS = 1000
FAILURES = {"analysis_failed", "validation_failed", "interrupted"}


def _json_float(token):
    value = float(token)
    if value == 0.0:
        return 0.0
    decimal = Decimal(token)
    # JSONB removes signed zero and decodes exponent-expanded integral numbers as integers.
    return int(decimal) if decimal.as_tuple().exponent >= 0 else value


def _canonical(value):
    if not isinstance(value, dict):
        raise ValueError("invalid evaluation JSON")
    try:
        content = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        if len(content) > MAX_JSON_BYTES:
            raise ValueError
        normalized = json.loads(content, parse_float=_json_float)

        def valid(item):
            if isinstance(item, str):
                return "\x00" not in item and not any(0xD800 <= ord(c) <= 0xDFFF for c in item)
            if isinstance(item, dict):
                return all(isinstance(k, str) and valid(k) and valid(v) for k, v in item.items())
            if isinstance(item, (list, tuple)):
                return all(valid(v) for v in item)
            return item is None or isinstance(item, (int, float, bool))

        if not valid(value):
            raise ValueError
        content = json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        if len(content) > MAX_JSON_BYTES:
            raise ValueError
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError("invalid or oversized evaluation JSON") from None
    return normalized, hashlib.sha256(content.encode("ascii")).hexdigest()


def _hash(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("invalid evaluation hash")
    return value


def _record(row):
    result = dict(row)
    result.pop("reservation_digest")
    for field in ("created_at", "claimed_at", "completed_at"):
        if result[field] is not None:
            result[field] = _dt(result[field]).isoformat()
    return result


def purge_source_connection(conn, source_key):
    """Revoke bound payloads atomically with the caller's locked source purge."""
    if preparations.name not in inspect(conn).get_table_names():
        return
    bound = select(sources.c.preparation_id).where(sources.c.source_key == source_key)
    rows = conn.execute(
        select(preparations.c.preparation_id, preparations.c.state)
        .where(preparations.c.preparation_id.in_(bound))
        .order_by(preparations.c.preparation_id)
        .with_for_update()
    ).all()
    if any(row.state == "claimed" for row in rows):
        raise ValueError(
            "evaluation in progress; stop worker and close interrupted receipt before purge"
        )
    if rows:
        conn.execute(
            update(preparations)
            .where(preparations.c.preparation_id.in_([row.preparation_id for row in rows]))
            .values(state="revoked", descriptor={}, artifacts={}, report={})
        )


class EvaluationLedger:
    def __init__(self, engine: Engine):
        self.engine = engine
        if engine.dialect.name == "postgresql":
            from bouncer.db.migrate import run_migrations

            run_migrations(engine)
        elif engine.dialect.name == "sqlite":
            if not engine.url.database:
                raise ValueError("evaluation requires a durable database")
            with engine.connect() as conn:
                files = conn.exec_driver_sql("PRAGMA database_list").all()
            if not any(row[1] == "main" and row[2] for row in files):
                raise ValueError("evaluation requires a durable database")
            metadata.create_all(engine)
        else:
            raise ValueError("unsupported evaluation database")

    @contextmanager
    def _transaction(self, connection=None, *, write=True):
        try:
            if connection is not None:
                if connection.engine is not self.engine or not connection.in_transaction():
                    raise ValueError(
                        "evaluation connection requires an active matching transaction"
                    )
                if (
                    connection.dialect.name == "sqlite"
                    and not connection.connection.driver_connection.in_transaction
                ):
                    # A SAVEPOINT must not become SQLite's otherwise absent outer transaction.
                    connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
                with connection.begin_nested():
                    yield connection
                return
            with self.engine.begin() as conn:
                if write and conn.dialect.name == "sqlite":
                    conn.exec_driver_sql("BEGIN IMMEDIATE")
                yield conn
        except OperationalError as exc:
            if self.engine.dialect.name == "sqlite" and getattr(
                exc.orig, "sqlite_errorcode", 0
            ) & 0xFF in {5, 6}:
                raise ValueError("evaluation state changed concurrently") from None
            raise

    def _insert(self, conn, table, values, *, returning=False):
        dialect_insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
        statement = dialect_insert(table).values(values).on_conflict_do_nothing()
        if returning:
            statement = statement.returning(*table.primary_key.columns)
        return conn.execute(statement)

    def _get(self, conn, preparation_id, *, lock=False):
        query = select(preparations).where(preparations.c.preparation_id == _hash(preparation_id))
        row = conn.execute(query.with_for_update() if lock else query).mappings().first()
        if row is None:
            raise ValueError("unknown evaluation preparation")
        return row

    def get(self, preparation_id, *, connection=None):
        with self._transaction(connection, write=False) as conn:
            return _record(self._get(conn, preparation_id))

    def reserve(
        self, *, descriptor, development_units, holdout_units, source_keys, connection=None
    ):
        descriptor, identifier = _canonical(descriptor)
        if not isinstance(development_units, set) or not isinstance(holdout_units, set):
            raise ValueError("invalid evaluation unit sets")
        if not holdout_units or len(development_units) + len(holdout_units) > 200_000:
            raise ValueError("invalid evaluation unit count")
        if development_units & holdout_units:
            raise ValueError("evaluation unit roles overlap")
        for value in development_units | holdout_units:
            _hash(value)
        if not isinstance(source_keys, (list, tuple)) or len(source_keys) > MAX_SOURCE_BINDINGS:
            raise ValueError("invalid evaluation source bindings")
        for key in source_keys:
            if not isinstance(key, str) or not key or len(key) > 256 or "\x00" in key:
                raise ValueError("invalid evaluation source binding")
            try:
                key.encode("utf-8")
            except UnicodeEncodeError:
                raise ValueError("invalid evaluation source binding") from None
        source_keys = sorted(set(source_keys))
        _, reservation_digest = _canonical(
            {
                "development_units": sorted(development_units),
                "holdout_units": sorted(holdout_units),
                "source_keys": source_keys,
            }
        )
        now = datetime.now(UTC)
        with self._transaction(connection) as conn:
            inserted = (
                self._insert(
                    conn,
                    preparations,
                    dict(
                        preparation_id=identifier,
                        created_at=now,
                        state="reserved",
                        descriptor=descriptor,
                        reservation_digest=reservation_digest,
                        artifacts={},
                        report={},
                    ),
                    returning=True,
                ).first()
                is not None
            )
            current = self._get(conn, identifier, lock=True)
            if current["state"] == "revoked":
                raise ValueError("evaluation preparation revoked")
            if not inserted and current["reservation_digest"] != reservation_digest:
                raise ValueError("evaluation reservation differs from original")
            ordered = sorted(development_units | holdout_units)
            # Global ordering covers both inserts and row locks across every batch.
            for start in range(0, len(ordered), 1000):
                batch = ordered[start : start + 1000]
                if inserted:
                    self._insert(
                        conn,
                        units,
                        [
                            dict(
                                unit_hash=value,
                                usage="holdout" if value in holdout_units else "development",
                                preparation_id=identifier if value in holdout_units else None,
                                created_at=now,
                            )
                            for value in batch
                        ],
                    )
                rows = (
                    conn.execute(
                        select(units)
                        .where(units.c.unit_hash.in_(batch))
                        .order_by(units.c.unit_hash)
                        .with_for_update()
                    )
                    .mappings()
                    .all()
                )
                if len(rows) != len(batch):
                    raise ValueError("evaluation unit reservation is incomplete")
                for row in rows:
                    expected = "holdout" if row["unit_hash"] in holdout_units else "development"
                    if row["usage"] != expected or (
                        expected == "holdout" and row["preparation_id"] != identifier
                    ):
                        raise ValueError("evaluation unit already assigned incompatibly")
            if inserted and source_keys:
                self._insert(
                    conn,
                    sources,
                    [dict(preparation_id=identifier, source_key=key) for key in source_keys],
                )
            if not inserted:
                bindings = conn.scalars(
                    select(sources.c.source_key)
                    .where(sources.c.preparation_id == identifier)
                    .order_by(sources.c.source_key)
                ).all()
                if bindings != source_keys:
                    raise ValueError("evaluation source bindings differ from original")
            return _record(current)

    def _transition(self, conn, current, values):
        changed = conn.execute(
            update(preparations)
            .where(
                preparations.c.preparation_id == current["preparation_id"],
                preparations.c.state == current["state"],
                preparations.c.artifact_digest == current["artifact_digest"],
            )
            .values(**values)
            .returning(preparations.c.preparation_id)
        ).first()
        if changed is None:
            raise ValueError("evaluation state changed concurrently")

    def set_artifacts(self, preparation_id, *, artifacts, connection=None):
        artifacts, digest = _canonical(artifacts)
        with self._transaction(connection) as conn:
            current = self._get(conn, preparation_id, lock=True)
            if current["state"] == "revoked":
                raise ValueError("evaluation preparation revoked")
            if current["state"] == "frozen" and current["artifact_digest"] == digest:
                return _record(current)
            if current["state"] != "reserved":
                raise ValueError("evaluation artifacts are immutable in this state")
            self._transition(
                conn, current, dict(state="frozen", artifact_digest=digest, artifacts=artifacts)
            )
            return _record(self._get(conn, preparation_id))

    def _frozen(self, conn, preparation_id, artifact_digest):
        current = self._get(conn, preparation_id, lock=True)
        if current["state"] == "revoked":
            raise ValueError("evaluation preparation revoked")
        if current["artifact_digest"] != _hash(artifact_digest):
            raise ValueError("evaluation artifact digest mismatch")
        return current

    def claim(self, preparation_id, *, artifact_digest, connection=None):
        with self._transaction(connection) as conn:
            current = self._frozen(conn, preparation_id, artifact_digest)
            if current["state"] == "complete":
                try:
                    _, report_digest = _canonical(current["report"])
                except ValueError:
                    raise ValueError("evaluation report digest mismatch") from None
                if current["report_digest"] != report_digest:
                    raise ValueError("evaluation report digest mismatch")
                return _record(current) | {"cached": True}
            if current["state"] in {"claimed", "unavailable"}:
                raise ValueError("evaluation holdout already consumed")
            if current["state"] != "frozen":
                raise ValueError("evaluation state requires frozen artifacts")
            self._transition(conn, current, dict(state="claimed", claimed_at=datetime.now(UTC)))
            return _record(self._get(conn, preparation_id)) | {"cached": False}

    def finish(
        self, preparation_id, *, artifact_digest, report=None, failure_code=None, connection=None
    ):
        if (report is None) == (failure_code is None):
            raise ValueError("evaluation finish requires exactly one outcome")
        if failure_code is not None and (
            not isinstance(failure_code, str) or failure_code not in FAILURES
        ):
            raise ValueError("invalid evaluation failure code")
        report_digest = None
        if report is not None:
            report, report_digest = _canonical(report)
        with self._transaction(connection) as conn:
            current = self._frozen(conn, preparation_id, artifact_digest)
            if current["state"] != "claimed":
                raise ValueError("evaluation state is not claimed")
            self._transition(
                conn,
                current,
                dict(
                    state="complete" if report is not None else "unavailable",
                    report={} if report is None else report,
                    report_digest=report_digest,
                    failure_code=failure_code,
                    completed_at=datetime.now(UTC),
                ),
            )
            return _record(self._get(conn, preparation_id))
