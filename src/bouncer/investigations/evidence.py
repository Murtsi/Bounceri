"""Bounded, private traffic evidence adapter; simulator truth is never evidence."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from bouncer.session.features import STATIC_EXTENSIONS, is_vuln_path

RULE_IDS = {"verified_crawler", "trap", "fake_crawler", "vuln_paths", "login_attack_campaign"}
CAMPAIGN_KINDS = {
    "credential_stuffing",
    "distributed_login_spray",
    "slow_credential_stuffing",
    "behavior_cluster",
}
FEATURES = {
    "duration_s",
    "requests_per_min",
    "peak_requests_per_min",
    "static_share",
    "html_share",
    "vuln_path_hits",
    "header_inconsistency_share",
    "ua_is_tool",
    "ua_claims_bot",
}


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return timestamp if timestamp.utcoffset() == UTC.utcoffset(timestamp) else None


def _enum(value: Any, allowed: set[str], default: Any = None) -> Any:
    return value if isinstance(value, str) and value in allowed else default


def _network(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    checked = _utc(raw.get("checked_at"))
    outcome = _enum(
        raw.get("resolver_outcome"),
        {
            "verified",
            "mismatch",
            "unavailable",
            "timeout",
            "capacity",
            "invalid",
        },
        "invalid",
    )
    crawler = _enum(raw.get("crawler"), {"googlebot", "bingbot"})
    verified = None
    if outcome == "verified":
        if checked is not None and crawler is not None and raw.get("verified_bot") is True:
            verified = True
        else:
            outcome = "invalid"
    elif outcome == "mismatch":
        if checked is not None and raw.get("verified_bot") is False:
            verified = False
        else:
            outcome = "invalid"
    asn = raw.get("asn")
    country = raw.get("country")
    return {
        "checked_at": checked.isoformat() if checked is not None else None,
        "resolver_outcome": outcome,
        "verified_bot": verified,
        "asn": asn if type(asn) is int and 1 <= asn <= 4_294_967_295 else None,
        "asn_type": _enum(
            raw.get("asn_type"),
            {
                "datacenter",
                "residential",
                "mobile",
                "unknown",
            },
            "unknown",
        ),
        "country": country
        if isinstance(country, str) and re.fullmatch(r"[A-Z]{2}", country)
        else None,
        "asn_origin": _enum(
            raw.get("asn_origin"),
            {
                "curated-prefix",
                "dns",
                "inferred",
                "unknown",
            },
            "unknown",
        ),
        "crawler": crawler,
    }


def _rules(raw: Any, n_requests: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    count, version = raw.get("trap_hits"), raw.get("trap_config_version")
    if (
        raw.get("version") != "bouncer-rule-observations-v1"
        or type(count) is not int
        or not 0 <= count <= n_requests
        or not isinstance(version, str)
        or not re.fullmatch(r"[a-f0-9]{64}", version)
    ):
        return None
    features = {}
    retained_features = raw.get("features", {})
    for key, value in retained_features.items() if isinstance(retained_features, dict) else []:
        if key not in FEATURES:
            continue
        if key in {"ua_is_tool", "ua_claims_bot"}:
            valid = type(value) is bool
        elif key in {"peak_requests_per_min", "vuln_path_hits"}:
            valid = type(value) is int and 0 <= value <= n_requests
        else:
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
            if key.endswith("_share"):
                valid = valid and value <= 1
        if valid:
            features[key] = value
    ids = raw.get("rule_ids", [])
    return {
        "version": "bouncer-rule-observations-v1",
        "trap_hits": count,
        "trap_config_version": version,
        "rule_ids": sorted({key for key in ids if _enum(key, RULE_IDS)})
        if isinstance(ids, list)
        else [],
        "features": features,
    }


def _campaigns(snapshot: dict[str, Any], sessions: list[dict], evidence: list[dict]) -> bool:
    index = {
        str(session.get("id")): (session, item["id"])
        for session, item in zip(sessions, evidence, strict=True)
    }
    complete = len(index) == len(sessions)
    campaigns = snapshot.get("campaigns", [])
    if not isinstance(campaigns, list):
        return False
    for campaign in campaigns:
        if not isinstance(campaign, dict) or not _enum(campaign.get("kind"), CAMPAIGN_KINDS):
            complete = False
            continue
        ids = campaign.get("session_ids")
        if (
            not isinstance(ids, list)
            or not ids
            or any(not isinstance(s, str) for s in ids)
            or len(set(ids)) != len(ids)
            or any(s not in index for s in ids)
        ):
            complete = False
            continue
        if len(ids) < 2:
            complete = False
            continue
        members = [index[s][0] for s in ids]
        targets: Counter[str] = Counter()
        timestamps = []
        failures = 0
        timed = True
        for session in members:
            accounts = set()
            for request in session.get("requests", []):
                timestamp = _utc(request.get("ts"))
                if timestamp is None:
                    timed = False
                else:
                    timestamps.append(timestamp)
                if (
                    str(request.get("path", "")).split("?", 1)[0] == "/login"
                    and str(request.get("method", "")).upper() == "POST"
                    and request.get("status") == 401
                ):
                    failures += 1
                    if isinstance(request.get("username"), str) and request["username"]:
                        accounts.add(request["username"])
            targets.update(accounts)
        if not timed or not timestamps:
            complete = False
        evidence.append(
            {
                "id": f"e{len(evidence) + 1}",
                "kind": "campaign_summary",
                "version": 1,
                "redacted": True,
                "data": {
                    "campaign_ref": hashlib.sha256(
                        str(campaign.get("id", "")).encode()
                    ).hexdigest()[:16],
                    "kind": campaign["kind"],
                    "member_refs": [index[s][1] for s in ids],
                    "n_sessions": len(ids),
                    "distinct_client_count": len({str(s.get("ip")) for s in members}),
                    "failed_logins": failures,
                    "shared_target_count": sum(count >= 2 for count in targets.values()),
                    "window_seconds": (max(timestamps) - min(timestamps)).total_seconds()
                    if timed and timestamps
                    else None,
                    "relationship_provenance": "scoped-requests-v1",
                },
            }
        )
    return complete


def now() -> str:
    return datetime.now(UTC).isoformat()


def traffic_packet(snapshot: dict[str, Any]) -> dict[str, Any]:
    sessions = snapshot.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("sessions must be a list")
    verdicts = snapshot.get("verdicts", {})
    evidence = []
    missing = []
    network = snapshot.get("ip_evidence", {})
    observations = snapshot.get("rule_observations", {})
    labels: Counter[str] = Counter()
    versions: set[str] = set()
    for i, session in enumerate(sessions[:500]):
        requests = session.get("requests", [])
        if not isinstance(requests, list):
            raise ValueError("requests must be a list")
        verdict = verdicts.get(str(session.get("id")), {})
        version = verdict.get("model_version")
        if isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", version):
            versions.add(version)
        label = verdict.get("label", "uncertain")
        if label not in {"human", "good_bot", "bad_bot", "uncertain"}:
            label = "uncertain"
        labels[label] += 1
        categories: Counter[str] = Counter()
        methods: Counter[str] = Counter()
        statuses: Counter[str] = Counter()
        failures = 0
        accounts = set()
        for request in requests:
            path = str(request.get("path", "")).split("?", 1)[0]
            method = str(request.get("method", "")).upper()
            methods[
                method
                if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                else "OTHER"
            ] += 1
            status = request.get("status")
            statuses[
                str(status) if isinstance(status, int) and 100 <= status <= 599 else "unknown"
            ] += 1
            category = (
                "login"
                if path == "/login"
                else "probe"
                if is_vuln_path(path)
                else "static"
                if path.rsplit(".", 1)[-1].lower() in STATIC_EXTENSIONS
                else "other"
            )
            categories[category] += 1
            failures += int(path == "/login" and method == "POST" and status == 401)
            if request.get("username"):
                accounts.add(str(request["username"]))
        score = verdict.get("score")
        data = {
            "session_ref": hashlib.sha256(str(session.get("id", i)).encode()).hexdigest()[:16],
            "n_requests": len(requests),
            "status_counts": dict(statuses),
            "method_counts": dict(methods),
            "path_category_counts": dict(categories),
            "category_provenance": "bouncer-path-categories-v1",
            "failed_logins": failures,
            "distinct_account_count": len(accounts),
            "local_label": label,
            "local_score": score if isinstance(score, (int, float)) and 0 <= score <= 1 else None,
            "verified_bot": None,
        }
        provenance = _network(network.get(session.get("ip"))) if isinstance(network, dict) else None
        if provenance is not None:
            data["network_provenance"] = provenance
            data["verified_bot"] = provenance["verified_bot"]
            data["crawler_verification_origin"] = (
                "forward_reverse_dns" if provenance["verified_bot"] is True else "unknown"
            )
        elif verdict.get("verified_bot") is not None or label == "good_bot":
            message = "Crawler verification provenance was not retained in the legacy snapshot."
            if message not in missing:
                missing.append(message)
        retained = (
            _rules(observations.get(str(session.get("id"))), len(requests))
            if isinstance(observations, dict)
            else None
        )
        if retained is not None:
            data["rule_observations"] = retained
        evidence.append(
            {
                "id": f"e{i + 1}",
                "kind": "session_summary",
                "version": 1,
                "redacted": True,
                "data": data,
            }
        )
    complete = 0 < len(sessions) <= 500 and any(s.get("requests") for s in sessions)
    if not complete:
        missing.append("Evidence is empty or exceeds 500 sessions.")
    if not _campaigns(snapshot, sessions[:500], evidence):
        complete = False
        missing.append("Campaign relationship scope or request timing is incomplete.")
    ingest = snapshot.get("ingest", {})
    if isinstance(ingest, dict) and ingest.get("rotation_gaps", 0) > 0:
        complete = False
        missing.append("Source rotation gaps were observed; traffic evidence is incomplete.")
    limitations = [
        "Local findings describe individual sessions, not every actor.",
        "Detector scores are estimates, not established truth probabilities.",
    ]
    if isinstance(ingest, dict) and ingest.get("discarded_by_retention", 0) > 0:
        limitations.append("Counts describe the retained window, which excludes older traffic.")
    return {
        "synthetic": snapshot.get("synthetic") is True,
        "complete": complete,
        "missing_information": missing,
        "distinct_client_count": len({str(s.get("ip")) for s in sessions}),
        "evidence": evidence,
        "local_assessment": {
            "stage": "local",
            "label": next(iter(labels)) if len(labels) == 1 else "uncertain",
            "score": None,
            "model_version": next(iter(versions))
            if len(versions) == 1
            else "mixed-local-detectors"
            if versions
            else "legacy-traffic-snapshot-v1",
            "label_counts": dict(labels),
            "reasons": [
                f"{n} session(s) received local label {label}."
                for label, n in sorted(labels.items())
            ],
            "evidence_ids": [e["id"] for e in evidence],
            "limitations": limitations,
        },
    }
