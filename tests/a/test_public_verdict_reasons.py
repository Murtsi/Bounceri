import json

from bouncer.api.investigations import public_legacy


def snapshot(label="uncertain", features=None, rule_ids=()):
    return {
        "synthetic": True,
        "sessions": [{"id": "safe-id", "ip": "192.0.2.1", "started_at": "2026-01-01",
                      "ended_at": "2026-01-01", "requests": [{"path": "/private-secret"}] * 5}],
        "verdicts": {"safe-id": {"label": label, "reasons": ["private-secret"],
                                 "model_version": "rules-v2"}},
        "rule_observations": {"safe-id": {"rule_ids": list(rule_ids),
                                           "features": features or {}}},
    }


def test_browser_like_activity_explains_uncertainty_without_changing_truth():
    result = public_legacy(snapshot(features={"static_share": 0.5, "html_share": 0.5}))
    verdict = result["verdicts"]["safe-id"]
    assert verdict["label"] == "uncertain"
    assert "browser assets" in verdict["reasons"][0]
    assert "unverified" in verdict["explanation"]
    assert "private-secret" not in json.dumps(result)


def test_hard_rule_reasons_are_safe_and_observable():
    result = public_legacy(snapshot("bad_bot", rule_ids=("trap", "private-secret")))
    assert "trap" in result["verdicts"]["safe-id"]["reasons"][0]
    assert "private-secret" not in json.dumps(result)


def test_tool_activity_is_not_silently_called_malicious():
    verdict = public_legacy(snapshot(features={"ua_is_tool": True}))["verdicts"]["safe-id"]
    assert verdict["label"] == "uncertain"
    assert "Automated-client" in verdict["reasons"][0]
