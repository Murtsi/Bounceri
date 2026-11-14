"""C-7: explain fallback + grounding guardrail."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
import sys

from bouncer.explain.explain import _llm_explain, explain, explanation_is_grounded, fallback_explain
from bouncer.network.types import make_campaign


def test_fallback_includes_reasons_and_campaign() -> None:
    verdict = SimpleNamespace(label="malicious_bot", reasons=["fast crawl", "no CSS"])
    campaign = make_campaign(
        id="camp-9",
        kind="behavior_cluster",
        session_ids=["1"],
        reasons=["same paths"],
    )
    text = fallback_explain(verdict, campaign=campaign)
    assert "malicious_bot" in text
    assert "fast crawl" in text
    assert "camp-9" in text


def test_grounding_rejects_invented_facts() -> None:
    reasons = ["fast crawl", "datacenter ASN"]
    assert explanation_is_grounded(
        "Flagged due to fast crawl and datacenter ASN.",
        reasons,
        [],
    )
    assert not explanation_is_grounded(
        "The visitor is a Russian APT using zero-days on WordPress.",
        reasons,
        [],
    )


def test_explain_uses_fallback_without_api_key() -> None:
    verdict = SimpleNamespace(label="uncertain", reasons=["missing accept-language"])
    with patch.dict("os.environ", {}, clear=True):
        text = explain(verdict, use_llm=True)
    assert "missing accept-language" in text


def _fake_client(monkeypatch, *, fail=False):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            calls.append(kwargs)
            if fail:
                raise RuntimeError("provider unavailable")
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fast crawl"))])

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    for key in ["LLM_PROVIDER", "LLM_MODEL", "FEATHERLESS_API_KEY", "HOSTINGER_AI_API_KEY",
                "HOSTINGER_ROUTER_API_KEY", "OPENAI_API_KEY", "HOSTINGER_AI_BASE_URL", "OPENAI_BASE_URL"]:
        monkeypatch.delenv(key, raising=False)
    return calls


def test_featherless_is_default_with_explicit_model(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-token")
    monkeypatch.setenv("LLM_MODEL", "example/reviewer")
    assert _llm_explain("fast crawl") == "fast crawl"
    assert calls[0]["base_url"] == "https://api.featherless.ai/v1"
    assert calls[0]["api_key"] == "test-token"
    assert calls[0]["max_retries"] == 0
    assert calls[1]["model"] == "example/reviewer"
    assert calls[1]["max_tokens"] == 220


def test_missing_model_does_not_call_any_provider(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-token")
    monkeypatch.setenv("HOSTINGER_AI_API_KEY", "test-hostinger-token")
    assert _llm_explain("fast crawl") is None
    assert calls == []


def test_featherless_never_uses_hostinger_credentials_implicitly(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.setenv("HOSTINGER_AI_API_KEY", "test-hostinger-token")
    monkeypatch.setenv("LLM_MODEL", "example/reviewer")
    assert _llm_explain("fast crawl") is None
    assert calls == []


def test_featherless_failure_does_not_fall_through_to_paid_provider(monkeypatch):
    calls = _fake_client(monkeypatch, fail=True)
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-token")
    monkeypatch.setenv("HOSTINGER_AI_API_KEY", "test-hostinger-token")
    monkeypatch.setenv("LLM_MODEL", "example/reviewer")
    assert _llm_explain("fast crawl") is None
    assert len(calls) == 2


def test_explicit_hostinger_provider_remains_supported(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "hostinger")
    monkeypatch.setenv("HOSTINGER_AI_API_KEY", "test-hostinger-token")
    monkeypatch.setenv("LLM_MODEL", "example-model")
    assert _llm_explain("fast crawl") == "fast crawl"
    assert calls[0]["base_url"] == "https://router.hostinger.com/v1"
