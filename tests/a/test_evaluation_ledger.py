"""Durable group independence and one-shot frozen evaluation consumption."""

import hashlib
import importlib
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.pool import StaticPool

from tests.a.test_migrations import engine, postgres_url  # noqa: F401


def api():
    assert importlib.util.find_spec("bouncer.db.evaluations") is not None, "ledger missing"
    return importlib.import_module("bouncer.db.evaluations")


@pytest.fixture(params=["sqlite", "postgres"])
def ledger(request, tmp_path):
    database = (
        request.getfixturevalue("engine")
        if request.param == "postgres"
        else create_engine("sqlite:///" + str(tmp_path / "evaluations.db"))
    )
    value = api().EvaluationLedger(database)
    yield value
    if request.param == "sqlite":
        database.dispose()


def unit(value):
    return hashlib.sha256(value.encode()).hexdigest()


def reserve(ledger, name="one", *, development=("fit",), holdout=("test",), sources=("s1",)):
    return ledger.reserve(
        descriptor={"name": name},
        development_units={unit(x) for x in development},
        holdout_units={unit(x) for x in holdout},
        source_keys=sources,
    )


def freeze(ledger, name="one", **kwargs):
    record = reserve(ledger, name, **kwargs)
    return ledger.set_artifacts(record["preparation_id"], artifacts={"model": [0.1, 0.2]})


def test_reservation_precedes_artifacts_and_replays_exactly(ledger):
    record = reserve(ledger)
    expected = hashlib.sha256(b'{"name":"one"}').hexdigest()
    assert record["preparation_id"] == expected
    assert record["state"] == "reserved"
    assert record["artifacts"] == {} and record["report"] == {}
    assert record["artifact_digest"] is None
    assert api().EvaluationLedger(ledger.engine).get(expected) == record
    assert reserve(ledger) == record
    for kwargs in ({"development": ("other",)}, {"holdout": ("other",)}, {"sources": ("s2",)}):
        with pytest.raises(ValueError, match="reservation"):
            reserve(ledger, **kwargs)
    with ledger.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().units)) == 2


@pytest.mark.parametrize("old_role,new_role", [("fit", "test"), ("test", "fit"), ("test", "test")])
def test_roles_are_global_and_conflicts_roll_back_all_assignments(ledger, old_role, new_role):
    reserve(ledger)
    kwargs = {"development": ("fresh",), "holdout": ("fresh-test",)}
    kwargs["development" if new_role == "fit" else "holdout"] = (old_role, "fresh")
    with pytest.raises(ValueError, match="unit"):
        reserve(ledger, "other", **kwargs)
    with ledger.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().preparations)) == 1
        assert conn.scalar(select(func.count()).select_from(api().units)) == 2
    assert reserve(ledger, "development-reuse", holdout=("new-test",))["state"] == "reserved"


def test_frozen_artifacts_are_exact_immutable_json(ledger):
    record = freeze(ledger)
    identifier = record["preparation_id"]
    digest = hashlib.sha256(b'{"model":[0.1,0.2]}').hexdigest()
    assert record["state"] == "frozen" and record["artifact_digest"] == digest
    assert ledger.set_artifacts(identifier, artifacts={"model": [0.1, 0.2]}) == record
    with pytest.raises(ValueError, match="artifact"):
        ledger.set_artifacts(identifier, artifacts={"model": [0.1, 0.20000000000000004]})
    with pytest.raises(ValueError, match="digest"):
        ledger.claim(identifier, artifact_digest="0" * 64)
    assert ledger.get(identifier)["state"] == "frozen"


def test_claim_commits_before_work_and_complete_replay_is_cached(ledger):
    record = freeze(ledger)
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    claimed = ledger.claim(identifier, artifact_digest=digest)
    assert claimed["state"] == "claimed" and claimed["cached"] is False
    restarted = api().EvaluationLedger(ledger.engine)
    assert restarted.get(identifier)["state"] == "claimed"
    with pytest.raises(ValueError, match="consum"):
        restarted.claim(identifier, artifact_digest=digest)
    finished = restarted.finish(identifier, artifact_digest=digest, report={"count": 3})
    assert finished["state"] == "complete" and finished["report"] == {"count": 3}
    cached = restarted.claim(identifier, artifact_digest=digest)
    assert cached["cached"] is True and cached["report"] == finished["report"]
    with pytest.raises(ValueError, match="state"):
        restarted.finish(identifier, artifact_digest=digest, report={"count": 4})


