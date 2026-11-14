import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bouncer.api.enforcement import router
from bouncer.api.investigations import get_store
from bouncer.enforcement import issue_token
from bouncer.site.app import app as site
from tests.a.test_investigations_store import snapshot

ADMIN = {"Authorization": "Bearer test-admin"}


@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUNCER_DATABASE_URL", f"sqlite:///{tmp_path / 'enforcement.db'}")
    monkeypatch.setenv("BOUNCER_ADMIN_TOKEN", "test-admin")
    monkeypatch.setenv("BOUNCER_DEMO_ACTOR_SECRET", "s" * 32)
    monkeypatch.setenv("BOUNCER_STORE_PATH", str(tmp_path / "legacy.json"))
    api = FastAPI()
    api.include_router(router)
    case = get_store().create_from_legacy(snapshot(), public_demo=True)
    return TestClient(api), TestClient(site), case


def test_admin_approval_actual_http_effect_reversal_and_isolation(clients):
    api, site_client, case = clients
    route = f"/api/investigations/{case['id']}/enforcements"
    body = {
        "actor_id": "attack",
        "action": "temporary_block",
        "ttl_seconds": 60,
        "evidence_version": case["evidence_version"],
    }
    assert api.post(route, json=body).status_code == 401
    assert api.post(route, headers=ADMIN, json={**body, "evidence_version": 999}).status_code == 409
    policy = api.post(route, headers=ADMIN, json=body)
    assert policy.status_code == 201
    policy_id = policy.json()["id"]
    assert api.post(route, headers=ADMIN, json=body).json()["id"] == policy_id
    assert site_client.get("/enforcement-demo/attack/probe").status_code == 401
    attack = {"Authorization": "Bearer " + issue_token("attack")}
    benign = {"Authorization": "Bearer " + issue_token("benign")}
    assert site_client.get("/enforcement-demo/attack/probe", headers=benign).status_code == 401
    assert site_client.get("/enforcement-demo/attack/probe", headers=attack).status_code == 403
    assert site_client.post("/enforcement-demo/attack/probe", headers=attack).status_code == 403
    assert site_client.get("/enforcement-demo/benign/probe", headers=benign).status_code == 200
    assert site_client.get("/").status_code == 200
    assert site_client.get("/products").status_code == 200
    status = api.get(route).json()[0]
    assert status["affected_requests"] == 2 and "approver" not in status
    assert "configured_administrator" in api.get(route, headers=ADMIN).text
    assert api.delete(f"/api/enforcements/{policy_id}").status_code == 401
    assert api.delete(f"/api/enforcements/{policy_id}", headers=ADMIN).status_code == 200
    assert api.delete(f"/api/enforcements/{policy_id}", headers=ADMIN).status_code == 200
    assert site_client.get("/enforcement-demo/attack/probe", headers=attack).status_code == 200
    assert "s" * 32 not in json.dumps(status)


def test_reject_real_cases_bad_targets_and_hide_private_policy(clients):
    api, _, case = clients
    live = get_store().create_from_legacy(snapshot(False))
    route = f"/api/investigations/{live['id']}/enforcements"
    body = {"actor_id": "attack", "action": "rate_limit"}
    assert api.post(route, headers=ADMIN, json=body).status_code == 409
    assert api.get(route).status_code == 404
    public = f"/api/investigations/{case['id']}/enforcements"
    for invalid in (
        {**body, "actor_id": "192.0.2.1"},
        {**body, "ttl_seconds": 301},
        {**body, "action": "firewall"},
        {**body, "url": "https://example.com"},
    ):
        assert api.post(public, headers=ADMIN, json=invalid).status_code == 422


def test_dedicated_route_fails_closed_on_lookup_failure_without_affecting_site(
    clients, monkeypatch
):
    from bouncer.api import enforcement

    _, site_client, _ = clients

    def unavailable():
        raise OSError("fixture database failure")

    monkeypatch.setattr(enforcement, "get_runtime", unavailable)
    auth = {"Authorization": "Bearer " + issue_token("attack")}
    assert site_client.get("/enforcement-demo/attack/probe", headers=auth).status_code == 503
    assert site_client.get("/").status_code == 200
    assert site_client.get("/products").status_code == 200


def test_rate_limit_is_actual_429_with_retry_after(clients):
    api, site_client, case = clients
    route = f"/api/investigations/{case['id']}/enforcements"
    api.post(route, headers=ADMIN, json={"actor_id": "attack", "action": "rate_limit"})
    auth = {"Authorization": "Bearer " + issue_token("attack")}
    responses = [site_client.get("/enforcement-demo/attack/probe", headers=auth) for _ in range(4)]
    assert [r.status_code for r in responses] == [200, 200, 200, 429]
    assert int(responses[-1].headers["Retry-After"]) >= 1


def test_admin_auth_precedes_body_read_and_approval_size_is_bounded(clients):
    api, _, case = clients
    route = f"/api/investigations/{case['id']}/enforcements"
    assert api.post(route, content="{malformed").status_code == 401
    assert api.post(route, headers=ADMIN, content="x" * 8193).status_code == 413


def test_demo_policy_truthfully_records_manual_override_basis(clients):
    api, _, case = clients
    route = f"/api/investigations/{case['id']}/enforcements"
    result = api.post(route, headers=ADMIN, json={"actor_id": "attack", "action": "rate_limit"})
    assert result.json()["approval_basis"] == "manual_demo_override"
    assert api.get(route).json()[0]["approval_basis"] == "manual_demo_override"
