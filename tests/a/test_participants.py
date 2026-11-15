"""Private consent collections and independently reviewed observations."""

import importlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select

from bouncer.contracts import Request, Session
from bouncer.db.store import _serialize_session
from bouncer.db.traffic import Checkpoint, SourceEvent, TrafficRepository
from tests.a.test_migrations import engine, postgres_url  # noqa: F401


def api():
    assert importlib.util.find_spec("bouncer.db.participants") is not None, "study storage missing"
    return importlib.import_module("bouncer.db.participants")


@pytest.fixture(params=["sqlite", "postgres"])
def study(request, tmp_path):
    database = (
        request.getfixturevalue("engine")
        if request.param == "postgres"
        else create_engine("sqlite:///" + str(tmp_path / "study.db"))
    )
    repo = TrafficRepository(database)
    store = api().StudyStore(database)
    yield store, repo
    if request.param == "sqlite":
        database.dispose()


START = datetime(2026, 11, 14, tzinfo=UTC)


def source(repo, key="collection-a", *, synthetic=False, count=1, expected=None):
    request = Request(START, "192.0.2.1", "GET", "/", 200, "fixture")
    session = Session(
        "same-session", request.ip, request.user_agent, START, START, (request,) * count
    )
    repo.apply_batch(
        key,
        events=[SourceEvent("fixture", i, request, session.id) for i in range(count)],
        snapshot={"synthetic": synthetic, "sessions": [_serialize_session(session)], "labels": []},
        checkpoint=Checkpoint("fixture", count),
        expected_checkpoint=expected,
    )
    return session


def enroll(store, key="collection-a", **kwargs):
    args = dict(
        source_key=key,
        consent_ref="consent-1",
        consent_version="v1",
        consent_granted_at=START - timedelta(hours=1),
        collection_from=START,
        collection_until=START + timedelta(hours=1),
        evaluation_allowed=True,
        exclusive_source=True,
        operator_ref="operator-1",
    )
    return store.enroll(**(args | kwargs))


def review(store, enrollment, **kwargs):
    args = dict(
        enrollment_id=enrollment["enrollment_id"],
        external_session_id="same-session",
        expected_revision=0,
        status="approved",
        behavior="manual",
        intent="benign",
        mapping_ref="mapping-1",
        evidence_ref="observation-1",
        reviewer_ref="reviewer-1",
    )
    args.update(kwargs)
    if "expected_session_digest" not in args:
        actual = next(
            (
                item
                for item in store.traffic.load_sessions(source_key=enrollment["source_key"])
                if item.id == args["external_session_id"]
            ),
            None,
        )
        args["expected_session_digest"] = api().session_digest(actual) if actual else "0" * 64
    return store.review_session(**args)


def test_enrollment_is_not_a_truth_label_and_review_uses_actual_session(study):
    store, repo = study
    actual = source(repo)
    enrolled = enroll(store)
    assert repo.load_labels(source_key="collection-a") == []
    assert store.load_approved(["collection-a"]) == []
    revision = review(store, enrolled)
    approved = store.load_approved(["collection-a"])
    assert len(approved) == 1
    assert approved[0].session == actual
    assert approved[0].digest == api().session_digest(actual)
    assert approved[0].subject_id == enrolled["subject_id"]
    assert approved[0].revision == revision["revision"] == 1
    assert approved[0].behavior == "manual" and approved[0].intent == "benign"


