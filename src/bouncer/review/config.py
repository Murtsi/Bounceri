"""Explicit provider capability declarations. Declarations are not live verification."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

PROMPT_VERSION = "traffic-review-v5"
SCHEMA_VERSION = "traffic-assessment-v1"
MAX_OUTPUT_TOKENS = 800
MAX_REQUEST_BYTES = 24_576
TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str = ""
    expected_model: str = ""
    endpoint: str = ""
    api_key: str = field(default="", repr=False)
    enabled: bool = False
    contract_verified: bool = False
    identity_verified: bool = False
    no_fallback_verified: bool = False
    pricing_verified: bool = False
    limits_verified: bool = False
    maximum_cost_microusd: int = 0
    pricing_version: str = ""

    def capability(self) -> dict:
        reasons = []
        for valid, reason in [
            (self.enabled, "disabled"),
            (bool(self.api_key), "missing_credentials"),
            (bool(self.model and self.expected_model), "unverified_model"),
            (
                "gemini" not in (self.model + self.expected_model).lower()
                and (
                    self.provider != "hostinger"
                    or self.expected_model.lower() == "microsoft-decision-1"
                ),
                "model_excluded_by_backend_policy",
            ),
            (
                self.contract_verified,
                "native_contract_unverified"
                if self.provider == "hostinger"
                else "chat_contract_unverified",
            ),
            (self.identity_verified, "exact_model_unverified"),
            (self.no_fallback_verified, "no_substitution_unverified"),
            (
                self.pricing_verified
                and bool(self.pricing_version)
                and type(self.maximum_cost_microusd) is int
                and self.maximum_cost_microusd > 0,
                "pricing_unverified",
            ),
            (self.limits_verified, "request_and_billing_limits_unverified"),
            (self._endpoint_allowed(), "unsupported_endpoint"),
        ]:
            if not valid:
                reasons.append(reason)
        return {
            "available": not reasons,
            "provider": self.provider,
            "model": self.model or None,
            "reasons": reasons,
            "structured_output": "native_choice"
            if self.provider == "hostinger"
            else "prompt_json_locally_validated",
            "verification": "operator_declared",
        }

    def _endpoint_allowed(self) -> bool:
        try:
            url = urlsplit(self.endpoint)
            if url.scheme != "https" or url.username or url.password or url.query or url.fragment:
                return False
            if url.port not in (None, 443):
                return False
            if self.provider == "hostinger":
                # Exact native route must be supplied after verification, never guessed here.
                return url.hostname == "router.hostinger.com" and url.path not in (
                    "",
                    "/",
                    "/v1",
                    "/v1/chat/completions",
                )
            return self.provider == "featherless" and self.endpoint == (
                "https://api.featherless.ai/v1/chat/completions"
            )
        except ValueError:
            return False


@dataclass(frozen=True)
class ReviewSettings:
    decision: ProviderConfig = field(default_factory=lambda: ProviderConfig("featherless"))
    reviewer: ProviderConfig = field(default_factory=lambda: ProviderConfig("featherless"))
    enabled: bool = False

    @property
    def config_key(self) -> str:
        # Rotating credentials does not change an experiment; routes/models/limits do.
        providers = [
            {
                "provider": cfg.provider,
                "model": cfg.model,
                "expected_model": cfg.expected_model,
                "endpoint": cfg.endpoint,
                "pricing_version": cfg.pricing_version,
                "maximum_cost_microusd": cfg.maximum_cost_microusd,
            }
            for cfg in (self.decision, self.reviewer)
        ]
        payload = json.dumps(
            {
                "providers": providers,
                "prompt": PROMPT_VERSION,
                "schema": SCHEMA_VERSION,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "max_request_bytes": MAX_REQUEST_BYTES,
            },
            sort_keys=True,
        )
        return "cascade-v1:" + hashlib.sha256(payload.encode()).hexdigest()

    @property
    def maximum_cost_microusd(self) -> int:
        return self.decision.maximum_cost_microusd + self.reviewer.maximum_cost_microusd

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ReviewSettings:
        env = os.environ if environ is None else environ

        def read(prefix: str, provider: str, credential: str, endpoint: str = ""):
            def flag(name):
                return env.get(prefix + name, "").lower() == "true"

            try:
                maximum = int(env.get(prefix + "MAXIMUM_COST_MICROUSD", "0"))
            except ValueError:
                maximum = 0
            return ProviderConfig(
                provider=provider,
                model=env.get(prefix + "MODEL", ""),
                expected_model=env.get(prefix + "EXPECTED_MODEL", ""),
                endpoint=env.get(prefix + "ENDPOINT", endpoint),
                api_key=env.get(credential, ""),
                enabled=flag("ENABLED"),
                contract_verified=flag("CONTRACT_VERIFIED"),
                identity_verified=flag("IDENTITY_VERIFIED"),
                no_fallback_verified=flag("NO_FALLBACK_VERIFIED"),
                pricing_verified=flag("PRICING_VERIFIED"),
                limits_verified=flag("LIMITS_VERIFIED"),
                maximum_cost_microusd=maximum,
                pricing_version=env.get(prefix + "PRICING_VERSION", ""),
            )

        decision_provider = env.get("BOUNCERI_DECISION_PROVIDER", "featherless").strip().lower()
        decision_credential = (
            "FEATHERLESS_API_KEY"
            if decision_provider == "featherless"
            else "HOSTINGER_ROUTER_API_KEY"
            if decision_provider == "hostinger"
            else ""
        )
        decision_endpoint = (
            "https://api.featherless.ai/v1/chat/completions"
            if decision_provider == "featherless"
            else ""
        )
        return cls(
            enabled=env.get("BOUNCERI_REVIEW_ENABLED", "").lower() == "true",
            decision=read(
                "BOUNCERI_DECISION_", decision_provider, decision_credential, decision_endpoint
            ),
            reviewer=read(
                "BOUNCERI_REVIEWER_",
                "featherless",
                "FEATHERLESS_API_KEY",
                "https://api.featherless.ai/v1/chat/completions",
            ),
        )


def capabilities(settings: ReviewSettings | None = None) -> dict:
    settings = settings or ReviewSettings.from_env()
    decision, reviewer = settings.decision.capability(), settings.reviewer.capability()
    decision["role"] = "bounded_decision"
    reviewer["role"] = "final_advisory_reviewer"
    return {
        "mode": "experimental",
        "enabled": settings.enabled and decision["available"] and reviewer["available"],
        "decision_model": decision,
        "reviewer": reviewer,
        "configuration_key": settings.config_key,
        "maximum_cost_microusd": settings.maximum_cost_microusd,
        "max_requests": 2,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "limitations": [
            "advisory_only",
            "model_estimates_not_calibrated_truth",
            "evidence_references_are_not_semantic_proof",
        ],
    }
