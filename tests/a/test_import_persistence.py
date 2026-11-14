"""Uploaded traffic and its redacted case are one private, immutable transaction."""

from copy import deepcopy

import pytest
from sqlalchemy import event, func, select

from bouncer.db import traffic
from bouncer.investigations import InvestigationStore
from bouncer.investigations.store import assessments, cases, jobs
from tests.a.test_migrations import engine, postgres_url  # noqa: F401
from tests.a.test_traffic_repository import fixture_payload


@pytest.fixture(params=["sqlite", "postgres"])
def store(request, tmp_path):
    url = (request.getfixturevalue("engine").url.render_as_string(hide_password=False)
           if request.param == "postgres" else f"sqlite:///{tmp_path / 'imports.db'}")
    value = InvestigationStore(url)
    yield value
    value.engine.dispose()


def snapshot(synthetic=False):
    return fixture_payload()[3] | {"labels": [], "synthetic": synthetic}


def import_case(store, raw=None, **kwargs):
    return store.create_traffic_import(
        snapshot() if raw is None else raw,
        source_key="import/one",
        report={"accepted": 2, "private_detail": "REPORT-CANARY"},
        provenance={"format": "caddy_jsonl", "name": "PROVENANCE-CANARY"},
        **kwargs,
    )


def test_case_failure_rolls_back_source_normalized_traffic_and_assessment(store):
    repo = traffic.TrafficRepository(store.engine)

    def fail_case(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO investigation_cases"):
            assert conn.scalar(select(func.count()).select_from(traffic.requests)) == 2
            raise RuntimeError("injected case failure")

    event.listen(store.engine, "before_cursor_execute", fail_case)
    try:
        with pytest.raises(RuntimeError, match="injected case failure"):
            import_case(store)
    finally:
        event.remove(store.engine, "before_cursor_execute", fail_case)
    with store.engine.connect() as conn:
        for table in (traffic.sources, traffic.requests, traffic.sessions, traffic.labels,
                      cases, assessments, jobs):
            assert conn.scalar(select(func.count()).select_from(table)) == 0
    assert repo.load_sessions(source_key="import/one") == []


@pytest.mark.parametrize("synthetic", [False, True])
def test_import_is_private_with_native_traffic_and_only_redacted_case_metadata(store, synthetic):
    raw = snapshot(synthetic)
    original = deepcopy(raw)
    case = import_case(store, raw)
    repo = traffic.TrafficRepository(store.engine)
    saved = repo.load_snapshot("import/one")
    assert saved["sessions"] == raw["sessions"]
    assert saved["import_report"]["private_detail"] == "REPORT-CANARY"
    assert saved["source_provenance"]["name"] == "PROVENANCE-CANARY"
    assert raw == original
    assert case["source"] == {"kind": "uploaded_log", "synthetic": synthetic}
    assert "REPORT-CANARY" not in str(case)
    assert "PROVENANCE-CANARY" not in str(case)
    assert store.list_cases() == []
    assert store.get_case(case["id"]) is None
    assert store.get_case(case["id"], False) == case
    assert store.list_assessments(case["id"])[0]["stage"] == "local"
    assert case["review"]["status"] == "not_requested"
    assert store.usage()["executions"] == 0
    assert repo.load_labels(source_key="import/one") == []
    with store.engine.connect() as conn:
        assert conn.scalar(select(traffic.sources.c.read_only)) is True
    with pytest.raises(ValueError, match="immutable archive"):
        repo.save_snapshot(saved | {"synthetic": not synthetic}, source_key="import/one")
    with pytest.raises(ValueError, match="read-only archive"):
        repo.apply_batch(
            "import/one", events=[], snapshot=raw,
            checkpoint=traffic.Checkpoint("live", 1), expected_checkpoint=None,
        )


def test_explicit_synthetic_import_can_be_public_demo(store):
    case = import_case(store, snapshot(True), public_demo=True)
    assert store.get_case(case["id"]) == case
    assert store.list_cases() == [case]


@pytest.mark.parametrize("synthetic", [False, None, 1, "true"])
def test_publication_requires_explicit_true_synthetic_provenance(store, synthetic):
    with pytest.raises(ValueError, match="synthetic"):
        import_case(store, snapshot(synthetic), public_demo=True)
    repo = traffic.TrafficRepository(store.engine)
    with store.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(traffic.sources)) == 0
    assert repo.load_sessions(source_key="import/one") == []


def test_missing_synthetic_provenance_is_rejected(store):
    raw = snapshot()
    del raw["synthetic"]
    with pytest.raises(ValueError, match="synthetic"):
        import_case(store, raw)


def test_untrusted_import_labels_are_rejected_before_any_write(store):
    with pytest.raises(ValueError, match="labels"):
        import_case(store, fixture_payload()[3])
    repo = traffic.TrafficRepository(store.engine)
    with store.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(traffic.sources)) == 0
    assert repo.load_labels(source_key="import/one") == []
