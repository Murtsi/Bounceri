import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from bouncer.api.app import app
from bouncer.api.investigations import get_store
from bouncer.db.traffic import TrafficRepository, requests, sources


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUNCER_DATABASE_URL", f"sqlite:///{tmp_path / 'imports.db'}")
    monkeypatch.setenv("BOUNCER_ADMIN_TOKEN", "import-admin")
    monkeypatch.setenv("BOUNCERI_REVIEW_ENABLED", "false")
    return TestClient(app, raise_server_exceptions=False)


ADMIN = {"Authorization": "Bearer import-admin"}


def body(**changes):
    value = {"format": "normalized_jsonl", "synthetic": False,
             "provenance": {"kind": "owner_log", "permission_confirmed": True},
             "data": json.dumps({"ts": "2026-11-14T12:00:00+00:00", "ip": "192.0.2.1",
                                  "method": "GET", "path": "/?token=private-secret", "status": 200,
                                  "headers": {"Authorization": "Bearer secret"}})}
    return value | changes


def test_import_requires_admin_before_consuming_data(client):
    assert client.post("/api/imports/traffic", content=b"not-json").status_code == 401
    response = client.post("/api/imports/traffic", headers=[(b"authorization", b"Bearer \xff")],
                           content=b"not-json")
    assert response.status_code == 401


def test_import_is_private_redacted_and_never_queues_paid_work(client):
    response = client.post("/api/imports/traffic", headers=ADMIN, json=body())
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["case"]["source"] == {"kind": "uploaded_log", "synthetic": False}
    assert value["report"]["accepted"] == 1
    assert client.get("/api/investigations").json() == []
    assert client.get("/api/usage").json()["requests"] == 0
    assert "private-secret" not in response.text and "Bearer secret" not in response.text
    repo = TrafficRepository(get_store().engine)
    snapshot = repo.load_snapshot(value["source_key"])
    raw = json.dumps(snapshot)
    assert "private-secret" not in raw and "Bearer secret" not in raw
    assert snapshot["labels"] == []


def test_bad_rows_are_reported_without_losing_later_rows(client):
    payload = body()
    payload["data"] = "not json\n" + payload["data"]
    response = client.post("/api/imports/traffic", headers=ADMIN, json=payload)
    assert response.status_code == 201
    assert response.json()["report"]["rejected"] == 1
    assert response.json()["report"]["accepted"] == 1
    assert response.json()["case"]["complete"] is False


def test_publication_needs_explicit_synthetic_permission(client):
    rejected = client.post("/api/imports/traffic", headers=ADMIN, json=body(public_demo=True))
    assert rejected.status_code == 422
    published = client.post("/api/imports/traffic", headers=ADMIN,
                            json=body(synthetic=True, public_demo=True))
    assert published.status_code == 201, published.text
    assert len(client.get("/api/investigations").json()) == 1


def test_invalid_contract_or_empty_import_never_persists(client):
    for value in (body(synthetic="false"), body(provenance={"kind": "owner_log"}),
                  body(data="bad"), body(format="unknown")):
        assert client.post("/api/imports/traffic", headers=ADMIN, json=value).status_code == 422
    repo = TrafficRepository(get_store().engine)
    with repo.engine.connect() as conn:
        assert list(conn.execute(select(sources))) == []
        assert list(conn.execute(select(requests))) == []


def test_parallel_import_is_rejected_before_another_analyzer(client, monkeypatch):
    import asyncio
    import threading

    import httpx

    from bouncer.api import traffic_imports
    started, release = threading.Event(), threading.Event()
    def held_import(body):
        started.set()
        assert release.wait(5)
        return {"report": {"accepted": 1}}
    monkeypatch.setattr(traffic_imports, "_import", held_import)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                    base_url="http://test") as api:
            first = asyncio.create_task(
                api.post("/api/imports/traffic", headers=ADMIN, json=body())
            )
            try:
                assert await asyncio.to_thread(started.wait, 3)
                second = await api.post("/api/imports/traffic", headers=ADMIN, json=body())
                assert second.status_code == 429
            finally:
                release.set()
                result = await first
                assert result.status_code == 201
    asyncio.run(scenario())


def test_upload_timeout_releases_capacity_without_storage(client, monkeypatch):
    import asyncio

    import httpx

    from bouncer.api import traffic_imports
    monkeypatch.setattr(traffic_imports, "UPLOAD_SECONDS", .01)
    async def slow():
        yield b"{"
        await asyncio.sleep(.1)
        yield b"}"
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                    base_url="http://test") as api:
            result = await api.post("/api/imports/traffic", headers=ADMIN, content=slow())
            assert result.status_code == 408
    asyncio.run(scenario())
    monkeypatch.setattr(traffic_imports, "UPLOAD_SECONDS", 10)
    assert client.post("/api/imports/traffic", headers=ADMIN, content=b"bad").status_code == 422


def test_nonsynthetic_uploaded_case_is_in_real_origin_filter(client):
    created = client.post("/api/imports/traffic", headers=ADMIN, json=body()).json()["case"]
    page = client.get("/api/investigations?origin=real", headers=ADMIN).json()
    assert [case["id"] for case in page] == [created["id"]]


def test_cancelled_request_cannot_admit_a_second_running_import(monkeypatch):
    import asyncio
    import threading
    from types import SimpleNamespace

    from fastapi import HTTPException

    from bouncer.api import traffic_imports
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def held_import(value):
        started.set()
        try:
            assert release.wait(5)
            return {}
        finally:
            finished.set()
    async def stream():
        yield json.dumps(body()).encode()
    monkeypatch.setattr(traffic_imports, "require_admin", lambda request: None)
    monkeypatch.setattr(traffic_imports, "_import", held_import)
    async def scenario():
        first = asyncio.create_task(traffic_imports.import_traffic(SimpleNamespace(stream=stream)))
        try:
            assert await asyncio.to_thread(started.wait, 3)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            with pytest.raises(HTTPException) as blocked:
                await traffic_imports.import_traffic(SimpleNamespace(stream=stream))
            assert blocked.value.status_code == 429
        finally:
            release.set()
            assert await asyncio.to_thread(finished.wait, 3)
            await asyncio.sleep(.01)
    asyncio.run(scenario())


def test_unknown_target_logging_is_visible_without_inventing_zero_accounts(client):
    response = client.post("/api/imports/traffic", headers=ADMIN, json=body())
    assert response.status_code == 201
    case = response.json()["case"]
    data = next(e["data"] for e in case["evidence"] if e["kind"] == "session_summary")
    assert "username" in data["unavailable_fields"]
    assert "distinct_account_count" not in data
    assert case["missing_information"]
    assert case["review_eligibility"]["eligible"] is True


def test_imported_path_patterns_do_not_prove_source_site_attack_context(client):
    from bouncer.review.validation import validate_decision_result
    rows = [{"ts": "2026-11-14T12:00:00+00:00", "ip": "192.0.2.1", "method": "GET",
             "path": path, "status": 200} for path in ("/wp-login.php", "/wp-admin/")]
    created = client.post("/api/imports/traffic", headers=ADMIN,
                          json=body(data="\n".join(json.dumps(row) for row in rows))).json()["case"]
    data = created["evidence"][0]["data"]
    assert data["path_category_counts"]["probe"] == 2
    assert data["category_provenance"] == "generic-path-patterns-v1"
    result = {"answers": {name: {"choice": "unknown"} for name in (
        "coordination", "explicit_attack", "automation", "benign_alternative", "sufficient_evidence"
    )}}
    result["answers"]["explicit_attack"]["choice"] = "yes"
    with pytest.raises(ValueError):
        validate_decision_result(result, created)