def test_same_subject_can_have_distinct_manual_and_automated_collections(study):
    store, repo = study
    source(repo)
    source(repo, "collection-b")
    first = enroll(store)
    second = enroll(store, "collection-b", subject_id=first["subject_id"])
    review(store, first)
    review(store, second, behavior="automated", intent="unknown")
    approved = store.load_approved(["collection-a", "collection-b"])
    assert {item.subject_id for item in approved} == {first["subject_id"]}
    assert {item.behavior for item in approved} == {"manual", "automated"}
    assert len({item.enrollment_id for item in approved}) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"exclusive_source": False},
        {"exclusive_source": 1},
        {"evaluation_allowed": 1},
        {"consent_ref": ""},
        {"consent_ref": "person@example.com"},
        {"consent_version": "a" * 129},
        {"operator_ref": ""},
        {"consent_granted_at": START + timedelta(seconds=1)},
        {"collection_from": START.replace(tzinfo=None)},
        {"collection_until": START},
        {"collection_until": START + timedelta(days=32)},
    ],
)
def test_enrollment_rejects_invalid_consent(study, change):
    store, repo = study
    source(repo)
    with pytest.raises(ValueError):
        enroll(store, **change)


def test_enrollment_rejects_synthetic_unknown_and_deleted_sources(study):
    store, repo = study
    source(repo, synthetic=True)
    with pytest.raises(ValueError):
        enroll(store)
    with pytest.raises(ValueError):
        enroll(store, "absent")
    source(repo, "deleted")
    repo.delete_source("deleted", expected_checkpoint=repo.load_checkpoint("deleted"))
    with pytest.raises(ValueError):
        enroll(store, "deleted")


def test_latest_review_and_exact_content_are_required(study):
    store, repo = study
    source(repo)
    enrollment = enroll(store)
    review(store, enrollment)
    with pytest.raises(ValueError):
        review(store, enrollment)
    review(store, enrollment, expected_revision=1, status="rejected")
    assert store.load_approved(["collection-a"]) == []
    review(store, enrollment, expected_revision=2)
    assert len(store.load_approved(["collection-a"])) == 1
    source(repo, count=2, expected=repo.load_checkpoint("collection-a"))
    assert store.load_approved(["collection-a"]) == []


@pytest.mark.parametrize(
    "change",
    [
        {"external_session_id": "absent"},
        {"reviewer_ref": ""},
        {"mapping_ref": ""},
        {"evidence_ref": "raw notes not permitted"},
        {"behavior": "human"},
        {"intent": "malicious"},
        {"status": "maybe"},
        {"expected_revision": True},
    ],
)
def test_review_rejects_missing_or_invalid_observation(study, change):
    store, repo = study
    source(repo)
    with pytest.raises(ValueError):
        review(store, enroll(store), **change)


def test_review_requires_all_requests_and_session_interval_in_consent_window(study):
    store, repo = study
    source(repo)
    enrollment = enroll(store, collection_from=START + timedelta(seconds=1))
    with pytest.raises(ValueError):
        review(store, enrollment)


def test_evaluation_permission_is_rechecked(study):
    store, repo = study
    source(repo)
    enrollment = enroll(store, evaluation_allowed=False)
    with pytest.raises(ValueError):
        review(store, enrollment)
    assert store.load_approved(["collection-a"]) == []


def test_withdrawal_purges_all_collections_only_and_prevents_resurrection(study):
    store, repo = study
    source(repo)
    source(repo, "collection-b")
    source(repo, "unrelated")
    enrolled = enroll(store)
    enroll(store, "collection-b", subject_id=enrolled["subject_id"])
    review(store, enrolled)
    report = store.withdraw(
        enrolled["subject_id"], confirm_subject=enrolled["subject_id"], writer_stopped=True
    )
    assert report["sources_purged"] == 2
    assert store.load_approved(["collection-a", "collection-b"]) == []
    assert repo.load_sessions(source_key="collection-a") == []
    assert len(repo.load_sessions(source_key="unrelated")) == 1
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().reviews)) == 0
        records = conn.execute(select(api().enrollments)).mappings().all()
        assert all(record["payload"] == {} and record["status"] == "purged" for record in records)
    with pytest.raises(ValueError):
        review(store, enrolled)
    with pytest.raises(ValueError):
        enroll(store, "unrelated", subject_id=enrolled["subject_id"])


