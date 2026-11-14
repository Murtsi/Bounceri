"""One claimed job, at most two reserved requests, no retries or fallback."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from .config import (
    MAX_OUTPUT_TOKENS,
    MAX_REQUEST_BYTES,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    TIMEOUT_SECONDS,
    ReviewSettings,
)
from .providers import (
    HttpTransport,
    decision_request,
    parse_decision_response,
    parse_reviewer_response,
    reviewer_request,
    usage_summary,
)
from .validation import validate_packet


class ReviewStore(Protocol):
    def claim_job(self, worker_id: str) -> dict | None: ...
    def review_packet(self, job_id: str) -> dict: ...
    def start_request(
        self,
        job_id: str,
        stage: str,
        provider: str,
        model: str,
        maximum_cost_microusd: int,
        pricing_version: str,
    ) -> dict: ...
    def settle_request(
        self,
        reservation_id: str,
        actual_cost_microusd: int | None,
        usage: dict,
        provider_request_id: str | None,
    ): ...
    def append_assessment(self, job_id: str, stage: str, payload: dict, metadata: dict): ...
    def finish_job(self, job_id: str, status: str, reason: str = ""): ...


class ReviewRunner:
    def __init__(
        self,
        store: ReviewStore,
        settings: ReviewSettings | None = None,
        *,
        transport=None,
        worker_id: str = "review-worker-1",
    ):
        self.store = store
        self.settings = settings or ReviewSettings.from_env()
        self.transport = transport or HttpTransport()
        self.worker_id = worker_id

    def run_once(self) -> bool:
        job = self.store.claim_job(self.worker_id)
        if job is None:
            return False
        job_id = job["id"]
        if job.get("config_key") != self.settings.config_key:
            self.store.finish_job(job_id, "unavailable", "configuration_mismatch")
            return True
        if not self.settings.enabled:
            self.store.finish_job(job_id, "unavailable", "paid_review_disabled")
            return True
        for cfg in (self.settings.decision, self.settings.reviewer):
            reasons = cfg.capability()["reasons"]
            if reasons:
                self.store.finish_job(job_id, "unavailable", ",".join(reasons))
                return True
        try:
            packet = validate_packet(self.store.review_packet(job_id))
        except (ValueError, TypeError, KeyError, OverflowError):
            self.store.finish_job(job_id, "unavailable", "invalid_evidence_packet")
            return True
        decision = self._stage(job_id, "decision_model", self.settings.decision, packet)
        if decision is None:
            return True
        reviewer = self._stage(job_id, "reviewer", self.settings.reviewer, packet, decision)
        if reviewer is not None:
            self.store.finish_job(job_id, "completed")
        return True

    def _stage(self, job_id, stage, cfg, packet, decision=None):
        body = (
            decision_request(cfg.model, packet)
            if stage == "decision_model"
            else reviewer_request(cfg.model, packet, decision)
        )
        if len(json.dumps(body, allow_nan=False).encode()) > MAX_REQUEST_BYTES:
            self.store.finish_job(job_id, "unavailable", "request_too_large")
            return None
        # Enqueue already reserved the whole job. start_request atomically consumes a slice
        # of that reservation AND counts a dispatch; it must succeed before network access.
        try:
            reservation = self.store.start_request(
                job_id,
                stage,
                cfg.provider,
                cfg.model,
                cfg.maximum_cost_microusd,
                cfg.pricing_version,
            )
        except ValueError:
            self.store.finish_job(job_id, "deferred_budget", "request_reservation_denied")
            return None
        reservation_id = reservation["id"]
        try:
            response = self.transport(
                cfg.endpoint,
                {
                    "Authorization": "Bearer " + cfg.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-Title": "Bounceri",
                },
                body,
                TIMEOUT_SECONDS,
            )
        except Exception:
            # Do not log exception text: providers/HTTP clients can include credentials,
            # request bodies, or arbitrary remote content. Unknown outcome remains held.
            self.store.settle_request(reservation_id, None, {}, None)
            self.store.finish_job(job_id, "unavailable", "provider_request_failed_unknown_charge")
            return None
        actual, usage, request_id = usage_summary(response, cfg.provider)
        self.store.settle_request(reservation_id, actual, usage, request_id)
        if stage == "reviewer" and usage.get("completion_tokens", 0) > MAX_OUTPUT_TOKENS:
            self.store.finish_job(job_id, "unavailable", "provider_output_limit_exceeded")
            return None
        if actual is not None and actual > cfg.maximum_cost_microusd:
            self.store.finish_job(
                job_id, "unavailable", "provider_charge_exceeded_verified_maximum"
            )
            return None
        try:
            result = (
                parse_decision_response(response, cfg.expected_model)
                if stage == "decision_model"
                else parse_reviewer_response(response, packet, cfg.expected_model)
            )
        except (ValueError, KeyError, TypeError):
            reason = (
                "model_identity_mismatch"
                if response.get("model") != cfg.expected_model
                else "invalid_decision_output"
                if stage == "decision_model"
                else "invalid_reviewer_output"
            )
            self.store.finish_job(job_id, "unavailable", reason)
            return None
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "evidence_hash": packet["evidence_hash"],
                    "stage": stage,
                    "configuration": self.settings.config_key,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        self.store.append_assessment(
            job_id,
            stage,
            result,
            {
                "provider": cfg.provider,
                "model": cfg.model,
                "returned_model": cfg.expected_model,
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "pricing_version": cfg.pricing_version,
                "evidence_hash": packet["evidence_hash"],
                "evidence_version": packet["evidence_version"],
                "cache_key": cache_key,
                "provider_request_id": request_id,
                "reservation_id": reservation_id,
                "advisory_only": True,
                "validation": "typed_facts_checked_not_semantic_proof",
            },
        )
        return result
