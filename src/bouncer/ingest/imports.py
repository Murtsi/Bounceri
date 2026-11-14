"""Bounded private traffic imports; callbacks only parse, shared validation removes secrets."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

from bouncer.ingest.combined import parse_combined_line
from bouncer.ingest.sample import canonical_ip

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_RECORDS = 2000
MAX_LINE_BYTES = 256 * 1024
MAX_SPAN_SECONDS = 7 * 24 * 60 * 60
PARSER_SECONDS = 5
ERROR_CODES = {name: number for number, name in enumerate((
    "invalid_utf8", "invalid_json", "invalid_record", "invalid_timestamp", "invalid_ip",
    "invalid_method", "invalid_path", "invalid_status", "invalid_bytes", "invalid_headers",
), start=1)}
METHODS = {"GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"}
HEADER_ALLOWLIST = {"accept", "user-agent", "accept-language", "accept-encoding", "content-type",
                    "sec-fetch-mode", "sec-fetch-dest", "sec-fetch-site", "sec-ch-ua"}


class ImportLimitError(ValueError):
    """An overall import cap failed: no partial result is returned."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class ImportResult:
    records: list[dict[str, Any]]
    report: dict[str, Any]


def _invalid(code: str) -> None:
    raise ValueError(code)


def _json_object(line: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _invalid("invalid_json")
            result[key] = value
        return result

    def reject_constant(_):
        _invalid("invalid_json")

    def finite_float(number):
        value = float(number)
        if not math.isfinite(value):
            _invalid("invalid_json")
        return value

    try:
        value = json.loads(line, object_pairs_hook=pairs, parse_constant=reject_constant,
                           parse_float=finite_float)
    except (ValueError, RecursionError):
        _invalid("invalid_json")
    if not isinstance(value, dict):
        _invalid("invalid_record")
    return value


def _caddy_jsonl(line: str) -> dict:
    raw = _json_object(line)
    allowed = {"ts", "request", "status", "size", "resp_headers"}
    request = raw.get("request")
    unknown = len(raw.keys() - allowed)
    if isinstance(request, dict):
        unknown += len(request.keys() - {"remote_ip", "client_ip", "method", "uri", "headers"})
    return {key: value for key, value in raw.items() if key in allowed} | {
        "_unmapped_fields": unknown}


def _normalized_jsonl(line: str) -> dict:
    raw = _json_object(line)
    allowed = {"ts", "ip", "method", "path", "status", "bytes", "user_agent", "headers",
               "content_type", "username"}
    request = {key: raw[name] for key, name in (
        ("client_ip", "ip"), ("method", "method"), ("uri", "path"), ("headers", "headers"))
        if name in raw}
    result = {key: raw[name] for key, name in (
        ("ts", "ts"), ("status", "status"), ("size", "bytes")) if name in raw}
    result.update(request=request, resp_headers={}, _unmapped_fields=len(raw.keys() - allowed))
    result["_headers_incomplete"] = not raw.get("headers")
    # Explicit normalized columns take precedence over optional header values.
    for name in ("user_agent", "content_type", "username"):
        if name in raw:
            result["_" + name] = raw[name]
    return result


# A parser receives one decoded line and returns Caddy-shaped fields. Validation is shared.
PARSERS: dict[str, Callable[[str], dict]] = {
    "nginx_combined": parse_combined_line,
    "apache_combined": parse_combined_line,
    "caddy_jsonl": _caddy_jsonl, "normalized_jsonl": _normalized_jsonl,
}


def _timestamp(value: Any) -> datetime:
    try:
        if type(value) in (int, float) and math.isfinite(value):
            return datetime.fromtimestamp(value, UTC)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.utcoffset() is not None:
                return parsed.astimezone(UTC)
    except (ValueError, OverflowError, OSError):
        pass
    _invalid("invalid_timestamp")


def _headers(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 32:
        _invalid("invalid_headers")
    result = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or key.lower() in result:
            _invalid("invalid_headers")
        if isinstance(item, list):
            if any(not isinstance(part, str) for part in item):
                _invalid("invalid_headers")
            item = item[0] if item else ""
        if not isinstance(item, str):
            _invalid("invalid_headers")
        try:
            key.encode("utf-8")
            item.encode("utf-8")
        except UnicodeError:
            _invalid("invalid_headers")
        if any(ord(char) < 32 or ord(char) == 127 for char in key + item):
            _invalid("invalid_headers")
        result[key.lower()] = item
    return result


def _safe_record(raw: dict, pseudonym_key: bytes) -> tuple[dict, datetime, dict, dict]:
    if not isinstance(raw, dict) or not isinstance(raw.get("request"), dict):
        _invalid("invalid_record")
    request = raw["request"]
    timestamp = _timestamp(raw.get("ts"))
    ip = request.get("client_ip") or request.get("remote_ip")
    if not isinstance(ip, str):
        _invalid("invalid_ip")
    try:
        ip = canonical_ip(ip)
    except ValueError:
        _invalid("invalid_ip")
    method = request.get("method")
    if not isinstance(method, str) or method not in METHODS:
        _invalid("invalid_method")
    status = raw.get("status")
    if type(status) is not int or not 100 <= status <= 599:
        _invalid("invalid_status")
    size = raw.get("size", 0)
    if type(size) is not int or not 0 <= size <= 2**63 - 1:
        _invalid("invalid_bytes")
    uri = request.get("uri")
    if not isinstance(uri, str) or not uri or len(uri) > 4096:
        _invalid("invalid_path")
    try:
        uri.encode("utf-8")
        if any(ord(char) < 32 or ord(char) == 127 for char in uri):
            _invalid("invalid_path")
        if uri.startswith("/"):
            path = uri.split("?", 1)[0].split("#", 1)[0]
            authority = False
        else:
            parsed = urlsplit(uri)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                _invalid("invalid_path")
            path, authority = parsed.path or "/", True
    except (ValueError, UnicodeError):
        _invalid("invalid_path")
    headers = _headers(request.get("headers"))
    response = _headers(raw.get("resp_headers"))
    ua = raw.get("_user_agent", headers.get("user-agent"))
    content_type = raw.get("_content_type", response.get("content-type"))
    username = raw.get("_username", response.get("x-login-user"))
    for value in (ua, content_type, username):
        if value is not None:
            if not isinstance(value, str):
                _invalid("invalid_headers")
            try:
                value.encode("utf-8")
            except UnicodeError:
                _invalid("invalid_headers")
            if any(ord(char) < 32 or ord(char) == 127 for char in value):
                _invalid("invalid_headers")
    if username is not None:
        username = username.strip().lower()
    missing = {"user_agent": not ua,
               "headers": not request.get("headers") or raw.get("_headers_incomplete") is True,
               "bytes": "size" not in raw, "content_type": not content_type,
               "username": not username}
    redacted = {"headers": 0, "query": int("?" in uri), "fragment": int("#" in uri),
                "url_authority": int(authority), "usernames": 0, "capped_values": 0}
    safe_headers = {}
    for key, value in headers.items():
        if key == "referer":
            redacted["headers"] += 1
            if value:
                safe_headers[key] = ["present"]
            continue
        if key not in HEADER_ALLOWLIST:
            redacted["headers"] += 1
            continue
        limit = 1024 if key == "user-agent" else 2048
        redacted["capped_values"] += int(len(value) > limit)
        if len(value) > limit:
            missing["headers"] = True
            if key == "user-agent":
                missing["user_agent"] = True
        safe_headers[key] = [value[:limit]]
    if "_user_agent" in raw and ua is not None:
        redacted["capped_values"] += int(len(ua) > 1024)
        if len(ua) > 1024:
            missing["user_agent"] = missing["headers"] = True
        safe_headers["user-agent"] = [ua[:1024]]
    safe_response = {}
    redacted["headers"] += len(response.keys() - {"content-type", "x-login-user"})
    if content_type:
        redacted["capped_values"] += int(len(content_type) > 2048)
        if len(content_type) > 2048:
            missing["content_type"] = True
        safe_response["content-type"] = [content_type[:2048]]
    if username:
        redacted["usernames"] += 1
        if method == "POST" and "/login" in path.lower():
            digest = hmac.new(pseudonym_key, username.encode("utf-8"), hashlib.sha256).hexdigest()
            safe_response["x-login-user"] = ["user_" + digest]
    return ({"ts": timestamp.isoformat(), "request": {"remote_ip": ip, "client_ip": ip,
             "method": method, "uri": path, "headers": safe_headers}, "status": status,
             "size": size, "resp_headers": safe_response,
             "_unavailable_fields": [field for field, absent in missing.items() if absent]},
            timestamp, missing, redacted)


def parse_import(data: bytes, format: str, *, pseudonym_key: bytes) -> ImportResult:
    """Parse a complete bounded upload or raise a fixed-code error without partial output."""
    if format not in PARSERS:
        raise ValueError("unsupported_format")
    if not isinstance(pseudonym_key, bytes) or not pseudonym_key:
        raise ValueError("invalid_pseudonym_key")
    if not isinstance(data, bytes):
        raise ValueError("invalid_input")
    started = monotonic()
    if len(data) > MAX_INPUT_BYTES:
        raise ImportLimitError("input_too_large")
    report = {"accepted": 0, "rejected": 0, "total_lines": 0, "errors": [],
              "error_codes": ERROR_CODES.copy(),
              "missing_fields": dict.fromkeys(("user_agent", "headers", "bytes", "content_type",
                                               "username"), 0),
              "unmapped_fields": 0,
              "redacted_fields": dict.fromkeys(("headers", "query", "fragment", "url_authority",
                                                "usernames", "capped_values"), 0),
              "time_range": {"min": None, "max": None},
              "limits": {"input_bytes": MAX_INPUT_BYTES, "records": MAX_RECORDS,
                         "line_bytes": MAX_LINE_BYTES, "span_seconds": MAX_SPAN_SECONDS,
                         "parser_seconds": PARSER_SECONDS, "record_scope": "all_nonempty_lines"},
              "limitations": ["Path segments and allowed header values may contain personal data.",
                              "Missing optional fields stay unknown; labels are discarded.",
                              "Native target matching ignores case and surrounding whitespace; "
                              "source-specific account identity is not proven."]}
    records = []
    earliest = latest = None
    for position, line in enumerate(data.split(b"\n"), start=1):
        if monotonic() - started >= PARSER_SECONDS:
            raise ImportLimitError("parser_timeout")
        if len(line) > MAX_LINE_BYTES:
            raise ImportLimitError("line_too_large")
        if not line.strip():
            continue
        report["total_lines"] += 1
        if report["total_lines"] > MAX_RECORDS:
            raise ImportLimitError("too_many_records")
        try:
            try:
                decoded = line.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                _invalid("invalid_utf8")
            raw = PARSERS[format](decoded)
            record, timestamp, missing, redacted = _safe_record(raw, pseudonym_key)
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            code = str(exc)
            if code not in ERROR_CODES:
                code = "invalid_record"
            report["rejected"] += 1
            if len(report["errors"]) < 20:
                report["errors"].append({"line": position, "code": ERROR_CODES[code]})
            continue
        earliest = min(earliest, timestamp) if earliest is not None else timestamp
        latest = max(latest, timestamp) if latest is not None else timestamp
        if latest - earliest > timedelta(seconds=MAX_SPAN_SECONDS):
            raise ImportLimitError("time_span_exceeded")
        records.append(record)
        report["accepted"] += 1
        report["unmapped_fields"] += raw.get("_unmapped_fields", 0)
        for field, value in missing.items():
            report["missing_fields"][field] += int(value)
        for field, value in redacted.items():
            report["redacted_fields"][field] += value
    if monotonic() - started >= PARSER_SECONDS:
        raise ImportLimitError("parser_timeout")
    if earliest is not None:
        report["time_range"] = {"min": earliest.isoformat(), "max": latest.isoformat()}
    return ImportResult(records, report)
