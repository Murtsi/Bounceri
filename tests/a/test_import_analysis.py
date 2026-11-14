"""Offline imports use the native pipeline behind a bounded process boundary."""

import copy
import importlib
import importlib.util
import io
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


def module():
    assert importlib.util.find_spec("bouncer.ingest.import_analysis") is not None
    return importlib.import_module("bouncer.ingest.import_analysis")


def record(ip="198.51.100.1", path="/", ts=1):
    return {"ts": ts, "request": {"client_ip": ip, "method": "GET", "uri": path,
            "headers": {"User-Agent": ["Googlebot/2.1"]}}, "status": 200, "size": 1}


def test_two_sessions_use_native_rules_without_dns_or_labels():
    analyzer = module()
    records = [record(path="/.env"), record(path="/wp-login.php", ts=2),
               record("198.51.100.2")]
    original = copy.deepcopy(records)
    with patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")):
        snapshot = analyzer.analyze_records(records, False)
    assert records == original
    assert len(snapshot["sessions"]) == 2
    assert snapshot["synthetic"] is False
    assert snapshot["labels"] == []
    assert snapshot["ip_evidence"] == {}
    assert snapshot["ingest"]["records"] == 3
    assert snapshot["ingest"]["discarded_by_retention"] == 0
    assert "vuln_paths" in [v["rule_id"] for v in snapshot["verdicts"].values()]
    assert all(v["verified_bot"] is None for v in snapshot["verdicts"].values())
    assert all(v["asn_type"] == "unknown" for v in snapshot["verdicts"].values())
    assert "worker_resume_state" not in snapshot
    assert "session_label_state" not in snapshot
    assert snapshot["source"] == "import:caddy"


def test_imported_site_does_not_inherit_local_honey_traps():
    analyzer = module()
    with (patch("bouncer.session.rules.load_traps", return_value=frozenset({"/ordinary-page"})),
          patch("socket.getaddrinfo", side_effect=AssertionError("no DNS"))):
        result = analyzer.analyze_records([record(path="/ordinary-page")], False)
    assert result["labels"] == []
    assert result["ip_evidence"] == {}
    assert all(v["rule_id"] != "trap" for v in result["verdicts"].values())
    assert all(o["trap_hits"] == 0 for o in result["rule_observations"].values())
    assert all("trap" not in o["rule_ids"] for o in result["rule_observations"].values())


def test_import_scoring_explicitly_disables_the_learned_model():
    analyzer = module()
    from bouncer.ingest import worker
    with patch.object(worker, "score", wraps=worker.score) as score:
        analyzer.analyze_records([record()], False)
    assert score.call_args.kwargs.get("model", "default") is None


@pytest.mark.parametrize("unavailable, omitted", [
    (["headers"], {"header_inconsistency_share"}),
    (["user_agent"], {"ua_is_tool", "ua_claims_bot", "header_inconsistency_share"}),
    (["content_type"], {"static_share", "html_share", "header_inconsistency_share"}),
])
def test_unavailable_optional_fields_are_not_reported_as_observed_features(unavailable, omitted):
    analyzer = module()
    raw = record()
    raw["request"]["headers"] = {"User-Agent": ["Mozilla/5.0 Chrome/140.0.0.0"]}
    raw["_unavailable_fields"] = unavailable
    result = analyzer.analyze_records([raw], False)
    for observation in result["rule_observations"].values():
        assert not omitted & observation["features"].keys()
        assert "requests_per_min" in observation["features"]
    assert "_unavailable_fields" not in json.dumps(result)
    verdict = next(iter(result["verdicts"].values()))
    assert verdict["label"] == "uncertain"
    assert verdict["reasons"] == [analyzer.INCOMPLETE_NOTICE]
    assert verdict["explanation"] == analyzer.INCOMPLETE_NOTICE


