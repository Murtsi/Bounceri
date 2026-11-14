"""PostgreSQL migration acceptance tests; opt in with BOUNCER_TEST_POSTGRES=1.

The fixture owns a disposable Docker PostgreSQL instance and never uses DATABASE_URL.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert, inspect, text

from bouncer.enforcement import metadata as enforcement_metadata
from bouncer.investigations.store import budget
from bouncer.investigations.store import metadata as investigation_metadata


def versions():
    return sorted(
        int(path.name.split("_", 1)[0]) for path in Path("src/bouncer/db/migrations").glob("*.sql")
    )


@pytest.fixture(scope="module")
def postgres_url():
    if os.getenv("BOUNCER_TEST_POSTGRES") != "1":
        pytest.skip("set BOUNCER_TEST_POSTGRES=1 for isolated Docker PostgreSQL tests")
    name = "bouncer-migrations-" + uuid.uuid4().hex
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--label",
            f"com.docker.compose.project={name}",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            "POSTGRES_PASSWORD=migration-test",
            "postgres:16-alpine",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        port = (
            subprocess.check_output(["docker", "port", name, "5432/tcp"], text=True, timeout=10)
            .strip()
            .rsplit(":", 1)[1]
        )
        url = f"postgresql+psycopg://postgres:migration-test@127.0.0.1:{port}/postgres"
        probe = create_engine(url)
        deadline = time.monotonic() + 30
        while True:
            try:
                with probe.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
        probe.dispose()
        yield url
    finally:
        subprocess.run(
            ["docker", "rm", "--force", name], check=True, capture_output=True, timeout=20
        )


@pytest.fixture
def engine(postgres_url):
    name = "test_" + uuid.uuid4().hex
    admin = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(postgres_url.rsplit("/", 1)[0] + "/" + name)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def migrate(engine, **kwargs):
    assert importlib.util.find_spec("bouncer.db.migrate") is not None, "versioned runner missing"
    return importlib.import_module("bouncer.db.migrate").run_migrations(engine, **kwargs)


def test_fresh_database_restart_and_concurrent_initialization(engine):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: migrate(engine), range(4)))
    assert sorted(map(len, results)) == [0, 0, 0, len(versions())]
    assert migrate(engine) == []
    tables = set(inspect(engine).get_table_names())
    assert {"requests", "sessions", "labels", "schema_migrations"} <= tables
    assert set(investigation_metadata.tables) | set(enforcement_metadata.tables) <= tables
    with engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).all() == [(version,) for version in versions()]


def test_populated_create_all_database_is_adopted_without_changing_types_or_data(engine):
    investigation_metadata.create_all(engine)
    enforcement_metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(budget).values(id=1, spent=17, reserved=23, executions=2, requests=4))
    before = inspect(engine).get_columns("investigation_budget")
    assert migrate(engine) == versions()
    assert migrate(engine) == []
    assert [(c["name"], str(c["type"])) for c in before] == [
        (c["name"], str(c["type"])) for c in inspect(engine).get_columns("investigation_budget")
    ]
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT spent, reserved FROM investigation_budget").one() == (
            17,
            23,
        )


def test_populated_001_database_upgrades_without_losing_traffic(engine):
    sql = Path("src/bouncer/db/migrations/001_init.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
        conn.exec_driver_sql(
            "INSERT INTO sessions (ip, user_agent, started_at, ended_at) "
            "VALUES ('192.0.2.1', 'fixture', now(), now())"
        )
        conn.exec_driver_sql(
            "INSERT INTO labels (session_id, run_id, sim_class) VALUES (1, 'fixture', 'human')"
        )
    assert migrate(engine) == versions()
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT run_id FROM labels").scalar_one() == "fixture"


@pytest.mark.parametrize("field,value", [("checksum", "corrupt"), ("name", "001_other.sql")])
def test_applied_migration_drift_is_rejected(engine, field, value):
    migrate(engine)
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE schema_migrations SET {field}=:value WHERE version=1"), {"value": value}
        )
    with pytest.raises(RuntimeError, match="drift"):
        migrate(engine)


def test_future_version_is_rejected(engine):
    migrate(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO schema_migrations (version, name, checksum) "
            "VALUES (999, 'future', 'future')"
        )
    with pytest.raises(RuntimeError, match="unsupported.*version"):
        migrate(engine)


def test_missing_ledger_history_is_rejected(engine):
    migrate(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM schema_migrations WHERE version=1")
    with pytest.raises(RuntimeError, match="history"):
        migrate(engine)


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE investigation_budget (id INTEGER PRIMARY KEY, spent TEXT NOT NULL)",
        "CREATE TABLE sessions (id BIGSERIAL PRIMARY KEY, ip TEXT NOT NULL, "
        "user_agent TEXT NOT NULL, started_at TIMESTAMPTZ NOT NULL, ended_at TIMESTAMPTZ NOT NULL)",
    ],
)
def test_incompatible_existing_schema_is_not_adopted(engine, ddl):
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)
    with pytest.raises(RuntimeError, match="schema mismatch"):
        migrate(engine)
    assert "schema_migrations" not in inspect(engine).get_table_names()


def test_missing_existing_constraint_is_not_silently_adopted(engine):
    investigation_metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE investigation_jobs DROP CONSTRAINT "
            "investigation_jobs_evidence_hash_config_key_key"
        )
    with pytest.raises(RuntimeError, match="schema mismatch"):
        migrate(engine)
    assert "schema_migrations" not in inspect(engine).get_table_names()


def test_transaction_rolls_back_failed_migration_including_ledger(engine, tmp_path):
    (tmp_path / "001_probe.sql").write_text(
        "CREATE TABLE rollback_probe (id INTEGER);", encoding="utf-8"
    )
    (tmp_path / "002_broken.sql").write_text(
        "DO $$ BEGIN RAISE EXCEPTION 'failure;semicolon'; END $$;", encoding="utf-8"
    )
    with pytest.raises(Exception, match="failure;semicolon"):
        migrate(engine, migrations_dir=tmp_path)
    assert inspect(engine).get_table_names() == []


def test_production_stores_initialize_through_checked_migrations(engine, monkeypatch):
    from bouncer.enforcement import EnforcementRuntime
    from bouncer.investigations import InvestigationStore

    def forbidden_create_all(*args, **kwargs):
        pytest.fail("production startup used unversioned create_all")

    monkeypatch.setattr(investigation_metadata, "create_all", forbidden_create_all)
    monkeypatch.setattr(enforcement_metadata, "create_all", forbidden_create_all)
    url = engine.url.render_as_string(hide_password=False)

    def start_store(_):
        store = InvestigationStore(url)
        try:
            EnforcementRuntime(store)
        finally:
            store.engine.dispose()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(start_store, range(4)))
    with engine.connect() as conn:
        assert (
            conn.exec_driver_sql("SELECT count(*) FROM investigation_budget WHERE id=1").scalar()
            == 1
        )
        assert conn.exec_driver_sql("SELECT count(*) FROM schema_migrations").scalar() == len(
            versions()
        )


@pytest.mark.parametrize(
    "ddl",
    [
        "ALTER TABLE sessions ALTER COLUMN id DROP DEFAULT",
        "ALTER TABLE requests ALTER COLUMN bytes SET DEFAULT 9",
        "ALTER TABLE requests ALTER COLUMN headers DROP DEFAULT",
    ],
)
def test_existing_serial_and_request_defaults_are_checked(engine, ddl):
    migrate(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)
    with pytest.raises(RuntimeError, match="schema mismatch.*default"):
        migrate(engine)


def test_known_version_one_upgrades_to_two_with_concurrent_budget_writers(engine):
    import hashlib

    migration = Path("src/bouncer/db/migrations/001_init.sql")
    with engine.begin() as conn:
        conn.exec_driver_sql(migration.read_text(encoding="utf-8"))
        conn.exec_driver_sql(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        conn.exec_driver_sql(
            "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
            (
                1,
                migration.name,
                hashlib.sha256(
                    migration.read_text(encoding="utf-8-sig").encode("utf-8")
                ).hexdigest(),
            ),
        )
    investigation_metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(budget).values(id=1, spent=17, reserved=23, executions=2, requests=4))

    def write_budget(_):
        for _ in range(8):
            with engine.begin() as conn:
                conn.exec_driver_sql("UPDATE investigation_budget SET spent=spent+1 WHERE id=1")

    with ThreadPoolExecutor(max_workers=5) as pool:
        writes = [pool.submit(write_budget, index) for index in range(4)]
        assert pool.submit(migrate, engine).result(timeout=15) == versions()[1:]
        for write in writes:
            write.result(timeout=15)
    assert migrate(engine) == []
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT spent FROM investigation_budget").scalar_one() == 49


def test_checksums_are_stable_across_platform_line_endings(engine, tmp_path):
    source = Path("src/bouncer/db/migrations")
    for path in source.glob("*.sql"):
        (tmp_path / path.name).write_bytes(path.read_text(encoding="utf-8-sig").encode("utf-8"))
    assert migrate(engine, migrations_dir=tmp_path) == versions()
    for path in tmp_path.glob("*.sql"):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert migrate(engine, migrations_dir=tmp_path) == []


def test_scripts_preserve_quoted_semicolons_and_do_blocks(engine, tmp_path):
    for path in Path("src/bouncer/db/migrations").glob("*.sql"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / f"{len(versions()) + 1:03d}_literal.sql").write_text(
        "CREATE TABLE literal_probe (value TEXT); "
        "DO $$ BEGIN INSERT INTO literal_probe VALUES ('a;b'); END $$;",
        encoding="utf-8",
    )
    assert migrate(engine, migrations_dir=tmp_path) == versions() + [len(versions()) + 1]
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT value FROM literal_probe").scalar_one() == "a;b"


def test_additive_column_upgrade_validates_the_resulting_schema(engine, tmp_path, monkeypatch):
    from sqlalchemy import Column, MetaData, Text

    module = importlib.import_module("bouncer.db.migrate")
    assert migrate(engine) == versions()
    for path in Path("src/bouncer/db/migrations").glob("*.sql"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / f"{len(versions()) + 1:03d}_source_reference.sql").write_text(
        "ALTER TABLE investigation_cases ADD COLUMN source_reference TEXT;", encoding="utf-8"
    )
    original_tables = module._expected_tables

    def expected_tables():
        tables = original_tables()
        table = tables["investigation_cases"].to_metadata(MetaData())
        table.append_column(Column("source_reference", Text))
        return tables | {"investigation_cases": table}

    monkeypatch.setattr(module, "_expected_tables", expected_tables)
    assert migrate(engine, migrations_dir=tmp_path) == [len(versions()) + 1]
    assert migrate(engine, migrations_dir=tmp_path) == []


def test_postgres_case_origin_filters_before_pagination_and_preserves_privacy(engine):
    from bouncer.investigations import InvestigationStore

    store = InvestigationStore(engine.url.render_as_string(hide_password=False))
    snapshot = {"sessions": [{"id": "s1", "requests": []}], "synthetic": True}
    try:
        for index in range(4):
            store.create_from_legacy(snapshot, source_key=f"synthetic-{index}", public_demo=True)
        real = store.create_from_legacy(snapshot | {"synthetic": False}, source_key="real")
        store.create_from_legacy(snapshot | {"synthetic": False}, source_key="fixture")
        assert [case["id"] for case in store.list_cases(False, origin="real", limit=1)] == [
            real["id"]
        ]
        assert store.list_cases(origin="real") == []
        first = store.list_cases(origin="synthetic", limit=2)
        second = store.list_cases(origin="synthetic", limit=2, offset=2)
        assert len(first) == len(second) == 2
        assert not {case["id"] for case in first} & {case["id"] for case in second}
    finally:
        store.engine.dispose()
