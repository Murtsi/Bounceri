"""Observed activity for presentation; never a replacement for classifier labels."""

ACTIVITIES = ("browser_like", "automation_signal", "insufficient_evidence")


def observed_activity(snapshot: dict, sid: str, label: str) -> str | None:
    if label != "uncertain":
        return None
    recorded = snapshot.get("verdicts", {}).get(sid, {}).get("activity")
    if isinstance(recorded, str) and recorded in ACTIVITIES:
        return recorded
    features = snapshot.get("rule_observations", {}).get(sid, {}).get("features", {})
    if features.get("ua_is_tool") is True:
        return "automation_signal"
    if all(type(features.get(key)) in (int, float) and 0 < features[key] <= 1
           for key in ("static_share", "html_share")):
        return "browser_like"
    return "insufficient_evidence"
