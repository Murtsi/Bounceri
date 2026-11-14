from concurrent.futures import ThreadPoolExecutor

import pytest

from bouncer.enforcement import EnforcementRuntime, EnforcementStore, issue_token, verify_token
from bouncer.investigations import InvestigationStore


@pytest.fixture
def runtime(tmp_path):
    clock = [1000.0]
    store = InvestigationStore(f"sqlite:///{tmp_path / 'policies.db'}")
    return EnforcementRuntime(store, clock=lambda: clock[0]), clock


def approve(runtime, **overrides):
    return runtime.approve(
        case_id="case-1",
        evidence_hash="hash",
        evidence_version=1,
        actor_id="attack",
        action="temporary_block",
        ttl_seconds=60,
        **overrides,
    )


def test_registered_actor_tokens_are_bound_to_actor_and_secret():
    token = issue_token("attack", "x" * 32)
    assert verify_token("attack", token, "x" * 32)
    assert not verify_token("benign", token, "x" * 32)
    assert not verify_token("attack", token + "forged", "x" * 32)
    with pytest.raises(ValueError):
        issue_token("arbitrary-ip", "x" * 32)
    with pytest.raises(ValueError):
        issue_token("attack", "")


def test_block_scope_revoke_and_durable_expiry(runtime):
    engine, clock = runtime
    policy = approve(engine)
    assert approve(engine)["id"] == policy["id"]
    assert engine.probe("attack")["status_code"] == 403
    assert engine.probe("benign")["status_code"] == 200
    rows = engine.list_policies("case-1")
    assert rows[0]["affected_requests"] == 1
    reopened = EnforcementStore(str(engine.store.engine.url), clock=lambda: clock[0])
    assert reopened.probe("attack")["status_code"] == 403
    clock[0] = 1060.0
    assert reopened.probe("attack")["status_code"] == 200
    assert reopened.list_policies("case-1")[0]["status"] == "expired"
    reopened.revoke(policy["id"])
    reopened.revoke(policy["id"])
    assert reopened.probe("attack")["status_code"] == 200


def test_rate_limit_burst_refill_and_parallel_requests(runtime):
    engine, clock = runtime
    engine.approve("case-1", "hash", 1, "attack", "rate_limit", 300)
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(lambda _: engine.probe("attack")["status_code"], range(4)))
    assert sorted(codes) == [200, 200, 200, 429]
    clock[0] += 5
    assert engine.probe("attack")["status_code"] == 429
    clock[0] += 1
    assert engine.probe("attack")["status_code"] == 200
    row = engine.list_policies("case-1")[0]
    assert row["affected_requests"] == 2 and row["allowed_requests"] == 4
    assert any(event["event"] == "rate_limited" for event in row["audit"])


def test_replacement_and_invalid_approvals(runtime):
    engine, _ = runtime
    old = approve(engine)
    new = engine.approve("case-2", "hash2", 1, "attack", "rate_limit", 60)
    assert old["id"] != new["id"]
    assert engine.list_policies("case-1")[0]["status"] == "revoked"
    assert engine.probe("attack")["status_code"] == 200
    for actor, action, ttl in [
        ("arbitrary", "temporary_block", 60),
        ("attack", "firewall", 60),
        ("attack", "temporary_block", 301),
    ]:
        with pytest.raises(ValueError):
            engine.approve("case-1", "hash", 1, actor, action, ttl)


def test_observed_expiry_never_reactivates_after_restart_or_clock_rollback(runtime):
    engine, clock = runtime
    approve(engine)
    clock[0] = 1061
    assert engine.probe("attack")["status_code"] == 200
    clock[0] = 1005
    reopened = EnforcementStore(str(engine.store.engine.url), clock=lambda: clock[0])
    assert reopened.probe("attack")["status_code"] == 200
    assert reopened.list_policies("case-1")[0]["status"] == "expired"
