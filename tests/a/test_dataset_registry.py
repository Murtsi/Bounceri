"""Native data provenance, grouped split and current-parser compatibility contracts."""

import hashlib
import json
from pathlib import Path

import pytest

from tools.datasets.native import evaluate_bundle, generate_bundle, verify_bundle
from tools.datasets.registry import load_registry


def rewrite_artifact(manifest_path, filename, rows):
    path = manifest_path.parent / filename
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][filename] = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_deterministic_native_bundle_uses_current_parser_and_separate_reference_truth(tmp_path):
    first = generate_bundle(tmp_path / "first", seed=17, runs_per_partition=1)
    second = generate_bundle(tmp_path / "second", seed=17, runs_per_partition=1)
    manifest = verify_bundle(first)
    assert manifest["files"] == verify_bundle(second)["files"]
    assert manifest["schema_version"] == "bounceri-dataset-v1"
    assert manifest["synthetic"] is True
    assert manifest["reserved_is_genuinely_hidden"] is False
    assert set(manifest["partitions"]) == {"fit", "calibration", "candidate_validation", "reserved"}
    records = [
        json.loads(line) for line in (first.parent / "access.jsonl").read_text().splitlines()
    ]
    from bouncer.ingest.sample import parse_access_records
    from tools.datasets.native import fixture_signing_key

    sessions, labels = parse_access_records(records, secret=fixture_signing_key(17))
    assert len(labels) == len(sessions) == manifest["n_sessions"]
    assert all(
        "x-sim-run" not in r.headers and "x-sim-sig" not in r.headers
        for session in sessions
        for r in session.requests
    )
    features = [
        json.loads(line) for line in (first.parent / "features.jsonl").read_text().splitlines()
    ]
    assert all(
        not {"label", "truth", "profile", "run_id", "ip", "username"} & row["features"].keys()
        for row in features
    )
    truth = [json.loads(line) for line in (first.parent / "truth.jsonl").read_text().splitlines()]
    assert any(
        row["profile"] == "legitimate_automation" and row["traffic_truth"] is None for row in truth
    )
    assert any(
        row["profile"] == "scraper_ambiguous" and row["maliciousness_truth"] == "unknown"
        for row in truth
    )
    assert not any(row.get("dns_verified") is True for row in truth)


def test_checksum_tampering_is_rejected(tmp_path):
    path = generate_bundle(tmp_path / "data", seed=2, runs_per_partition=1)
    with (path.parent / "access.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{}\n")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(path)


def test_whole_run_and_campaign_overlap_is_rejected_even_after_rehash(tmp_path):
    path = generate_bundle(tmp_path / "data", seed=3, runs_per_partition=1)
    rows = [json.loads(line) for line in (path.parent / "truth.jsonl").read_text().splitlines()]
    rows[0]["partition"] = "reserved" if rows[0]["partition"] != "reserved" else "fit"
    rewrite_artifact(path, "truth.jsonl", rows)
    with pytest.raises(ValueError, match="group|partition"):
        verify_bundle(path)


def test_missing_reference_truth_is_rejected_even_after_rehash(tmp_path):
    path = generate_bundle(tmp_path / "data", seed=5, runs_per_partition=1)
    rows = [json.loads(line) for line in (path.parent / "truth.jsonl").read_text().splitlines()]
    rewrite_artifact(path, "truth.jsonl", rows[1:])
    with pytest.raises(ValueError, match="truth"):
        verify_bundle(path)


def test_baseline_report_has_denominators_intervals_and_never_reads_reserved_by_default(tmp_path):
    path = generate_bundle(tmp_path / "data", seed=7, runs_per_partition=1)
    protected = Path("models/metrics.json").read_bytes()
    report = evaluate_bundle(path)
    assert report["partitions"] == ["candidate_validation"]
    assert report["synthetic"] is True and report["model_calls"] == 0
    assert report["independent_real_humans"] == report["genuinely_hidden_attack"] == "unavailable"
    for metric in ("bad_bot_precision", "human_fpr", "uncertain_share"):
        value = report["overall"][metric]
        assert isinstance(value["denominator"], int)
        assert "ci95_wilson" in value
    assert report["overall"]["unknown_truth_sessions"] > 0
    assert {
        "cached_rapid_browser",
        "assetless_rapid_browser",
        "privacy_headers_missing",
        "legitimate_automation",
        "ordinary_login_retries",
        "shared_nat",
        "scanner",
        "distributed_authentication",
        "scraper_ambiguous",
    } <= report["by_profile"].keys()
    with pytest.raises(ValueError, match="reserved"):
        evaluate_bundle(path, partitions=["reserved"])
    assert Path("models/metrics.json").read_bytes() == protected


def test_registry_terms_and_historical_task_boundaries_are_explicit():
    registry = load_registry(Path("tools/datasets/registry.example.json"))
    historical = next(
        item for item in registry["datasets"] if item["id"] == "zenodo-3477932-simple"
    )
    assert historical["task"] == "historical_robot_label"
    assert historical["native_feature_mapping"] == "not_available"
    assert historical["license"]["id"] == "CC-BY-4.0"
    assert len(historical["sha256"]) == 64
    assert historical["maliciousness_labels"] is False


def test_campaign_group_cannot_cross_partitions_after_rehash(tmp_path):
    path = generate_bundle(tmp_path / "data", seed=11, runs_per_partition=1)
    rows = [json.loads(line) for line in (path.parent / "truth.jsonl").read_text().splitlines()]
    fit = next(row for row in rows if row["partition"] == "fit" and row["campaign_group"])
    reserved = next(row for row in rows if row["partition"] == "reserved" and row["campaign_group"])
    reserved["campaign_group"] = fit["campaign_group"]
    rewrite_artifact(path, "truth.jsonl", rows)
    with pytest.raises(ValueError, match="campaign_group"):
        verify_bundle(path)


def test_client_group_fingerprint_must_match_actual_parsed_source(tmp_path):
    path = generate_bundle(tmp_path / "data", seed=13, runs_per_partition=1)
    rows = [json.loads(line) for line in (path.parent / "truth.jsonl").read_text().splitlines()]
    rows[0]["client_group"] = "f" * 64
    rewrite_artifact(path, "truth.jsonl", rows)
    with pytest.raises(ValueError, match="client group"):
        verify_bundle(path)


def test_cli_is_offline_and_protects_repository_and_existing_outputs(tmp_path, monkeypatch, capsys):
    import socket

    from tools.datasets.__main__ import main

    def forbidden(*args, **kwargs):
        pytest.fail("dataset commands must not use the network")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    output = tmp_path / "data"
    assert main(["generate", "--output", str(output), "--runs-per-partition", "1"]) == 0
    capsys.readouterr()
    assert main(["verify", "--manifest", str(output / "manifest.json")]) == 0
    report = tmp_path / "report.json"
    assert (
        main(["evaluate", "--manifest", str(output / "manifest.json"), "--output", str(report)])
        == 0
    )
    assert json.loads(report.read_text())["model_calls"] == 0
    with pytest.raises(SystemExit) as exit_code:
        main(["generate", "--output", str(output)])
    assert exit_code.value.code == 2
    with pytest.raises(ValueError, match="outside"):
        generate_bundle(Path("models/forbidden-generated-output"))


def test_registry_missing_redistribution_terms_is_rejected(tmp_path):
    source = json.loads(Path("tools/datasets/registry.example.json").read_text())
    del source["datasets"][0]["license"]["redistribution"]
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="redistribution"):
        load_registry(path)
