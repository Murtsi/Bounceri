import base64
import io
import tarfile

import pytest

from tools.hostinger.package import capsule, compose


def test_capsule_excludes_credentials_raw_data_and_symlinks(tmp_path):
    for name in (
        "src/bouncer/a.py",
        "src/bouncer/.env",
        "frontend/dist/index.html",
        "data/store.json",
        ".env",
        "src/bouncer/__pycache__/x.pyc",
        "src/bouncer/credentials.json",
        "models/private-labels.json",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("secret" if ".env" in name else "fixture")
    encoded, digest = capsule(tmp_path)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(encoded)), mode="r:gz") as archive:
        assert sorted(archive.getnames()) == ["frontend/dist/index.html", "src/bouncer/a.py"]
    assert len(digest) == 64


def test_capsule_requires_prebuilt_dashboard(tmp_path):
    with pytest.raises(ValueError, match="dashboard"):
        capsule(tmp_path)


def test_required_gateway_config_and_release_restart_marker(tmp_path):
    for name in (
        "frontend/dist/index.html",
        "deploy/Caddyfile.simulation",
        "tools/hostinger/bootstrap.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    encoded, _ = capsule(tmp_path)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(encoded)), mode="r:gz") as archive:
        assert "deploy/Caddyfile.simulation" in archive.getnames()
    env = {
        name: "x" * 64
        for name in (
            "POSTGRES_PASSWORD",
            "BOUNCER_ADMIN_TOKEN",
            "BOUNCER_DEMO_ACTOR_SECRET",
            "SIM_RUN_SECRET",
        )
    }
    a = compose(tmp_path, "test.example", env)
    (tmp_path / "frontend/dist/index.html").write_text("new release")
    b = compose(tmp_path, "test.example", env)
    assert (
        b["services"]["site"]["labels"]["traefik.http.routers.bounceri-demo.rule"]
        == "Host(`demo.test.example`)"
    )
    for service in ("api", "site", "ingest", "review", "simulator", "simulation-gateway"):
        assert a["services"][service] != b["services"][service]
    routed = compose(tmp_path, "test.example", env, aliases=("bounceri.tech", "www.bounceri.tech"))
    rule = routed["services"]["api"]["labels"]["traefik.http.routers.bounceri.rule"]
    assert rule == "Host(`test.example`) || Host(`bounceri.tech`) || Host(`www.bounceri.tech`)"
    with pytest.raises(ValueError):
        compose(tmp_path, "test.example", env, aliases=("unsafe`)",))
