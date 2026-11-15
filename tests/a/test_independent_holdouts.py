"""Synthetic fixtures for the private declared-independent commitment registry."""

import hashlib
import importlib
import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, update

from bouncer.db.evaluations import EvaluationLedger, preparations, purge_source_connection
from tests.a.test_migrations import engine, postgres_url  # noqa: F401

BUNDLE = b'{"fixture":"controlled-attack"}'
DIGEST = hashlib.sha256(BUNDLE).hexdigest()


def api():
    assert importlib.util.find_spec("bouncer.db.holdouts") is not None, "registry missing"
    return importlib.import_module("bouncer.db.holdouts")


@pytest.fixture(params=["sqlite", "postgres"])
def registry(request, tmp_path):
    database = (
        request.getfixturevalue("engine")
        if request.param == "postgres"
        else create_engine("sqlite:///" + str(tmp_path / "holdouts.db"))
    )
    value = api().IndependentHoldouts(database)
    yield value
    if request.param == "sqlite":
        database.dispose()


def seal(registry, **kwargs):
    return registry.seal(
        **dict(
            bundle_digest=DIGEST,
            author_ref="author-fixture-1",
            permission_ref="permission-fixture-1",
            independence_ref="independence-fixture-1",
            declared_independent=True,
        ) | kwargs
    )


def candidate(registry, name="candidate", *, frozen=True):
    ledger = EvaluationLedger(registry.engine)
    record = ledger.reserve(
        descriptor={"fixture": name},
        development_units=set(),
        holdout_units={hashlib.sha256(name.encode()).hexdigest()},
        source_keys=["source-fixture"],
    )
    if frozen:
        record = ledger.set_artifacts(record["preparation_id"], artifacts={"weights": [0.1]})
    return record


def reveal(registry, sealed, parent, bundle=BUNDLE):
    return registry.reveal(
        sealed["holdout_id"],
        preparation_id=parent["preparation_id"],
        artifact_digest=parent["artifact_digest"],
        bundle=bundle,
    )


def test_seal_is_private_durable_idempotent_and_declared_only(registry):
    sealed = seal(registry)
    assert uuid.UUID(sealed["holdout_id"]).version == 4
    assert sealed["state"] == "sealed"
    assert sealed["preparation_id"] is sealed["artifact_digest"] is sealed["revealed_at"] is None
    assert "bundle" not in sealed
    assert sealed["independence_status"] == "owner_declared_not_independently_verified"
    assert datetime.fromisoformat(sealed["sealed_at"]).tzinfo is not None
    restarted = api().IndependentHoldouts(registry.engine)
    assert restarted.get(sealed["holdout_id"]) == sealed == seal(restarted)
    with pytest.raises(ValueError, match="revealed"):
        restarted.read_revealed(sealed["holdout_id"])
    for field in ("author_ref", "permission_ref", "independence_ref"):
        with pytest.raises(ValueError, match="declaration"):
            seal(registry, **{field: "different"})
    with registry.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().holdouts)) == 1
        assert conn.scalar(select(api().holdouts.c.bundle)) is None


def test_reveal_requires_earlier_seal_frozen_actual_candidate_and_exact_replay(registry):
    sealed = seal(registry)
    reserved = candidate(registry, frozen=False)
    with pytest.raises(ValueError, match="frozen"):
        reveal(registry, sealed, reserved | {"artifact_digest": "0" * 64})
    parent = EvaluationLedger(registry.engine).set_artifacts(
        reserved["preparation_id"], artifacts={"weights": [0.1]}
    )
    with pytest.raises(ValueError, match="artifact"):
        reveal(registry, sealed, parent | {"artifact_digest": "0" * 64})
    result = reveal(registry, sealed, parent)
    assert result["cached"] is False and result["state"] == "revealed"
    assert result["preparation_id"] == parent["preparation_id"]
    assert result["artifact_digest"] == parent["artifact_digest"]
    assert (
        datetime.fromisoformat(result["revealed_at"])
        > datetime.fromisoformat(parent["created_at"])
    )
    restarted = api().IndependentHoldouts(registry.engine)
    assert restarted.read_revealed(sealed["holdout_id"]) == BUNDLE
    assert reveal(restarted, sealed, parent) == result | {"cached": True}
    other = candidate(registry, "other")
    with pytest.raises(ValueError, match="bound"):
        reveal(registry, sealed, other)


