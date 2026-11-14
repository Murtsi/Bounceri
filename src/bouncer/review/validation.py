"""Bound packets and validate checkable facts; prose entailment remains unproved."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import MAX_REQUEST_BYTES

LABELS = {"human", "good_bot", "bad_bot", "uncertain"}
COUNT_FIELDS = {
    "n_sessions",
    "n_requests",
    "failed_logins",
    "distinct_account_count",
    "distinct_client_count",
}
MAP_FIELDS = {"status_counts", "method_counts", "path_category_counts"}
DATA_FIELDS = (
    COUNT_FIELDS
    | MAP_FIELDS
    | {
        "session_ref",
        "started_at",
        "ended_at",
        "local_label",
        "local_score",
        "verified_bot",
        "verified_crawler",
        "crawler_verification_origin",
        "attack_signals",
        "path_category_version",
        "category_provenance",
    }
)
ATTACK_SIGNALS = {"probe", "trap", "vulnerability_probe", "trap_hit", "scan", "scanner"}


def strict_json(text: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("nonfinite_json")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def _count(value) -> bool:
    return type(value) is int and 0 <= value <= 1_000_000_000


def validate_packet(packet: dict) -> dict:
    """Reject unknown fields instead of accidentally forwarding private source data."""
    allowed = {
        "case_id",
        "investigation_id",
        "evidence_version",
        "evidence_hash",
        "synthetic",
        "complete",
        "evidence",
        "local_assessment",
        "missing_information",
        "distinct_client_count",
    }
    if not isinstance(packet, dict) or set(packet) - allowed:
        raise ValueError("invalid_evidence_packet")
    if packet.get("complete") is not True or type(packet.get("synthetic")) is not bool:
        raise ValueError("invalid_evidence_packet")
    if not re.fullmatch(r"[a-f0-9]{64}", str(packet.get("evidence_hash", ""))):
        raise ValueError("invalid_evidence_packet")
    if not _count(packet.get("evidence_version")) or packet["evidence_version"] < 1:
        raise ValueError("invalid_evidence_packet")
    if "distinct_client_count" in packet and not _count(packet["distinct_client_count"]):
        raise ValueError("invalid_evidence_packet")
    missing = packet.get("missing_information", [])
    if (
        not isinstance(missing, list)
        or len(missing) > 10
        or any(not isinstance(value, str) or len(value) > 160 for value in missing)
    ):
        raise ValueError("invalid_evidence_packet")
    case_id = packet.get("case_id", packet.get("investigation_id"))
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", case_id):
        raise ValueError("invalid_evidence_packet")
    evidence = packet.get("evidence")
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 200:
        raise ValueError("invalid_evidence_packet")
    ids = set()
    for item in evidence:
        if (
            not isinstance(item, dict)
            or set(item) - {"id", "kind", "data", "version", "redacted"}
            or not {"id", "kind", "data"} <= item.keys()
        ):
            raise ValueError("invalid_evidence_packet")
        if "redacted" in item and item["redacted"] is not True:
            raise ValueError("invalid_evidence_packet")
        if "version" in item and not _count(item["version"]):
            raise ValueError("invalid_evidence_packet")
        ident = item["id"]
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", ident):
            raise ValueError("invalid_evidence_packet")
        if ident in ids or item["kind"] not in {"session_summary", "traffic_summary"}:
            raise ValueError("invalid_evidence_packet")
        ids.add(ident)
        data = item["data"]
        if not isinstance(data, dict) or set(data) - DATA_FIELDS:
            raise ValueError("invalid_evidence_packet")
        for key, value in data.items():
            valid = True
            if key in COUNT_FIELDS:
                valid = _count(value)
            elif key in MAP_FIELDS:
                valid = (
                    isinstance(value, dict)
                    and len(value) <= 30
                    and all(
                        isinstance(k, str) and _map_key_allowed(key, k) and _count(v)
                        for k, v in value.items()
                    )
                )
            elif key in {"verified_bot", "verified_crawler"}:
                valid = value is None or type(value) is bool
            elif key == "crawler_verification_origin":
                valid = value in {"dns", "forward_reverse_dns", "synthetic", "unknown", None}
            elif key == "attack_signals":
                valid = (
                    isinstance(value, list)
                    and len(value) <= 8
                    and all(isinstance(v, str) and v in ATTACK_SIGNALS for v in value)
                )
            elif key == "local_label":
                valid = value in LABELS
            elif key == "local_score":
                valid = value is None or (
                    type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
                )
            elif key in {"started_at", "ended_at"}:
                valid = isinstance(value, str) and len(value) <= 40
                if valid:
                    try:
                        datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except ValueError:
                        valid = False
            elif key == "path_category_version":
                valid = value == "categories-v1"
            elif key == "category_provenance":
                valid = value == "bouncer-path-categories-v1"
            elif key == "session_ref":
                valid = isinstance(value, str) and bool(
                    re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value)
                )
            if not valid:
                raise ValueError("invalid_evidence_packet")
        if "n_requests" in data:
            for field in MAP_FIELDS:
                if field in data and sum(data[field].values()) != data["n_requests"]:
                    raise ValueError("invalid_evidence_packet")
            if data.get("failed_logins", 0) > data["n_requests"]:
                raise ValueError("invalid_evidence_packet")
    local = packet.get("local_assessment")
    if not isinstance(local, dict) or set(local) - {
        "stage",
        "label",
        "model_version",
        "score",
        "reasons",
        "label_counts",
        "evidence_ids",
        "limitations",
    }:
        raise ValueError("invalid_evidence_packet")
    if local.get("label") not in LABELS:
        raise ValueError("invalid_evidence_packet")
    # Local prose is deliberately omitted from the model view. Only finite local observations
    # are useful context; arbitrary legacy reasons must never become provider instructions.
    clean = {k: v for k, v in packet.items() if k != "local_assessment"}
    clean["local_assessment"] = {"label": local["label"]}
    version = local.get("model_version")
    if isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", version):
        clean["local_assessment"]["model_version"] = version
    encoded = json.dumps(clean, allow_nan=False).encode()
    if len(encoded) > MAX_REQUEST_BYTES // 2:
        raise ValueError("invalid_evidence_packet")
    return clean


def _map_key_allowed(field: str, key: str) -> bool:
    if field == "status_counts":
        return key == "unknown" or bool(re.fullmatch(r"[1-5][0-9]{2}", key))
    if field == "method_counts":
        return key in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "OTHER"}
    return key in {"probe", "trap", "login", "asset", "page", "other", "robots", "static"}


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    evidence_id: str = Field(min_length=1, max_length=128)
    field: str = Field(min_length=1, max_length=80)
    value: int | bool


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: Literal["human", "good_bot", "bad_bot", "uncertain"]
    automation: Literal["human_like", "automated", "unknown"]
    authentication_pattern: Literal[
        "not_observed", "repeated_failures", "distributed_failed_authentication", "unknown"
    ]
    crawler_verification: Literal["verified", "unverified", "unknown"]
    coordination: Literal["observed", "not_established", "unknown"]
    maliciousness: Literal["supported", "not_established", "unknown"]
    suggested_action: Literal["monitor", "rate_limit", "temporary_block", "human_review"]
    supporting_evidence_ids: list[str] = Field(max_length=200)
    contradicting_evidence_ids: list[str] = Field(max_length=200)
    missing_information: list[str] = Field(max_length=8)
    benign_alternatives: list[str] = Field(max_length=8)
    rationale: str = Field(min_length=1, max_length=1200)
    observations: list[Observation] = Field(max_length=40)


def validate_recommendation(value: dict, packet: dict) -> dict:
    result = Recommendation.model_validate(value)
    evidence = {item["id"]: item["data"] for item in packet["evidence"]}
    support = result.supporting_evidence_ids
    contrary = result.contradicting_evidence_ids
    if (
        set(support + contrary) - evidence.keys()
        or len(support) != len(set(support))
        or len(contrary) != len(set(contrary))
        or set(support) & set(contrary)
    ):
        raise ValueError("invalid_reviewer_output")
    if any(
        not text or len(text) > 160
        for text in (result.missing_information + result.benign_alternatives)
    ):
        raise ValueError("invalid_reviewer_output")
    if result.label != "uncertain" and not support:
        raise ValueError("invalid_reviewer_output")
    for observation in result.observations:
        data = evidence.get(observation.evidence_id)
        if data is None or observation.evidence_id not in support + contrary:
            raise ValueError("invalid_reviewer_output")
        parts = observation.field.split(".")
        if parts[0] not in COUNT_FIELDS | MAP_FIELDS | {"verified_bot", "verified_crawler"}:
            raise ValueError("invalid_reviewer_output")
        actual = data
        for part in parts:
            actual = actual.get(part) if isinstance(actual, dict) else None
        if type(actual) is not type(observation.value) or actual != observation.value:
            raise ValueError("invalid_reviewer_output")
    facts = [evidence[ident] for ident in support]
    if (result.label == "human" and result.automation != "human_like") or (
        result.label in {"good_bot", "bad_bot"} and result.automation != "automated"
    ):
        raise ValueError("invalid_reviewer_output")
    if result.authentication_pattern == "not_observed" and any(
        data.get("failed_logins", 0) > 0 for data in evidence.values()
    ):
        raise ValueError("invalid_reviewer_output")
    verified = any(
        (data.get("verified_crawler") is True or data.get("verified_bot") is True)
        and (
            data.get("crawler_verification_origin") in {"dns", "forward_reverse_dns"}
            or packet["synthetic"]
            and data.get("crawler_verification_origin") == "synthetic"
        )
        for data in facts
    )
    if (result.label == "good_bot" or result.crawler_verification == "verified") and not verified:
        raise ValueError("invalid_reviewer_output")
    attack = any(
        (
            data.get("category_provenance") == "bouncer-path-categories-v1"
            or data.get("attack_signals")
            and data.get("path_category_version") == "categories-v1"
        )
        and any(data.get("path_category_counts", {}).get(key, 0) > 0 for key in ("probe", "trap"))
        for data in facts
    )
    if (result.label == "bad_bot" or result.maliciousness == "supported") and not attack:
        raise ValueError("invalid_reviewer_output")
    if result.label == "bad_bot" and result.maliciousness != "supported":
        raise ValueError("invalid_reviewer_output")
    if result.authentication_pattern == "repeated_failures" and not any(
        data.get("failed_logins", 0) >= 2 for data in facts
    ):
        raise ValueError("invalid_reviewer_output")
    if result.authentication_pattern == "distributed_failed_authentication" and not any(
        data.get("failed_logins", 0) >= 2 and data.get("distinct_client_count", 0) >= 2
        for data in facts
    ):
        raise ValueError("invalid_reviewer_output")
    # Timing/identity aggregates alone cannot establish coordination. This capability has no
    # relationship evidence in phase one, so the model must explicitly abstain from that claim.
    if result.coordination == "observed":
        raise ValueError("invalid_reviewer_output")
    if result.suggested_action in {"rate_limit", "temporary_block"} and not attack:
        raise ValueError("invalid_reviewer_output")
    return result.model_dump()
