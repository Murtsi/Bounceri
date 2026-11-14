"""Private imports validate before analysis and never preserve uploaded credentials."""

import json

import pytest

from bouncer.ingest import imports
from bouncer.ingest.sample import parse_access_record

KEY = b"private-test-key"


def row(**changes):
    value = {"ts": "2026-11-14T12:00:00Z", "ip": "2001:0db8::1", "method": "GET",
             "path": "/page?secret=query", "status": 200}
    return value | changes


def parse(*rows, format="normalized_jsonl"):
    data = b"\n".join(json.dumps(value).encode() for value in rows)
    return imports.parse_import(data, format, pseudonym_key=KEY)


def test_imports_produce_canonical_worker_input_and_explicit_unknowns():
    result = parse(row())
    request, marker = parse_access_record(result.records[0], secret=None)
    assert (request.ip, request.path, request.query, request.bytes) == (
        "2001:db8::1", "/page", "", 0)
    assert marker is None
    assert request.username is None and request.content_type is None
    assert result.report["accepted"] == 1 and result.report["rejected"] == 0
    assert result.report["missing_fields"] == {
        "user_agent": 1, "headers": 1, "bytes": 1, "content_type": 1, "username": 1}
    assert result.report["time_range"] == {
        "min": "2026-11-14T12:00:00+00:00", "max": "2026-11-14T12:00:00+00:00"}


def test_credentials_truth_and_bodies_never_reach_worker_or_report():
    sensitive = row(method="POST", path="https://raw-user:raw-pass@example.org/login?token=secret#x",
        username="private-name", bytes=2**40, content_type="text/html",
        headers={"User-Agent": "browser", "Authorization": "Bearer secret", "Cookie": "session=s",
                 "Referer": "https://secret/", "X-Sim-Run": "run:human", "X-Sim-Sig": "signature"},
        body="password=secret", labels={"human": True})
    result = parse(sensitive)
    request, marker = parse_access_record(result.records[0], secret=None)
    assert request.path == "/login" and request.query == "" and request.bytes == 2**40
    assert request.user_agent == "browser" and request.content_type == "text/html"
    assert request.username.startswith("user_") and len(request.username) == 69
    assert marker is None and request.headers == {"user-agent": "browser", "referer": "present"}
    serialized = json.dumps(result.records) + json.dumps(result.report)
    for secret in ("raw-user", "raw-pass", "private-name", "example.org", "Bearer", "session=s",
                   "https://secret", "run:human", "signature", "password=secret"):
        assert secret not in serialized
    assert result.report["unmapped_fields"] == 2
    assert result.report["missing_fields"]["bytes"] == 0
    assert parse(sensitive).records == result.records
    other = imports.parse_import(json.dumps(sensitive).encode(), "normalized_jsonl",
                                 pseudonym_key=b"another-key")
    assert other.records[0]["resp_headers"] != result.records[0]["resp_headers"]


def test_caddy_response_login_target_is_pseudonymized_and_all_truth_dropped():
    source = {"ts": 1794657600, "status": 401, "size": 4,
              "request": {"client_ip": "192.0.2.1", "method": "POST", "uri": "//login?a=1",
                          "headers": {"User-Agent": ["ua"], "X-Sim-Run": ["x:human"]}},
              "resp_headers": {"X-Login-User": ["admin"], "Content-Type": ["text/plain"],
                               "Set-Cookie": ["secret"]}, "label": "human"}
    result = parse(source, format="caddy_jsonl")
    request, marker = parse_access_record(result.records[0], secret=None)
    assert request.path == "//login" and request.username.startswith("user_")
    assert marker is None and "admin" not in json.dumps(result.records)