def test_source_purge_erases_consent_and_review_payload(study):
    store, repo = study
    source(repo)
    enrollment = enroll(store)
    review(store, enrollment)
    repo.delete_source("collection-a", expected_checkpoint=repo.load_checkpoint("collection-a"))
    assert store.load_approved(["collection-a"]) == []
    with repo.engine.connect() as conn:
        assert conn.scalar(select(api().enrollments.c.payload)) == {}
        assert conn.scalar(select(func.count()).select_from(api().reviews)) == 0


def test_provenance_is_derived_from_source_and_absence_is_explicit(study):
    store, repo = study
    source(repo)
    enrolled = enroll(store)
    review(store, enrolled)
    assert (
        store.load_approved(["collection-a"])[0].provenance["consent"]["source_provenance"][
            "origin"
        ]
        == "unavailable"
    )
    with repo.engine.begin() as conn:
        from bouncer.db.traffic import sources

        conn.execute(
            sources.update()
            .where(sources.c.source_key == "collection-a")
            .values(
                snapshot={
                    "synthetic": False,
                    "source": {"kind": "private_collection", "id": "fixture"},
                }
            )
        )
    source(repo, "collection-b")
    with repo.engine.begin() as conn:
        conn.execute(
            sources.update()
            .where(sources.c.source_key == "collection-b")
            .values(
                snapshot={
                    "synthetic": False,
                    "source": {"kind": "private_collection", "id": "fixture"},
                }
            )
        )
    second = enroll(store, "collection-b")
    review(store, second)
    provenance = store.load_approved(["collection-b"])[0].provenance["consent"]["source_provenance"]
    assert provenance["origin"] == "recorded"
    assert len(provenance["origin_digest"]) == 64


@pytest.mark.parametrize("key", ["a\x00b", "a\ud800b"])
def test_invalid_database_text_is_rejected_without_driver_errors(study, key):
    store, _ = study
    with pytest.raises(ValueError):
        enroll(store, key)


def test_retention_of_reviewed_requests_invalidates_approval(study):
    store, repo = study
    source(repo)
    enrolled = enroll(store)
    review(store, enrolled)
    repo.apply_batch(
        "collection-a",
        events=[],
        snapshot={"synthetic": False},
        checkpoint=Checkpoint("fixture", 2),
        expected_checkpoint=repo.load_checkpoint("collection-a"),
    )
    assert len(store.load_approved(["collection-a"])) == 1
    repo.prune_before("collection-a", START + timedelta(seconds=1))
    assert store.load_approved(["collection-a"]) == []


def test_cross_source_session_ids_are_independent(study):
    store, repo = study
    source(repo)
    source(repo, "collection-b")
    enrolled = enroll(store)
    enroll(store, "collection-b")
    review(store, enrolled)
    assert len(store.load_approved(["collection-a"])) == 1
    assert store.load_approved(["collection-b"]) == []


def test_withdrawal_rolls_back_all_sources_and_preserves_budget_when_job_is_active(study):
    from bouncer.investigations.store import budget, jobs
    from tests.a.test_source_lifecycle import case_store, snapshot

    store, repo = study
    source(repo)
    source(repo, "collection-b")
    enrolled = enroll(store)
    enroll(store, "collection-b", subject_id=enrolled["subject_id"])
    review(store, enrolled)
    investigation = case_store(repo)
    case = investigation.create_from_legacy(snapshot(), "private-scope", source_id="collection-b")
    investigation.enqueue_review(case["id"], "fixture", 100)
    usage = investigation.usage()
    with pytest.raises(ValueError, match="queued|running"):
        store.withdraw(
            enrolled["subject_id"], confirm_subject=enrolled["subject_id"], writer_stopped=True
        )
    assert len(store.load_approved(["collection-a"])) == 1
    assert len(repo.load_sessions(source_key="collection-a")) == 1
    assert len(repo.load_sessions(source_key="collection-b")) == 1
    assert investigation.usage() == usage
    job = investigation.claim_job("fixture")
    investigation.finish_job(job["id"], "unavailable", "stopped")
    with repo.engine.connect() as conn:
        audit = {
            table.name: [dict(row) for row in conn.execute(select(table)).mappings()]
            for table in (jobs, budget)
        }
    store.withdraw(
        enrolled["subject_id"], confirm_subject=enrolled["subject_id"], writer_stopped=True
    )
    with repo.engine.connect() as conn:
        assert audit == {
            table.name: [dict(row) for row in conn.execute(select(table)).mappings()]
            for table in (jobs, budget)
        }