def test_unavailable_mask_is_applied_to_whole_session_but_not_other_sessions():
    analyzer = module()
    records = [record(), record(ts=2), record(ip="198.51.100.2")]
    records[1]["_unavailable_fields"] = ["headers"]
    result = analyzer.analyze_records(records, False)
    for session in result["sessions"]:
        features = result["rule_observations"][session["id"]]["features"]
        assert ("header_inconsistency_share" in features) == (session["ip"] == "198.51.100.2")


def test_incomplete_logging_keeps_only_deterministic_rule_reasons():
    analyzer = module()
    records = [record(path="/.env"), record(path="/wp-login.php", ts=2)]
    for raw in records:
        raw["_unavailable_fields"] = ["user_agent", "headers", "content_type"]
        raw["request"]["headers"] = {}
    result = analyzer.analyze_records(records, False)
    verdict = next(iter(result["verdicts"].values()))
    assert verdict["rule_id"] == "vuln_paths"
    assert len(verdict["reasons"]) == 1
    assert verdict["reasons"][0].startswith("Probed 2 known vulnerability paths")
    assert verdict["explanation"] == verdict["reasons"][0]
    assert "command-line" not in json.dumps(result)


@pytest.mark.parametrize("mask", [None, "headers", ["provider_key"], ["headers", "headers"], [1]])
def test_unavailable_mask_is_a_fixed_unique_enum_list(mask):
    analyzer = module()
    raw = record()
    raw["_unavailable_fields"] = mask
    def forbidden(*args):
        pytest.fail("invalid semantic mask must not start a child")
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_import([raw], False, runner=forbidden)


@pytest.mark.parametrize("field", ["headers", "user_agent"])
def test_behavior_campaign_requires_observed_headers_and_ua_for_every_member(field):
    analyzer = module()
    records = [record(f"198.51.100.{i}") for i in range(1, 4)]
    known = analyzer.analyze_records(records, False)
    assert any(c["kind"] == "behavior_cluster" for c in known["campaigns"])
    records[1]["_unavailable_fields"] = [field]
    incomplete = analyzer.analyze_records(records, False)
    assert not any(c["kind"] == "behavior_cluster" for c in incomplete["campaigns"])
    assert all(v["campaign_id"] is None for v in incomplete["verdicts"].values())
    assert "same header fingerprint" not in json.dumps(incomplete)


def test_known_login_targets_still_form_campaigns_without_observed_browser_headers():
    analyzer = module()
    records = [record(f"198.51.100.{i}", "/login") for i in range(1, 4)]
    for raw in records:
        raw["request"]["method"] = "POST"
        raw["status"] = 401
        raw["resp_headers"] = {"X-Login-User": ["hmac-shared-user"]}
        raw["_unavailable_fields"] = ["headers", "content_type"]
    result = analyzer.analyze_records(records, False)
    assert any(c["kind"] == "credential_stuffing" for c in result["campaigns"])
    assert not any(c["kind"] == "behavior_cluster" for c in result["campaigns"])
    assert all(v["rule_id"] == "login_attack_campaign" for v in result["verdicts"].values())
    assert all(len(v["reasons"]) == 1 for v in result["verdicts"].values())


def test_case_variant_simulator_truth_and_private_state_are_discarded():
    analyzer = module()
    raw = record()
    raw.update(labels=[{"sim_class": "human"}], _session_id="attacker")
    raw["request"]["headers"].update({"x-SIM-Run": ["evil:human:campaign"],
                                        "X-sim-SIG": ["unsigned"]})
    result = analyzer.analyze_records([raw], True)
    assert result["labels"] == []
    assert "evil" not in json.dumps(result)
    assert "x-sim" not in json.dumps(result).lower()
    assert result["sessions"][0]["id"] != "attacker"


def test_local_credential_campaign_survives_import():
    analyzer = module()
    records = [record(f"198.51.100.{i}", "/login") for i in range(1, 4)]
    for raw in records:
        raw["request"]["method"] = "POST"
        raw["status"] = 401
        raw["resp_headers"] = {"X-Login-User": ["hmac-shared-user"]}
    result = analyzer.analyze_records(records, True)
    assert any(c["kind"] == "credential_stuffing" for c in result["campaigns"])
    assert all(v["rule_id"] == "login_attack_campaign" for v in result["verdicts"].values())