@pytest.mark.parametrize("failure", ["analysis_failed", "validation_failed", "interrupted"])
def test_failed_consumption_survives_restart_without_retry(ledger, failure):
    record = freeze(ledger)
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    ledger.claim(identifier, artifact_digest=digest)
    ledger.finish(identifier, artifact_digest=digest, failure_code=failure)
    restarted = api().EvaluationLedger(ledger.engine)
    result = restarted.get(identifier)
    assert result["state"] == "unavailable" and result["failure_code"] == failure
    with pytest.raises(ValueError, match="consum"):
        restarted.claim(identifier, artifact_digest=digest)


def test_only_one_concurrent_claim_wins(ledger):
    record = freeze(ledger)

    def claim(_):
        try:
            return ledger.claim(record["preparation_id"], artifact_digest=record["artifact_digest"])
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(claim, range(4)))
    assert len([result for result in results if result is not None]) == 1


def test_revocation_scrubs_payloads_atomically_and_cannot_resurrect(ledger):
    record = freeze(ledger)
    other = freeze(ledger, "other", holdout=("other-test",), sources=("s2",))
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    ledger.claim(identifier, artifact_digest=digest)
    ledger.finish(identifier, artifact_digest=digest, report={"private": "report"})
    with pytest.raises(RuntimeError), ledger.engine.begin() as conn:
        api().purge_source_connection(conn, "s1")
        raise RuntimeError("rollback")
    assert ledger.get(identifier)["state"] == "complete"
    with ledger.engine.begin() as conn:
        api().purge_source_connection(conn, "s1")
    revoked = ledger.get(identifier)
    assert revoked["state"] == "revoked"
    assert revoked["descriptor"] == revoked["artifacts"] == revoked["report"] == {}
    assert revoked["artifact_digest"] == digest
    assert ledger.get(other["preparation_id"]) == other
    for operation in (
        lambda: reserve(ledger),
        lambda: ledger.set_artifacts(identifier, artifacts={}),
        lambda: ledger.claim(identifier, artifact_digest=digest),
        lambda: ledger.finish(identifier, artifact_digest=digest, report={}),
    ):
        with pytest.raises(ValueError, match="revoked"):
            operation()
    with pytest.raises(ValueError, match="unit"):
        reserve(ledger, "reuse", development=("test",), holdout=("fresh",))
    assert ledger.get(identifier) == revoked


@pytest.mark.parametrize(
    "kwargs",
    [
        {"descriptor": {"bad": float("nan")}},
        {"descriptor": {"bad": "x" * (16 * 1024 * 1024)}},
        {"descriptor": {"bad": "\x00"}},
        {"development_units": {"A" * 64}},
        {"holdout_units": set()},
        {"development_units": {unit("test")}},
        {"source_keys": ["bad\x00ref"]},
        {"source_keys": ["x" * 257]},
        {"source_keys": [f"source-{index}" for index in range(1001)]},
    ],
)
def test_untrusted_reservations_are_bounded_and_atomic(ledger, kwargs):
    params = (
        dict(
            descriptor={"name": "invalid"},
            development_units={unit("fit")},
            holdout_units={unit("test")},
            source_keys=["s1"],
        )
        | kwargs
    )
    with pytest.raises(ValueError):
        ledger.reserve(**params)
    with ledger.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().preparations)) == 0


def test_finish_requires_exactly_one_bounded_outcome(ledger):
    record = freeze(ledger)
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    ledger.claim(identifier, artifact_digest=digest)
    for kwargs in (
        {},
        {"report": {}, "failure_code": "interrupted"},
        {"failure_code": "secret text"},
        {"report": {"bad": float("inf")}},
    ):
        with pytest.raises(ValueError):
            ledger.finish(identifier, artifact_digest=digest, **kwargs)
    assert ledger.get(identifier)["state"] == "claimed"
    ledger.finish(identifier, artifact_digest=digest, report={})


