"""Deterministic native Caddy fixtures and honest, offline local-baseline evaluation."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import random
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from bouncer.contracts import IpIntel
from bouncer.eval.evaluate import wilson_upper
from bouncer.eval.run import network_signals
from bouncer.ingest import simrun
from bouncer.ingest.sample import parse_access_records
from bouncer.ingest.simrun import IngestStats
from bouncer.ingest.worker import stable_id
from bouncer.network import find_campaigns
from bouncer.session import score
from bouncer.session.features import compute_features
from tools.datasets.registry import checksum

PARTITIONS = ("fit", "calibration", "candidate_validation", "reserved")
REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION = "native-synthetic-v1"
PROFILES = (
    "cached_rapid_browser",
    "assetless_rapid_browser",
    "privacy_headers_missing",
    "legitimate_automation",
    "ordinary_login_retries",
    "shared_nat",
    "shared_nat",
    "shared_nat",
    "scanner",
    "distributed_authentication",
    "distributed_authentication",
    "distributed_authentication",
    "distributed_authentication",
    "scraper_ambiguous",
)


def fixture_signing_key(seed: int) -> str:
    """Public, reproducible FIXTURE key. Never use as a production simulator secret."""
    return hashlib.sha256(f"bounceri-public-native-fixture-v1:{seed}".encode()).hexdigest()


def outside_repository(path: Path) -> Path:
    target = path.resolve()
    if target.is_relative_to(REPO_ROOT):
        raise ValueError("generated artifacts must stay outside the repository")
    return target


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )


def write_lines(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _actor(profile: str, index: int, run_index: int, seed: int, rng: random.Random):
    suffix = run_index * 100 + index + seed * 10000
    ua = f"Mozilla/5.0 Chrome/131.0.{suffix}.0 Safari/537.36"
    address = int(ipaddress.IPv6Address("2001:db8::")) + (seed << 64) + (run_index << 16)
    ip = str(ipaddress.IPv6Address(address + (100 if profile == "shared_nat" else index + 1)))
    headers = {
        "Accept": ["text/html"],
        "Accept-Language": ["en"],
        "Sec-Fetch-Mode": ["navigate"],
        "Sec-Fetch-Dest": ["document"],
    }
    traffic_truth, automation, maliciousness = "human", "human_like", "benign"
    steps = []
    if profile in {"cached_rapid_browser", "assetless_rapid_browser", "privacy_headers_missing"}:
        count = 16 if profile == "cached_rapid_browser" else 8
        steps = [
            (i * (0.08 + rng.random() * 0.04), "GET", f"/products/{i % 6 + 1}", 200, None)
            for i in range(count)
        ]
        if profile == "privacy_headers_missing":
            headers = {}
    elif profile == "legitimate_automation":
        ua = "ExampleMonitor/1.0"
        steps = [(i * 5.0, "GET", "/products", 200, None) for i in range(8)]
        traffic_truth, automation = None, "automated"
    elif profile == "ordinary_login_retries":
        steps = [
            (0.0, "GET", "/login", 200, None),
            (3.0, "POST", "/login", 401, f"user-{suffix}"),
            (9.0, "POST", "/login", 401, f"user-{suffix}"),
            (16.0, "POST", "/login", 200, f"user-{suffix}"),
        ]
    elif profile == "shared_nat":
        steps = [
            (i * (3 + rng.random() * 3), "GET", path, 200, None)
            for i, path in enumerate(("/", "/products", "/static/app.css", "/about"))
        ]
    elif profile == "scanner":
        ua = "curl/8.5.0"
        steps = [
            (i * 0.2, "GET", path, 404, None)
            for i, path in enumerate(
                ("/.env", "/.git/config", "/wp-login.php", "/xmlrpc.php", "/backup.sql")
            )
        ]
        traffic_truth, automation, maliciousness = "bad_bot", "automated", "hostile_probe_fixture"
    elif profile == "distributed_authentication":
        steps = [
            (i * 4.0 + index * 0.1, "POST", "/login", 401, f"test-target-{seed}-{run_index}")
            for i in range(3)
        ]
        traffic_truth, automation, maliciousness = "bad_bot", "automated", "hostile_auth_fixture"
    elif profile == "scraper_ambiguous":
        steps = [(i * 0.1, "GET", f"/products/{i % 6 + 1}", 200, None) for i in range(16)]
        traffic_truth, automation, maliciousness = None, "automated", "unknown"
    return ip, ua, headers, steps, traffic_truth, automation, maliciousness


def generate_bundle(output: Path, *, seed=7, runs_per_partition=2) -> Path:
    if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
        raise ValueError("seed must be an integer in 0..2**31-1")
    if type(runs_per_partition) is not int or not 1 <= runs_per_partition <= 100:
        raise ValueError("runs_per_partition must be in 1..100")
    output = outside_repository(Path(output))
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty; existing evidence is never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    records, actors, runs = [], {}, []
    for partition_index, partition in enumerate(PARTITIONS):
        for repetition in range(runs_per_partition):
            run_index = partition_index * runs_per_partition + repetition
            run_id = f"native-{seed}-run-{run_index}"
            rng = random.Random(f"{seed}:{run_id}")
            runs.append({"run_id": run_id, "partition": partition, "generator_seed": seed})
            for index, profile in enumerate(PROFILES):
                ip, ua, headers, steps, truth, automation, maliciousness = _actor(
                    profile, index, run_index, seed, rng
                )
                campaign = f"{run_id}-auth" if profile == "distributed_authentication" else None
                actor_id = f"{run_id}-actor-{index}"
                actors[(ip, ua)] = {
                    "actor_id": actor_id,
                    "run_id": run_id,
                    "partition": partition,
                    "campaign_group": campaign,
                    "source_identity": hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest(),
                    "client_group": hashlib.sha256(ip.encode()).hexdigest(),
                    "profile": profile,
                    "traffic_truth": truth,
                    "automation_truth": automation,
                    "maliciousness_truth": maliciousness,
                    "label_source": "generator_reference_intent",
                    "synthetic": True,
                    "dns_verified": None,
                }
                marker = f"{run_id}:{profile}:{campaign or '-'}"
                signed = {
                    **headers,
                    "User-Agent": [ua],
                    "X-Sim-Run": [marker],
                    "X-Sim-Sig": [simrun.sign(marker, fixture_signing_key(seed))],
                }
                for at, method, path, status, username in steps:
                    records.append(
                        {
                            "ts": 1767225600.0 + run_index * 3600 + at,
                            "request": {
                                "remote_ip": ip,
                                "client_ip": ip,
                                "method": method,
                                "uri": path,
                                "headers": signed,
                            },
                            "status": status,
                            "size": 100,
                            "resp_headers": {"X-Login-User": [username]} if username else {},
                        }
                    )
    records.sort(key=lambda record: (record["ts"], record["request"]["client_ip"]))
    sessions, labels = parse_access_records(records, secret=fixture_signing_key(seed))
    if len(labels) != len(actors) or len(sessions) != len(actors):
        raise ValueError("generated identities unexpectedly collided in current session parser")
    truth_rows, feature_rows = [], []
    for session in sessions:
        sid = stable_id(session)
        truth_rows.append({"session_id": sid, **actors[(session.ip, session.user_agent)]})
        feature_rows.append({"session_id": sid, "features": asdict(compute_features(session))})
    write_lines(output / "access.jsonl", records)
    write_lines(output / "truth.jsonl", truth_rows)
    write_lines(output / "features.jsonl", feature_rows)
    code_paths = (
        "tools/datasets/native.py",
        "src/bouncer/contracts.py",
        "src/bouncer/ingest/sample.py",
        "src/bouncer/ingest/simrun.py",
        "src/bouncer/session/features.py",
        "src/bouncer/session/rules.py",
        "src/bouncer/session/score.py",
        "src/bouncer/network/campaigns.py",
    )
    manifest = {
        "schema_version": "bounceri-dataset-v1",
        "dataset_id": f"native-{seed}",
        "version": VERSION,
        "source_url": "https://github.com/Murtsi/Bounceri",
        "source_unit": "whole_generated_run",
        "synthetic": True,
        "seed": seed,
        "label_source": "generator_reference_intent_not_model_predictions",
        "license": {
            "id": "MIT",
            "use": "Offline development and synthetic evaluation.",
            "redistribution": "Retain the repository MIT copyright and license notice.",
        },
        "partitions": list(PARTITIONS),
        "runs": runs,
        "n_sessions": len(sessions),
        "reserved_is_genuinely_hidden": False,
        "signing_key_kind": "public_reproducible_fixture_key_never_production",
        "real_human_evidence": "unavailable",
        "genuinely_hidden_attack": "unavailable",
        "files": {
            name: checksum(output / name)
            for name in ("access.jsonl", "truth.jsonl", "features.jsonl")
        },
        "code_sha256": {name: checksum(REPO_ROOT / name)["sha256"] for name in code_paths},
    }
    write_json(output / "manifest.json", manifest)
    verify_bundle(output / "manifest.json")
    return output / "manifest.json"


def verify_bundle(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"source_url", "version", "source_unit", "label_source", "license", "files", "runs"}
    if manifest.get("schema_version") != "bounceri-dataset-v1" or not required <= manifest.keys():
        raise ValueError("missing dataset provenance manifest")
    if (
        manifest.get("synthetic") is not True
        or manifest.get("reserved_is_genuinely_hidden") is not False
        or not {"id", "use", "redistribution"} <= manifest["license"].keys()
    ):
        raise ValueError("synthetic status and use/redistribution terms must be explicit")
    for name in ("access.jsonl", "truth.jsonl", "features.jsonl"):
        path = (manifest_path.parent / name).resolve()
        if not path.is_relative_to(manifest_path.parent) or checksum(path) != manifest["files"].get(
            name
        ):
            raise ValueError(f"checksum mismatch: {name}")
    records = read_lines(manifest_path.parent / "access.jsonl")
    stats = IngestStats()
    sessions, labels = parse_access_records(
        records, secret=fixture_signing_key(manifest["seed"]), stats=stats
    )
    if stats.unsigned_markers or stats.invalid_markers or stats.conflicting_sessions:
        raise ValueError("signed marker validation failed")
    truth = read_lines(manifest_path.parent / "truth.jsonl")
    by_id = {row["session_id"]: row for row in truth}
    if len(by_id) != len(truth) or set(by_id) != {stable_id(session) for session in sessions}:
        raise ValueError("missing or duplicate reference truth")
    if len(labels) != len(sessions) or manifest.get("n_sessions") != len(sessions):
        raise ValueError("missing current-parser labels or session truth")
    expected_run = {run["run_id"]: run["partition"] for run in manifest["runs"]}
    groups = {
        field: {}
        for field in ("run_id", "campaign_group", "actor_id", "source_identity", "client_group")
    }
    for row in truth:
        partition = row["partition"]
        if partition not in PARTITIONS or expected_run.get(row["run_id"]) != partition:
            raise ValueError("run partition mismatch")
        for field, index in groups.items():
            value = row.get(field)
            if value is not None and index.setdefault(value, partition) != partition:
                raise ValueError(f"{field} group crosses partitions")
    labels_by_id = {label.session_id: label for label in labels}
    for session in sessions:
        row = by_id[stable_id(session)]
        if labels_by_id[session.id].run_id != row["run_id"]:
            raise ValueError("truth run differs from signed source run")
        if (
            row["source_identity"]
            != hashlib.sha256(f"{session.ip}|{session.user_agent}".encode()).hexdigest()
        ):
            raise ValueError("truth source identity mismatch")
        if row["client_group"] != hashlib.sha256(session.ip.encode()).hexdigest():
            raise ValueError("truth client group differs from parsed source")
    feature_rows = read_lines(manifest_path.parent / "features.jsonl")
    expected_features = {
        stable_id(session): asdict(compute_features(session)) for session in sessions
    }
    actual_features = {row["session_id"]: row["features"] for row in feature_rows}
    if len(feature_rows) != len(sessions) or expected_features != actual_features:
        raise ValueError("features do not match current repository feature contract")
    return manifest


def _metric(k: int, n: int) -> dict:
    upper = wilson_upper(k, n)
    lower = 1 - wilson_upper(n - k, n) if n else None
    return {
        "numerator": k,
        "denominator": n,
        "value": k / n if n else None,
        "ci95_wilson": [max(0.0, lower) if lower is not None else None, upper],
    }


def _metrics(rows) -> dict:
    eligible = [row for row in rows if row["truth"] in {"human", "bad_bot"}]
    positives = [row for row in eligible if row["prediction"] == "bad_bot"]
    humans = [row for row in eligible if row["truth"] == "human"]
    return {
        "n_sessions": len(rows),
        "known_truth_sessions": len(eligible),
        "unknown_truth_sessions": len(rows) - len(eligible),
        "bad_bot_precision": _metric(
            sum(row["truth"] == "bad_bot" for row in positives), len(positives)
        ),
        "human_fpr": _metric(
            sum(row["prediction"] in {"bad_bot", "good_bot"} for row in humans), len(humans)
        ),
        "uncertain_share": _metric(
            sum(row["prediction"] == "uncertain" for row in rows), len(rows)
        ),
        "unknown_intent_flagged_bad_bot": sum(
            row["truth"] is None and row["prediction"] == "bad_bot" for row in rows
        ),
    }


def evaluate_bundle(manifest_path: Path, *, partitions=None, allow_reserved=False) -> dict:
    manifest = verify_bundle(manifest_path)
    partitions = list(partitions or ["candidate_validation"])
    if not set(partitions) <= set(PARTITIONS):
        raise ValueError("unknown evaluation partition")
    if "reserved" in partitions and not allow_reserved:
        raise ValueError(
            "reserved requires explicit --allow-reserved; it is not a genuinely hidden attack"
        )
    root = Path(manifest_path).resolve().parent
    sessions, _ = parse_access_records(
        read_lines(root / "access.jsonl"), secret=fixture_signing_key(manifest["seed"])
    )
    truth = {row["session_id"]: row for row in read_lines(root / "truth.jsonl")}
    grouped = defaultdict(list)
    for session in sessions:
        reference = truth[stable_id(session)]
        if reference["partition"] in partitions:
            grouped[reference["run_id"]].append(session)
    results = []
    for members in grouped.values():
        _, campaigns = network_signals(members, None, find_campaigns)
        for session in members:
            reference = truth[stable_id(session)]
            verdict = score(
                session, IpIntel(), campaigns.get(session.id), traps=frozenset(), model=None
            )
            results.append(
                {
                    "session_id": stable_id(session),
                    "run_id": reference["run_id"],
                    "profile": reference["profile"],
                    "truth": reference["traffic_truth"],
                    "prediction": verdict.label,
                    "model_version": verdict.model_version,
                }
            )
    by_profile = {
        profile: _metrics([row for row in results if row["profile"] == profile])
        for profile in sorted({row["profile"] for row in results})
    }
    by_run = {
        run: _metrics([row for row in results if row["run_id"] == run])
        for run in sorted({row["run_id"] for row in results})
    }
    return {
        "schema_version": "bounceri-offline-baseline-v1",
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": checksum(Path(manifest_path))["sha256"],
        "synthetic": True,
        "task": "scenario_traffic_classification",
        "partitions": partitions,
        "model_calls": 0,
        "baseline": "current rules + current network campaigns; no model file, traps or DNS",
        "independent_real_humans": "unavailable",
        "genuinely_hidden_attack": "unavailable",
        "overall": _metrics(results),
        "by_profile": by_profile,
        "by_run": by_run,
        "predictions": results,
        "limitations": [
            "Generated reference intent is not independent human or maliciousness ground truth.",
            "Historical robot labels are not used or mapped to missing native features.",
            "Precision uses known synthetic truth only; unknown intent is excluded.",
            "Wilson intervals are descriptive and do not correct within-run dependence.",
            "Reserved uses known templates and a separate run; it is not independently hidden.",
            "Familiar probes test pipeline behavior, not novel-attack generalization.",
            "Legitimate automation has no verified crawler identity; no fake DNS is injected.",
        ],
    }
