"""Ohut API (MVP vaihe 4): lukee workerin storea sellaisenaan."""

import json

import pytest
from fastapi.testclient import TestClient

from bouncer.api.app import app

STORE = {
    "sessions": [
        {"id": "s1", "ip": "203.0.113.24", "user_agent": "curl/8.5.0",
         "started_at": "2026-11-14T12:00:00+00:00", "ended_at": "2026-11-14T12:00:01+00:00",
         "requests": [{"ts": "2026-11-14T12:00:00+00:00", "method": "GET", "path": "/.env",
                       "status": 404, "username": None, "content_type": None, "headers": {}}]},
        {"id": "s2", "ip": "198.51.100.10", "user_agent": "Mozilla/5.0",
         "started_at": "2026-11-14T12:01:00+00:00", "ended_at": "2026-11-14T12:01:30+00:00",
         "requests": []},
    ],
    "labels": [{"session_id": "s1", "run_id": "r", "sim_class": "scanner", "campaign_id": None}],
    "synthetic": True,
    "verdicts": {
        "s1": {"label": "bad_bot", "score": 1.0, "reasons": ["Kokeili 2 polkua"],
               "campaign_id": "c1",
               "explanation": "Verdict: bad_bot.", "model_version": "rules-v1"},
        "s2": {"label": "uncertain", "score": 0.5, "reasons": ["x"], "campaign_id": None},
    },
    "campaigns": [{"id": "c1", "kind": "credential_stuffing", "session_ids": ["s1"], "reasons": [],
                   "size": 1}],
    "ingest": {"updated_at": "2026-11-14T12:02:00+00:00", "unsigned_markers": 2},
}  # fmt: skip


@pytest.fixture
def client(tmp_path, monkeypatch):
    p = tmp_path / "store.json"
    p.write_text(json.dumps(STORE), "utf-8")
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(p))
    return TestClient(app)


def test_summary(client):
    s = client.get("/api/summary").json()
    assert s["n_sessions"] == 2 and s["synthetic"] is True
    assert s["by_label"]["bad_bot"] == 1 and s["by_label"]["uncertain"] == 1
    assert s["ingest"]["unsigned_markers"] == 2


def test_sessions_list_newest_first_and_filter(client):
    rows = client.get("/api/sessions").json()
    assert [r["id"] for r in rows] == ["s2", "s1"]
    assert rows[1]["reason"] == "Local detector label: bad_bot."
    assert rows[1]["sim_class"] == "scanner"
    assert [r["id"] for r in client.get("/api/sessions?label=bad_bot").json()] == ["s1"]


def test_session_detail_has_verdict_campaign_and_requests(client):
    d = client.get("/api/sessions/s1").json()
    assert d["verdict"]["explanation"] == "Local detector label: bad_bot; advisory finding."
    assert d["campaign"]["kind"] == "credential_stuffing"
    assert d["requests"][0]["path"] == "/.env" and "headers" not in d["requests"][0]
    assert client.get("/api/sessions/nope").status_code == 404


def test_campaigns_with_member_labels(client):
    assert client.get("/api/campaigns").json()[0]["labels"] == {"bad_bot": 1}


def test_metrics_is_honest_about_stub_and_synthetic(client):
    m = client.get("/api/metrics").json()
    assert m["stub"] is True and m["synthetic_data"] is True
    assert len(m["known_weaknesses"]) >= 5


def test_empty_store_does_not_break(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(tmp_path / "missing.json"))
    c = TestClient(app)
    assert c.get("/api/sessions").json() == []
    assert c.get("/api/summary").json()["n_sessions"] == 0
