"""Package only runtime sources and the built dashboard for Hostinger's Docker API.

No Git credential, image registry, SSH access or public repository is needed.
Generated files are private deployment material; never commit them.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import re
import secrets
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def capsule(root: Path) -> tuple[str, str]:
    if not (root / "frontend/dist/index.html").is_file():
        raise ValueError("Build the dashboard with pnpm run build before packaging")
    paths = []
    for folder in ("src/bouncer", "tools/sim", "tools/hostinger", "tools/datasets"):
        paths.extend((root / folder).rglob("*.py"))
    paths.extend((root / "frontend/dist").rglob("*"))
    paths.extend((root / "src/bouncer/db/migrations").glob("*.sql"))
    paths.extend(
        root / name
        for name in (
            "deploy/traps.txt",
            "deploy/Caddyfile.simulation",
            "deploy/requirements-runtime.txt",
            "samples/access.sample.jsonl",
            "LICENSE",
            "README.md",
            "src/bouncer/site/static/app.css",
            "src/bouncer/site/static/app.js",
            "src/bouncer/site/static/logo.svg",
            "src/bouncer/network/data/asn_prefixes.json",
            "src/bouncer/network/data/threat_prefixes.json",
            "src/bouncer/network/campaign_metrics.json",
            "models/metrics.json",
            "models/evaluation.synthetic.json",
            "models/model.json",
            "tools/datasets/registry.example.json",
        )
    )
    stream = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        for path in sorted(set(paths)):
            relative = path.relative_to(root)
            if (
                not path.is_file()
                or path.is_symlink()
                or any(
                    p.startswith(".") or p in {"__pycache__", "node_modules"}
                    for p in relative.parts
                )
                or (
                    relative.as_posix() != "deploy/Caddyfile.simulation"
                    and path.suffix
                    not in {
                        ".py",
                        ".sql",
                        ".json",
                        ".jsonl",
                        ".html",
                        ".js",
                        ".css",
                        ".svg",
                        ".txt",
                        ".md",
                        ".woff",
                        ".woff2",
                        "",
                    }
                )
            ):
                continue
            info = archive.gettarinfo(str(path), arcname=relative.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            info.mtime = 0
            with path.open("rb") as source:
                archive.addfile(info, source)
    raw = stream.getvalue()
    if len(raw) > 2_000_000:
        raise ValueError("Runtime capsule unexpectedly exceeds 2 MB")
    return base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest()


def compose(
    root: Path, host: str, environment: dict, *, local: bool = False, aliases: tuple[str, ...] = (),
    traffic_sql: bool = False,
) -> dict:
    if any(not re.fullmatch(r"[a-z0-9.-]+", value) for value in (host, *aliases)):
        raise ValueError("Invalid deployment host")
    demo_host = "demo-" + host if host.endswith(".hstgr.cloud") else "demo." + host
    encoded, digest = capsule(root)
    release = f"/app/releases/{digest}"
    chunks = [encoded[n : n + 48000] for n in range(0, len(encoded), 48000)]
    source_env = {f"CAPSULE_{i:03}": chunk for i, chunk in enumerate(chunks)}
    bootstrap = base64.b64encode((root / "tools/hostinger/bootstrap.py").read_bytes()).decode()
    database = "postgresql+psycopg://bouncer:" + environment["POSTGRES_PASSWORD"] + "@db/bouncer"
    common_env = {
        "PYTHONPATH": f"{release}/src:{release}",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "BOUNCER_STORE_PATH": "/data/store.json",
        "BOUNCER_TRAFFIC_SOURCE": "private-simulation",
        "BOUNCER_DATABASE_URL": database,
        "BOUNCERI_DATABASE_URL": database,
        "BOUNCERI_REVIEW_ENABLED": "false",
        "BOUNCER_RELEASE": digest,
    }
    if traffic_sql:
        common_env.update({
            "BOUNCER_TRAFFIC_DATABASE_URL": database,
            "BOUNCER_TRAFFIC_RETENTION_SECONDS": "86400",
        })
    review_env = {
        key: str(value)
        for key, value in environment.items()
        if key
        in {
            "FEATHERLESS_API_KEY",
            "HOSTINGER_ROUTER_API_KEY",
            "BOUNCERI_REVIEW_ENABLED",
            "BOUNCERI_DECISION_PROVIDER",
            "BOUNCERI_AUTO_REVIEW",
            "BOUNCERI_AUTO_REVIEW_MAX_EXECUTIONS",
        }
        or key.startswith(("BOUNCERI_DECISION_", "BOUNCERI_REVIEWER_"))
    }

    def app(command, *, data=False):
        return {
            "image": "python:3.12-slim-bookworm",
            "restart": "unless-stopped",
            "user": "10001:10001",
            "working_dir": release,
            "command": [f"{release}/.venv/bin/python", *command],
            "environment": dict(common_env),
            "volumes": ["source:/app:ro", "data:/data" + ("" if data else ":ro")],
            "depends_on": {"init": {"condition": "service_completed_successfully"}},
            "read_only": True,
            "tmpfs": ["/tmp:size=32m"],
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
            "mem_limit": "512m",
            "cpus": 0.5,
            "logging": {"driver": "json-file", "options": {"max-size": "5m", "max-file": "2"}},
        }

    services = {
        "db": {
            "image": "postgres:16-alpine",
            "restart": "unless-stopped",
            "environment": {
                "POSTGRES_USER": "bouncer",
                "POSTGRES_DB": "bouncer",
                "POSTGRES_PASSWORD": environment["POSTGRES_PASSWORD"],
            },
            "volumes": ["postgres:/var/lib/postgresql/data"],
            "mem_limit": "512m",
            "healthcheck": {
                "test": ["CMD-SHELL", "pg_isready -U bouncer -d bouncer"],
                "interval": "5s",
                "timeout": "3s",
                "retries": 20,
            },
        },
        "init": {
            "image": "python:3.12-slim-bookworm",
            "restart": "no",
            "command": ["python", "-c", f"import base64;exec(base64.b64decode('{bootstrap}'))"],
            "environment": {
                **common_env,
                **source_env,
                "CAPSULE_SHA256": digest,
                "CAPSULE_CHUNKS": str(len(chunks)),
            },
            "volumes": ["source:/app", "data:/data", "logs:/logs"],
            "depends_on": {"db": {"condition": "service_healthy"}},
            "mem_limit": "768m",
        },
        "site": app(
            ["-m", "uvicorn", "bouncer.site.app:app", "--host", "0.0.0.0", "--port", "8000"]
        ),
        "api": app(["-m", "uvicorn", "bouncer.api.app:app", "--host", "0.0.0.0", "--port", "8001"]),
        "ingest": app(["-m", "tools.hostinger.runtime", "ingest"], data=True),
        "simulator": app(["-m", "tools.hostinger.runtime", "simulate"]),
        "review": app(["-m", "bouncer.review.worker"]),
        "simulation-gateway": {
            "image": "caddy:2.8.4",
            "restart": "unless-stopped",
            "command": [
                "caddy",
                "run",
                "--config",
                f"{release}/deploy/Caddyfile.simulation",
                "--adapter",
                "caddyfile",
            ],
            "volumes": ["source:/app:ro", "logs:/var/log/caddy"],
            "depends_on": {"site": {"condition": "service_started"}},
            "mem_limit": "128m",
            "user": "10001:10001",
            "read_only": True,
            "tmpfs": ["/tmp:size=32m"],
            "cap_drop": ["ALL"],
            # The official 2.8 binary has a file capability; its bounding-set bit
            # must remain available even though this private listener uses 8080.
            "cap_add": ["NET_BIND_SERVICE"],
            "security_opt": ["no-new-privileges:true"],
            "environment": {
                "BOUNCER_RELEASE": digest,
                "XDG_CONFIG_HOME": "/tmp",
                "XDG_DATA_HOME": "/tmp",
            },
        },
    }
    for service in ("api", "site"):
        services[service]["environment"]["BOUNCER_DEMO_ACTOR_SECRET"] = environment[
            "BOUNCER_DEMO_ACTOR_SECRET"
        ]
    services["api"]["environment"]["BOUNCER_ADMIN_TOKEN"] = environment["BOUNCER_ADMIN_TOKEN"]
    for service in ("api", "review", "ingest"):
        services[service]["environment"].update(review_env)
    for service in ("ingest", "simulator"):
        services[service]["environment"]["SIM_RUN_SECRET"] = environment["SIM_RUN_SECRET"]
    for key in ("BOUNCER_DATABASE_URL", "BOUNCERI_DATABASE_URL", "BOUNCER_TRAFFIC_DATABASE_URL"):
        services["simulator"]["environment"].pop(key, None)
    services["ingest"]["volumes"].append("logs:/logs:ro")
    services["simulation-gateway"]["healthcheck"] = {
        "test": ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"],
        "interval": "5s",
        "timeout": "3s",
        "retries": 20,
    }
    services["simulator"]["depends_on"]["simulation-gateway"] = {"condition": "service_healthy"}
    services["api"]["ports"] = ["127.0.0.1:18181:8001"]
    services["api"]["healthcheck"] = {
        "test": [
            "CMD",
            f"{release}/.venv/bin/python",
            "-c",
            "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/api/healthz')",
        ],
        "interval": "15s",
        "timeout": "5s",
        "retries": 10,
    }
    if local:
        services["site"]["ports"] = ["127.0.0.1:18180:8000"]
    else:
        services["api"]["labels"] = {
            "traefik.enable": "true",
            "traefik.http.routers.bounceri.rule": " || ".join(
                f"Host(`{value}`)" for value in dict.fromkeys((host, *aliases))
            ),
            "traefik.http.routers.bounceri.entrypoints": "websecure",
            "traefik.http.routers.bounceri.tls.certresolver": "letsencrypt",
            "traefik.http.services.bounceri.loadbalancer.server.port": "8001",
        }
        services["site"]["labels"] = {
            "traefik.enable": "true",
            "traefik.http.routers.bounceri-demo.rule": f"Host(`{demo_host}`)",
            "traefik.http.routers.bounceri-demo.entrypoints": "websecure",
            "traefik.http.routers.bounceri-demo.tls.certresolver": "letsencrypt",
            "traefik.http.services.bounceri-demo.loadbalancer.server.port": "8000",
        }
    return {
        "name": "bounceri-live",
        "services": services,
        "volumes": {name: {} for name in ("postgres", "source", "data", "logs")},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="bounceri.srv2159025.hstgr.cloud")
    parser.add_argument(
        "--alias", action="append", default=[], help="Additional dashboard hostname"
    )
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--traffic-sql", action="store_true",
                        help="Use SQL traffic after verified archive/cutover; default keeps JSON")
    parser.add_argument(
        "--review-config", type=Path, help="Verified server review env as private JSON"
    )
    parser.add_argument(
        "--credentials", type=Path, help="Ignored local dotenv containing Featherless key"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    secret_file = args.output / ".env.hostinger"
    if secret_file.exists():
        env = json.loads(secret_file.read_text())
    else:
        env = {
            name: secrets.token_hex(32)
            for name in (
                "POSTGRES_PASSWORD",
                "BOUNCER_ADMIN_TOKEN",
                "BOUNCER_DEMO_ACTOR_SECRET",
                "SIM_RUN_SECRET",
            )
        }
        secret_file.write_text(json.dumps(env), encoding="utf-8")
    if args.review_config:
        env.update(json.loads(args.review_config.read_text(encoding="utf-8")))
    if args.credentials:
        for line in args.credentials.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "FEATHERLESS_API_KEY" and value.strip():
                env["FEATHERLESS_API_KEY"] = value.strip().strip("\"'")
    target = args.output / "compose.private.json"
    target.write_text(
        json.dumps(compose(ROOT, args.host, env, local=args.local, aliases=tuple(args.alias),
                           traffic_sql=args.traffic_sql)),
        encoding="utf-8",
    )
    print(f"Private deployment bundle written to {target}; secret values are not displayed.")


if __name__ == "__main__":
    main()
