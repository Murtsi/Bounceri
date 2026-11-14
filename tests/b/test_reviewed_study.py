from dataclasses import replace

import pytest

from bouncer.db.participants import ReviewedSession, session_digest
from tests.b.synthetic import human_session


def observation(*, source="private-one", behavior="manual", intent="benign", subject="actor-one"):
    session = human_session()
    return ReviewedSession(
        session=session, source_id=source, subject_id=subject, enrollment_id="collection-one",
        review_id="review-one", revision=1, digest=session_digest(session), behavior=behavior,
        intent=intent, provenance={"consent_ref": "private-reference"},
    )


def test_consent_and_automation_are_separate_from_human_reference_truth():
    from bouncer.eval.study import build_reviewed_corpus

    rows = [observation(source=str(index), behavior=behavior, intent=intent)
            for index, (behavior, intent) in enumerate([
                ("manual", "benign"), ("automated", "benign"),
                ("manual", "abusive"), ("unknown", "unknown"),
            ])]
    corpus = build_reviewed_corpus(rows)
    assert len(corpus.dataset.rows) == 1
    row = corpus.dataset.rows[0]
    assert (row.truth, row.source, row.origin) == ("human", "study", "real")
    assert row.actor_id == "actor-one"
    assert row.source_id == "0" and row.external_session_id == rows[0].session.id
    assert row.session_digest == rows[0].digest
    assert row.annotation_id == "review-one" and row.annotation_revision == 1
    assert row.ended_at == rows[0].session.ended_at
    assert "subject:actor-one" in row.group_ids
    assert len(corpus.dataset.unlabeled) == 3
    assert len(corpus.sessions) == len(corpus.observations) == 4


def test_same_native_session_id_in_distinct_sources_never_collides():
    from bouncer.eval.study import build_reviewed_corpus

    first = observation(source="source-one")
    second = observation(source="source-two")
    corpus = build_reviewed_corpus([first, second])
    keys = [row.session_id for row in corpus.dataset.rows]
    assert len(set(keys)) == 2
    assert set(keys) == set(corpus.sessions)
    assert all(corpus.sessions[key].id == key for key in keys)
    assert first.session.id == second.session.id
    assert {row.actor_id for row in corpus.dataset.rows} == {"actor-one"}


def test_changed_or_duplicate_reviewed_content_cannot_enter_reference_denominators():
    from bouncer.eval.study import build_reviewed_corpus

    row = observation()
    changed = replace(row, session=replace(row.session, requests=row.session.requests[:-1]))
    with pytest.raises(ValueError, match="changed"):
        build_reviewed_corpus([changed])
    with pytest.raises(ValueError, match="duplicate"):
        build_reviewed_corpus([row, row])


def test_study_bridge_does_not_merge_or_relabel_simulator_truth():
    from bouncer.eval.dataset import build_dataset
    from bouncer.eval.study import build_reviewed_corpus

    row = observation()
    studied = build_reviewed_corpus([row]).dataset
    legacy = build_dataset([row.session], [])
    assert legacy.rows == [] and len(legacy.unlabeled) == 1
    assert studied.summary()["by_origin_source_truth"] == {"real/study/human": 1}


def test_source_availability_mask_survives_study_reference_mapping():
    from bouncer.eval.study import build_reviewed_corpus

    row = replace(observation(), provenance={"source": {"unavailable_fields": ["target"]}})
    corpus = build_reviewed_corpus([row])
    assert list(corpus.unavailable_fields.values()) == [("target",)]
