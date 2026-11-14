"""Case API plus public projections of the legacy dashboard data."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from contextvars import ContextVar
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, ValidationError

from bouncer.contracts import IpIntel
from bouncer.db.store import _read_raw, _serialize_session, store_path
from bouncer.ingest.sample import load_sample_data
from bouncer.investigations import InvestigationStore
from bouncer.session import score
from bouncer.session.features import is_vuln_path

router = APIRouter()
admin_context: ContextVar[bool] = ContextVar("bouncer_admin", default=False)
MAX_IMPORT_BYTES = 10 * 1024 * 1024


def is_admin(request: Request) -> bool:
    token = os.getenv("BOUNCER_ADMIN_TOKEN", "")
    supplied = request.headers.get("authorization", "")
    return bool(token) and hmac.compare_digest(supplied, "Bearer " + token)


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(401, "Administrator bearer token required")


@lru_cache(maxsize=8)
def _database(url: str) -> InvestigationStore:
    return InvestigationStore(url)


def get_store() -> InvestigationStore:
    default = Path(os.getenv("BOUNCER_STORE_PATH", ".bouncer_store.json")).resolve().parent
    url = os.getenv("BOUNCER_DATABASE_URL", f"sqlite:///{default / 'investigations.sqlite3'}")
    return _database(url)


def review_configuration():
    """Load the review worker's single configuration contract, when installed."""
    try:
        from bouncer.review import ReviewSettings
        from bouncer.review import capabilities as review_capabilities
    except ModuleNotFoundError as exc:
        if exc.name != "bouncer.review":
            raise
        return None, {"enabled": False, "reason": "review_worker_not_installed"}
    settings = ReviewSettings.from_env()
    return settings, review_capabilities(settings)


def paid_enabled() -> bool:
    return bool(review_configuration()[1]["enabled"])


def public_legacy(snapshot: dict) -> dict:
    """Project before enrichment so generated prose cannot leak raw identifiers."""
    if snapshot.get("synthetic") is not True:
        return {
            "sessions": [],
            "campaigns": [],
            "verdicts": {},
            "labels": [],
            "synthetic": False,
            "source": "Private monitored traffic",
        }
    sessions = []
    verdicts = {}
    for source in snapshot.get("sessions", []):
        sid = str(source["id"])
        # Preserve existing hashed session references; no raw identifier is used in prose.
        client = "client-" + hashlib.sha256(str(source.get("ip", "")).encode()).hexdigest()[:10]
        requests = []
        for request in source.get("requests", []):
            path = str(request.get("path", ""))
            # Fixed allowlist preserves useful demo paths; arbitrary private paths stay hidden.
            public_path = (
                path
                if path in {"/", "/login", "/robots.txt", "/.env", "/.git/config"}
                else "/[probe]"
                if is_vuln_path(path)
                else "/[redacted]"
            )
            requests.append(
                {
                    "ts": request.get("ts", source.get("started_at")),
                    "method": request.get("method")
                    if request.get("method")
                    in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                    else "OTHER",
                    "path": public_path,
                    "status": request.get("status"),
                    "username": None,
                    "content_type": None,
                }
            )
        sessions.append(
            {
                "id": sid,
                "ip": client,
                "user_agent": "Redacted demo client",
                "started_at": source["started_at"],
                "ended_at": source["ended_at"],
                "requests": requests,
            }
        )
        verdict = snapshot.get("verdicts", {}).get(sid, {})
        label = verdict.get("label", "uncertain")
        if label not in {"human", "good_bot", "bad_bot", "uncertain"}:
            label = "uncertain"
        verdicts[sid] = {
            "label": label,
            "score": verdict.get("score"),
            "reasons": [f"Local detector label: {label}."],
            "explanation": f"Local detector label: {label}; advisory finding.",
            "model_version": "local-detector",
            "campaign_id": verdict.get("campaign_id"),
            "action": verdict.get("action")
            if verdict.get("action") in {"monitor", "block", "rate_limit", "challenge"}
            else "monitor",
        }
    campaigns = []
    for campaign in snapshot.get("campaigns", []):
        kind = campaign.get("kind")
        if kind not in {"credential_stuffing", "distributed_login_spray", "behavior_cluster"}:
            kind = "behavior_cluster"
        campaigns.append(
            {
                "id": campaign["id"],
                "kind": kind,
                "session_ids": campaign.get("session_ids", []),
                "size": len(campaign.get("session_ids", [])),
                "reasons": ["Local cross-session relationship; attribution remains uncertain."],
            }
        )
    safe_classes = {
        "human",
        "human_browser",
        "scraper",
        "scanner",
        "fake_googlebot",
        "credential_stuffing",
        "distributed_login_spray",
        "good_bot",
    }
    labels = [
        {"session_id": label["session_id"], "sim_class": label["sim_class"]}
        for label in snapshot.get("labels", [])
        if label.get("session_id") and label.get("sim_class") in safe_classes
    ]
    ingest = snapshot.get("ingest", {})
    return {
        "synthetic": True,
        "source": "Controlled synthetic demonstration",
        "sessions": sessions,
        "verdicts": verdicts,
        "campaigns": campaigns,
        "labels": labels,
        "ingest": {key: ingest[key] for key in ("updated_at", "unsigned_markers") if key in ingest},
    }


class CreateCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["monitored_traffic", "fixture"]
    source_key: str = "overview"
    public_demo: bool = False


@router.get("/api/capabilities")
def capabilities():
    return {
        "modules": [
            {"id": "clean_the_traffic", "implemented": True, "enabled": True},
            *[
                {"id": module, "implemented": False, "enabled": False}
                for module in ("spot_the_swarm", "name_the_technique", "trust_the_source")
            ],
        ],
        "paid_review_enabled": paid_enabled(),
        "review_status": "configured" if paid_enabled() else "unavailable",
        "enforcement": {"requires_admin": True, "advisory_default": True},
        "providers": review_configuration()[1],
    }


@router.post("/api/investigations", status_code=201)
async def create_case(request: Request):
    require_admin(request)
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > MAX_IMPORT_BYTES:
            raise HTTPException(413, "Import exceeds 10 MB")
    try:
        body = CreateCase.model_validate(json.loads(chunks))
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(
            422, "Supported source: monitored_traffic or repository fixture"
        ) from exc
    if len(body.source_key) > 128:
        raise HTTPException(422, "Source key exceeds 128 characters")
    if body.source == "fixture":
        sessions, _ = load_sample_data()
        snapshot = {
            "synthetic": True,
            "sessions": [_serialize_session(s) for s in sessions],
            "verdicts": {s.id: asdict(score(s, IpIntel(), None)) for s in sessions},
        }
        source_key = "fixture"
    else:
        snapshot, source_key = _read_raw(store_path()), body.source_key
    try:
        return get_store().create_from_legacy(snapshot, source_key, body.public_demo)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/investigations")
def list_cases(request: Request):
    return [
        {k: v for k, v in case.items() if k != "evidence"}
        for case in get_store().list_cases(public_only=not is_admin(request))
    ]


def visible_case(case_id: str, request: Request):
    case = get_store().get_case(case_id, public_only=not is_admin(request))
    if case is None:
        raise HTTPException(404, "Investigation not found")
    return case


@router.get("/api/investigations/{case_id}")
def get_case(case_id: str, request: Request):
    return visible_case(case_id, request)


@router.get("/api/investigations/{case_id}/assessments")
def list_assessments(case_id: str, request: Request):
    visible_case(case_id, request)
    return get_store().list_assessments(case_id)


@router.post("/api/investigations/{case_id}/reviews", status_code=202)
def request_review(case_id: str, request: Request):
    require_admin(request)
    visible_case(case_id, request)
    settings, capability = review_configuration()
    if not capability["enabled"] or settings is None:
        raise HTTPException(503, {"status": "unavailable", "reason": "Paid review is disabled"})
    try:
        job = get_store().enqueue_review(
            case_id,
            settings.config_key,
            settings.maximum_cost_microusd,
            max_requests=capability.get("max_requests", 2),
        )
    except ValueError as exc:
        raise HTTPException(409, {"status": "deferred_budget", "reason": str(exc)}) from exc
    return {"job_id": job["id"], "status": job["status"], "cached": job["status"] == "completed"}


@router.get("/api/usage")
def usage():
    return {**get_store().usage(), "paid_review_enabled": paid_enabled()}