@pytest.mark.parametrize(("field", "value", "code"), [
    ("ts", "2026-11-14T12:00:00", "invalid_timestamp"),
    ("ts", True, "invalid_timestamp"), ("ts", None, "invalid_timestamp"),
    ("ip", "192.0.2.1:80", "invalid_ip"), ("ip", "fe80::1%eth0", "invalid_ip"),
    ("status", True, "invalid_status"), ("status", "200", "invalid_status"),
    ("status", 600, "invalid_status"), ("status", 99, "invalid_status"),
    ("method", "get", "invalid_method"), ("method", "MAGIC", "invalid_method"),
    ("path", "relative", "invalid_path"), ("path", "ftp://secret/path", "invalid_path"),
    ("path", "/" + "x" * 4096, "invalid_path"),
    ("bytes", -1, "invalid_bytes"), ("bytes", True, "invalid_bytes"),
    ("bytes", 2**63, "invalid_bytes"), ("bytes", 1.0, "invalid_bytes"),
    ("headers", ["secret"], "invalid_headers"),
])
def test_invalid_core_rejects_only_that_row_and_reports_fixed_codes(field, value, code):
    result = parse(row(**{field: value}), row())
    assert len(result.records) == 1
    assert result.report["rejected"] == 1
    assert result.report["errors"] == [{"line": 1, "code": imports.ERROR_CODES[code]}]
    assert result.report["total_lines"] == 2


@pytest.mark.parametrize("field", ["ts", "ip", "method", "path", "status"])
def test_missing_core_is_never_fabricated(field):
    source = row()
    del source[field]
    assert parse(source).report["accepted"] == 0


def test_strict_json_and_utf8_failures_do_not_stop_later_valid_rows():
    bad = [b'\xff', b'{"ts":1,"ts":2}', b'{"ts":NaN}', b'[]', b'null', b'{',
           b'{"ts":1e999}', b'{"a":"\\ud800"}']
    result = imports.parse_import(b"\n".join([*bad, json.dumps(row()).encode()]),
                                 "normalized_jsonl", pseudonym_key=KEY)
    assert result.report["accepted"] == 1 and result.report["rejected"] == len(bad)
    assert all(type(error["code"]) is int for error in result.report["errors"])
    assert "\ufffd" not in json.dumps(result.report)


def test_report_error_positions_are_bounded_without_raw_input():
    result = imports.parse_import(b"\n" + b"private credential garbage\n" * 25,
                                 "normalized_jsonl", pseudonym_key=KEY)
    assert result.report["total_lines"] == 25 and result.report["rejected"] == 25
    assert len(result.report["errors"]) == 20 and result.report["errors"][0]["line"] == 2
    assert "private" not in json.dumps(result.report)


@pytest.mark.parametrize(("data", "code"), [
    (b"x" * (10 * 1024 * 1024 + 1), "input_too_large"),
    (b"bad\n" * 2001, "too_many_records"),
    (b"x" * (256 * 1024 + 1), "line_too_large"),
], ids=["input", "records", "line"])
def test_limit_excess_rejects_whole_import(data, code):
    with pytest.raises(imports.ImportLimitError) as exc:
        imports.parse_import(data, "normalized_jsonl", pseudonym_key=KEY)
    assert exc.value.code == code


def test_time_span_cap_uses_out_of_order_valid_rows_and_is_inclusive():
    parse(row(ts="2026-11-21T12:00:00Z"), row())
    with pytest.raises(imports.ImportLimitError, match="time_span_exceeded"):
        parse(row(ts="2026-11-21T12:00:01Z"), row())


def test_parser_deadline_rejects_whole_import(monkeypatch):
    times = iter([0, 0, 6, 6])
    monkeypatch.setattr(imports, "monotonic", lambda: next(times))
    with pytest.raises(imports.ImportLimitError, match="parser_timeout"):
        parse(row(), row())


def test_header_and_ua_bounds_and_timezone_normalization():
    result = parse(row(ts="2026-11-14T14:00:00+02:00", user_agent="a" * 1500,
                       headers={"Accept": "b" * 3000}))
    request, _ = parse_access_record(result.records[0])
    assert len(request.user_agent) == 1024
    assert len(request.headers["accept"]) == 2048
    assert result.records[0]["ts"] == "2026-11-14T12:00:00+00:00"
    assert result.report["redacted_fields"]["capped_values"] == 2


