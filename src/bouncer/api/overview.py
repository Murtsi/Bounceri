"""Sivuston omistajan yleiskuva workerin storesta (puhtaita funktioita, ei I/O:ta).

"Nyt" = uusimman pyynnön aika storessa (ei seinäkello), jotta tallennettu demoajo
näyttää samalta myöhemminkin. Luvut ovat laskettuja suoraan päätöksistä; mitään
ei arvata. Simuloidun ajon väärät hälytykset raportoidaan aina erikseen ja
merkittynä simuloiduiksi (AGENTS.md §7).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from bouncer.eval.evaluate import wilson_upper
from bouncer.session.actions import ACTION_TEXT, recommend
from bouncer.session.rules import LOGIN_ATTACK_CAMPAIGNS

LABELS = ("human", "good_bot", "uncertain", "bad_bot")
#: Kampanja on "käynnissä", jos sen viimeinen pyyntö on näin lähellä uusinta pyyntöä.
ACTIVE_WINDOW = timedelta(minutes=10)

_TITLES = {
    "credential_stuffing": "Coordinated login attack",
    "distributed_login_spray": "Distributed login spray",
    "behavior_cluster": "Group behaving alike",
}
_ACTOR_TITLE = {
    "fake_crawler": "Fake search-engine bot",
    "vuln_paths": "Vulnerability scanner",
    "trap": "Bot caught in a trap",
}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _now(st: dict[str, Any]) -> datetime | None:
    ends = [_dt(s["ended_at"]) for s in st.get("sessions", [])]
    return max(ends) if ends else None


def _username(sessions: list[dict[str, Any]]) -> str | None:
    names = Counter(r["username"] for s in sessions for r in s["requests"] if r.get("username"))
    return names.most_common(1)[0][0] if names else None


def enrich_campaigns(st: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {s["id"]: s for s in st.get("sessions", [])}
    verdicts = st.get("verdicts", {})
    now = _now(st)
    out = []
    for c in st.get("campaigns", []):
        members = [by_id[sid] for sid in c["session_ids"] if sid in by_id]
        if not members:
            continue
        started = min(_dt(s["started_at"]) for s in members)
        last = max(_dt(s["ended_at"]) for s in members)
        labels = Counter(verdicts.get(s["id"], {}).get("label", "uncertain") for s in members)
        login = c["kind"] in LOGIN_ATTACK_CAMPAIGNS
        user = _username(members) if login else None
        n_ips = len({s["ip"] for s in members})
        title = _TITLES.get(c["kind"], c["kind"])
        if user:
            title += f": account “{user}” tried from {n_ips} different IPs"
        else:
            title += f" ({n_ips} IPs)"
        action = "rate_limit" if login else "monitor"
        out.append({
            **c,
            "title": title,
            "login_attack": login,
            "username": user,
            "n_ips": n_ips,
            "started_at": started.isoformat(),
            "last_seen": last.isoformat(),
            "duration_s": (last - started).total_seconds(),
            "active": now is not None and now - last <= ACTIVE_WINDOW,
            "labels": dict(labels),
            "action": action,
            "action_text": ACTION_TEXT[action],
        })  # fmt: skip
    return sorted(out, key=lambda c: (not c["login_attack"], -c["size"]))


#: Palkin pituudet (s); valitaan lyhin, jolla `BUCKETS` palkkia kattaa datan keston.
STEPS_S = (1, 2, 5, 10, 30, 60, 300, 900)
BUCKETS = 40
MIN_POINTS = 12


def step_for(st: dict[str, Any], buckets: int = BUCKETS) -> int:
    times = [_dt(r["ts"]) for s in st.get("sessions", []) for r in s["requests"]]
    if not times:
        return STEPS_S[0]
    # Ikkuna päättyy hetkeen "nyt" (_now), joten kesto mitataan siitä, ei viimeisestä pyynnöstä.
    end = max([*times, _now(st) or max(times)])
    span = (end - min(times)).total_seconds()
    return next((s for s in STEPS_S if s * buckets >= span), STEPS_S[-1])


def timeline(st: dict[str, Any], buckets: int = BUCKETS) -> dict[str, Any]:
    """Pyynnöt aikaväleittäin session luokan mukaan. Välin pituus mukautuu datan
    kestoon, jotta lyhytkin demoajo näkyy tiheänä sarjana (1 s … 15 min)."""
    now = _now(st)
    step = step_for(st, buckets)
    if now is None:
        return {"step_s": step, "points": []}
    epoch = int(now.timestamp()) // step * step
    starts = [epoch - step * (buckets - 1 - i) for i in range(buckets)]
    counts = {t: Counter() for t in starts}
    verdicts = st.get("verdicts", {})
    for s in st.get("sessions", []):
        label = verdicts.get(s["id"], {}).get("label", "uncertain")
        for r in s["requests"]:
            t = int(_dt(r["ts"]).timestamp()) // step * step
            if t in counts:
                counts[t][label] += 1
    tz = now.tzinfo
    points = [
        {"t": datetime.fromtimestamp(t, tz).isoformat(), **{lab: c.get(lab, 0) for lab in LABELS}}
        for t, c in counts.items()
    ]
    # Tyhjät palkit alusta pois (lyhyt ajo ei jää kaavion reunaan), vähintään MIN_POINTS.
    while len(points) > MIN_POINTS and not any(points[0][lab] for lab in LABELS):
        points.pop(0)
    return {"step_s": step, "points": points}


def actors(st: dict[str, Any], campaigns: list[dict[str, Any]], limit: int = 6) -> list[dict]:
    """Haitalliset toimijat: kirjautumishyökkäys yhtenä, muut IP:ittäin."""
    verdicts = st.get("verdicts", {})
    in_attack = {sid for c in campaigns if c["login_attack"] for sid in c["session_ids"]}
    out: list[dict[str, Any]] = [
        {"kind": "campaign", "id": c["id"], "title": c["title"],
         "detail": (c["reasons"] or [""])[0], "action": c["action"],
         "action_text": c["action_text"], "last_seen": c["last_seen"]}
        for c in campaigns if c["login_attack"]
    ]  # fmt: skip
    by_ip: dict[str, dict[str, Any]] = {}
    for s in st.get("sessions", []):
        v = verdicts.get(s["id"], {})
        if v.get("label") != "bad_bot" or s["id"] in in_attack:
            continue
        rule = v.get("rule_id")
        action = v.get("action") or recommend("bad_bot", rule)
        cur = by_ip.get(s["ip"])
        if cur is None or s["ended_at"] > cur["last_seen"]:
            by_ip[s["ip"]] = {
                "kind": "ip", "id": s["id"],
                "title": f"{_ACTOR_TITLE.get(rule, 'Suspicious bot')} · {s['ip']}",
                "detail": (v.get("reasons") or [""])[0],
                "action": action, "action_text": ACTION_TEXT.get(action, action),
                "last_seen": s["ended_at"],
            }  # fmt: skip
    out += sorted(by_ip.values(), key=lambda a: a["last_seen"], reverse=True)
    return out[:limit]


def honesty(st: dict[str, Any]) -> dict[str, Any]:
    """Kuinka usein olimme väärässä ihmisten kanssa — vain labeloiduista sessioista."""
    verdicts = st.get("verdicts", {})
    humans = [lab["session_id"] for lab in st.get("labels", [])
              if re.match(r"human", lab.get("sim_class", ""))]  # fmt: skip
    false_alarms = sum(
        verdicts.get(sid, {}).get("label") in ("bad_bot", "good_bot") for sid in humans
    )
    n = len(humans)
    return {
        "synthetic": bool(st.get("synthetic")),
        "n_humans": n,
        "false_alarms": false_alarms,
        "fpr": false_alarms / n if n else None,
        "fpr_ci95_upper": wilson_upper(false_alarms, n),
    }


def overview(st: dict[str, Any]) -> dict[str, Any]:
    camps = enrich_campaigns(st)
    dist = Counter(v.get("label", "uncertain") for v in st.get("verdicts", {}).values())
    now = _now(st)
    return {
        "now": now.isoformat() if now else None,
        "updated_at": st.get("ingest", {}).get("updated_at"),
        "n_sessions": len(st.get("sessions", [])),
        "distribution": {lab: dist.get(lab, 0) for lab in LABELS},
        "timeline": timeline(st),
        "alerts": [c for c in camps if c["login_attack"] and c["active"]],
        "actors": actors(st, camps),
        "honesty": honesty(st),
    }
