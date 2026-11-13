"""S7-välimuisti A:n API:lle — yksi LLM-kutsu / verdict+campaign -avain.

Puhdas in-memory helper. A omistaa pysyvän tallennuksen (DB);
tämä estää AI Router -saldon polttamisen saman session uudelleenlatauksissa.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def explanation_cache_key(
    verdict: Any,
    campaign: Any = None,
    *,
    model: str | None = None,
) -> str:
    """Stabilli avain: label + reasons + campaign id/reasons (+ LLM-malli)."""
    payload = {
        "label": _get(verdict, "label", default=None),
        "reasons": list(_get(verdict, "reasons", default=()) or ()),
        "model_version": _get(verdict, "model_version", default=None),
        "campaign_id": _get(campaign, "id", default=None),
        "campaign_reasons": list(_get(campaign, "reasons", default=()) or ()),
        "llm_model": model,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ExplainCache:
    """Prosessin sisäinen välimuisti. Ei jaettu workerien välillä."""

    store: dict[str, str] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def get(self, key: str) -> str | None:
        text = self.store.get(key)
        if text is not None:
            self.hits += 1
        return text

    def put(self, key: str, text: str) -> str:
        self.store[key] = text
        return text

    def get_or_explain(
        self,
        explain_fn: Callable[..., str],
        verdict: Any,
        session: Any = None,
        campaign: Any = None,
        *,
        use_llm: bool = True,
        model: str | None = None,
    ) -> str:
        key = explanation_cache_key(verdict, campaign, model=model)
        cached = self.get(key)
        if cached is not None:
            return cached
        self.misses += 1
        text = explain_fn(verdict, session, campaign, use_llm=use_llm)
        return self.put(key, text)