def test_temporary_worker_files_are_removed():
    analyzer = module()
    from bouncer.ingest.worker import Worker
    original = Worker.cycle
    paths = []
    def cycle(worker):
        paths.extend([worker.store, worker.tail.path])
        return original(worker)
    with patch.object(Worker, "cycle", cycle):
        analyzer.analyze_records([record()], True)
    assert paths
    assert all(not path.parent.exists() for path in paths)
    assert all(not path.is_relative_to(Path.cwd()) for path in paths)


def test_real_child_roundtrip_is_bounded_and_offline(monkeypatch):
    analyzer = module()
    monkeypatch.setenv("SIM_RUN_SECRET", "must-not-be-used")
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", "must-not-be-used")
    result = analyzer.analyze_import([record()], False)
    assert len(result["sessions"]) == 1
    assert result["labels"] == []
    assert result["synthetic"] is False


def test_parser_availability_survives_real_child_roundtrip():
    analyzer = module()
    from bouncer.ingest.imports import parse_import
    row = {"ts": "2026-11-14T12:00:00Z", "ip": "198.51.100.1", "method": "GET",
           "path": "/", "status": 200, "user_agent": "Mozilla/5.0 Chrome/140.0.0.0"}
    parsed = parse_import(json.dumps(row).encode(), "normalized_jsonl", pseudonym_key=b"test")
    result = analyzer.analyze_import(parsed.records, False)
    observation = next(iter(result["rule_observations"].values()))
    assert "header_inconsistency_share" not in observation["features"]
    assert "static_share" not in observation["features"]
    assert "html_share" not in observation["features"]
    assert "ua_is_tool" in observation["features"]
    assert next(iter(result["verdicts"].values()))["reasons"] == [analyzer.INCOMPLETE_NOTICE]
    assert "_unavailable_fields" not in json.dumps(result)


def test_native_integer_feature_counts_survive_child_and_case_adapter():
    analyzer = module()
    from bouncer.investigations.evidence import traffic_packet
    result = analyzer.analyze_import([record(path="/.env"),
                                      record(path="/wp-login.php", ts=2)], False)
    observation = next(iter(result["rule_observations"].values()))
    assert type(observation["features"]["peak_requests_per_min"]) is int
    assert type(observation["features"]["vuln_path_hits"]) is int
    assert type(observation["features"]["duration_s"]) is float
    assert type(observation["features"]["ua_is_tool"]) is bool
    packet = traffic_packet(result)
    summary = next(item for item in packet["evidence"] if item["kind"] == "session_summary")
    features = summary["data"]["rule_observations"]["features"]
    assert features["peak_requests_per_min"] == 2
    assert features["vuln_path_hits"] == 2
    assert type(features["peak_requests_per_min"]) is int
    assert type(features["vuln_path_hits"]) is int


def test_safe_availability_metadata_is_the_per_session_union():
    analyzer = module()
    records = [record(), record(ts=2), record(ip="198.51.100.2")]
    records[0]["_unavailable_fields"] = ["headers", "username"]
    records[1]["_unavailable_fields"] = ["content_type", "headers"]
    result = analyzer.analyze_import(records, False)
    for session in result["sessions"]:
        expected = (["content_type", "headers", "username"]
                    if session["ip"] == "198.51.100.1" else [])
        assert result["unavailable_fields"].get(session["id"], []) == expected
        assert all("_unavailable_fields" not in request for request in session["requests"])


@pytest.mark.parametrize("change", ["drop", "add", "unknown-session", "duplicate", "invalid-enum",
                                    "string", "missing-map"])
