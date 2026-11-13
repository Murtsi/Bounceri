"""C-7: explain fallback + grounding guardrail."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from bouncer.explain.explain import explain, explanation_is_grounded, fallback_explain
from bouncer.network.types import Campaign


def test_fallback_includes_reasons_and_campaign() -> None:
    verdict = SimpleNamespace(label="malicious_bot", reasons=["fast crawl", "no CSS"])
    campaign = Campaign(id="camp-9", kind="behavior_cluster", session_ids=[1], reasons=["same paths"])
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
    with patch.dict("os.environ", {"HOSTINGER_AI_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
        text = explain(verdict, use_llm=True)
    assert "missing accept-language" in text
