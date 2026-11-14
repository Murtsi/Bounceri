"""Read provider metadata without inference, account writes, or automatic activation."""

from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import quote

from .config import TIMEOUT_SECONDS
from .providers import HttpTransport


def discover_featherless(api_key: str, model: str, *, get_json=None) -> dict:
    """Call only documented GET /plan and /models/{id}; omit private account balances.

    This report does not establish no-substitution behavior, structured-schema support,
    a conservative total charge ceiling, or model quality. It never enables review.
    """
    unavailable = {
        "provider": "featherless",
        "model": model,
        "available": False,
        "reason": "metadata_unavailable",
    }
    if (
        not api_key
        or not isinstance(model, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", model)
    ):
        return unavailable | {"reason": "missing_credentials_or_invalid_model"}
    get_json = get_json or HttpTransport().get_json
    headers = {"Authorization": "Bearer " + api_key, "Accept": "application/json"}
    try:
        plan = get_json("https://api.featherless.ai/v1/plan", headers, TIMEOUT_SECONDS)
        detail = get_json(
            "https://api.featherless.ai/v1/models/" + quote(model, safe=""),
            headers,
            TIMEOUT_SECONDS,
        )
        model_context, plan_context = detail["context_length"], plan.get("max_context_length")
        output = detail.get("max_completion_tokens")
        if (
            detail.get("id") != model
            or type(model_context) is not int
            or model_context <= 0
            or "max_completion_tokens" in detail
            and (type(output) is not int or output <= 0)
            or plan_context is not None
            and (type(plan_context) is not int or plan_context <= 0)
        ):
            return unavailable | {"reason": "invalid_metadata"}
        context = min(model_context, plan_context) if plan_context is not None else model_context
        pricing = {}
        for name in ("prompt", "completion", "request"):
            price = Decimal(str(detail.get("pricing", {}).get(name, "NaN")))
            if not price.is_finite() or price < 0:
                return unavailable | {"reason": "invalid_pricing_metadata"}
            pricing[name] = str(price)
        accessible = (
            plan.get("api_access") is True
            and detail.get("available_on_current_plan") is True
            and detail.get("status") == "active"
            and detail.get("is_gated") is False
        )
        return {
            "provider": "featherless",
            "model": model,
            "available": accessible,
            "reason": "metadata_accessible" if accessible else "model_access_not_established",
            "effective_context_length": context,
            "max_completion_tokens": output,
            "output_limit_verified": output is not None,
            "pricing_usd_per_token": {key: pricing[key] for key in ("prompt", "completion")},
            "request_cost_usd": pricing["request"],
            "structured_schema_support": "unverified",
            "activation": "unchanged",
        }
    except Exception:
        # Never surface credential-bearing HTTP exception strings or private provider bodies.
        return unavailable