def test_unknown_format_and_empty_pseudonym_key_are_rejected():
    with pytest.raises(ValueError, match="unsupported_format"):
        imports.parse_import(b"", "magic", pseudonym_key=KEY)
    with pytest.raises(ValueError, match="invalid_pseudonym_key"):
        imports.parse_import(b"", "normalized_jsonl", pseudonym_key=b"")


def test_nonfinite_numbers_anywhere_in_json_are_rejected():
    source = json.dumps(row()).replace('"status": 200', '"status": 200, "ignored": [1e999]')
    result = imports.parse_import(source.encode(), "normalized_jsonl", pseudonym_key=KEY)
    assert result.report["accepted"] == 0
    assert result.report["errors"] == [{"line": 1, "code": imports.ERROR_CODES["invalid_json"]}]


def test_registry_parser_uses_shared_validation_and_redaction(monkeypatch):
    def adapter(line):
        return {"ts": "2026-11-14T12:00:00Z", "status": 201, "request": {
            "remote_ip": "192.0.2.5", "method": "GET", "uri": "/ok?secret=gone",
            "headers": {"Cookie": "hidden"}}}

    monkeypatch.setitem(imports.PARSERS, "custom", adapter)
    result = imports.parse_import(b"custom format line", "custom", pseudonym_key=KEY)
    assert result.records[0]["request"]["uri"] == "/ok"
    assert result.records[0]["request"]["headers"] == {}
    assert result.report["missing_fields"]["bytes"] == 1


def test_large_header_maps_are_rejected_and_maximum_int64_bytes_are_preserved():
    result = parse(row(headers={f"X-{i}": "x" for i in range(33)}), row(bytes=2**63 - 1))
    assert result.report["accepted"] == 1
    assert result.records[0]["size"] == 2**63 - 1
    assert result.report["errors"] == [{"line": 1, "code": imports.ERROR_CODES["invalid_headers"]}]


@pytest.mark.parametrize("format", ["nginx_combined", "apache_combined"])
def test_combined_adapter_reports_unrecoverable_fields_and_redacts(format):
    raw = (b'192.0.2.1 - private-user [10/Oct/2000:13:55:36 +0000] '
           b'"GET /products?password=secret HTTP/1.1" 200 - '
           b'"https://private.example/?token=secret" "ExampleBrowser/1.0"\n')
    result = imports.parse_import(raw, format, pseudonym_key=b"x" * 32)
    assert result.report["accepted"] == 1
    assert result.records[0]["request"]["uri"] == "/products"
    assert result.report["missing_fields"]["bytes"] == 1
    assert result.report["missing_fields"]["content_type"] == 1
    assert result.report["unmapped_fields"] >= 1
    text = json.dumps(result.records) + json.dumps(result.report)
    assert "private-user" not in text and "secret" not in text


def test_missing_measurement_mask_comes_from_validated_fields_only():
    result = parse(row(_unavailable_fields=["status", "raw-secret-field"],
                       _headers_incomplete=False))
    assert result.records[0]["_unavailable_fields"] == [
        "user_agent", "headers", "bytes", "content_type", "username"]
    assert "raw-secret-field" not in json.dumps(result.records)
    assert result.report["unmapped_fields"] == 2


@pytest.mark.parametrize("format", ["normalized_jsonl", "caddy_jsonl"])
def test_client_flags_cannot_hide_available_measurements(format):
    if format == "normalized_jsonl":
        source = row(method="POST", path="/login", bytes=0, user_agent="browser",
                     headers={"Accept": "text/html"}, content_type="text/html", username="private")
    else:
        source = {"ts": 1794657600, "status": 200, "size": 0,
                  "request": {"client_ip": "192.0.2.1", "method": "POST", "uri": "/login",
                              "headers": {"User-Agent": "browser", "Accept": "text/html"}},
                  "resp_headers": {"Content-Type": "text/html", "X-Login-User": "private"}}
    source.update(_unavailable_fields=["user_agent", "bytes"], _headers_incomplete=True)
    result = parse(source, format=format)
    assert result.records[0]["_unavailable_fields"] == []
    assert not any(result.report["missing_fields"].values())


