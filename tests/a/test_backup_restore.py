"""Whole-database backups never reset review spending or select a user's live DB in tests."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
from pathlib import Path

import pytest


def api():
    module = importlib.import_module("bouncer.db.backup")
    return module.backup_database, module.restore_database


def sqlite_url(path):
    return "sqlite:///" + str(path)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.db"
    with sqlite3.connect(path) as db:
        for table in (
            "requests",
            "investigation_cases",
            "investigation_assessments",
            "investigation_budget",
            "enforcement_policies",
            "study_subjects",
            "study_enrollments",
            "study_session_reviews",
        ):
            db.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute(f"INSERT INTO {table} VALUES (1, ?)", (table + "-private",))
        db.execute("INSERT INTO investigation_budget VALUES (2, 'spent=17,reserved=23')")
    return path


def contents(path):
    with sqlite3.connect(path) as db:
        return {
            row[0]: db.execute(f'SELECT * FROM "{row[0]}"').fetchall()
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_full_sqlite_roundtrip_preserves_budget_and_all_tables(source, tmp_path):
    backup, restore = api()
    artifact = tmp_path / "backup.sqlite"
    manifest = backup(sqlite_url(source), artifact)
    assert manifest["format"] == "sqlite"
    assert manifest["sha256"] and manifest["schema"]
    target = tmp_path / "restored.db"
    report = restore(str(artifact) + ".manifest.json", sqlite_url(target))
    assert report["verified"] is True
    assert contents(source) == contents(target)
    assert contents(source)["investigation_budget"][-1][1] == "spent=17,reserved=23"
    assert "private" not in json.dumps(manifest)
    if os.name != "nt":
        assert artifact.stat().st_mode & 0o777 == 0o600
        assert Path(str(artifact) + ".manifest.json").stat().st_mode & 0o777 == 0o600


def test_refuses_existing_files_same_source_and_tampered_backup(source, tmp_path):
    backup, restore = api()
    artifact = tmp_path / "backup.sqlite"
    backup(sqlite_url(source), artifact)
    before = source.read_bytes()
    for path in (source, artifact):
        with pytest.raises(ValueError):
            backup(sqlite_url(source), path)
    with pytest.raises(ValueError):
        restore(str(artifact) + ".manifest.json", sqlite_url(source))
    assert source.read_bytes() == before
    with artifact.open("ab") as stream:
        stream.write(b"tamper")
    target = tmp_path / "target.db"
    with pytest.raises(ValueError, match="checksum|size"):
        restore(str(artifact) + ".manifest.json", sqlite_url(target))
    assert not target.exists()


def test_backup_size_limit_removes_incomplete_artifacts(source, tmp_path):
    backup, _ = api()
    artifact = tmp_path / "small.sqlite"
    with pytest.raises(ValueError, match="size"):
        backup(sqlite_url(source), artifact, max_bytes=32)
    assert not artifact.exists()
    assert not Path(str(artifact) + ".manifest.json").exists()


def test_sqlite_refuses_symlinks_and_manifest_traversal(source, tmp_path):
    backup, restore = api()
    artifact = tmp_path / "backup.sqlite"
    backup(sqlite_url(source), artifact)
    manifest_path = Path(str(artifact) + ".manifest.json")
    manifest = json.loads(manifest_path.read_text())
    manifest["artifact"] = "../source.db"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="artifact"):
        restore(manifest_path, sqlite_url(tmp_path / "target.db"))
    if os.name != "nt":
        link = tmp_path / "link"
        link.symlink_to(source)
        with pytest.raises(ValueError, match="symlink"):
            backup(sqlite_url(link), tmp_path / "other.sqlite")


def test_postgres_environment_has_no_credentials_or_connection_string_in_arguments():
    module = importlib.import_module("bouncer.db.backup")
    url = "postgresql+psycopg://operator:top%20secret@db:5433/source?sslmode=require"
    env = module.postgres_environment(url)
    assert env["PGPASSWORD"] == "top secret"
    assert env["PGSSLMODE"] == "require"
    assert env["PGDATABASE"] == "source"
    with pytest.raises(ValueError, match="unsupported"):
        module.postgres_environment(url + "&options=-c%20search_path%3Devil")


def test_cli_uses_environment_urls_and_sanitizes_errors(source, tmp_path, monkeypatch, capsys):
    module = importlib.import_module("tools.hostinger.backup")
    artifact = tmp_path / "cli.sqlite"
    monkeypatch.setenv("DATABASE_URL", sqlite_url(source))
    monkeypatch.setenv("RESTORE_DATABASE_URL", sqlite_url(tmp_path / "restored-cli.db"))
    assert module.main(["backup", "--output", str(artifact)]) == 0
    assert module.main(["restore", "--manifest", str(artifact) + ".manifest.json"]) == 0
    assert contents(source) == contents(tmp_path / "restored-cli.db")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:private-secret@127.0.0.1:1/no")
    assert module.main(["backup", "--output", str(tmp_path / "bad"), "--timeout", "1"]) == 2
    captured = capsys.readouterr()
    assert "private-secret" not in captured.out + captured.err


@pytest.fixture(scope="module")
def owned_postgres():
    import subprocess
    import time
    import uuid

    from sqlalchemy import create_engine

    if os.getenv("BOUNCER_TEST_POSTGRES") != "1":
        pytest.skip("set BOUNCER_TEST_POSTGRES=1 for owned disposable PostgreSQL roundtrip")
    name = "bouncer-backup-" + uuid.uuid4().hex
    env = dict(os.environ, POSTGRES_PASSWORD="backup-disposable-only")
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--publish",
            "127.0.0.1::5432",
            "--env",
            "POSTGRES_PASSWORD",
            "postgres:16-alpine",
        ],
        env=env,
        check=True,
        capture_output=True,
        timeout=60,
    )
    admin = None
    try:
        port = (
            subprocess.check_output(["docker", "port", name, "5432/tcp"], text=True, timeout=10)
            .strip()
            .rsplit(":", 1)[1]
        )
        base = f"postgresql+psycopg://postgres:backup-disposable-only@127.0.0.1:{port}/"
        admin = create_engine(base + "postgres", isolation_level="AUTOCOMMIT")
        deadline = time.monotonic() + 30
        while True:
            try:
                with admin.connect() as conn:
                    conn.exec_driver_sql("SELECT 1")
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
        with admin.connect() as conn:
            for database in ("backup_source", "backup_target", "backup_failed"):
                conn.exec_driver_sql(f'CREATE DATABASE "{database}"')

        def runner(command, *, env, **kwargs):
            from bouncer.db.backup import run_client

            assert not any("backup-disposable-only" in value for value in command)
            forwarded = dict(env, PGHOST="127.0.0.1", PGPORT="5432")
            args = ["docker", "exec", "-i"]
            for key in forwarded:
                if key.startswith("PG"):
                    args.extend(["--env", key])
            run_client(args + [name] + command, env=forwarded, **kwargs)

        yield base, runner
    finally:
        if admin:
            admin.dispose()
        subprocess.run(
            ["docker", "rm", "--force", name], check=True, capture_output=True, timeout=20
        )


def test_real_postgres_full_roundtrip_and_occupied_target_refusal(owned_postgres, tmp_path):
    from sqlalchemy import create_engine

    from bouncer.db.migrate import run_migrations

    base, runner = owned_postgres
    source = create_engine(base + "backup_source")
    target = create_engine(base + "backup_target")
    backup, restore = api()
    try:
        run_migrations(source)
        with source.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO investigation_budget "
                "(id,spent,reserved,executions,requests) VALUES (1,17,23,2,4)"
            )
            conn.exec_driver_sql(
                "INSERT INTO investigation_cases VALUES "
                "('case','private-source','hash',false,'{\"secret\":1}', 'now')"
            )
            conn.exec_driver_sql(
                "INSERT INTO investigation_assessments VALUES "
                "('assessment','case','job','review','{}','{}','now')"
            )
            conn.exec_driver_sql(
                "INSERT INTO investigation_jobs VALUES "
                "('job','case','hash','config','running',23,2,1,'worker','','now')"
            )
            conn.exec_driver_sql(
                "INSERT INTO investigation_reservations VALUES "
                "('reservation','job','review','provider','model',23,NULL,"
                "'dispatched','{}',NULL,'test')"
            )
            conn.exec_driver_sql(
                "INSERT INTO demo_enforcement_audit VALUES ('audit','policy','approved',1,'{}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO sessions "
                "(ip,user_agent,started_at,ended_at,external_id,"
                "view_started_at,view_ended_at) VALUES "
                "('192.0.2.1','fixture',now(),now(),'opaque',now(),now())"
            )
            conn.exec_driver_sql(
                "INSERT INTO requests "
                "(ts,ip,method,path,status,session_id,byte_offset) VALUES "
                "(now(),'192.0.2.1','GET','/private',200,1,1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO labels (session_id,run_id,sim_class) VALUES (1,'fixture','human')"
            )
        from bouncer.db.participants import StudyStore
        from tests.a.test_participants import enroll, review
        from tests.a.test_participants import source as study_source

        study = StudyStore(source)
        study_source(study.traffic)
        enrolled = enroll(study)
        review(study, enrolled)
        from bouncer.db.evaluations import EvaluationLedger

        ledger = EvaluationLedger(source)
        prepared = ledger.reserve(descriptor={"fixture": "backup-consumed-holdout"},
                                  development_units={"1" * 64}, holdout_units={"2" * 64},
                                  source_keys=["collection-a"])
        prepared = ledger.set_artifacts(prepared["preparation_id"], artifacts={"fixture": True})
        ledger.claim(prepared["preparation_id"], artifact_digest=prepared["artifact_digest"])
        ledger.finish(prepared["preparation_id"], artifact_digest=prepared["artifact_digest"],
                      report={"fixture": "private-consumed-report"})
        artifact = tmp_path / "database.dump"
        manifest = backup(base + "backup_source", artifact, runner=runner)
        assert artifact.read_bytes().startswith(b"PGDMP")
        assert manifest["schema"]["version"] >= 8
        report = restore(str(artifact) + ".manifest.json", base + "backup_target", runner=runner)
        assert report["verified"] is True
        with source.connect() as left, target.connect() as right:
            tables = left.exec_driver_sql(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            ).scalars()
            for table in tables:
                assert left.exec_driver_sql(f'SELECT * FROM "{table}"').all() == (
                    right.exec_driver_sql(f'SELECT * FROM "{table}"').all()
                )
            assert right.exec_driver_sql(
                "SELECT spent,reserved FROM investigation_budget"
            ).one() == (17, 23)
        restored_ledger = EvaluationLedger(target)
        assert restored_ledger.claim(prepared["preparation_id"],
                                     artifact_digest=prepared["artifact_digest"])["cached"] is True
        for database in ("backup_target", "backup_source"):
            with pytest.raises(ValueError, match="empty|differ"):
                restore(str(artifact) + ".manifest.json", base + database, runner=runner)
    finally:
        source.dispose()
        target.dispose()


def test_client_timeout_size_limit_and_missing_binary_are_sanitized(tmp_path, monkeypatch):
    import subprocess
    import sys

    from bouncer.db.backup import run_client

    with pytest.raises(ValueError, match="timed out"):
        run_client(
            [sys.executable, "-c", "import time; time.sleep(20)"], env=dict(os.environ), timeout=0.1
        )
    with (tmp_path / "limit").open("wb") as stream, pytest.raises(ValueError, match="size"):
        run_client(
            [
                sys.executable,
                "-c",
                "import sys,time; sys.stdout.buffer.write(b'x'*100000);"
                "sys.stdout.flush(); time.sleep(10)",
            ],
            env=dict(os.environ),
            stdout=stream,
            timeout=2,
            max_bytes=32,
        )

    def missing(*args, **kwargs):
        raise FileNotFoundError("credential-secret")

    monkeypatch.setattr(subprocess, "Popen", missing)
    with pytest.raises(RuntimeError, match="unavailable") as error:
        run_client(["pg_dump"], env={})
    assert "credential-secret" not in str(error.value)


def test_broken_postgres_archive_rolls_back_all_restored_objects(owned_postgres, tmp_path):
    import hashlib

    from sqlalchemy import create_engine, inspect

    from bouncer.db.migrate import run_migrations

    base, runner = owned_postgres
    source = create_engine(base + "backup_source")
    try:
        run_migrations(source)
    finally:
        source.dispose()
    backup, restore = api()
    artifact = tmp_path / "broken.dump"
    manifest = backup(base + "backup_source", artifact, runner=runner)
    raw = artifact.read_bytes()
    artifact.write_bytes(raw[:-128])
    manifest["sha256"] = hashlib.sha256(raw[:-128]).hexdigest()
    manifest["bytes"] = len(raw) - 128
    manifest_path = Path(str(artifact) + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="client failed"):
        restore(manifest_path, base + "backup_failed", runner=runner)
    target = create_engine(base + "backup_failed")
    try:
        assert inspect(target).get_table_names() == []
    finally:
        target.dispose()


def test_malformed_database_urls_never_echo_credentials(tmp_path):
    backup, restore = api()
    with pytest.raises(ValueError) as error:
        backup("private-credential-is-not-a-url", tmp_path / "bad")
    assert "private-credential" not in str(error.value)


def test_plain_postgres_urls_use_installed_psycopg_driver(monkeypatch):
    module = importlib.import_module("bouncer.db.backup")

    def engine(url, **kwargs):
        assert url.drivername == "postgresql+psycopg"
        raise RuntimeError("driver selected")

    monkeypatch.setattr(module, "create_engine", engine)
    with pytest.raises(RuntimeError, match="driver selected"):
        module._pg_state("postgresql://operator:secret@db/source", 1)


def test_fast_client_output_cannot_bypass_size_limit(tmp_path):
    import sys

    from bouncer.db.backup import run_client

    with (tmp_path / "fast-limit").open("wb") as stream, pytest.raises(ValueError, match="size"):
        run_client(
            [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'x'*10000)"],
            env=dict(os.environ),
            stdout=stream,
            timeout=2,
            max_bytes=32,
        )
