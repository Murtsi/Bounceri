"""S7 explain cache for A API (C-8 prep)."""

from __future__ import annotations

from types import SimpleNamespace

from bouncer.explain import ExplainCache, explanation_cache_key
from bouncer.network.types import make_campaign


def test_cache_key_stable() -> None:
    verdict = SimpleNamespace(label="bad_bot", reasons=["fast crawl"], model_version="rules-v1")
    camp = make_campaign(id="c1", kind="behavior_cluster", session_ids=["1"], reasons=["same paths"])
    a = explanation_cache_key(verdict, camp, model="example/reviewer")
    b = explanation_cache_key(verdict, camp, model="example/reviewer")
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


def test_cache_tracks_configured_provider_and_model(monkeypatch) -> None:
    verdict = SimpleNamespace(label="uncertain", reasons=["fast crawl"])
    monkeypatch.setenv("LLM_PROVIDER", "featherless")
    monkeypatch.setenv("LLM_MODEL", "example/reviewer")
    first = explanation_cache_key(verdict)
    monkeypatch.setenv("LLM_PROVIDER", "hostinger")
    assert explanation_cache_key(verdict) != first
    monkeypatch.setenv("LLM_PROVIDER", "featherless")
    monkeypatch.setenv("LLM_MODEL", "example/other")
    assert explanation_cache_key(verdict) != first
