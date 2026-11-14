import json

import pytest
from fastapi.testclient import TestClient

from bouncer.api.app import app
from tests.a.test_investigations_store import snapshot


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUNCER_DATABASE_URL", f"sqlite:///{tmp_path / 'cases.db'}")
    monkeypatch.setenv("BOUNCER_ADMIN_TOKEN", "test-admin")
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(snapshot()), encoding="utf-8")
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(path))
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    return TestClient(app)


ADMIN = {"Authorization": "Bearer test-admin"}


def test_case_routes_auth_private_visibility_and_disabled_review(client):
    assert (
        client.post("/api/investigations", json={"source": "monitored_traffic"}).status_code == 401
    )
    response = client.post(
        "/api/investigations",
        headers=ADMIN,
        json={"source": "monitored_traffic", "public_demo": True},
    )
    assert response.status_code == 201
    case_id = response.json()["id"]
    assert client.get("/api/investigations").json()[0]["id"] == case_id
    assert client.get(f"/api/investigations/{case_id}").status_code == 200
    assert len(client.get(f"/api/investigations/{case_id}/assessments").json()) == 1
    assert client.post(f"/api/investigations/{case_id}/reviews").status_code == 401
    assert client.post(f"/api/investigations/{case_id}/reviews", headers=ADMIN).status_code == 503
    assert client.get("/api/usage").json()["paid_review_enabled"] is False
    assert client.get("/api/usage").json()["executions"] == 0
    assert client.get("/api/capabilities").json()["modules"][0]["implemented"] is True


def test_private_case_and_unsupported_import(client):
    private = client.post(
        "/api/investigations", headers=ADMIN, json={"source": "monitored_traffic"}
    ).json()
    assert client.get("/api/investigations").json() == []
    assert client.get(f"/api/investigations/{private['id']}").status_code == 404
    assert client.get(f"/api/investigations/{private['id']}", headers=ADMIN).status_code == 200
    assert client.get(f"/api/investigations/{private['id']}/assessments").status_code == 404
    assert (
        client.post(
            "/api/investigations",
            headers=ADMIN,
            json={"source": "arbitrary", "path": "/etc/passwd"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/investigations", headers=ADMIN, content=b" " * (10 * 1024 * 1024 + 1)
        ).status_code
        == 413
    )


def test_public_legacy_endpoints_do_not_leak_identifiers(client):
    for route in ("summary", "sessions", "sessions/s1", "campaigns", "overview", "metrics"):
        response = client.get("/api/" + route)
        assert response.status_code == 200
        text = response.text
        for secret in ("192.0.2.1", "secret-name", "secret-query", "private-agent"):
            assert secret not in text
    assert "192.0.2.1" in client.get("/api/sessions", headers=ADMIN).text


def test_review_enqueue_uses_verified_worker_configuration_and_budget(client, monkeypatch):
    from types import SimpleNamespace

    from bouncer.api import investigations

    settings = SimpleNamespace(config_key="verified-fixture-v1", maximum_cost_microusd=3_000_000)
    monkeypatch.setattr(
        investigations,
        "review_configuration",
        lambda: (settings, {"enabled": True, "max_requests": 2}),
    )
    case_id = client.post(
        "/api/investigations", headers=ADMIN, json={"source": "monitored_traffic"}
    ).json()["id"]
    route = f"/api/investigations/{case_id}/reviews"
    accepted = client.post(route, headers=ADMIN)
    assert accepted.status_code == 202
    assert client.post(route, headers=ADMIN).json()["job_id"] == accepted.json()["job_id"]
    assert client.get("/api/usage").json()["reserved_usd"] == 3
    assert client.get("/api/usage").json()["executions"] == 1
    settings.config_key = "different-config"
    deferred = client.post(route, headers=ADMIN)
    assert deferred.status_code == 409
    assert deferred.json()["detail"]["status"] == "deferred_budget"


def test_live_private_legacy_data_is_hidden_and_admin_token_never_defaults(client, monkeypatch):
    from bouncer.db.store import store_path

    raw = snapshot(False)
    raw["sessions"][0]["requests"][0]["ts"] = raw["sessions"][0]["started_at"]
    store_path().write_text(json.dumps(raw), encoding="utf-8")
    assert client.get("/api/sessions").json() == []
    assert client.get("/api/sessions/s1").status_code == 404
    assert client.get("/api/summary").json()["n_sessions"] == 0
    monkeypatch.delenv("BOUNCER_ADMIN_TOKEN")
    assert (
        client.post("/api/investigations", headers=ADMIN, json={"source": "fixture"}).status_code
        == 401
    )


@pytest.mark.parametrize("session_count", [48, 72])
def test_review_endpoint_rejects_model_ineligible_packet_before_reserving(
    client, monkeypatch, session_count
):
    from types import SimpleNamespace

    from bouncer.api import investigations

    raw = {
        "synthetic": True,
        "sessions": [
            {
                "id": f"session-{i}",
                "ip": "192.0.2.1",
                "requests": [{"method": "GET", "path": "/", "status": 200}],
            }
            for i in range(session_count)
        ],
    }
    case = investigations.get_store().create_from_legacy(raw, source_key="large", public_demo=True)
    settings = SimpleNamespace(config_key="verified-fixture-v1", maximum_cost_microusd=100)
    monkeypatch.setattr(
        investigations,
        "review_configuration",
        lambda: (settings, {"enabled": True, "max_requests": 2}),
    )
    response = client.post(f"/api/investigations/{case['id']}/reviews", headers=ADMIN)
    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "review_ineligible"
    assert response.json()["detail"]["reason"]
    assert (
        client.get(f"/api/investigations/{case['id']}").json()["review_eligibility"]["eligible"]
        is False
    )
    usage = client.get("/api/usage").json()
    assert usage["executions"] == usage["requests"] == 0
    assert usage["reserved_usd"] == 0


def test_repository_fixture_creates_case(client):
    response = client.post("/api/investigations", headers=ADMIN,
                           json={"source": "fixture", "public_demo": True})
    assert response.status_code == 201, response.text
    assert response.json()["source"] == {"kind": "fixture", "synthetic": True}


def test_case_list_pagination_validates_and_preserves_visibility(client):
    case = client.post("/api/investigations", headers=ADMIN,
                       json={"source": "monitored_traffic"}).json()
    assert client.get("/api/investigations?limit=1&offset=0").json() == []
    page = client.get("/api/investigations?limit=1&offset=0&origin=synthetic", headers=ADMIN)
    assert page.status_code == 200
    assert page.json()[0]["id"] == case["id"]
    assert "evidence" not in page.json()[0]
    assert client.get("/api/investigations?offset=1", headers=ADMIN).json() == []
    for query in ("limit=0", "limit=101", "offset=-1", "origin=unknown"):
        assert client.get("/api/investigations?" + query).status_code == 422
