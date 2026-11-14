"""Private full-database archives; restore only to an explicit, empty separate target.

PostgreSQL requires installed pg_dump/pg_restore matching the server major version.
No store constructor is used: restoring must never initialize or reset budget state.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from bouncer.db.migrate import MIGRATIONS_DIR, _validate_schema

MAX_BYTES = 1024 * 1024 * 1024
_SSL = {
    "sslmode": "PGSSLMODE",
    "sslrootcert": "PGSSLROOTCERT",
    "sslcert": "PGSSLCERT",
    "sslkey": "PGSSLKEY",
    "sslcrl": "PGSSLCRL",
}


def _url(value):
    try:
        return make_url(value)
    except (ArgumentError, TypeError, ValueError):
        raise ValueError("invalid database URL") from None


def postgres_environment(database_url: str) -> dict[str, str]:
    """Parse an explicit URL; never inherit libpq overrides or put secrets in argv."""
    url = _url(database_url)
    if url.get_backend_name() != "postgresql" or not url.host or not url.database:
        raise ValueError("explicit PostgreSQL host and database are required")
    if any(key not in _SSL or not isinstance(value, str) for key, value in url.query.items()):
        raise ValueError("unsupported PostgreSQL connection option")
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PG")}
    env.update(
        PGHOST=url.host,
        PGPORT=str(url.port or 5432),
        PGDATABASE=url.database,
        PGUSER=url.username or "",
        PGPASSWORD=url.password or "",
        PGCONNECT_TIMEOUT="10",
        PGPASSFILE=os.devnull,
        PGSERVICEFILE=os.devnull,
    )
    env.update({_SSL[key]: value for key, value in url.query.items()})
    return env


def _path(path: str | Path, *, exists: bool = False) -> Path:
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("symlink paths are not allowed")
    if exists and not path.is_file():
        raise ValueError("a regular existing file is required")
    if not exists and path.exists():
        raise ValueError("refusing to overwrite an existing file")
    return path.resolve()


def _sqlite_path(database_url: str, *, exists: bool) -> Path:
    url = _url(database_url)
    if (
        url.get_backend_name() != "sqlite"
        or url.query
        or not url.database
        or (url.database == ":memory:")
    ):
        raise ValueError("an explicit SQLite file without URL options is required")
    return _path(url.database, exists=exists)


def _private_file(path: Path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _ledger() -> list[list]:
    return [
        [
            int(path.name.split("_", 1)[0]),
            path.name,
            hashlib.sha256(path.read_text(encoding="utf-8-sig").encode()).hexdigest(),
        ]
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
    ]


def _pg_state(database_url: str, timeout: float, *, empty: bool = False) -> tuple[str, dict]:
    postgres_environment(database_url)
    engine = create_engine(
        _url(database_url).set(drivername="postgresql+psycopg"),
        connect_args={"connect_timeout": max(1, int(timeout))},
    )
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(
                "SELECT set_config('statement_timeout', %s, true)",
                (str(max(1, int(timeout * 1000))),),
            )
            identity = _identity(
                list(
                    conn.exec_driver_sql(
                        "SELECT inet_server_addr()::text, inet_server_port(), current_database()"
                    ).one()
                )
            )
            if empty:
                populated = conn.exec_driver_sql(
                    "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n "
                    "ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' "
                    "AND n.nspname <> 'information_schema') OR EXISTS "
                    "(SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_' "
                    "AND nspname NOT IN ('public', 'information_schema')) OR EXISTS "
                    "(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='public') OR EXISTS "
                    "(SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                    "WHERE n.nspname='public') OR EXISTS "
                    "(SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')"
                ).scalar_one()
                if populated:
                    raise ValueError("restore requires an empty target database")
                return identity, {}
            conn.exec_driver_sql("SET LOCAL search_path TO public")
            history = [
                list(row)
                for row in conn.exec_driver_sql(
                    "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
                )
            ]
            if history != _ledger():
                raise ValueError("backup requires the current checked migration ledger")
            _validate_schema(conn)
            return identity, {"version": history[-1][0], "ledger": history}
    finally:
        engine.dispose()


def _sqlite_schema(path: Path) -> dict:
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("SQLite integrity check failed")
        rows = conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY type, name"
        ).fetchall()
    return {"sha256": _identity(rows)}


def run_client(command, *, env, stdin=None, stdout=None, timeout=120, max_bytes=MAX_BYTES):
    """Bound the process and archive; suppress driver/tool output containing private data."""
    try:
        process = subprocess.Popen(
            command,
            env=env,
            stdin=stdin or subprocess.DEVNULL,
            stdout=stdout or subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "PostgreSQL backup client unavailable; install pg_dump/pg_restore"
        ) from None
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                raise ValueError("database archive operation timed out")
            if stdout is not None and os.fstat(stdout.fileno()).st_size > max_bytes:
                raise ValueError("backup exceeds size limit")
            time.sleep(0.02)
        if process.returncode:
            raise RuntimeError("PostgreSQL archive client failed; check configuration and versions")
        if stdout is not None and os.fstat(stdout.fileno()).st_size > max_bytes:
            raise ValueError("backup exceeds size limit")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def _copy_sqlite(source: Path, target: Path, timeout: float, max_bytes: int) -> None:
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise ValueError("database archive operation timed out")
        if target.stat().st_size > max_bytes:
            raise ValueError("backup exceeds size limit")

    with (
        closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=timeout)) as src,
        closing(sqlite3.connect(target, timeout=timeout)) as dst,
    ):
        src.backup(dst, pages=256, progress=progress, sleep=0.01)


def _limits(timeout, max_bytes):
    if not 0 < timeout <= 3600 or not 0 < max_bytes <= 100 * MAX_BYTES:
        raise ValueError("invalid archive timeout or size limit")


def backup_database(
    database_url: str, output_path: str | Path, *, timeout=120, max_bytes=MAX_BYTES, runner=None
) -> dict:
    """Write a new private full archive plus adjacent checksum/schema manifest."""
    _limits(timeout, max_bytes)
    artifact = _path(output_path)
    manifest_path = _path(str(artifact) + ".manifest.json")
    backend = _url(database_url).get_backend_name()
    if backend not in {"postgresql", "sqlite"}:
        raise ValueError("unsupported database backend")
    owned = []
    try:
        if backend == "sqlite":
            source = _sqlite_path(database_url, exists=True)
            source_identity = _identity(["sqlite", os.path.normcase(str(source))])
        else:
            source_identity, schema = _pg_state(database_url, timeout)
        with _private_file(artifact) as stream:
            owned.append(artifact)
            if backend == "sqlite":
                stream.close()
                _copy_sqlite(source, artifact, timeout, max_bytes)
                schema = _sqlite_schema(artifact)
            else:
                (runner or run_client)(
                    ["pg_dump", "--format=custom", "--no-owner", "--no-acl"],
                    env=postgres_environment(database_url),
                    stdout=stream,
                    timeout=timeout,
                    max_bytes=max_bytes,
                )
        if artifact.stat().st_size > max_bytes:
            raise ValueError("backup exceeds size limit")
        if backend == "postgresql" and _pg_state(database_url, timeout)[1] != schema:
            raise ValueError("schema changed while creating backup")
        manifest = {
            "manifest_version": 1,
            "format": "sqlite" if backend == "sqlite" else "postgresql-custom",
            "artifact": artifact.name,
            "bytes": artifact.stat().st_size,
            "sha256": _digest(artifact),
            "schema": schema,
            "source_identity": source_identity,
        }
        with _private_file(manifest_path) as stream:
            owned.append(manifest_path)
            stream.write((json.dumps(manifest, sort_keys=True) + "\n").encode())
        return manifest
    except (ValueError, RuntimeError):
        for path in owned:
            path.unlink(missing_ok=True)
        raise
    except Exception:
        for path in owned:
            path.unlink(missing_ok=True)
        raise RuntimeError(
            "database backup failed; check configuration and file permissions"
        ) from None


def restore_database(
    manifest_path: str | Path, target_url: str, *, timeout=120, max_bytes=MAX_BYTES, runner=None
) -> dict:
    """Restore and validate without migrations; PostgreSQL target must already be empty."""
    _limits(timeout, max_bytes)
    target = None
    owned = False
    try:
        manifest_path = _path(manifest_path, exists=True)
        with manifest_path.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("manifest exceeds size limit")
        manifest = json.loads(raw)
        name = manifest.get("artifact")
        if (
            not isinstance(name, str)
            or name in {"", ".", ".."}
            or ("/" in name or "\\" in name or ":" in name)
        ):
            raise ValueError("invalid manifest artifact")
        artifact = _path(manifest_path.parent / name, exists=True)
        if manifest.get("manifest_version") != 1 or not 0 < artifact.stat().st_size <= max_bytes:
            raise ValueError("invalid backup version or size")
        if artifact.stat().st_size != manifest.get("bytes") or _digest(artifact) != manifest.get(
            "sha256"
        ):
            raise ValueError("backup checksum or size mismatch")
        backend = _url(target_url).get_backend_name()
        if manifest.get("format") == "sqlite" and backend == "sqlite":
            target = _sqlite_path(target_url, exists=False)
            if manifest["source_identity"] == _identity(["sqlite", os.path.normcase(str(target))]):
                raise ValueError("restore target must differ from source")
            if _sqlite_schema(artifact) != manifest["schema"]:
                raise ValueError("backup schema mismatch")
            with _private_file(target):
                owned = True
            _copy_sqlite(artifact, target, timeout, max_bytes)
            if _sqlite_schema(target) != manifest["schema"]:
                raise ValueError("restored schema mismatch")
        elif manifest.get("format") == "postgresql-custom" and backend == "postgresql":
            if manifest["schema"] != {"version": _ledger()[-1][0], "ledger": _ledger()}:
                raise ValueError("backup schema requires the current checked migration ledger")
            identity, _ = _pg_state(target_url, timeout, empty=True)
            if identity == manifest["source_identity"]:
                raise ValueError("restore target must differ from source")
            with artifact.open("rb") as stream:
                (runner or run_client)(
                    [
                        "pg_restore",
                        "--dbname=",
                        "--single-transaction",
                        "--exit-on-error",
                        "--no-owner",
                        "--no-acl",
                    ],
                    env=postgres_environment(target_url),
                    stdin=stream,
                    timeout=timeout,
                    max_bytes=max_bytes,
                )
            if _pg_state(target_url, timeout)[1] != manifest["schema"]:
                raise ValueError("restored schema mismatch")
        else:
            raise ValueError("backup and target database formats differ")
        return {
            "verified": True,
            "format": manifest["format"],
            "sha256": manifest["sha256"],
            "schema": manifest["schema"],
        }
    except (ValueError, RuntimeError):
        if owned:
            target.unlink(missing_ok=True)
        raise
    except Exception:
        if owned:
            target.unlink(missing_ok=True)
        raise RuntimeError(
            "database restore failed; check manifest and target configuration"
        ) from None
