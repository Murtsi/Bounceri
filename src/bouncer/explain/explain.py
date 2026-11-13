"""S7 — `explain(verdict, session, campaign) -> str` (C-7).

LLM (Hostinger AI Router) vain syiden pohjalta. Jos avain puuttuu / kutsu
epäonnistuu / malli hallusinoi → varateksti reasons-kentistä.
"""

from __future__ import annotations

import os
import re
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


def _reasons_from(verdict: Any) -> list[str]:
    reasons = _get(verdict, "reasons", default=None)
    if not reasons:
        return []
    return [str(r) for r in reasons]


def _campaign_bits(campaign: Any) -> tuple[str | None, list[str]]:
    if campaign is None:
        return None, []
    camp_id = _get(campaign, "id", default=None)
    camp_reasons = _get(campaign, "reasons", default=None) or []
    return (
        str(camp_id) if camp_id is not None else None,
        [str(r) for r in camp_reasons],
    )


def fallback_explain(
    verdict: Any,
    session: Any = None,
    campaign: Any = None,
) -> str:
    """Sääntöpohjainen selitys — aina turvallinen, ei LLM:ää."""
    _ = session
    reasons = _reasons_from(verdict)
    parts: list[str] = []
    label = _get(verdict, "label", default=None)
    if label:
        parts.append(f"Verdict: {label}.")
    if reasons:
        parts.append("Reasons: " + "; ".join(reasons) + ".")
    else:
        parts.append("No scoring reasons available yet.")

    camp_id, camp_reasons = _campaign_bits(campaign)
    if camp_id:
        parts.append(f"Campaign {camp_id}.")
    if camp_reasons:
        parts.append("Campaign signals: " + "; ".join(camp_reasons) + ".")
    return " ".join(parts)


def _allowed_tokens(reasons: list[str], camp_reasons: list[str]) -> set[str]:
    text = " ".join(reasons + camp_reasons).lower()
    return {t for t in re.findall(r"[a-z0-9_./'-]+", text) if len(t) > 2}


def explanation_is_grounded(text: str, reasons: list[str], camp_reasons: list[str]) -> bool:
    """Karkea hallusinaatioeste: numeroiden/sanojen pitää esiintyä syissä.

    Ei täydellinen NLP — hackathon-guardrail. Jos syitä ei ole, LLM-teksti hylätään.
    """
    if not reasons and not camp_reasons:
        return False
    allowed = _allowed_tokens(reasons, camp_reasons)
    # Extract content words from explanation longer than 3 chars
    words = [w for w in re.findall(r"[a-z0-9_./'-]+", text.lower()) if len(w) > 3]
    if not words:
        return False
    # Stopwords that may appear in any explanation
    stop = {
        "this",
        "that",
        "with",
        "from",
        "have",
        "been",
        "were",
        "which",
        "session",
        "visitor",
        "traffic",
        "because",
        "suggest",
        "recommend",
        "action",
        "likely",
        "appears",
        "based",
        "reasons",
        "campaign",
        "verdict",
        "human",
        "bot",
        "malicious",
        "benign",
        "uncertain",
        "should",
        "monitor",
        "block",
        "challenge",
        "rate-limit",
        "rate",
        "limit",
    }
    content = [w for w in words if w not in stop]
    if not content:
        return True
    grounded = sum(1 for w in content if w in allowed or any(w in a for a in allowed))
    return (grounded / len(content)) >= 0.4


def _llm_explain(prompt: str) -> str | None:
    api_key = (
        os.getenv("HOSTINGER_AI_API_KEY")
        or os.getenv("HOSTINGER_ROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key:
        return None
    # Docs: https://router.hostinger.com/v1 (OpenAI-compatible)
    base_url = os.getenv(
        "HOSTINGER_AI_BASE_URL",
        os.getenv("OPENAI_BASE_URL", "https://router.hostinger.com/v1"),
    )
    model = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=220,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You explain bot-detection verdicts for a site owner. "
                        "Use ONLY the provided reasons. Do not invent IPs, counts, "
                        "or facts. Two short sentences + one recommended action "
                        "(monitor|rate-limit|challenge|block)."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except Exception:
        return None


def explain(
    verdict: Any,
    session: Any = None,
    campaign: Any = None,
    *,
    use_llm: bool = True,
) -> str:
    """Selitä päätös. LLM vain jos saatavilla ja grounded; muuten fallback."""
    reasons = _reasons_from(verdict)
    camp_id, camp_reasons = _campaign_bits(campaign)
    fallback = fallback_explain(verdict, session, campaign)

    if not use_llm:
        return fallback

    label = _get(verdict, "label", default="unknown")
    prompt_lines = [f"Label: {label}", "Reasons:"]
    if reasons:
        prompt_lines.extend(f"- {r}" for r in reasons)
    else:
        prompt_lines.append("- (none)")
    if camp_id:
        prompt_lines.append(f"Campaign: {camp_id}")
        prompt_lines.extend(f"- {r}" for r in camp_reasons)

    llm_text = _llm_explain("\n".join(prompt_lines))
    if not llm_text:
        return fallback
    if not explanation_is_grounded(llm_text, reasons, camp_reasons):
        return fallback
    return llm_text
