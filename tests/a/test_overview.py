"""Omistajan yleiskuva (/api/overview) ja toimenpidesuositukset."""

import pytest

from bouncer.api.overview import MIN_POINTS, enrich_campaigns, overview, step_for, timeline
from bouncer.session.actions import recommend


def _s(sid, ip, start, end=None, reqs=None):
    end = end or start
    return {"id": sid, "ip": ip, "user_agent": "curl/8.5.0", "started_at": start, "ended_at": end,
            "requests": reqs or [{"ts": start, "method": "GET", "path": "/", "status": 200,
                                  "username": None}]}  # fmt: skip


def _login(sid, ip, ts):
    return _s(sid, ip, ts, reqs=[{"ts": ts, "method": "POST", "path": "/login", "status": 401,
                                  "username": "admin"}])  # fmt: skip


T = "2026-11-14T12:00:{:02d}+00:00"
STORE = {
    "synthetic": True,
    "sessions": [
        *(_login(f"st{i}", f"203.0.113.{100 + i}", T.format(5 * i)) for i in range(4)),
        _s("scan", "203.0.113.24", T.format(1), T.format(3)),
        _s("h1", "198.51.100.10", T.format(0), T.format(50)),
        _s("h2", "198.51.100.11", T.format(2), T.format(40)),
    ],
    "labels": [
        {"session_id": "h1", "run_id": "r", "sim_class": "human", "campaign_id": None},
        {"session_id": "h2", "run_id": "r", "sim_class": "human_playwright", "campaign_id": None},
    ],
    "verdicts": {
        **{f"st{i}": {"label": "bad_bot", "rule_id": "login_attack_campaign",
                      "action": "rate_limit",
                      "reasons": ["x"]} for i in range(4)},
        "scan": {"label": "bad_bot", "rule_id": "vuln_paths", "action": "block",
                 "reasons": ["Probed 7 known vulnerability paths"]},
        "h1": {"label": "uncertain", "rule_id": None, "action": "monitor", "reasons": ["y"]},
        "h2": {"label": "bad_bot", "rule_id": None, "action": "challenge", "reasons": ["z"]},
    },
    "campaigns": [
        {"id": "stuffing:admin", "kind": "credential_stuffing",
         "session_ids": ["st0", "st1", "st2", "st3"],
         "reasons": ["username 'admin' failed from 4 IPs"],
         "size": 4},
        {"id": "behavior:1", "kind": "behavior_cluster", "session_ids": ["h1", "h2"], "reasons": [],
         "size": 2},
    ],
}  # fmt: skip


@pytest.mark.parametrize(
    ("label", "rule", "action"),
    [("bad_bot", "login_attack_campaign", "rate_limit"), ("bad_bot", "vuln_paths", "block"),
     ("bad_bot", "fake_crawler", "block"), ("bad_bot", "trap", "block"),
     ("bad_bot", None, "challenge"), ("uncertain", None, "monitor"),
     ("good_bot", "verified_crawler", "none"), ("human", None, "none")],
)  # fmt: skip
def test_recommend(label, rule, action):
    assert recommend(label, rule) == action


def test_login_campaign_is_an_active_alert_with_readable_title():
    o = overview(STORE)
    assert len(o["alerts"]) == 1
    a = o["alerts"][0]
    assert a["title"].startswith("Coordinated login attack: account “admin”")
    assert a["n_ips"] == 4 and a["duration_s"] == 15 and a["action"] == "rate_limit"


def test_behavior_cluster_is_never_an_alert():
    camps = enrich_campaigns(STORE)
    beh = next(c for c in camps if c["kind"] == "behavior_cluster")
    assert beh["login_attack"] is False and beh["action"] == "monitor"
    assert all(a["kind"] != "behavior_cluster" for a in overview(STORE)["alerts"])


def test_actors_group_the_campaign_and_list_others_by_ip():
    actors = overview(STORE)["actors"]
    assert actors[0]["kind"] == "campaign"
    titles = [a["title"] for a in actors]
    assert "Vulnerability scanner · 203.0.113.24" in titles
    assert sum(a["kind"] == "campaign" for a in actors) == 1  # 4 sessiota → yksi toimija


def test_honesty_counts_labelled_humans_only_and_reports_upper_bound():
    h = overview(STORE)["honesty"]
    assert h["n_humans"] == 2 and h["false_alarms"] == 1  # h2 merkittiin botiksi
    assert h["synthetic"] is True and h["fpr_ci95_upper"] > h["fpr"]


def test_timeline_adapts_step_to_short_runs():
    # Ikkuna 12:00:00 → 12:00:50 (= viimeisen session loppu) → 2 s palkit, tiheä sarja
    assert step_for(STORE) == 2
    assert step_for(STORE, buckets=5) == 10  # sama ikkuna harvemmilla palkeilla → 10 s
    tl = timeline(STORE)
    # Tyhjät palkit alusta pois; ensimmäinen palkki sisältää dataa
    assert tl["step_s"] == 2 and len(tl["points"]) >= MIN_POINTS
    assert any(tl["points"][0][lab] for lab in ("human", "good_bot", "uncertain", "bad_bot"))
    total = sum(
        p[lab] for p in tl["points"] for lab in ("human", "good_bot", "uncertain", "bad_bot")
    )
    assert total == 7  # jokainen pyyntö lasketaan kerran


def test_activity_graph_splits_uncertainty_without_changing_classifier_counts():
    from bouncer.api.investigations import public_legacy

    labels = {"browser": "uncertain", "tool": "uncertain", "missing": "uncertain",
              "human": "human", "crawler": "good_bot", "attack": "bad_bot"}
    store = {
        "synthetic": True,
        "sessions": [_s(sid, "192.0.2.1", T.format(1)) for sid in labels],
        "verdicts": {sid: {"label": label} for sid, label in labels.items()},
        "rule_observations": {
            "browser": {"features": {"static_share": 0.4, "html_share": 0.6}},
            "tool": {"features": {"ua_is_tool": True}},
            "attack": {"features": {"static_share": 0.4, "html_share": 0.6}},
        },
    }
    for snapshot in (store, public_legacy(store)):
        result = overview(snapshot)
        assert result["distribution"]["uncertain"] == 3
        timeline = result["timeline"]
        assert sum(point["uncertain"] for point in timeline["points"]) == 3
        activity = timeline["activity_points"]
        assert [point["t"] for point in activity] == [p["t"] for p in timeline["points"]]
        for category in ("human", "good_bot", "bad_bot", "browser_like",
                         "automation_signal", "insufficient_evidence"):
            assert sum(point[category] for point in activity) == 1
        assert sum(sum(value for key, value in point.items() if key != "t")
                   for point in activity) == 6


def test_empty_store():
    o = overview({"sessions": [], "verdicts": {}, "campaigns": [], "labels": []})
    assert o["n_sessions"] == 0 and o["alerts"] == [] and o["timeline"]["points"] == []