def test_initialization_never_creates_or_resets_financial_budget(ledger):
    from bouncer.investigations.store import budget, metadata

    assert budget.name not in inspect(ledger.engine).get_table_names() or (
        ledger.engine.dialect.name == "postgresql"
    )
    metadata.create_all(ledger.engine)
    with ledger.engine.begin() as conn:
        conn.execute(budget.insert().values(id=1, spent=17, reserved=23, executions=2, requests=4))
    api().EvaluationLedger(ledger.engine)
    reserve(ledger)
    with ledger.engine.connect() as conn:
        row = conn.execute(select(budget)).mappings().one()
    assert row["spent"] == 17 and row["reserved"] == 23


def test_canonical_descriptor_has_no_whitespace_or_order_dependency(ledger):
    kwargs = dict(development_units=set(), holdout_units={unit("test")}, source_keys=[])
    first = ledger.reserve(descriptor={"b": [2, 1], "a": "ä"}, **kwargs)
    second = ledger.reserve(descriptor={"a": "ä", "b": [2, 1]}, **kwargs)
    content = json.dumps({"a": "ä", "b": [2, 1]}, sort_keys=True, separators=(",", ":"))
    assert first == second
    assert first["preparation_id"] == hashlib.sha256(content.encode()).hexdigest()


def test_shared_connection_obeys_caller_rollback_and_commit(ledger):
    kwargs = dict(
        descriptor={"name": "shared"},
        development_units=set(),
        holdout_units={unit("shared")},
        source_keys=["s1"],
    )
    with pytest.raises(RuntimeError), ledger.engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        record = ledger.reserve(**kwargs, connection=conn)
        ledger.set_artifacts(record["preparation_id"], artifacts={}, connection=conn)
        assert ledger.get(record["preparation_id"], connection=conn)["state"] == "frozen"
        raise RuntimeError("rollback")
    with pytest.raises(ValueError, match="unknown"):
        ledger.get(record["preparation_id"])
    with ledger.engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        record = ledger.reserve(**kwargs, connection=conn)
        record = ledger.set_artifacts(record["preparation_id"], artifacts={}, connection=conn)
        ledger.claim(
            record["preparation_id"], artifact_digest=record["artifact_digest"], connection=conn
        )
    assert ledger.get(record["preparation_id"])["state"] == "claimed"


def test_claimed_purge_is_blocked_until_explicit_interrupted_close(ledger):
    record = freeze(ledger)
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    ledger.claim(identifier, artifact_digest=digest)
    with (
        pytest.raises(ValueError, match="evaluation in progress"),
        ledger.engine.begin() as conn,
    ):
        api().purge_source_connection(conn, "s1")
    assert ledger.get(identifier)["state"] == "claimed"
    ledger.finish(identifier, artifact_digest=digest, failure_code="interrupted")
    with ledger.engine.begin() as conn:
        api().purge_source_connection(conn, "s1")
    assert ledger.get(identifier)["state"] == "revoked"


def test_concurrent_reservations_have_one_holdout_owner(ledger):
    def compete(name):
        try:
            return reserve(ledger, name)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(compete, ("one", "two", "three", "four")))
    assert len([result for result in results if result is not None]) == 1
    with ledger.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().preparations)) == 1


def test_concurrent_identical_reservations_are_exact_replay(ledger):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: reserve(ledger), range(4)))
    assert all(result == results[0] for result in results)


def test_shared_connection_rejects_wrong_engine_or_missing_transaction(ledger, tmp_path):
    other = create_engine("sqlite:///" + str(tmp_path / "other.db"))
    try:
        with other.begin() as conn, pytest.raises(ValueError, match="connection"):
            ledger.get("0" * 64, connection=conn)
        with ledger.engine.connect() as conn, pytest.raises(ValueError, match="connection"):
            ledger.get("0" * 64, connection=conn)
    finally:
        other.dispose()


