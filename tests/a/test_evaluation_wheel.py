"""Native reference evaluation works from the installed wheel without checkout tools."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from tools.datasets.native import generate_bundle


def test_installed_wheel_builds_verified_native_references_without_tools(tmp_path):
    root = Path(__file__).resolve().parents[2]
    uv = shutil.which("uv")
    assert uv is not None, "the project's uv build tool is required"
    wheel_dir = tmp_path / "wheel"
    built = subprocess.run(
        [uv, "build", "--offline", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=root, capture_output=True, text=True, timeout=60,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    target = tmp_path / "installed"
    installed = subprocess.run(
        [uv, "pip", "install", "--offline", "--no-deps", "--target", str(target),
         str(next(wheel_dir.glob("*.whl")))],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    script = """
import importlib.util
import json
import sys
from pathlib import Path

target, checkout, output = map(Path, sys.argv[1:])
sys.path[:] = [p for p in sys.path if Path(p).resolve() not in (checkout, checkout / 'src')]
sys.path.insert(0, str(target))
assert importlib.util.find_spec('tools') is None
import bouncer
assert Path(bouncer.__file__).resolve().is_relative_to(target)
from bouncer.eval.reference import build_references
from bouncer.eval.native_fixtures import generate_bundle, outside_repository, verify_bundle
from bouncer.eval.source_registry import checksum
from bouncer.eval.frozen import fingerprint
from bouncer.eval.frozen_cli import main
import contextlib
import io

with contextlib.redirect_stdout(io.StringIO()):
    try:
        main(['--help'])
    except SystemExit as exc:
        assert exc.code == 0
assert fingerprint()['code']

manifest_path = generate_bundle(output, seed=17, runs_per_partition=1)
manifest = verify_bundle(manifest_path)
references = build_references([], [], [manifest_path])
assert len(references.sessions) == len(references.examples) == manifest['n_sessions']
assert references.rows
assert len(checksum(manifest_path)['sha256']) == 64
for forbidden in (target, target / 'bouncer' / 'generated'):
    try:
        outside_repository(forbidden)
    except ValueError:
        pass
    else:
        raise AssertionError('installed library artifacts were not rejected')
assert outside_repository(output) == output.resolve()
print(json.dumps(manifest['code_sha256'], sort_keys=True))
"""
    checked = subprocess.run(
        [sys.executable, "-I", "-c", script, str(target), str(root),
         str(tmp_path / "wheel-bundle")],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    source_path = generate_bundle(tmp_path / "source-bundle", seed=17, runs_per_partition=1)
    source_manifest = json.loads(source_path.read_text(encoding="utf-8"))
    assert json.loads(checked.stdout) == source_manifest["code_sha256"]
    assert {
        "src/bouncer/eval/native_fixtures.py", "src/bouncer/eval/source_registry.py",
    } <= source_manifest["code_sha256"].keys()
