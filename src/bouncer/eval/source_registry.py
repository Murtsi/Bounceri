"""Small offline dataset registry; never downloads or reinterprets historical labels."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def checksum(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def load_registry(path: Path) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("schema_version") != "bounceri-source-registry-v1":
        raise ValueError("unsupported registry version")
    for item in registry.get("datasets", []):
        required = {
            "id",
            "version",
            "source_url",
            "sha256",
            "source_unit",
            "label_source",
            "task",
            "synthetic",
            "license",
        }
        if not required <= item.keys() or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
            raise ValueError("dataset provenance or checksum is missing")
        if not str(item["source_url"]).startswith("https://") or not item["label_source"]:
            raise ValueError("source URL and annotation source are required")
        if not {"id", "use", "redistribution"} <= item["license"].keys():
            raise ValueError("dataset use and redistribution terms are required")
        if item["task"] == "historical_robot_label" and (
            item.get("maliciousness_labels") is not False
            or item.get("native_feature_mapping") != "not_available"
        ):
            raise ValueError("historical robot labels cannot become maliciousness/native labels")
    return registry
