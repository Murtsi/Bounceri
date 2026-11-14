"""Bounded, private traffic evidence adapter; simulator truth is never evidence."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from bouncer.session.features import STATIC_EXTENSIONS, is_vuln_path


def now() -> str:
    return datetime.now(UTC).isoformat()


def traffic_packet(snapshot: dict[str, Any]) -> dict[str, Any]:
    sessions = snapshot.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("sessions must be a list")
    verdicts = snapshot.get("verdicts", {})
    evidence = []
    labels: Counter[str] = Counter()
    for i, session in enumerate(sessions[:500]):
        requests = session.get("requests", [])
        if not isinstance(requests, list):
            raise ValueError("requests must be a list")
        verdict = verdicts.get(str(session.get("id")), {})
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
        evidence.append(
            {
                "id": f"e{i + 1}",
                "kind": "session_summary",
                "version": 1,
                "redacted": True,
                "data": data,
            }
        )
    complete = 0 < len(sessions) <= 500
    missing = [] if complete else ["Evidence is empty or exceeds 500 sessions."]
    if any(
        v.get("verified_bot") is not None or v.get("label") == "good_bot" for v in verdicts.values()
    ):
        missing.append("Crawler verification provenance was not retained in the legacy snapshot.")
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
            "model_version": "legacy-traffic-snapshot-v1",
            "label_counts": dict(labels),
            "reasons": [
                f"{n} session(s) received local label {label}."
                for label, n in sorted(labels.items())
            ],
            "evidence_ids": [e["id"] for e in evidence],
            "limitations": [
                "Local findings describe individual sessions, not every actor.",
                "Detector scores are estimates, not established truth probabilities.",
            ],
        },
    }
