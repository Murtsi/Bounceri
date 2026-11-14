"""Operator-confirmed recovery never retries inference or guesses provider charges."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from bouncer.investigations import InvestigationStore
from bouncer.investigations.store import jobs, reservations
from bouncer.review.worker import main


@pytest.fixture
def interrupted(tmp_path):
    url = f"sqlite:///{tmp_path / 'interrupted.db'}"
    store = InvestigationStore(url)
    case = store.create_from_legacy(
        {
            "synthetic": True,
            "sessions": [
                {
                    "id": "s1",
                    "ip": "192.0.2.1",
                    "requests": [{"method": "GET", "path": "/", "status": 200}],
                }
            ],
        }
    )
    job = store.enqueue_review(case["id"], "interrupted-config", 1_000_000)
    assert store.claim_job("stopped-worker")["id"] == job["id"]
    return store, case, job, url


def test_close_interrupted_job_releases_unused_reservation_and_persists(interrupted):
    store, case, job, url = interrupted
    assert InvestigationStore(url).claim_job("replacement-worker") is None
    store.close_interrupted_job(job["id"], "stopped-worker")

    reopened = InvestigationStore(url)
    review = reopened.get_case(case["id"], False)["review"]
    assert review["status"] == "unavailable"
    assert review["reason"] == "interrupted"
    assert reopened.usage()["reserved_usd"] == 0
    assert reopened.usage()["spent_usd"] == 0
    assert reopened.usage()["requests"] == 0
    assert reopened.usage()["executions"] == 1
    assert reopened.claim_job("replacement-worker") is None
    assert reopened.enqueue_review(case["id"], "interrupted-config", 1_000_000)["id"] == job["id"]
    with pytest.raises(ValueError):
        reopened.start_request(job["id"], "reviewer", "fixture", "model", 1, "v1")


@pytest.mark.parametrize("state", ["pending", "unknown", "settled"])
def test_close_preserves_dispatched_charge_reservation(interrupted, state):
    store, _, job, url = interrupted
    request = store.start_request(job["id"], "reviewer", "fixture", "model", 800_000, "v1")
    if state != "pending":
        store.settle_request(request["id"], 100_000 if state == "settled" else None, {}, None)
    store.close_interrupted_job(job["id"], "stopped-worker")

    reopened = InvestigationStore(url)
    assert reopened.usage()["reserved_usd"] == (0 if state == "settled" else 0.8)
    assert reopened.usage()["spent_usd"] == (0.1 if state == "settled" else 0)
    assert reopened.usage()["requests"] == 1
    with reopened.engine.connect() as conn:
        saved = conn.execute(select(reservations)).mappings().one()
    assert saved["id"] == request["id"]
    assert saved["state"] == state


def test_wrong_owner_cannot_close_job_or_release_budget(interrupted):
    store, _, job, _ = interrupted
    before = store.usage()
    with pytest.raises(ValueError, match="owner"):
        store.close_interrupted_job(job["id"], "replacement-worker")
    assert store.usage() == before
    with store.engine.connect() as conn:
        saved = conn.execute(select(jobs)).mappings().one()
    assert saved["status"] == "running"
    assert saved["worker_id"] == "stopped-worker"
    assert saved["remaining"] == 1_000_000


@pytest.mark.parametrize("status", ["queued", "unavailable"])
def test_recovery_rejects_jobs_that_are_not_running(interrupted, status):
    store, case, job, _ = interrupted
    store.finish_job(job["id"], "unavailable")
    if status == "queued":
        job = store.enqueue_review(case["id"], "queued-config", 1_000_000)
    before = store.usage()
    with pytest.raises(ValueError, match="running"):
        store.close_interrupted_job(job["id"], "stopped-worker")
    assert store.usage() == before


def test_concurrent_recovery_releases_unused_budget_once(interrupted):
    store, _, job, url = interrupted

    def close(_):
        try:
            InvestigationStore(url).close_interrupted_job(job["id"], "stopped-worker")
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(close, range(2))) == 1
    assert store.usage()["reserved_usd"] == 0


@pytest.mark.parametrize("extra", [[], ["--confirm-worker-stopped"]])
def test_cli_recovery_requires_explicit_stopped_confirmation_and_owner(interrupted, extra):
    store, _, job, url = interrupted
    before = store.usage()

    def forbidden(*args, **kwargs):
        pytest.fail("incomplete recovery arguments must not open the store or send inference")

    args = ["--database-url", url, "--close-interrupted", job["id"], *extra]
    if not extra:
        args += ["--worker-id", "stopped-worker"]
    with pytest.raises(SystemExit) as exc:
        main(args, store_factory=forbidden, transport=forbidden)
    assert exc.value.code == 2
    assert store.usage() == before


def test_cli_recovery_never_constructs_runner_or_sends_inference(interrupted, monkeypatch):
    store, case, job, url = interrupted

    def forbidden(*args, **kwargs):
        pytest.fail("recovery must not construct a review runner or send inference")

    monkeypatch.setattr("bouncer.review.worker.ReviewRunner", forbidden)
    assert (
        main(
            [
                "--database-url",
                url,
                "--close-interrupted",
                job["id"],
                "--worker-id",
                "stopped-worker",
                "--confirm-worker-stopped",
            ],
            transport=forbidden,
        )
        == 0
    )
    assert store.get_case(case["id"], False)["review"]["reason"] == "interrupted"


def test_cli_wrong_owner_keeps_budget_and_fails(interrupted):
    store, _, job, url = interrupted
    before = store.usage()
    assert (
        main(
            [
                "--database-url",
                url,
                "--close-interrupted",
                job["id"],
                "--worker-id",
                "wrong-worker",
                "--confirm-worker-stopped",
            ],
        )
        == 1
    )
    assert store.usage() == before
