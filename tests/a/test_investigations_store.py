import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from bouncer.investigations import InvestigationStore


def snapshot(synthetic=True):
    return {
        "synthetic": synthetic,
        "sessions": [
            {
                "id": "s1",
                "ip": "192.0.2.1",
                "user_agent": "private-agent",
                "started_at": "2026-11-14T12:00:00Z",
                "ended_at": "2026-11-14T12:01:00Z",
                "requests": [
                    {
                        "method": "POST",
                        "path": "/login",
                        "status": 401,
                        "username": "secret-name",
                        "headers": {"authorization": "secret"},
                        "query": "secret-query",
                    }
                ],
            }
        ],
        "labels": [{"session_id": "s1", "sim_class": "secret-truth"}],
        "verdicts": {
            "s1": {
                "label": "bad_bot",
                "score": 1,
                "reasons": ["192.0.2.1 secret-name secret-query"],
                "model_version": "rules-v1",
            }
        },
    }


@pytest.fixture
def store(tmp_path):
    return InvestigationStore(f"sqlite:///{tmp_path / 'cases.db'}")


def test_snapshot_is_immutable_redacted_idempotent_and_persistent(store):
    raw = snapshot()
    case = store.create_from_legacy(raw, public_demo=True)
    assert case["id"] == store.create_from_legacy(raw, public_demo=True)["id"]
    text = json.dumps(case)
    for secret in ("192.0.2.1", "secret-name", "secret-query", "secret-truth", "private-agent"):
        assert secret not in text
    raw["sessions"][0]["requests"].append({"method": "GET", "path": "/", "status": 200})
    revision = store.create_from_legacy(raw, public_demo=True)
    assert revision["id"] != case["id"]
    assert store.get_case(case["id"])["evidence"][0]["data"]["n_requests"] == 1
    reopened = InvestigationStore(str(store.engine.url))
    assert len(reopened.list_cases()) == 2
    assert len(store.list_assessments(case["id"])) == 1


def test_private_live_cases_are_never_public(store):
    case = store.create_from_legacy(snapshot(False))
    assert store.list_cases() == []
    assert store.get_case(case["id"]) is None
    assert store.get_case(case["id"], public_only=False)
    with pytest.raises(ValueError):
        store.create_from_legacy(snapshot(False), public_demo=True)


