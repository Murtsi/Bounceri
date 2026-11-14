"""Native offline import analysis in a fixed, deadline-bounded child process."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from bouncer.contracts import TRAFFIC_UNAVAILABLE_FEATURES as _UNAVAILABLE_FEATURES

MAX_INPUT_BYTES = 10 * 1024**2
MAX_OUTPUT_BYTES = 8 * 1024**2
MAX_RECORDS = 2000
TIMEOUT_SECONDS = 5.0
UNAVAILABLE_FIELDS = frozenset({"user_agent", "headers", "bytes", "content_type", "username"})
INCOMPLETE_NOTICE = "Imported logging is incomplete; no certain rule matched."

_UnavailableField = Literal["user_agent", "headers", "bytes", "content_type", "username"]


class AnalysisError(ValueError):
    """Sanitized import failure; never includes source records or child output."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class _Request(_Strict):
    ts: AwareDatetime
    ip: str
    method: str
    path: str
    status: int
    user_agent: str
    query: str
    bytes: int
    headers: dict[str, str]
    content_type: str | None
    username: str | None


class _Session(_Strict):
    id: str
    ip: str
    user_agent: str
    started_at: AwareDatetime
    ended_at: AwareDatetime
    requests: list[_Request] = Field(min_length=1, max_length=MAX_RECORDS)


class _Verdict(_Strict):
    rule_id: str | None
    action: Literal["none", "monitor", "rate_limit", "challenge", "block"]
    label: Literal["human", "good_bot", "bad_bot", "uncertain"]
    score: float = Field(ge=0, le=1)
    reasons: list[str]
    model_version: str
    campaign_id: str | None
    explanation: str
    verified_bot: None
    asn_type: Literal["unknown"]


class _Campaign(_Strict):
    id: str
    kind: str
    session_ids: list[str]
    reasons: list[str]
    size: int


class _Observation(_Strict):
    version: Literal["bouncer-rule-observations-v1"]
    trap_hits: int = Field(ge=0)
    trap_config_version: str
    rule_ids: list[str]
    features: dict[str, int | float | bool]


class _Ingest(_Strict):
    records: int = Field(ge=1, le=MAX_RECORDS)
    invalid_records: Literal[0]
    unsigned_markers: Literal[0]
    invalid_markers: Literal[0]
    conflicting_sessions: list[str]
    login_events: int = Field(ge=0)
    bad_lines: Literal[0]
    rotation_gaps: Literal[0]
    retained_records: int = Field(ge=1, le=MAX_RECORDS)
    retained_bytes: int = Field(ge=0, le=16 * 1024**2)
    last_event_at: AwareDatetime | None
    discarded_by_retention: Literal[0]
    updated_at: AwareDatetime


class _Snapshot(_Strict):
    sessions: list[_Session] = Field(min_length=1, max_length=MAX_RECORDS)
    labels: list[None] = Field(max_length=0)
    synthetic: bool
    source: Literal["import:caddy"]
    verdicts: dict[str, _Verdict]
    ip_evidence: dict[str, None] = Field(max_length=0)
    rule_observations: dict[str, _Observation]
    unavailable_fields: dict[str, list[_UnavailableField]]
    campaigns: list[_Campaign]
    ingest: _Ingest


def _input(records: list[dict], synthetic: bool) -> bytes:
    if (type(records) is not list or not 1 <= len(records) <= MAX_RECORDS
            or type(synthetic) is not bool or any(type(r) is not dict for r in records)):
        raise AnalysisError("Invalid import analysis input")
    for record in records:
        mask = record.get("_unavailable_fields", [])
        if (type(mask) is not list
                or any(type(field) is not str or field not in UNAVAILABLE_FIELDS for field in mask)
                or len(set(mask)) != len(mask)):
            raise AnalysisError("Invalid import field availability")
    try:
        data = json.dumps({"records": records, "synthetic": synthetic},
                          allow_nan=False, separators=(",", ":")).encode()
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise AnalysisError("Invalid import analysis input") from None
    if len(data) > MAX_INPUT_BYTES:
        raise AnalysisError("Import analysis input is too large")
    return data