def test_real_source_purge_revokes_and_blocked_purge_rolls_back_traffic(ledger):
    from bouncer.db.traffic import TrafficRepository
    from tests.a.test_participants import source

    traffic = TrafficRepository(ledger.engine)
    source(traffic, "s1")
    record = freeze(ledger)
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    ledger.claim(identifier, artifact_digest=digest)
    with pytest.raises(ValueError, match="evaluation in progress"):
        traffic.delete_source("s1", expected_checkpoint=traffic.load_checkpoint("s1"))
    assert len(traffic.load_sessions(source_key="s1")) == 1
    ledger.finish(identifier, artifact_digest=digest, failure_code="interrupted")
    traffic.delete_source("s1", expected_checkpoint=traffic.load_checkpoint("s1"))
    assert not traffic.load_sessions(source_key="s1")
    assert ledger.get(identifier)["state"] == "revoked"


def test_malformed_failure_code_raises_sanitized_error(ledger):
    record = freeze(ledger)
    ledger.claim(record["preparation_id"], artifact_digest=record["artifact_digest"])
    with pytest.raises(ValueError, match="failure code"):
        ledger.finish(
            record["preparation_id"],
            artifact_digest=record["artifact_digest"],
            failure_code=["private"],
        )


def test_shared_conflict_rolls_back_only_failed_reservation(ledger):
    reserve(ledger)
    failed_id = hashlib.sha256(b'{"name":"failed"}').hexdigest()
    with ledger.engine.begin() as conn:
        successful = ledger.reserve(
            descriptor={"name": "outer-work"},
            development_units={unit("outer-fit")},
            holdout_units={unit("outer-test")},
            source_keys=["s2"],
            connection=conn,
        )
        with pytest.raises(ValueError, match="unit"):
            ledger.reserve(
                descriptor={"name": "failed"},
                development_units={unit("fresh")},
                holdout_units={unit("test")},
                source_keys=["s1"],
                connection=conn,
            )
        assert ledger.get(successful["preparation_id"], connection=conn)["state"] == "reserved"
    assert ledger.get(successful["preparation_id"])["state"] == "reserved"
    with pytest.raises(ValueError, match="unknown"):
        ledger.get(failed_id)
    with pytest.raises(ValueError, match="unknown"):
        ledger.set_artifacts(failed_id, artifacts={})
    with pytest.raises(ValueError, match="unknown"):
        ledger.claim(failed_id, artifact_digest=hashlib.sha256(b"{}").hexdigest())
    with ledger.engine.connect() as conn:
        assert (
            conn.scalar(
                select(api().units.c.unit_hash).where(api().units.c.unit_hash == unit("fresh"))
            )
            is None
        )


def test_shared_operation_cannot_escape_sqlite_virtual_outer_rollback(ledger):
    identifier = hashlib.sha256(b'{"name":"virtual"}').hexdigest()
    with pytest.raises(RuntimeError), ledger.engine.begin() as conn:
        ledger.reserve(
            descriptor={"name": "virtual"},
            development_units=set(),
            holdout_units={unit("virtual")},
            source_keys=[],
            connection=conn,
        )
        raise RuntimeError("rollback caller")
    with pytest.raises(ValueError, match="unknown"):
        ledger.get(identifier)


@pytest.mark.parametrize("corruption", ["missing", "wrong-owner", "source-binding"])
def test_exact_replay_rejects_incomplete_or_incompatible_persisted_reservations(ledger, corruption):
    record = reserve(ledger)
    other = reserve(ledger, "other", holdout=("other-test",))
    with ledger.engine.begin() as conn:
        if corruption == "missing":
            conn.execute(api().units.delete().where(api().units.c.unit_hash == unit("test")))
        elif corruption == "wrong-owner":
            conn.execute(
                api()
                .units.update()
                .where(api().units.c.unit_hash == unit("test"))
                .values(preparation_id=other["preparation_id"])
            )
        else:
            conn.execute(
                api()
                .sources.delete()
                .where(api().sources.c.preparation_id == record["preparation_id"])
            )
    with pytest.raises(ValueError, match="unit|binding"):
        reserve(ledger)