def test_atomic_budget_claim_unknown_spend_and_no_retry(store):
    case = store.create_from_legacy(snapshot())

    def enqueue(i):
        try:
            return store.enqueue_review(case["id"], f"config-{i}", 3_000_000)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(enqueue, range(2)))
    accepted = [j for j in jobs if j]
    assert len(accepted) == 1
    job = accepted[0]
    assert store.enqueue_review(case["id"], job["config_key"], 3_000_000)["id"] == job["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(store.claim_job, ["worker-1", "worker-2"]))
    assert sum(c is not None for c in claims) == 1
    assert store.review_packet(job["id"])["complete"] is True
    reservation = store.start_request(job["id"], "reviewer", "fixture", "model", 2_000_000, "v1")
    store.settle_request(reservation["id"], None, {}, None)
    store.finish_job(job["id"], "unavailable", "timeout")
    usage = store.usage()
    assert usage["reserved_usd"] == 2
    assert usage["available_usd"] == 3
    assert usage["requests"] == 1 and usage["executions"] == 1
    assert store.claim_job("worker-3") is None
    with pytest.raises(ValueError):
        store.start_request(job["id"], "reviewer", "fixture", "model", 1, "v1")


def test_settlement_releases_only_unused_budget_and_preserves_assessments(store):
    case = store.create_from_legacy(snapshot())
    job = store.enqueue_review(case["id"], "config", 1_000_000)
    store.claim_job("w")
    r = store.start_request(job["id"], "reviewer", "fixture", "model", 800_000, "v1")
    store.settle_request(r["id"], 100_000, {"tokens": 1}, "request-1")
    store.append_assessment(job["id"], "reviewer", {"recommendation": "monitor"}, {})
    store.finish_job(job["id"], "completed")
    assert store.usage()["spent_usd"] == 0.1
    assert store.usage()["reserved_usd"] == 0
    assert len(store.list_assessments(case["id"])) == 2
    assert store.get_case(case["id"], False)["review"]["status"] == "completed"
    with pytest.raises(ValueError):
        store.settle_request(r["id"], 200_000, {}, None)


def test_caps_and_oversized_request_reservation(store):
    case = store.create_from_legacy(snapshot())
    job = store.enqueue_review(case["id"], "config", 100, max_requests=1)
    store.claim_job("w")
    with pytest.raises(ValueError):
        store.start_request(job["id"], "reviewer", "fixture", "model", 101, "v1")
    r = store.start_request(job["id"], "reviewer", "fixture", "model", 100, "v1")
    store.settle_request(r["id"], 0, {}, None)
    with pytest.raises(ValueError):
        store.start_request(job["id"], "reviewer", "fixture", "model", 0, "v1")


def test_source_keys_scope_cache_and_requests_are_never_retried(store):
    first = store.create_from_legacy(snapshot(), "dataset-a")
    second = store.create_from_legacy(snapshot(), "dataset-b")
    assert first["evidence_hash"] != second["evidence_hash"]
    job = store.enqueue_review(first["id"], "configuration", 1000)
    store.claim_job("w")
    reservation = store.start_request(job["id"], "reviewer", "fixture", "model", 500, "v1")
    store.settle_request(reservation["id"], None, {}, None)
    with pytest.raises(ValueError):
        store.start_request(job["id"], "reviewer", "fixture", "model", 500, "v1")
    store.settle_request(reservation["id"], 100, {}, "settled-later")
    store.settle_request(reservation["id"], 100, {}, "settled-later")
    store.finish_job(job["id"], "unavailable")
    assert store.usage()["spent_usd"] == 0.0001
    assert store.usage()["reserved_usd"] == 0


def test_global_execution_and_request_caps(store):
    from sqlalchemy import update

    from bouncer.investigations.store import budget

    case = store.create_from_legacy(snapshot())
    with store.engine.begin() as conn:
        conn.execute(update(budget).values(executions=100))
    with pytest.raises(ValueError, match="deferred_budget"):
        store.enqueue_review(case["id"], "new-config", 1)
    with store.engine.begin() as conn:
        conn.execute(update(budget).values(executions=0, requests=199))
    with pytest.raises(ValueError, match="deferred_budget"):
        store.enqueue_review(case["id"], "new-config", 1)
    job = store.enqueue_review(case["id"], "last-request", 1, max_requests=1)
    store.claim_job("w")
    store.start_request(job["id"], "reviewer", "fixture", "model", 1, "v1")
    assert store.usage()["requests"] == 200


def test_mixed_traffic_and_empty_evidence_remain_uncertain(store):
    raw = snapshot()
    benign = dict(raw["sessions"][0], id="benign")
    raw["sessions"].append(benign)
    raw["verdicts"]["benign"] = {"label": "human", "score": 0.1}
    case = store.create_from_legacy(raw)
    assert case["local_assessment"]["label"] == "uncertain"
    assert case["local_assessment"]["label_counts"] == {"bad_bot": 1, "human": 1}
    empty = store.create_from_legacy({"sessions": []}, "empty")
    assert empty["complete"] is False


def test_new_configuration_does_not_reuse_previous_final_recommendation(store):
    case = store.create_from_legacy(snapshot())
    job = store.enqueue_review(case["id"], "first", 100)
    store.claim_job("w")
    store.append_assessment(job["id"], "reviewer", {"recommendation": "monitor"}, {})
    store.finish_job(job["id"], "completed")
    store.enqueue_review(case["id"], "second", 100)
    latest = store.get_case(case["id"], False)
    assert latest["review"]["status"] == "queued"
    assert latest["review"]["result"] is None
    assert len(store.list_assessments(case["id"])) == 2


def test_crawler_label_without_verification_origin_is_explicitly_unknown(store):
    raw = snapshot()
    raw["verdicts"]["s1"].update(label="good_bot", verified_bot=True)
    case = store.create_from_legacy(raw)
    assert case["evidence"][0]["data"]["verified_bot"] is None
    assert any("verification provenance" in limit for limit in case["missing_information"])