def _decode(payload: bytes, records: list[dict], synthetic: bool) -> dict:
    from bouncer.ingest.sample import parse_access_record

    if type(payload) is not bytes or len(payload) > MAX_OUTPUT_BYTES:
        raise AnalysisError("Invalid import analysis output")
    try:
        snapshot = _Snapshot.model_validate_json(payload)
        count = len(records)
        ids = {s.id for s in snapshot.sessions}
        requests = [r for s in snapshot.sessions for r in s.requests]
        if (snapshot.synthetic is not synthetic or len(ids) != len(snapshot.sessions)
                or set(snapshot.verdicts) != ids or set(snapshot.rule_observations) != ids
                or len(requests) != count or snapshot.ingest.records != count
                or snapshot.ingest.retained_records != count
                or snapshot.ingest.conflicting_sessions):
            raise ValueError("incomplete analysis")
        if not snapshot.unavailable_fields.keys() <= ids:
            raise ValueError("unknown field availability owner")
        original_counts, returned_counts = Counter(), Counter()
        original_masks = {}
        for raw in records:
            request, _ = parse_access_record(raw, secret=None)
            key = (request.ip, request.user_agent, request.ts)
            original_counts[key] += 1
            original_masks.setdefault(key, set()).update(raw.get("_unavailable_fields", []))
        for session in snapshot.sessions:
            expected = set()
            for request in session.requests:
                key = (request.ip, request.user_agent, request.ts)
                returned_counts[key] += 1
                expected.update(original_masks.get(key, ()))
            fields = snapshot.unavailable_fields.get(session.id, [])
            if len(fields) != len(set(fields)) or set(fields) != expected:
                raise ValueError("invalid field availability")
            features = snapshot.rule_observations[session.id].features
            if any(_UNAVAILABLE_FEATURES.get(field, set()).intersection(features)
                   for field in fields):
                raise ValueError("unavailable feature reported as observed")
            for name in ("peak_requests_per_min", "vuln_path_hits"):
                if name in features and (type(features[name]) is not int
                                         or not 0 <= features[name] <= len(session.requests)):
                    raise ValueError("invalid native count feature")
        if original_counts != returned_counts:
            raise ValueError("incomplete source ownership")
        campaigns = {c.id for c in snapshot.campaigns}
        if len(campaigns) != len(snapshot.campaigns):
            raise ValueError("duplicate campaign")
        for campaign in snapshot.campaigns:
            if (not set(campaign.session_ids) <= ids or campaign.size != len(campaign.session_ids)
                    or len(set(campaign.session_ids)) != campaign.size):
                raise ValueError("invalid campaign membership")
        for session in snapshot.sessions:
            if (session.ended_at < session.started_at
                    or any(r.ip != session.ip or r.user_agent != session.user_agent
                           or not session.started_at <= r.ts <= session.ended_at
                           or any(k.lower() in {"x-sim-run", "x-sim-sig"} for k in r.headers)
                           for r in session.requests)):
                raise ValueError("invalid session")
        if any(v.campaign_id is not None and v.campaign_id not in campaigns
               for v in snapshot.verdicts.values()):
            raise ValueError("invalid verdict campaign")
        return snapshot.model_dump(mode="json")
    except (ValueError, TypeError, OverflowError, RecursionError, OSError, AttributeError):
        raise AnalysisError("Invalid import analysis output") from None


