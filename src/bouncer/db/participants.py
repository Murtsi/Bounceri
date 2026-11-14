"""Private, consented collections; enrollment never supplies session truth labels."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    delete,
    insert,
    inspect,
    select,
    update,
)
from sqlalchemy.engine import Engine

from bouncer.contracts import Session
from bouncer.db.store import _dt, _serialize_session
from bouncer.db.traffic import DOCUMENT, TrafficRepository, sources

metadata = MetaData()
subjects = Table(
    "study_subjects",
    metadata,
    Column("subject_id", Text, primary_key=True),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("withdrawn_at", DateTime(timezone=True)),
)
enrollments = Table(
    "study_enrollments",
    metadata,
    Column("enrollment_id", Text, primary_key=True),
    Column("subject_id", Text, ForeignKey("study_subjects.subject_id"), nullable=False),
    Column("source_key", Text, nullable=False, unique=True),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", DOCUMENT, nullable=False),
)
reviews = Table(
    "study_session_reviews",
    metadata,
    Column("review_id", Text, primary_key=True),
    Column("enrollment_id", Text, ForeignKey("study_enrollments.enrollment_id"), nullable=False),
    Column("external_session_id", Text, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("digest", Text, nullable=False),
    Column("behavior", Text, nullable=False),
    Column("intent", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", DOCUMENT, nullable=False),
    UniqueConstraint("enrollment_id", "external_session_id", "revision"),
)


@dataclass(frozen=True)
class ReviewedSession:
    session: Session
    source_id: str
    subject_id: str
    enrollment_id: str
    review_id: str
    revision: int
    digest: str
    behavior: str
    intent: str
    provenance: dict


def session_digest(session: Session) -> str:
    """Bind observation approval to every serialized field and request multiplicity."""
    content = json.dumps(
        _serialize_session(session),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _ref(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", value) is None
    ):
        raise ValueError("invalid opaque reference")
    return value


def _uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid study identity") from None
    return value


def _database_text(value):
    if not isinstance(value, str) or not value or len(value) > 256 or "\x00" in value:
        raise ValueError("invalid collection identity")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("invalid collection identity") from None
    return value


def _source_provenance(snapshot, session_id=None):
    origin = {
        key: snapshot[key]
        for key in ("source", "source_provenance", "import_provenance")
        if key in snapshot
    }
    result = {"synthetic": False, "origin": "recorded" if origin else "unavailable"}
    if origin:
        result["origin_digest"] = hashlib.sha256(
            json.dumps(origin, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
    if session_id is not None:
        result["unavailable_fields"] = snapshot.get("unavailable_fields", {}).get(session_id, [])
    return result


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("collection times must be timezone-aware")
    return value.astimezone(UTC)


def purge_source_connection(conn, source_key):
    """Called only with the traffic source locked, inside its purge transaction."""
    if enrollments.name not in inspect(conn).get_table_names():
        return
    ids = select(enrollments.c.enrollment_id).where(enrollments.c.source_key == source_key)
    conn.execute(delete(reviews).where(reviews.c.enrollment_id.in_(ids)))
    conn.execute(
        update(enrollments)
        .where(enrollments.c.source_key == source_key)
        .values(
            status="purged",
            payload={},
        )
    )


class StudyStore:
    def __init__(self, database: str | Engine):
        self.traffic = TrafficRepository(database)
        self.engine = self.traffic.engine
        if self.engine.dialect.name != "postgresql":
            metadata.create_all(self.engine)

    @contextmanager
    def _transaction(self):
        from bouncer.investigations.store import budget

        with self.engine.begin() as conn:
            if conn.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            if budget.name in inspect(conn).get_table_names():
                conn.execute(select(budget).where(budget.c.id == 1).with_for_update())
            yield conn

    def _source(self, conn, source_key):
        _database_text(source_key)
        row = (
            conn.execute(
                select(sources).where(sources.c.source_key == source_key).with_for_update()
            )
            .mappings()
            .first()
        )
        if (
            row is None
            or row["snapshot"].get("synthetic") is not False
            or (row["snapshot"].get("source_deleted") or row["snapshot"].get("public") is True)
        ):
            raise ValueError("collection requires an existing private non-synthetic source")
        if self.traffic._labels(conn, source_key):
            raise ValueError("collection source cannot carry simulator labels")
        return row

    def _subject(self, conn, subject_id):
        row = (
            conn.execute(
                select(subjects).where(subjects.c.subject_id == subject_id).with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None or row["status"] != "active":
            raise ValueError("study subject is not active")
        return row

    def enroll(
        self,
        *,
        source_key,
        consent_ref,
        consent_version,
        consent_granted_at,
        collection_from,
        collection_until,
        evaluation_allowed,
        exclusive_source,
        operator_ref,
        subject_id=None,
    ) -> dict:
        consent_ref, consent_version, operator_ref = map(
            _ref, (consent_ref, consent_version, operator_ref)
        )
        granted, start, end = map(_utc, (consent_granted_at, collection_from, collection_until))
        now = datetime.now(UTC)
        if not (granted <= start < end and granted <= now and end - start <= timedelta(days=31)):
            raise ValueError("invalid consent collection window")
        if type(evaluation_allowed) is not bool or exclusive_source is not True:
            raise ValueError(
                "explicit evaluation permission and exclusive source attestation required"
            )
        if subject_id is not None:
            _uuid(subject_id)
        with self._transaction() as conn:
            source = self._source(conn, source_key)
            if (
                conn.scalar(
                    select(enrollments.c.enrollment_id).where(
                        enrollments.c.source_key == source_key
                    )
                )
                is not None
            ):
                raise ValueError("collection source already enrolled")
            if subject_id is None:
                subject_id = str(uuid4())
                conn.execute(
                    insert(subjects).values(subject_id=subject_id, status="active", created_at=now)
                )
            else:
                self._subject(conn, subject_id)
            enrollment_id = str(uuid4())
            payload = {
                "consent_ref": consent_ref,
                "consent_version": consent_version,
                "consent_granted_at": granted.isoformat(),
                "collection_from": start.isoformat(),
                "collection_until": end.isoformat(),
                "evaluation_allowed": evaluation_allowed,
                "exclusive_source": True,
                "operator_ref": operator_ref,
                "operator_at": now.isoformat(),
                "source_provenance": _source_provenance(source["snapshot"]),
            }
            conn.execute(
                insert(enrollments).values(
                    enrollment_id=enrollment_id,
                    subject_id=subject_id,
                    source_key=source_key,
                    status="active",
                    created_at=now,
                    payload=payload,
                )
            )
        return {"enrollment_id": enrollment_id, "subject_id": subject_id, "source_key": source_key}

    def _enrollment(self, conn, enrollment_id):
        row = (
            conn.execute(
                select(enrollments)
                .where(enrollments.c.enrollment_id == enrollment_id)
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None or row["status"] != "active":
            raise ValueError("collection consent is not active")
        payload = row["payload"]
        if (
            payload.get("evaluation_allowed") is not True
            or payload.get("exclusive_source") is not True
        ):
            raise ValueError("collection evaluation permission required")
        return row

    def _session(self, conn, enrollment, external_session_id):
        session = next(
            iter(
                self.traffic._sessions(
                    conn, enrollment["source_key"], external_id=external_session_id
                )
            ),
            None,
        )
        if session is None:
            raise ValueError("unknown collection session")
        return self._check_window(enrollment, session)

    def _check_window(self, enrollment, session):
        payload = enrollment["payload"]
        start, end = _dt(payload["collection_from"]), _dt(payload["collection_until"])
        if (
            not session.requests
            or not start <= session.started_at <= session.ended_at <= end
            or any(not start <= request.ts <= end for request in session.requests)
        ):
            raise ValueError("session is outside consent collection window")
        return session

    def _inspect_session_connection(self, conn, enrollment_id, external_session_id):
        origin = (
            conn.execute(select(enrollments).where(enrollments.c.enrollment_id == enrollment_id))
            .mappings()
            .first()
        )
        if origin is None:
            raise ValueError("unknown collection enrollment")
        source = self._source(conn, origin["source_key"])
        self._subject(conn, origin["subject_id"])
        enrollment = self._enrollment(conn, enrollment_id)
        session = self._session(conn, enrollment, external_session_id)
        revision = (
            conn.scalar(
                select(reviews.c.revision)
                .where(
                    reviews.c.enrollment_id == enrollment_id,
                    reviews.c.external_session_id == external_session_id,
                )
                .order_by(reviews.c.revision.desc())
                .limit(1)
            )
            or 0
        )
        return {
            "enrollment_id": enrollment_id,
            "source_key": enrollment["source_key"],
            "external_session_id": external_session_id,
            "session": _serialize_session(session),
            "digest": session_digest(session),
            "expected_revision": revision,
            "source": _source_provenance(source["snapshot"], session.id),
        }

    def inspect_session(self, *, enrollment_id, external_session_id) -> dict:
        """Return private current content for deliberate review; this supplies no truth label."""
        _uuid(enrollment_id)
        _database_text(external_session_id)
        with self._transaction() as conn:
            return self._inspect_session_connection(conn, enrollment_id, external_session_id)

    def review_session(
        self,
        *,
        enrollment_id,
        external_session_id,
        expected_revision,
        expected_session_digest,
        status,
        behavior,
        intent,
        mapping_ref,
        evidence_ref,
        reviewer_ref,
    ) -> dict:
        _uuid(enrollment_id)
        if (
            not isinstance(expected_session_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_session_digest) is None
        ):
            raise ValueError("invalid expected session digest")
        for value in (mapping_ref, evidence_ref, reviewer_ref):
            _ref(value)
        _database_text(external_session_id)
        if (
            type(expected_revision) is not int
            or expected_revision < 0
            or not all(isinstance(value, str) for value in (status, behavior, intent))
            or status not in {"pending", "approved", "rejected"}
            or behavior not in {"manual", "automated", "mixed", "unknown"}
            or intent not in {"benign", "abusive", "unknown"}
        ):
            raise ValueError("invalid session review")
        with self._transaction() as conn:
            packet = self._inspect_session_connection(conn, enrollment_id, external_session_id)
            if packet["digest"] != expected_session_digest:
                raise ValueError("session content changed; inspect again before reviewing")
            latest = packet["expected_revision"]
            if latest != expected_revision:
                raise ValueError("session review revision changed; reload before reviewing")
            result = dict(
                review_id=str(uuid4()),
                enrollment_id=enrollment_id,
                external_session_id=external_session_id,
                revision=latest + 1,
                status=status,
                digest=packet["digest"],
                behavior=behavior,
                intent=intent,
                created_at=datetime.now(UTC),
                payload=dict(
                    mapping_ref=mapping_ref, evidence_ref=evidence_ref, reviewer_ref=reviewer_ref
                ),
            )
            conn.execute(insert(reviews).values(**result))
        return result

    def load_approved(self, source_keys) -> list[ReviewedSession]:
        approved = []
        with self._transaction() as conn:
            keys = sorted({_database_text(key) for key in source_keys})
            # Acquire every selected source before study rows, matching multi-source withdrawal.
            source_rows = {
                row["source_key"]: row
                for row in conn.execute(
                    select(sources)
                    .where(sources.c.source_key.in_(keys))
                    .order_by(sources.c.source_key)
                    .with_for_update()
                ).mappings()
            }
            origins = {
                row["source_key"]: row
                for row in conn.execute(
                    select(enrollments).where(enrollments.c.source_key.in_(keys))
                ).mappings()
            }
            # Fresh stores may not have the budget singleton; subject order must stand alone.
            subject_ids = {row["subject_id"] for row in origins.values()}
            conn.execute(
                select(subjects).where(subjects.c.subject_id.in_(subject_ids))
                .order_by(subjects.c.subject_id).with_for_update()
            ).all()
            for key in keys:
                origin = origins.get(key)
                if origin is None or origin["status"] != "active":
                    continue
                try:
                    self._source(conn, key)
                    self._subject(conn, origin["subject_id"])
                    enrollment = self._enrollment(conn, origin["enrollment_id"])
                except ValueError:
                    continue
                session_map = {session.id: session for session in self.traffic._sessions(conn, key)}
                latest = {}
                for row in conn.execute(
                    select(reviews)
                    .where(reviews.c.enrollment_id == enrollment["enrollment_id"])
                    .order_by(reviews.c.revision)
                ).mappings():
                    latest[row["external_session_id"]] = row
                for sid, row in latest.items():
                    if row["status"] != "approved":
                        continue
                    try:
                        session = self._check_window(enrollment, session_map[sid])
                    except (ValueError, KeyError):
                        continue
                    if session_digest(session) != row["digest"]:
                        continue
                    source_provenance = _source_provenance(source_rows[key]["snapshot"], sid)
                    approved.append(
                        ReviewedSession(
                            session,
                            key,
                            enrollment["subject_id"],
                            enrollment["enrollment_id"],
                            row["review_id"],
                            row["revision"],
                            row["digest"],
                            row["behavior"],
                            row["intent"],
                            dict(
                                consent=enrollment["payload"],
                                review=row["payload"],
                                source=source_provenance,
                            ),
                        )
                    )
        return approved

    def withdraw(self, subject_id, *, confirm_subject, writer_stopped) -> dict:
        _uuid(subject_id)
        if confirm_subject != subject_id or writer_stopped is not True:
            raise ValueError(
                "confirm subject identity and stop collection writers before withdrawal"
            )
        with self._transaction() as conn:
            keys = sorted(
                conn.scalars(
                    select(enrollments.c.source_key).where(enrollments.c.subject_id == subject_id)
                )
            )
            current = {}
            for key in keys:
                current[key] = (
                    conn.execute(
                        select(sources).where(sources.c.source_key == key).with_for_update()
                    )
                    .mappings()
                    .one()
                )
            subject = (
                conn.execute(
                    select(subjects).where(subjects.c.subject_id == subject_id).with_for_update()
                )
                .mappings()
                .first()
            )
            if subject is None:
                raise ValueError("unknown study subject")
            if keys != sorted(
                conn.scalars(
                    select(enrollments.c.source_key).where(enrollments.c.subject_id == subject_id)
                )
            ):
                raise ValueError("subject collections changed; retry withdrawal")
            conn.execute(
                update(subjects)
                .where(subjects.c.subject_id == subject_id)
                .values(status="withdrawn", withdrawn_at=datetime.now(UTC))
            )
            for key in keys:
                self.traffic._delete_source_connection(conn, key, current=current[key])
        return {
            "subject_id": subject_id,
            "sources_purged": len(keys),
            "scope": "selected database only; original files, exports and backups are excluded",
        }