def test_parent_rejects_corrupted_child_availability_metadata(change):
    analyzer = module()
    raw = record()
    raw["_unavailable_fields"] = ["username"]
    snapshot = analyzer.analyze_records([raw], False)
    session_id = snapshot["sessions"][0]["id"]
    masks = {session_id: ["username"]}
    if change == "drop":
        masks = {}
    elif change == "add":
        masks[session_id].append("headers")
    elif change == "unknown-session":
        masks["not-a-session"] = []
    elif change == "duplicate":
        masks[session_id].append("username")
    elif change == "invalid-enum":
        masks[session_id] = ["private-token"]
    elif change == "string":
        masks[session_id] = "username"
    snapshot["unavailable_fields"] = masks
    if change == "missing-map":
        snapshot.pop("unavailable_fields")
    payload = json.dumps(snapshot).encode()
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_import([raw], False, runner=lambda data, timeout: payload)


@pytest.mark.parametrize("count", [2.0, True, "2"])
def test_parent_requires_native_integers_for_count_features(count):
    analyzer = module()
    snapshot = analyzer.analyze_records([record()], False)
    observation = next(iter(snapshot["rule_observations"].values()))
    observation["features"]["peak_requests_per_min"] = count
    payload = json.dumps(snapshot).encode()
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_import([record()], False, runner=lambda data, timeout: payload)


def test_parent_accepts_optional_empty_availability_entries_for_known_sessions():
    analyzer = module()
    snapshot = analyzer.analyze_records([record()], False)
    session_id = snapshot["sessions"][0]["id"]
    for masks in [{}, {session_id: []}]:
        snapshot["unavailable_fields"] = masks
        payload = json.dumps(snapshot).encode()
        result = analyzer.analyze_import([record()], False,
                                         runner=lambda data, timeout, payload=payload: payload)
        assert result["unavailable_fields"] == masks


def test_parent_rejects_availability_moved_between_known_sessions():
    analyzer = module()
    records = [record(), record(ip="198.51.100.2")]
    records[0]["_unavailable_fields"] = ["username"]
    snapshot = analyzer.analyze_records(records, False)
    other = next(s["id"] for s in snapshot["sessions"] if s["ip"] == "198.51.100.2")
    snapshot["unavailable_fields"] = {other: ["username"]}
    payload = json.dumps(snapshot).encode()
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_import(records, False, runner=lambda data, timeout: payload)


@pytest.mark.parametrize("payload", [b"not-json", b"[]", b"{}", b"x" * (8 * 1024**2 + 1)],
                         ids=["invalid-json", "array", "missing-fields", "oversized"])
def test_parent_rejects_invalid_or_oversized_protocol(payload):
    analyzer = module()
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_import([record()], True, runner=lambda data, timeout: payload)


def test_parent_rejects_spoofed_nested_protocol():
    analyzer = module()
    valid = analyzer.analyze_records([record()], True)
    for mutate in [lambda p: p.update(labels=[{"sim_class": "human"}]),
                   lambda p: p["verdicts"][next(iter(p["verdicts"]))].update(verified_bot=True),
                   lambda p: p["sessions"][0].update(unexpected="private"),
                   lambda p: p["ingest"].update(retained_records=0)]:
        packet = copy.deepcopy(valid)
        mutate(packet)
        payload = json.dumps(packet).encode()
        with pytest.raises(analyzer.AnalysisError):
            analyzer.analyze_import([record()], True,
                                    runner=lambda data, timeout, payload=payload: payload)


def test_timeout_and_late_success_are_sanitized():
    analyzer = module()
    def timeout(data, seconds):
        raise subprocess.TimeoutExpired("private secret", seconds)
    with pytest.raises(analyzer.AnalysisError) as error:
        analyzer.analyze_import([record()], True, runner=timeout)
    assert "private secret" not in str(error.value)
    packet = json.dumps(analyzer.analyze_records([record()], True)).encode()
    with (patch.object(analyzer.time, "monotonic", side_effect=[0.0, 5.1]),
          pytest.raises(analyzer.AnalysisError)):
        analyzer.analyze_import([record()], True, runner=lambda data, seconds: packet)


@pytest.mark.parametrize("records, synthetic", [([record()] * 2001, True),
                                               ([record()], "true"), ([], True)])
def test_input_bounds_reject_without_starting_child(records, synthetic):
    analyzer = module()
    def forbidden(*args):
        pytest.fail("invalid input must not start child")
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_import(records, synthetic, runner=forbidden)