@pytest.mark.parametrize("deferred", [False, True])
def test_shared_sqlite_claim_has_one_winner_with_plain_or_deferred_transaction(
    ledger,
    monkeypatch,
    deferred,
):
    if ledger.engine.dialect.name != "sqlite":
        pytest.skip("SQLite shared transaction semantics")
    record = freeze(ledger)
    if deferred:
        original = ledger._frozen
        barrier = Barrier(2)

        def synchronize(*args):
            current = original(*args)
            barrier.wait(timeout=5)
            return current

        monkeypatch.setattr(ledger, "_frozen", synchronize)

    def claim(_):
        try:
            with ledger.engine.begin() as conn:
                if deferred:
                    conn.exec_driver_sql("BEGIN")
                return ledger.claim(
                    record["preparation_id"],
                    artifact_digest=record["artifact_digest"],
                    connection=conn,
                )
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert len([result for result in results if result is not None]) == 1


@pytest.mark.parametrize("transition", ["artifacts", "claim", "finish"])
def test_state_transition_rejects_stale_preparation_reads(ledger, monkeypatch, transition):
    record = reserve(ledger) if transition == "artifacts" else freeze(ledger)
    identifier = record["preparation_id"]
    digest = record["artifact_digest"]
    if transition == "finish":
        ledger.claim(identifier, artifact_digest=digest)
    with ledger.engine.connect() as conn:
        stale = dict(ledger._get(conn, identifier))
    if transition == "artifacts":
        ledger.set_artifacts(identifier, artifacts={"original": True})
        original_get = ledger._get

        def stale_locked_read(conn, preparation_id, *, lock=False):
            return stale if lock else original_get(conn, preparation_id)

        monkeypatch.setattr(ledger, "_get", stale_locked_read)
        operation, kwargs = ledger.set_artifacts, {"artifacts": {"overwrite": True}}
    elif transition == "claim":
        ledger.claim(identifier, artifact_digest=digest)
        monkeypatch.setattr(ledger, "_frozen", lambda *args: stale)
        operation, kwargs = ledger.claim, {"artifact_digest": digest}
    else:
        ledger.finish(identifier, artifact_digest=digest, report={"original": True})
        monkeypatch.setattr(ledger, "_frozen", lambda *args: stale)
        operation, kwargs = (
            ledger.finish,
            {"artifact_digest": digest, "report": {"overwrite": True}},
        )
    with pytest.raises(ValueError, match="concurrently"):
        operation(identifier, **kwargs)
    current = ledger.get(identifier)
    if transition == "artifacts":
        assert current["artifacts"] == {"original": True}
    elif transition == "finish":
        assert current["report"] == {"original": True}
    else:
        assert current["state"] == "claimed"


def test_completed_report_digest_rejects_valid_shape_tampering_without_reopening(ledger):
    record = freeze(ledger)
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    ledger.claim(identifier, artifact_digest=digest)
    ledger.finish(
        identifier, artifact_digest=digest, report={"prediction": "uncertain", "score": 0.5}
    )
    with ledger.engine.begin() as conn:
        conn.execute(
            api()
            .preparations.update()
            .where(api().preparations.c.preparation_id == identifier)
            .values(report={"prediction": "bad_bot", "score": 1.0})
        )
    with pytest.raises(ValueError, match="report digest"):
        ledger.claim(identifier, artifact_digest=digest)
    assert ledger.get(identifier)["state"] == "complete"
    with pytest.raises(ValueError, match="state"):
        ledger.finish(identifier, artifact_digest=digest, report={})


