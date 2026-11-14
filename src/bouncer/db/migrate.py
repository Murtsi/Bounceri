"""Checked, transactionally serialized PostgreSQL schema migrations.

SQLite remains a local/test adapter initialized by its existing metadata path.
Applied SQL files are immutable: edit drift and unsupported newer versions fail closed.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy import UniqueConstraint, inspect
from sqlalchemy.engine import Connection, Engine

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
# Shared by API, ingest and review processes; released automatically on rollback/commit.
ADVISORY_LOCK = 0x424F554E434552
REQUEST_DEFAULTS = {
    "user_agent": "''::text",
    "query": "''::text",
    "bytes": "0",
    "headers": "'{}'::jsonb",
}


def _expected_tables():
    # Import lazily: both stores call this runner after defining their metadata.
    from bouncer.db.traffic import metadata as traffic
    from bouncer.enforcement import metadata as enforcement
    from bouncer.investigations.store import metadata as investigations

    return {**traffic.tables, **investigations.tables, **enforcement.tables}


def _type_name(column_type, dialect):
    name = str(column_type.compile(dialect=dialect))
    return "DOUBLE PRECISION" if name in {"FLOAT", "FLOAT(53)"} else name


def _validate_schema(conn: Connection) -> None:
    inspector = inspect(conn)
    present = set(inspector.get_table_names())
    for name, table in _expected_tables().items():
        if name not in present:
            raise RuntimeError(f"schema mismatch: missing table {name}")
        columns = {column["name"]: column for column in inspector.get_columns(name)}
        for expected in table.columns:
            actual = columns.get(expected.name)
            if actual is None or (
                _type_name(actual["type"], conn.dialect) != _type_name(expected.type, conn.dialect)
                or actual["nullable"] != expected.nullable
            ):
                raise RuntimeError(f"schema mismatch: {name}.{expected.name}")
            if table.autoincrement_column is expected and not (
                actual.get("identity") or (actual.get("default") or "").startswith("nextval(")
            ):
                raise RuntimeError(f"schema mismatch: {name}.{expected.name} serial default")
            if (
                name == "requests"
                and expected.name in REQUEST_DEFAULTS
                and (actual.get("default") != REQUEST_DEFAULTS[expected.name])
            ):
                raise RuntimeError(f"schema mismatch: {name}.{expected.name} default")
        primary_key = tuple(inspector.get_pk_constraint(name)["constrained_columns"])
        if primary_key != tuple(column.name for column in table.primary_key.columns):
            raise RuntimeError(f"schema mismatch: {name} primary key")
        unique = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(name)
        }
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint) and (
                tuple(column.name for column in constraint.columns) not in unique
            ):
                raise RuntimeError(f"schema mismatch: {name} unique constraint")
        foreign_keys = {
            (
                tuple(fk["constrained_columns"]),
                fk["referred_table"],
                tuple(fk["referred_columns"]),
                fk["options"].get("ondelete"),
            )
            for fk in inspector.get_foreign_keys(name)
        }
        for fk in table.foreign_key_constraints:
            expected_fk = (
                tuple(column.name for column in fk.columns),
                fk.referred_table.name,
                tuple(element.column.name for element in fk.elements),
                fk.ondelete,
            )
            if expected_fk not in foreign_keys:
                raise RuntimeError(f"schema mismatch: {name} foreign key")
        indexes = {tuple(index["column_names"]) for index in inspector.get_indexes(name)}
        if any(
            tuple(column.name for column in index.columns) not in indexes for index in table.indexes
        ):
            raise RuntimeError(f"schema mismatch: {name} index")


def run_migrations(engine: Engine, *, migrations_dir: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply pending checked SQL and return newly recorded versions, in one transaction."""
    if engine.dialect.name != "postgresql":
        raise ValueError("versioned migrations require PostgreSQL")
    migrations = []
    for path in sorted(migrations_dir.glob("*.sql")):
        match = re.fullmatch(r"(\d{3})_.+\.sql", path.name)
        if match is None:
            raise RuntimeError(f"invalid migration filename: {path.name}")
        # Normalize BOM/newlines so Windows and Linux agree on the same checked-in SQL.
        content = path.read_text(encoding="utf-8-sig")
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        migrations.append((int(match[1]), path.name, checksum, content))
    if not migrations or [migration[0] for migration in migrations] != list(
        range(1, len(migrations) + 1)
    ):
        raise RuntimeError("migration files must have contiguous versions starting at 001")
    with engine.begin() as conn:
        conn.exec_driver_sql(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK})")
        conn.exec_driver_sql("SET LOCAL search_path TO public")
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        history = conn.exec_driver_sql(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        ).all()
        if history and history[-1].version > len(migrations):
            raise RuntimeError(f"unsupported schema version: {history[-1].version}")
        if [row.version for row in history] != list(range(1, len(history) + 1)):
            raise RuntimeError("invalid migration history: missing or out-of-order version")
        for row, migration in zip(history, migrations, strict=False):
            if (row.name, row.checksum) != migration[1:3]:
                raise RuntimeError(f"migration drift at version {row.version}")
        applied = []
        for version, name, checksum, content in migrations[len(history) :]:
            # psycopg executes the entire SQL script, including quoted semicolons/DO blocks.
            conn.exec_driver_sql(content)
            conn.exec_driver_sql(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (version, name, checksum),
            )
            applied.append(version)
        # Validate after upgrades, before commit: IF NOT EXISTS cannot mask a mismatch,
        # and an older table may legitimately lack a column supplied by a pending migration.
        _validate_schema(conn)
    return applied
