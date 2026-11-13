"""S7 explain cache for A API (C-8 prep)."""

from __future__ import annotations

from types import SimpleNamespace

from bouncer.explain import ExplainCache, explanation_cache_key
from bouncer.network.types import make_campaign


def test_cache_key_stable() -> None:
    verdict = SimpleNamespace(label="bad_bot", reasons=["fast crawl"], model_version="rules-v1")
    camp = make_campaign(id="c1", kind="behavior_cluster", session_ids=["1"], reasons=["same paths"])
    a = explanation_cache_key(verdict, camp, model="gemini-2.0-flash")
    b = explanation_cache_key(verdict, camp, model="gemini-2.0-flash")
    assert a == b
    other = explanation_cache_key(verdict, camp, model="other")
    assert a != other


def test_explain_cache_hit() -> None:
    calls = {"n": 0}

    def fake_explain(verdict, session=None, campaign=None, *, use_llm=True) -> str:
        calls["n"] += 1
        return "cached text"

    cache = ExplainCache()
    verdict = SimpleNamespace(label="uncertain", reasons=["missing accept-language"])
    t1 = cache.get_or_explain(fake_explain, verdict, use_llm=False)
    t2 = cache.get_or_explain(fake_explain, verdict, use_llm=False)
    assert t1 == t2 == "cached text"
    assert calls["n"] == 1
    assert cache.hits == 1
    assert cache.misses == 1
