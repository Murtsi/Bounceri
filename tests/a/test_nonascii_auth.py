from fastapi.testclient import TestClient

from bouncer.ingest.worker import Worker
from tests.a.test_worker import SECRET, _rec, _write


def test_invalid_unicode_sim_signature_does_not_hide_traffic(tmp_path):
    rows = [_rec(1000, "192.0.2.1", uri="/.env", marker="untrusted:human"),
            _rec(1001, "192.0.2.1", uri="/.git/config", marker="untrusted:human")]
    for row in rows:
        row["request"]["headers"]["X-Sim-Sig"] = ["bad-\u00ff"]
    _write(tmp_path / "access.log", rows, "w")
    worker = Worker(tmp_path / "access.log", tmp_path / "store.json", secret=SECRET,
                    intel_fn=None, campaigns_fn=None, synthetic=True)
    result = worker.cycle()
    assert len(result["sessions"][0]["requests"]) == 2
    assert result["ingest"]["unsigned_markers"] == 2
    assert result["labels"] == []


def test_invalid_unicode_demo_actor_token_returns_unauthorized(monkeypatch):
    from bouncer.site.app import app
    monkeypatch.setenv("BOUNCER_DEMO_ACTOR_SECRET", "s" * 32)
    response = TestClient(app, raise_server_exceptions=False).get(
        "/enforcement-demo/attack/probe", headers=[(b"authorization", b"Bearer bad-\xff")]
    )
    assert response.status_code == 401