def test_runner_charges_startup_and_uses_fixed_module_with_private_environment():
    analyzer = module()
    with patch.object(analyzer.subprocess, "Popen") as popen:
        process = popen.return_value
        process.wait.return_value = 0
        with patch.object(analyzer.time, "monotonic", side_effect=[0.0, .3]):
            analyzer.run_analysis(b"{}", 1)
    args, kwargs = popen.call_args
    assert args[0][1:] == ["-m", "bouncer.ingest.import_analysis"]
    assert kwargs["shell"] is False
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert not any(k.startswith("BOUNCER") or k == "SIM_RUN_SECRET" for k in kwargs["env"])
    assert process.wait.call_args.kwargs["timeout"] == pytest.approx(.6)


def test_runner_timeout_kills_and_bounds_cleanup():
    analyzer = module()
    with patch.object(analyzer.subprocess, "Popen") as popen:
        process = popen.return_value
        process.wait.side_effect = [subprocess.TimeoutExpired("child", 1), 0]
        with pytest.raises(subprocess.TimeoutExpired):
            analyzer.run_analysis(b"{}", 1)
    process.kill.assert_called_once()
    assert 0 <= process.wait.call_args.kwargs["timeout"] <= .1


def test_parent_owns_child_temporary_directory_even_after_timeout():
    analyzer = module()
    roots = []
    with patch.object(analyzer.subprocess, "Popen") as popen:
        process = popen.return_value
        def start(*args, **kwargs):
            root = Path(kwargs["env"]["TMPDIR"])
            roots.append(root)
            (root / "private-worker-state.json").write_text("private", encoding="utf-8")
            return process
        popen.side_effect = start
        process.wait.side_effect = [subprocess.TimeoutExpired("child", 1), 0]
        with pytest.raises(subprocess.TimeoutExpired):
            analyzer.run_analysis(b"{}", 1)
    assert roots and all(not root.exists() for root in roots)


def test_input_byte_cap_and_timeout_cap_never_start_runner():
    analyzer = module()
    raw = record(path="/" + "x" * analyzer.MAX_INPUT_BYTES)
    def forbidden(*args):
        pytest.fail("invalid input must not start child")
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_import([raw], True, runner=forbidden)
    for timeout in [0, 6, float("nan"), True]:
        with pytest.raises(analyzer.AnalysisError):
            analyzer.analyze_import([record()], True, runner=forbidden, timeout_seconds=timeout)


def test_runner_reads_only_output_cap_plus_one():
    analyzer = module()
    with patch.object(analyzer.subprocess, "Popen") as popen:
        process = popen.return_value
        def start(*args, **kwargs):
            kwargs["stdout"].write(b"x" * (analyzer.MAX_OUTPUT_BYTES + 100))
            return process
        popen.side_effect = start
        process.wait.return_value = 0
        payload = analyzer.run_analysis(b"{}", 1)
    assert len(payload) == analyzer.MAX_OUTPUT_BYTES + 1


def test_output_validation_is_charged_to_deadline():
    analyzer = module()
    packet = json.dumps(analyzer.analyze_records([record()], True)).encode()
    with (patch.object(analyzer.time, "monotonic", side_effect=[0.0, 4.99, 5.01]),
          pytest.raises(analyzer.AnalysisError)):
        analyzer.analyze_import([record()], True, runner=lambda data, timeout: packet)


@pytest.mark.parametrize("packet", [b"private malformed input", b"[]", b"{}",
                                    b"x" * (10 * 1024**2 + 1)],
                         ids=["private-error", "array", "missing-fields", "oversized"])
def test_child_rejects_invalid_input_without_stdout_or_stderr(packet, capsys):
    analyzer = module()
    with (patch.object(analyzer.sys, "argv", ["import_analysis"]),
          patch.object(analyzer.sys, "stdin") as stdin):
        stdin.buffer = io.BytesIO(packet)
        assert analyzer.main() != 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
