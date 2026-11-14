"""Ohut API (A-11, MVP vaihe 4): lukee workerin JSON-storea, ei laske mitään itse.

    uv run uvicorn bouncer.api.app:app --port 8000

Dashboardin liikenne EI kulje tarkkaillun Caddyn kautta (muuten se päätyisi
analysoitavaan lokiin). Jos `frontend/dist` on olemassa, sama palvelu tarjoilee
myös React-dashboardin.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from bouncer.db.store import _read_raw, store_path
from bouncer.eval.metrics import METRICS_PATH
from bouncer.eval.weaknesses import KNOWN_WEAKNESSES

DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
LABELS = ("bad_bot", "good_bot", "human", "uncertain")

app = FastAPI(title="Bouncer API", version="0.1.0")


def _store() -> dict[str, Any]:
    return _read_raw(store_path())


def _truth(store: dict[str, Any]) -> dict[str, str]:
    return {lab["session_id"]: lab["sim_class"] for lab in store.get("labels", [])}


def _row(s: dict[str, Any], v: dict[str, Any], truth: dict[str, str]) -> dict[str, Any]:
    return {
        "id": s["id"],
        "ip": s["ip"],
        "user_agent": s["user_agent"],
        "started_at": s["started_at"],
        "ended_at": s["ended_at"],
        "n_requests": len(s["requests"]),
        "label": v.get("label", "uncertain"),
        "score": v.get("score"),
        "reason": (v.get("reasons") or [""])[0],
        "campaign_id": v.get("campaign_id"),
        "sim_class": truth.get(s["id"]),
    }


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/summary")
def summary() -> dict[str, Any]:
    st = _store()
    verdicts = st.get("verdicts", {})
    by_label = {lab: 0 for lab in LABELS}
    for v in verdicts.values():
        by_label[v["label"]] = by_label.get(v["label"], 0) + 1
    return {
        "updated_at": st.get("ingest", {}).get("updated_at"),
        "synthetic": bool(st.get("synthetic")),
        "source": st.get("source"),
        "n_sessions": len(st.get("sessions", [])),
        "by_label": by_label,
        "n_campaigns": len(st.get("campaigns", [])),
        "ingest": st.get("ingest", {}),
    }


@app.get("/api/sessions")
def sessions(label: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    st = _store()
    verdicts, truth = st.get("verdicts", {}), _truth(st)
    rows = [_row(s, verdicts.get(s["id"], {}), truth) for s in st.get("sessions", [])]
    if label:
        rows = [r for r in rows if r["label"] == label]
    rows.sort(key=lambda r: r["started_at"], reverse=True)
    return rows[: max(1, min(limit, 5000))]


@app.get("/api/sessions/{sid}")
def session(sid: str) -> dict[str, Any]:
    st = _store()
    s = next((x for x in st.get("sessions", []) if x["id"] == sid), None)
    if s is None:
        raise HTTPException(404, "sessiota ei löytynyt")
    v = st.get("verdicts", {}).get(sid, {})
    camp = next((c for c in st.get("campaigns", []) if c["id"] == v.get("campaign_id")), None)
    return {
        **_row(s, v, _truth(st)),
        "verdict": v,
        "campaign": camp,
        "requests": [
            {k: r.get(k) for k in ("ts", "method", "path", "status", "username", "content_type")}
            for r in s["requests"]
        ],
    }


@app.get("/api/campaigns")
def campaigns() -> list[dict[str, Any]]:
    st = _store()
    verdicts = st.get("verdicts", {})
    out = []
    for c in st.get("campaigns", []):
        labels = [verdicts.get(sid, {}).get("label", "uncertain") for sid in c["session_ids"]]
        out.append({**c, "labels": {lab: labels.count(lab) for lab in set(labels)}})
    return sorted(out, key=lambda c: c["size"], reverse=True)


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    try:
        m = json.loads(METRICS_PATH.read_text("utf-8"))
    except FileNotFoundError:
        m = {"stub": True}
    st = _store()
    return {
        "metrics": m,
        "stub": bool(m.get("stub", True)),
        "synthetic_data": bool(st.get("synthetic")) or bool(m.get("data", {}).get("synthetic")),
        "known_weaknesses": m.get("known_weaknesses") or list(KNOWN_WEAKNESSES),
        "ingest": st.get("ingest", {}),
    }


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
