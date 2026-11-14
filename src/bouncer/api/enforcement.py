"""Authenticated approvals and token-bound probes for controlled synthetic actors."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.exc import SQLAlchemyError

from bouncer.api.investigations import get_store, is_admin, require_admin
from bouncer.enforcement import ACTORS, EnforcementRuntime, actor_secret, verify_token

router = APIRouter()
probe_router = APIRouter()


@lru_cache(maxsize=8)
def _runtime(store):
    return EnforcementRuntime(store)


def get_runtime():
    return _runtime(get_store())


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: Literal["attack", "benign"]
    action: Literal["rate_limit", "temporary_block"]
    ttl_seconds: StrictInt = Field(default=60, ge=1, le=300)
    evidence_version: StrictInt | None = Field(default=None, ge=1)
    evidence_hash: str | None = Field(default=None, max_length=64)


def investigation(case_id, request):
    case = get_store().get_case(case_id, public_only=not is_admin(request))
    if case is None:
        raise HTTPException(404, "Investigation not found")
    return case


@router.post("/api/investigations/{case_id}/enforcements", status_code=201)
def approve(case_id: str, body: Approval, request: Request):
    require_admin(request)
    case = investigation(case_id, request)
    if case.get("source", {}).get("synthetic") is not True:
        raise HTTPException(
            409, "Only controlled synthetic investigations can authorize demo policies"
        )
    if (
        body.evidence_version is not None and body.evidence_version != case["evidence_version"]
    ) or (body.evidence_hash is not None and body.evidence_hash != case["evidence_hash"]):
        raise HTTPException(409, "Evidence version is stale")
    try:
        actor_secret()  # Do not approve a policy when actor authentication cannot operate.
        return get_runtime().approve(
            case_id,
            case["evidence_hash"],
            case["evidence_version"],
            body.actor_id,
            body.action,
            body.ttl_seconds,
        )
    except (SQLAlchemyError, OSError, ValueError) as exc:
        raise HTTPException(503, "Enforcement approval is unavailable") from exc


@router.get("/api/investigations/{case_id}/enforcements")
def list_policies(case_id: str, request: Request):
    investigation(case_id, request)
    try:
        return get_runtime().list_policies(case_id, admin=is_admin(request))
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "Enforcement status is unavailable") from exc


@router.delete("/api/enforcements/{policy_id}")
def revoke(policy_id: str, request: Request):
    require_admin(request)
    try:
        return get_runtime().revoke(policy_id)
    except ValueError as exc:
        raise HTTPException(404, "Policy not found") from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "Enforcement revocation is unavailable") from exc


@probe_router.api_route("/enforcement-demo/{actor_id}/probe", methods=["GET", "POST"])
def probe(actor_id: str, request: Request):
    supplied = request.headers.get("authorization", "")
    try:
        valid = (
            actor_id in ACTORS
            and supplied.startswith("Bearer ")
            and verify_token(actor_id, supplied.removeprefix("Bearer "))
        )
    except ValueError as exc:
        raise HTTPException(503, "Demo actor authentication is unavailable") from exc
    if not valid:
        raise HTTPException(401, "Registered demo actor bearer token required")
    try:
        outcome = get_runtime().probe(actor_id)
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "Controlled demo policy lookup is unavailable") from exc
    code = outcome.pop("status_code")
    retry_after = outcome.pop("retry_after", None)
    headers = {"Cache-Control": "no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(outcome, status_code=code, headers=headers)