def test_concurrent_review_and_withdrawal_cannot_leave_approved_payloads(study):
    from concurrent.futures import ThreadPoolExecutor

    store, repo = study
    source(repo)
    enrolled = enroll(store)

    def approve():
        try:
            return review(store, enrolled)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        approval = pool.submit(approve)
        withdrawal = pool.submit(
            store.withdraw,
            enrolled["subject_id"],
            confirm_subject=enrolled["subject_id"],
            writer_stopped=True,
        )
        approval.result(timeout=10)
        withdrawal.result(timeout=10)
    assert store.load_approved(["collection-a"]) == []
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().reviews)) == 0


@pytest.mark.parametrize("change", [{"status": []}, {"behavior": {}}, {"intent": []}])
def test_review_rejects_non_string_enums(study, change):
    store, repo = study
    source(repo)
    with pytest.raises(ValueError):
        review(store, enroll(store), **change)


def test_actual_source_availability_mask_reaches_reviewed_session(study):
    from bouncer.db.traffic import sources

    store, repo = study
    source(repo)
    with repo.engine.begin() as conn:
        conn.execute(
            sources.update()
            .where(sources.c.source_key == "collection-a")
            .values(
                snapshot={
                    "synthetic": False,
                    "unavailable_fields": {"same-session": ["headers", "bytes"]},
                }
            )
        )
    enrolled = enroll(store)
    packet = store.inspect_session(enrollment_id=enrolled["enrollment_id"],
                                   external_session_id="same-session")
    assert packet["source"]["unavailable_fields"] == ["headers", "bytes"]
    review(store, enrolled)
    assert store.load_approved(["collection-a"])[0].provenance["source"]["unavailable_fields"] == [
        "headers",
        "bytes",
    ]


@pytest.mark.parametrize("status", ["pending", "approved", "rejected"])
def test_review_requires_digest_of_deliberately_inspected_actual_content(study, status):
    store, repo = study
    original = source(repo)
    enrolled = enroll(store)
    stale_digest = api().session_digest(original)
    source(repo, count=2, expected=repo.load_checkpoint("collection-a"))
    with pytest.raises(ValueError, match="content changed"):
        review(store, enrolled, status=status, expected_session_digest=stale_digest)
    assert store.load_approved(["collection-a"]) == []
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().reviews)) == 0


def test_pending_annotation_revision_cannot_approve_changed_session_content(study):
    store, repo = study
    original = source(repo)
    enrolled = enroll(store)
    pending = review(store, enrolled, status="pending")
    assert pending["digest"] == api().session_digest(original)
    source(repo, count=2, expected=repo.load_checkpoint("collection-a"))
    with pytest.raises(ValueError, match="content changed"):
        review(store, enrolled, expected_revision=1, expected_session_digest=pending["digest"])
    assert store.load_approved(["collection-a"]) == []
    with repo.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(api().reviews)) == 1
    fresh = review(store, enrolled, expected_revision=1)
    assert fresh["digest"] != pending["digest"]
    assert fresh["revision"] == 2


@pytest.mark.parametrize("digest", [None, "", "a" * 63, "g" * 64, "A" * 64, ["a"] * 64])
def test_review_rejects_invalid_expected_digest(study, digest):
    store, repo = study
    source(repo)
    with pytest.raises(ValueError, match="digest"):
        review(store, enroll(store), expected_session_digest=digest)