def analyze_records(records: list[dict], synthetic: bool) -> dict:
    """Child-side pipeline; private worker continuity files die with its temp directory."""
    from bouncer.ingest.worker import Worker
    from bouncer.network import find_campaigns

    _input(records, synthetic)
    safe = []
    try:
        for record in records:
            raw = {k: v for k, v in record.items() if k in {"ts", "status", "size"}}
            raw["_unavailable_fields"] = record.get("_unavailable_fields", [])[:]
            request = record["request"]
            raw["request"] = {k: v for k, v in request.items()
                              if k in {"client_ip", "remote_ip", "method", "uri"}}
            for owner, headers in [(raw["request"], request.get("headers", {})),
                                   (raw, record.get("resp_headers", {}))]:
                key = "headers" if owner is raw["request"] else "resp_headers"
                owner[key] = {k: v for k, v in headers.items()
                              if k.lower() not in {"x-sim-run", "x-sim-sig"}}
            safe.append(raw)

        def import_campaigns(sessions):
            unsupported = {raw["_session_id"] for raw in safe
                           if {"headers", "user_agent"}.intersection(raw["_unavailable_fields"])}
            return [campaign for campaign in find_campaigns(sessions)
                    if campaign.kind != "behavior_cluster"
                    or not unsupported.intersection(campaign.session_ids)]

        with tempfile.TemporaryDirectory(prefix="bouncer-import-") as directory:
            root = Path(directory)
            worker = Worker(root / "empty.log", root / "snapshot.json", secret=None,
                            intel_fn=None, campaigns_fn=import_campaigns, synthetic=synthetic,
                            max_records=MAX_RECORDS, traps=frozenset(), rules_only=True,
                            max_retained_bytes=16 * 1024**2)
            worker.records = safe
            result = worker.cycle()
            unavailable = {}
            for raw in worker.records:
                unavailable.setdefault(raw["_session_id"], set()).update(raw["_unavailable_fields"])
        result["unavailable_fields"] = {sid: sorted(fields) for sid, fields in unavailable.items()
                                        if fields}
        result = {k: result[k] for k in _Snapshot.model_fields}
        result.update(labels=[], source="import:caddy", ip_evidence={})
        for session_id, fields in unavailable.items():
            if not fields:
                continue
            observation = result["rule_observations"][session_id]
            for field in fields:
                for feature in _UNAVAILABLE_FEATURES.get(field, ()):
                    observation["features"].pop(feature, None)
            verdict = result["verdicts"][session_id]
            if verdict["rule_id"] is not None and verdict["rule_id"] in observation["rule_ids"]:
                # Native scoring places deterministic rule reasons before soft observations.
                verdict["reasons"] = verdict["reasons"][:len(observation["rule_ids"])]
                verdict["explanation"] = " ".join(verdict["reasons"])
            else:
                verdict.update(reasons=[INCOMPLETE_NOTICE], explanation=INCOMPLETE_NOTICE)
        payload = json.dumps(result, allow_nan=False, separators=(",", ":")).encode()
        return _decode(payload, records, synthetic)
    except AnalysisError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OSError,
            OverflowError, RecursionError):
        raise AnalysisError("Import analysis failed") from None


def run_analysis(data: bytes, timeout: float) -> bytes:
    """Charge startup, process execution and bounded cleanup to one deadline."""
    deadline = time.monotonic() + timeout
    cleanup_budget = min(.1, timeout / 4)
    # Provider credentials/config never enter this offline worker.
    env = {k: v for k, v in os.environ.items()
           if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    with (tempfile.TemporaryDirectory(prefix="bouncer-import-run-") as directory,
          tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as output):
        # The parent removes private worker files even when the child is killed.
        env.update(TMPDIR=directory, TEMP=directory, TMP=directory)
        source.write(data)
        source.seek(0)
        process = subprocess.Popen(
            [sys.executable, "-m", "bouncer.ingest.import_analysis"],
            shell=False, stdin=source, stdout=output, stderr=subprocess.DEVNULL, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            remaining = deadline - time.monotonic() - cleanup_budget
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            status = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=max(0, min(cleanup_budget, deadline - time.monotonic())))
            raise
        if status != 0:
            raise OSError("import analysis child failed")
        output.seek(0)
        return output.read(MAX_OUTPUT_BYTES + 1)


def analyze_import(
    records: list[dict], synthetic: bool, *,
    runner: Callable[[bytes, float], bytes] = run_analysis,
    timeout_seconds: float = TIMEOUT_SECONDS,
) -> dict:
    """Return a validated, complete offline snapshot or a sanitized typed failure."""
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= TIMEOUT_SECONDS):
        raise AnalysisError("Invalid import analysis timeout")
    data = _input(records, synthetic)
    started = time.monotonic()
    try:
        payload = runner(data, timeout_seconds)
        if time.monotonic() - started > timeout_seconds:
            raise subprocess.TimeoutExpired("import analysis", timeout_seconds)
        result = _decode(payload, records, synthetic)
        if time.monotonic() - started > timeout_seconds:
            raise subprocess.TimeoutExpired("import analysis", timeout_seconds)
        return result
    except subprocess.TimeoutExpired:
        raise AnalysisError("Import analysis timed out") from None
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise AnalysisError("Import analysis failed") from None


def main() -> int:
    try:
        if len(sys.argv) != 1:
            return 2
        data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            return 2
        packet = json.loads(data)
        if type(packet) is not dict or packet.keys() != {"records", "synthetic"}:
            return 2
        result = analyze_records(packet["records"], packet["synthetic"])
        output = json.dumps(result, allow_nan=False, separators=(",", ":")).encode()
        if len(output) > MAX_OUTPUT_BYTES:
            return 1
        sys.stdout.buffer.write(output)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
