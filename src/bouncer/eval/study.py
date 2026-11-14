"""Bridge current private approvals to reference observations, never simulator labels.

Call StudyStore.load_approved immediately before building this in-memory corpus.
Stored copies require renewed consent/review checks before evaluation. This bridge
does not split, train, evaluate, or authorize production metric publication.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, replace

from bouncer.contracts import Session
from bouncer.db.participants import ReviewedSession, session_digest
from bouncer.eval.dataset import Dataset, DatasetRow
from bouncer.session.features import compute_features


@dataclass
class ReviewedCorpus:
    dataset: Dataset
    sessions: dict[str, Session]
    observations: dict[str, ReviewedSession]
    unavailable_fields: dict[str, tuple[str, ...]]


def observation_key(row: ReviewedSession) -> str:
    content = json.dumps([row.source_id, row.session.id, row.digest], separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


def build_reviewed_corpus(observations: Iterable[ReviewedSession]) -> ReviewedCorpus:
    corpus = ReviewedCorpus(Dataset(), {}, {}, {})
    for row in observations:
        if session_digest(row.session) != row.digest:
            raise ValueError("reviewed session content changed")
        key = observation_key(row)
        if key in corpus.sessions:
            raise ValueError("duplicate reviewed observation")
        corpus.observations[key] = row
        corpus.sessions[key] = replace(row.session, id=key)
        corpus.unavailable_fields[key] = tuple(
            row.provenance.get("source", {}).get("unavailable_fields", ())
        )
        features = compute_features(row.session)
        if row.behavior == "manual" and row.intent == "benign":
            corpus.dataset.rows.append(DatasetRow(
                key, row.session.started_at, features, "human", "consented_manual_benign",
                "study", "real", source_id=row.source_id, external_session_id=row.session.id,
                actor_id=row.subject_id, ended_at=row.session.ended_at,
                group_ids=("subject:" + row.subject_id, "collection:" + row.enrollment_id),
                session_digest=row.digest, annotation_id=row.review_id,
                annotation_revision=row.revision,
            ))
        else:
            # Automation and intent observations do not establish either bot traffic class.
            corpus.dataset.unlabeled.append((key, features))
    return corpus