def test_inspection_returns_actual_content_digest_and_independent_annotation_revision(study):
    store, repo = study
    original = source(repo)
    enrolled = enroll(store)
    assert hasattr(store, "inspect_session"), "private session inspection missing"
    first = store.inspect_session(
        enrollment_id=enrolled["enrollment_id"], external_session_id=original.id
    )
    assert first == {
        "enrollment_id": enrolled["enrollment_id"],
        "source_key": "collection-a",
        "external_session_id": original.id,
        "session": _serialize_session(original),
        "digest": api().session_digest(original),
        "expected_revision": 0,
        "source": {"synthetic": False, "origin": "unavailable", "unavailable_fields": [],
                   "runtime_context": {"availability": "unavailable",
                                       "reason": "runtime_context_unavailable"}},
    }
    review(store, enrolled, status="pending", expected_session_digest=first["digest"])
    revised = source(repo, count=2, expected=repo.load_checkpoint("collection-a"))
    second = store.inspect_session(
        enrollment_id=enrolled["enrollment_id"], external_session_id=original.id
    )
    assert second["session"] == _serialize_session(revised)
    assert second["digest"] != first["digest"]
    assert second["expected_revision"] == 1


@pytest.mark.parametrize("invalid", ["absent_session", "outside_window", "permission", "purged"])
def test_inspection_rechecks_active_consent_and_actual_session(study, invalid):
    store, repo = study
    source(repo)
    options = (
        {"collection_from": START + timedelta(seconds=1)} if invalid == "outside_window" else {}
    )
    if invalid == "permission":
        options["evaluation_allowed"] = False
    enrolled = enroll(store, **options)
    if invalid == "purged":
        repo.delete_source("collection-a", expected_checkpoint=repo.load_checkpoint("collection-a"))
    assert hasattr(store, "inspect_session"), "private session inspection missing"
    with pytest.raises(ValueError):
        store.inspect_session(
            enrollment_id=enrolled["enrollment_id"],
            external_session_id="missing" if invalid == "absent_session" else "same-session",
        )


def test_fresh_postgres_approval_reads_lock_shared_subjects_consistently(engine):  # noqa: F811
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, local
    from time import sleep

    from sqlalchemy import event, text

    store = api().StudyStore(engine)
    for key in ("a", "b", "c", "d"):
        source(store.traffic, key)
    first = enroll(store, "a")
    second = enroll(store, "b")
    enrollments = [first, second, enroll(store, "c", subject_id=second["subject_id"]),
                   enroll(store, "d", subject_id=first["subject_id"])]
    for enrollment in enrollments:
        review(store, enrollment)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM investigation_budget")) == 0
    ready, state = Barrier(2), local()
    subject = store._subject

    def sources_locked(conn, cursor, statement, parameters, context, executemany):
        if "WHERE traffic_sources.source_key IN" in statement and "FOR UPDATE" in statement:
            ready.wait(timeout=5)

    def paced_subject(conn, subject_id):
        row = subject(conn, subject_id)
        if not getattr(state, "first_subject", False):
            state.first_subject = True
            sleep(0.15)
        return row

    store._subject = paced_subject
    event.listen(engine, "after_cursor_execute", sources_locked)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            left = pool.submit(store.load_approved, ["a", "b"])
            right = pool.submit(store.load_approved, ["c", "d"])
            assert len(left.result(timeout=10)) == len(right.result(timeout=10)) == 2
    finally:
        event.remove(engine, "after_cursor_execute", sources_locked)


def test_current_approval_guard_can_share_an_existing_atomic_transaction(study):
    store, repo = study
    source(repo)
    enrolled = enroll(store)
    review(store, enrolled)
    with pytest.raises(RuntimeError, match="rollback"), store._transaction() as conn:
        current = store._load_approved_connection(conn, ["collection-a"])
        assert len(current) == 1
        conn.execute(api().subjects.update().where(
            api().subjects.c.subject_id == enrolled["subject_id"]
        ).values(status="withdrawn"))
        assert store._load_approved_connection(conn, ["collection-a"]) == []
        raise RuntimeError("rollback")
    assert len(store.load_approved(["collection-a"])) == 1