def test_trusted_partial_headers_keep_ua_available_without_fabricating_other_headers(monkeypatch):
    def adapter(line):
        return {"ts": 1794657600, "status": 200, "size": 0,
                "request": {"remote_ip": "192.0.2.1", "method": "GET", "uri": "/",
                            "headers": {"User-Agent": "browser"}},
                "_headers_incomplete": True, "_unavailable_fields": ["arbitrary-secret"]}

    monkeypatch.setitem(imports.PARSERS, "partial", adapter)
    result = imports.parse_import(b"partial line", "partial", pseudonym_key=KEY)
    assert result.records[0]["request"]["headers"] == {"user-agent": ["browser"]}
    assert result.records[0]["_unavailable_fields"] == ["headers", "content_type", "username"]
    assert result.report["missing_fields"]["headers"] == 1
    assert result.report["missing_fields"]["user_agent"] == 0
    assert "arbitrary-secret" not in json.dumps(result.records)


def test_import_keeps_encoding_differences_used_by_native_header_fingerprints():
    from bouncer.ingest.import_analysis import analyze_records

    result = parse(*[
        row(ip=f"192.0.2.{i}", path="/", user_agent="ExampleAgent/1.0",
            headers={"User-Agent": "ExampleAgent/1.0", "Accept-Encoding": encoding})
        for i, encoding in enumerate(("gzip", "br", "deflate"), start=1)
    ])
    snapshot = analyze_records(result.records, False)
    assert not any(c["kind"] == "behavior_cluster" for c in snapshot["campaigns"])
    assert [r["request"]["headers"]["accept-encoding"] for r in result.records] == [
        ["gzip"], ["br"], ["deflate"]]


def test_pseudonymized_login_targets_preserve_native_case_and_whitespace_matching():
    from bouncer.ingest.import_analysis import analyze_records

    result = parse(*[
        row(ip=f"192.0.2.{i}", method="POST", path="/login", status=401, username=target)
        for i, target in enumerate((" Admin ", "admin", "ADMIN"), start=1)
    ])
    snapshot = analyze_records(result.records, False)
    assert any(c["kind"] == "credential_stuffing" for c in snapshot["campaigns"])
    assert all(v["rule_id"] == "login_attack_campaign" for v in snapshot["verdicts"].values())
    serialized = json.dumps(result.records) + json.dumps(snapshot)
    assert "Admin" not in serialized and "admin" not in serialized and "ADMIN" not in serialized
    assert any("ignores case" in text for text in result.report["limitations"])


def test_whitespace_only_login_target_stays_unavailable():
    result = parse(row(method="POST", path="/login", username="   "))
    assert "x-login-user" not in result.records[0]["resp_headers"]
    assert "username" in result.records[0]["_unavailable_fields"]
    assert result.report["missing_fields"]["username"] == 1


def test_referer_presence_is_measured_without_retaining_its_secret_url():
    result = parse(row(headers={"User-Agent": "Browser", "Referer": "https://private/?secret=value"}))
    headers = result.records[0]["request"]["headers"]
    assert headers["referer"] == ["present"]
    assert "private" not in json.dumps(result.records)
    assert result.report["redacted_fields"]["headers"] >= 1


def test_capped_values_are_unknown_measurements_not_complete_fingerprints():
    result = parse(row(user_agent="Browser" + "x" * 1100,
                       headers={"Accept-Encoding": "gzip," + "x" * 2100},
                       content_type="text/html;" + "x" * 2100))
    unavailable = result.records[0]["_unavailable_fields"]
    assert {"user_agent", "headers", "content_type"} <= set(unavailable)
    assert result.report["redacted_fields"]["capped_values"] >= 3