@pytest.mark.parametrize("report", [{}, {"predictions": [{"value": 0.5}]}])
def test_report_digest_is_canonical_and_payload_has_no_caller_alias(ledger, report):
    report = json.loads(json.dumps(report))
    record = freeze(ledger)
    identifier, digest = record["preparation_id"], record["artifact_digest"]
    ledger.claim(identifier, artifact_digest=digest)
    expected = json.loads(json.dumps(report))
    content = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    expected_digest = hashlib.sha256(content.encode()).hexdigest()
    completed = ledger.finish(identifier, artifact_digest=digest, report=report)
    assert completed["report_digest"] == expected_digest
    report["mutated"] = True
    completed["report"]["mutated-return"] = True
    restarted = api().EvaluationLedger(ledger.engine)
    cached = restarted.claim(identifier, artifact_digest=digest)
    assert cached["report"] == expected and cached["report_digest"] == expected_digest
    with ledger.engine.begin() as conn:
        api().purge_source_connection(conn, "s1")
    revoked = restarted.get(identifier)
    assert revoked["report"] == {} and revoked["report_digest"] == expected_digest


@pytest.mark.parametrize(
    "url",
    [
        "sqlite://",
        "sqlite:///",
        "sqlite:///:memory:",
        "sqlite:///file::memory:?cache=shared&uri=true",
        "sqlite:///file:ledger-transient?mode=memory&cache=shared&uri=true",
    ],
)
def test_durable_ledger_rejects_transient_sqlite_before_initializing_tables(url):
    database = create_engine(url, poolclass=StaticPool)
    try:
        with pytest.raises(ValueError, match="durable"):
            api().EvaluationLedger(database)
        assert "evaluation_preparations" not in inspect(database).get_table_names()
    finally:
        database.dispose()


def test_finite_numeric_artifact_and_report_hashes_survive_database_roundtrip(ledger):
    values = [-0.0, 0.0, 1e-300, 1e300, 1.0, 0]
    prepared = ledger.reserve(
        descriptor={"numbers": values},
        development_units={unit("fit")},
        holdout_units={unit("test")},
        source_keys=["s1"],
    )
    identifier = prepared["preparation_id"]
    content = json.dumps(
        prepared["descriptor"], sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    assert hashlib.sha256(content.encode()).hexdigest() == identifier
    frozen = ledger.set_artifacts(identifier, artifacts={"weights": values})
    stored = ledger.get(identifier)
    content = json.dumps(
        stored["artifacts"], sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    assert hashlib.sha256(content.encode()).hexdigest() == frozen["artifact_digest"], (
        stored["artifacts"],
        [type(value).__name__ for value in stored["artifacts"]["weights"]],
    )
    ledger.claim(identifier, artifact_digest=frozen["artifact_digest"])
    ledger.finish(
        identifier, artifact_digest=frozen["artifact_digest"], report={"nested": {"values": values}}
    )
    cached = ledger.claim(identifier, artifact_digest=frozen["artifact_digest"])
    assert cached["cached"] is True
    content = json.dumps(cached["report"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert hashlib.sha256(content.encode()).hexdigest() == cached["report_digest"]
    assert type(cached["report"]["nested"]["values"][1]) is float
    assert json.dumps(cached["report"]["nested"]["values"][0]) == "0.0"
    assert type(cached["report"]["nested"]["values"][-2]) is float
    assert type(cached["report"]["nested"]["values"][-1]) is int
    assert cached["report"]["nested"]["values"][3] == 10**300


@pytest.mark.parametrize("source_count", [351, 1000])
def test_large_source_binding_sets_survive_restart_replay_and_selective_purge(ledger, source_count):
    keys = [f"subject-source-{index:04d}" for index in range(source_count)]
    record = reserve(ledger, sources=keys)
    other = reserve(ledger, "other", holdout=("other-test",), sources=["other-source"])
    restarted = api().EvaluationLedger(ledger.engine)
    assert api().MAX_SOURCE_BINDINGS == 1000
    assert restarted.get(record["preparation_id"]) == record
    assert reserve(restarted, sources=list(reversed(keys))) == record
    with ledger.engine.begin() as conn:
        api().purge_source_connection(conn, keys[-1])
    assert restarted.get(record["preparation_id"])["state"] == "revoked"
    assert restarted.get(other["preparation_id"]) == other
    with ledger.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().sources)) == source_count + 1
