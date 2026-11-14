"""Authenticated bounded native-log imports; no provider or enforcement calls."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import threading
import uuid
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from bouncer.api.investigations import get_store, require_admin
from bouncer.ingest.import_analysis import AnalysisError, analyze_import
from bouncer.ingest.imports import MAX_INPUT_BYTES, ImportLimitError, parse_import
from bouncer.review.validation import strict_json

router = APIRouter()
UPLOAD_SECONDS = 10
IMPORT_SLOT = asyncio.Semaphore(1)
IMPORT_JOB = threading.Lock()


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["owner_log", "public_dataset", "consented_input"]
    permission_confirmed: StrictBool
    source_url: str | None = Field(default=None, max_length=2048)
    license: str | None = Field(default=None, min_length=1, max_length=128)
    consent_reference: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def complete(self):
        if not self.permission_confirmed:
            raise ValueError("permission acknowledgment required")
        if self.kind == "public_dataset" and not (self.source_url and self.license):
            raise ValueError("public data requires source and terms")
        if self.kind == "consented_input" and not self.consent_reference:
            raise ValueError("consented input requires a reference")
        if self.source_url:
            url = urlsplit(self.source_url)
            if url.scheme != "https" or not url.hostname:
                raise ValueError("source requires an HTTPS reference")
            # Source references are metadata only; the importer never fetches them.
            host = f"[{url.hostname}]" if ":" in url.hostname else url.hostname
            port = f":{url.port}" if url.port not in (None, 443) else ""
            self.source_url = urlunsplit((url.scheme, host + port, url.path, "", ""))
        return self


class ImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format: Literal["caddy_jsonl", "normalized_jsonl", "nginx_combined", "apache_combined"]
    data: str = Field(max_length=MAX_INPUT_BYTES)
    provenance: Provenance
    synthetic: StrictBool = False
    public_demo: StrictBool = False


def _import(body: ImportBody):
    parsed = parse_import(
        body.data.encode("utf-8"), body.format, pseudonym_key=secrets.token_bytes(32)
    )
    if not parsed.records:
        raise HTTPException(422, {"code": "no_valid_records", "report": parsed.report})
    snapshot = analyze_import(parsed.records, body.synthetic)
    provenance = body.provenance.model_dump(exclude_none=True)
    reference = provenance.pop("consent_reference", None)
    if reference:
        provenance["consent_reference_sha256"] = hashlib.sha256(reference.encode()).hexdigest()
    provenance["permission_status"] = "owner_attested_not_independent_truth"
    provenance["format"] = body.format
    provenance["content_sha256"] = hashlib.sha256(body.data.encode("utf-8")).hexdigest()
    source_key = "import/" + uuid.uuid4().hex
    case = get_store().create_traffic_import(
        snapshot, source_key=source_key, report=parsed.report, provenance=provenance,
        public_demo=body.public_demo,
    )
    return {"case": case, "source_key": source_key, "report": parsed.report}


def _guarded_import(body: ImportBody):
    # A disconnected request must not release capacity while its thread still owns the job.
    if not IMPORT_JOB.acquire(blocking=False):
        raise HTTPException(429, {"code": "import_busy"}, headers={"Retry-After": "1"})
    try:
        return _import(body)
    finally:
        IMPORT_JOB.release()


@router.post("/api/imports/traffic", status_code=201)
async def import_traffic(request: Request):
    require_admin(request)
    if IMPORT_SLOT.locked() or IMPORT_JOB.locked():
        raise HTTPException(429, {"code": "import_busy"}, headers={"Retry-After": "1"})
    async with IMPORT_SLOT:
        return await _consume_import(request)


async def _consume_import(request: Request):
    data = bytearray()
    try:
        async with asyncio.timeout(UPLOAD_SECONDS):
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_INPUT_BYTES:
                    raise HTTPException(413, {"code": "upload_too_large"})
                data.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(408, {"code": "upload_timeout"}) from exc
    try:
        body = ImportBody.model_validate(strict_json(data.decode("utf-8")))
    except (ValidationError, ValueError, TypeError, RecursionError) as exc:
        raise HTTPException(422, {"code": "invalid_import_contract"}) from exc
    if body.public_demo and not body.synthetic:
        raise HTTPException(422, {"code": "publication_requires_synthetic"})
    try:
        return await run_in_threadpool(_guarded_import, body)
    except ImportLimitError as exc:
        raise HTTPException(413, {"code": exc.code}) from exc
    except AnalysisError as exc:
        raise HTTPException(422, {"code": "analysis_unavailable"}) from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, {"code": "import_storage_unavailable"}) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, {"code": "invalid_import_data"}) from exc
