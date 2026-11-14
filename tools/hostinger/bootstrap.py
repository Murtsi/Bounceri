"""One-shot capsule installation, executed by the deployment init container."""

import base64
import hashlib
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path


def main():
    chunks = int(os.environ["CAPSULE_CHUNKS"])
    raw = base64.b64decode(
        "".join(os.environ[f"CAPSULE_{i:03}"] for i in range(chunks)), validate=True
    )
    expected = os.environ["CAPSULE_SHA256"]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Deployment capsule checksum mismatch")
    target = Path("/app/releases") / expected
    marker = target / ".ready"
    if not marker.exists():
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            if sum(m.size for m in archive.getmembers()) > 25_000_000:
                raise ValueError("Deployment capsule is too large")
            archive.extractall(target, filter="data")
        subprocess.run([sys.executable, "-m", "venv", str(target / ".venv")], check=True)
        subprocess.run(
            [
                str(target / ".venv/bin/python"),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "-r",
                str(target / "deploy/requirements-runtime.txt"),
            ],
            check=True,
        )
        marker.touch()
    Path("/data").mkdir(exist_ok=True)
    os.chown("/data", 10001, 10001)
    os.chmod("/data", 0o700)
    Path("/logs").mkdir(exist_ok=True)
    os.chown("/logs", 10001, 10001)
    os.chmod("/logs", 0o700)
    for logfile in Path("/logs").glob("access*"):
        if logfile.is_file() and not logfile.is_symlink():
            os.chown(logfile, 10001, 10001)
            os.chmod(logfile, 0o600)
    subprocess.run(
        [str(target / ".venv/bin/python"), "-m", "tools.hostinger.runtime", "init"],
        cwd=target,
        env={**os.environ, "PYTHONPATH": str(target / "src")},
        check=True,
    )
    print(f"Capsule ready: {expected}", flush=True)


if __name__ == "__main__":
    main()