def test_seal_after_candidate_or_equal_timestamp_cannot_be_used(registry):
    parent = candidate(registry)
    sealed = seal(registry)
    with pytest.raises(ValueError, match="precede"):
        reveal(registry, sealed, parent)
    with registry.engine.begin() as conn:
        conn.execute(
            update(preparations).values(created_at=datetime.fromisoformat(sealed["sealed_at"]))
        )
    with pytest.raises(ValueError, match="precede"):
        reveal(registry, sealed, parent)
    with registry.engine.begin() as conn:
        conn.execute(update(preparations).values(created_at=datetime.now(UTC) + timedelta(days=1)))
    with pytest.raises(ValueError, match="timeline"):
        reveal(registry, sealed, parent)


@pytest.mark.parametrize(
    "changes",
    [
        {"bundle_digest": "A" * 64}, {"bundle_digest": 1}, {"author_ref": ""},
        {"permission_ref": "x" * 129}, {"independence_ref": "person name"},
        {"author_ref": "private@example.org"}, {"author_ref": "\u00e4"},
        {"permission_ref": "bad\x00"}, {"declared_independent": False},
        {"declared_independent": 1}, {"permission_ref": None},
    ],
)
def test_invalid_declarations_are_sanitized_and_never_written(registry, changes):
    with pytest.raises(ValueError, match="invalid holdout") as error:
        seal(registry, **changes)
    assert all(str(value) not in str(error.value) for value in changes.values() if value)
    with registry.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().holdouts)) == 0


@pytest.mark.parametrize(
    "bundle", [b"different", b"", "not bytes", bytearray(BUNDLE), b"x" * (16 * 1024 * 1024 + 1)],
    ids=["checksum", "empty", "string", "mutable", "oversized"],
)
def test_invalid_reveal_bytes_are_atomic(registry, bundle):
    sealed = seal(registry)
    parent = candidate(registry)
    with pytest.raises(ValueError, match="bundle"):
        reveal(registry, sealed, parent, bundle)
    assert registry.get(sealed["holdout_id"])["state"] == "sealed"


@pytest.mark.parametrize(
    "field,value", [("artifacts", {"changed": True}), ("state", "unavailable")]
)
def test_current_parent_corruption_and_source_purge_deny_bytes(registry, field, value):
    sealed = seal(registry)
    parent = candidate(registry)
    reveal(registry, sealed, parent)
    with registry.engine.begin() as conn:
        conn.execute(update(preparations).values(**{field: value}))
    with pytest.raises(ValueError):
        registry.read_revealed(sealed["holdout_id"])
    with pytest.raises(ValueError):
        reveal(registry, sealed, parent)


def test_source_purge_blocks_read_and_explicit_revoke_scrubs_without_resurrection(registry):
    sealed = seal(registry)
    parent = candidate(registry)
    reveal(registry, sealed, parent)
    with registry.engine.begin() as conn:
        purge_source_connection(conn, "source-fixture")
    with pytest.raises(ValueError, match="frozen"):
        registry.read_revealed(sealed["holdout_id"])
    with pytest.raises(ValueError, match="confirmation"):
        registry.revoke(sealed["holdout_id"], confirm_holdout="wrong")
    revoked = registry.revoke(sealed["holdout_id"], confirm_holdout=sealed["holdout_id"])
    assert revoked["state"] == "revoked"
    assert revoked["bundle_digest"] == DIGEST
    assert revoked["artifact_digest"] == parent["artifact_digest"]
    assert revoked["author_ref"] is revoked["permission_ref"] is revoked["independence_ref"] is None
    with registry.engine.connect() as conn:
        assert conn.scalar(select(api().holdouts.c.bundle)) is None
    assert registry.revoke(sealed["holdout_id"], confirm_holdout=sealed["holdout_id"]) == revoked
    with pytest.raises(ValueError, match="revoked"):
        seal(registry)
    with pytest.raises(ValueError, match="revealed"):
        registry.read_revealed(sealed["holdout_id"])


def test_only_one_candidate_wins_concurrent_binding(registry):
    sealed = seal(registry)
    parents = [candidate(registry, str(index)) for index in range(4)]

    def attempt(parent):
        try:
            return reveal(registry, sealed, parent)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [value for value in pool.map(attempt, parents) if value is not None]
    assert len(results) == 1
    assert registry.get(sealed["holdout_id"])["preparation_id"] == results[0]["preparation_id"]


def test_no_in_memory_registry_claims_durability():
    with pytest.raises(ValueError, match="durable"):
        api().IndependentHoldouts(create_engine("sqlite:///:memory:"))
