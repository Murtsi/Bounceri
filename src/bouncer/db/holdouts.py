"""Private commitments: owner-declared independence is not verified independence."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    LargeBinary,
    MetaData,
    Table,
    Text,
    Uuid,
    select,
    update,
)

from bouncer.db.evaluations import EvaluationLedger, _canonical, _hash, preparations
from bouncer.db.store import _dt

metadata = MetaData()
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
holdouts = Table(
    "independent_holdouts",
    metadata,
    Column("holdout_id", Uuid(as_uuid=False), primary_key=True),
    Column("bundle_digest", Text, nullable=False, unique=True),
    Column("author_ref", Text),
    Column("permission_ref", Text),
    Column("independence_ref", Text),
    Column("declared_independent", Boolean, nullable=False),
    Column("sealed_at", DateTime(timezone=True), nullable=False),
    Column("state", Text, nullable=False),
    Column("preparation_id", Text, ForeignKey(preparations.c.preparation_id)),
    Column("artifact_digest", Text),
    Column("revealed_at", DateTime(timezone=True)),
    Column("bundle", LargeBinary),
    CheckConstraint("state IN ('sealed','revealed','revoked')"),
    CheckConstraint("declared_independent = true"),
    CheckConstraint("bundle IS NULL OR length(bundle) BETWEEN 1 AND 16777216"),
    CheckConstraint(
        "(state = 'revoked' AND author_ref IS NULL AND permission_ref IS NULL "
        "AND independence_ref IS NULL AND bundle IS NULL) OR "
        "(state <> 'revoked' AND author_ref IS NOT NULL AND permission_ref IS NOT NULL "
        "AND independence_ref IS NOT NULL)"
    ),
    CheckConstraint(
        "(state = 'sealed' AND preparation_id IS NULL AND artifact_digest IS NULL "
        "AND revealed_at IS NULL AND bundle IS NULL) OR "
        "(state = 'revealed' AND preparation_id IS NOT NULL AND artifact_digest IS NOT NULL "
        "AND revealed_at IS NOT NULL AND bundle IS NOT NULL) OR state = 'revoked'"
    ),
)


def _identifier(value):
    try:
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid holdout identifier") from None
    return value


def _reference(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is None
    ):
        raise ValueError("invalid holdout opaque reference")
    return value


def _digest(value):
    try:
        return _hash(value)
    except ValueError:
        raise ValueError("invalid holdout digest") from None


def _bundle(value):
    if type(value) is not bytes or not 0 < len(value) <= MAX_BUNDLE_BYTES:
        raise ValueError("invalid holdout bundle")
    return hashlib.sha256(value).hexdigest()


def _validate(row):
    try:
        _identifier(row["holdout_id"])
        _digest(row["bundle_digest"])
        if row["declared_independent"] is not True:
            raise ValueError
        sealed = _dt(row["sealed_at"])
        if row["state"] == "revoked":
            if any(row[field] is not None for field in (
                "author_ref", "permission_ref", "independence_ref", "bundle"
            )):
                raise ValueError
            return
        for field in ("author_ref", "permission_ref", "independence_ref"):
            _reference(row[field])
        if row["state"] == "sealed":
            if any(row[field] is not None for field in (
                "preparation_id", "artifact_digest", "revealed_at", "bundle"
            )):
                raise ValueError
        elif row["state"] == "revealed":
            _digest(row["preparation_id"])
            _digest(row["artifact_digest"])
            if _bundle(row["bundle"]) != row["bundle_digest"] or _dt(row["revealed_at"]) <= sealed:
                raise ValueError
        else:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid holdout stored state") from None


def _record(row):
    result = dict(row)
    result.pop("bundle")
    result.pop("declared_independent")
    for field in ("sealed_at", "revealed_at"):
        if result[field] is not None:
            result[field] = _dt(result[field]).isoformat()
    result["independence_status"] = "owner_declared_not_independently_verified"
    return result


class IndependentHoldouts:
    def __init__(self, engine):
        self.engine = engine
        self._ledger = EvaluationLedger(engine)
        if engine.dialect.name == "sqlite":
            metadata.create_all(engine)

    def _get(self, conn, holdout_id, *, lock=False):
        query = select(holdouts).where(holdouts.c.holdout_id == _identifier(holdout_id))
        row = conn.execute(query.with_for_update() if lock else query).mappings().first()
        if row is None:
            raise ValueError("unknown holdout")
        _validate(row)
        return row

    def get(self, holdout_id, *, connection=None):
        with self._ledger._transaction(connection, write=False) as conn:
            return _record(self._get(conn, holdout_id))

    def seal(
        self, *, bundle_digest, author_ref, permission_ref, independence_ref,
        declared_independent, connection=None,
    ):
        digest = _digest(bundle_digest)
        declaration = {
            "author_ref": _reference(author_ref),
            "permission_ref": _reference(permission_ref),
            "independence_ref": _reference(independence_ref),
        }
        if declared_independent is not True:
            raise ValueError("invalid holdout independence declaration")
        with self._ledger._transaction(connection) as conn:
            self._ledger._insert(conn, holdouts, dict(
                holdout_id=str(uuid4()), bundle_digest=digest, **declaration,
                declared_independent=True, sealed_at=datetime.now(UTC), state="sealed",
            ))
            row = conn.execute(
                select(holdouts).where(holdouts.c.bundle_digest == digest).with_for_update()
            ).mappings().one()
            _validate(row)
            if row["state"] == "revoked":
                raise ValueError("holdout revoked")
            if any(row[field] != value for field, value in declaration.items()):
                raise ValueError("holdout declaration differs from original")
            return _record(row)

    def _parent(self, conn, preparation_id, artifact_digest):
        parent = self._ledger._get(conn, preparation_id, lock=True)
        if parent["state"] not in {"frozen", "complete"}:
            raise ValueError("holdout requires frozen evaluation artifacts")
        try:
            _, actual = _canonical(parent["artifacts"])
        except ValueError:
            raise ValueError("holdout evaluation artifact mismatch") from None
        if (
            not parent["artifacts"] or actual != artifact_digest
            or parent["artifact_digest"] != actual
        ):
            raise ValueError("holdout evaluation artifact mismatch")
        return parent

    def _timeline(self, row, parent, now):
        if _dt(row["sealed_at"]) >= _dt(parent["created_at"]):
            raise ValueError("holdout seal must precede evaluation preparation")
        if now <= _dt(parent["created_at"]):
            raise ValueError("invalid holdout reveal timeline")
        if row["revealed_at"] is not None and _dt(row["revealed_at"]) <= _dt(parent["created_at"]):
            raise ValueError("invalid holdout reveal timeline")

    def reveal(self, holdout_id, *, preparation_id, artifact_digest, bundle, connection=None):
        _identifier(holdout_id)
        _digest(preparation_id)
        _digest(artifact_digest)
        digest = _bundle(bundle)
        with self._ledger._transaction(connection) as conn:
            # Parent first everywhere: source withdrawal also locks the parent preparation.
            parent = self._parent(conn, preparation_id, artifact_digest)
            row = self._get(conn, holdout_id, lock=True)
            if row["state"] == "revoked":
                raise ValueError("holdout revoked")
            if digest != row["bundle_digest"]:
                raise ValueError("holdout bundle digest mismatch")
            if row["state"] == "revealed" and (
                row["preparation_id"] != preparation_id or row["artifact_digest"] != artifact_digest
            ):
                raise ValueError("holdout already bound to another candidate")
            now = datetime.now(UTC)
            self._timeline(row, parent, now)
            if row["state"] == "revealed":
                return _record(row) | {"cached": True}
            conn.execute(update(holdouts).where(holdouts.c.holdout_id == holdout_id).values(
                state="revealed", preparation_id=preparation_id, artifact_digest=artifact_digest,
                revealed_at=now, bundle=bundle,
            ))
            return _record(self._get(conn, holdout_id)) | {"cached": False}

    def read_revealed(self, holdout_id, *, connection=None):
        with self._ledger._transaction(connection) as conn:
            initial = self._get(conn, holdout_id)
            if initial["state"] != "revealed":
                raise ValueError("holdout is not revealed")
            parent = self._parent(conn, initial["preparation_id"], initial["artifact_digest"])
            row = self._get(conn, holdout_id, lock=True)
            if row["state"] != "revealed":
                raise ValueError("holdout is not revealed")
            if any(row[field] != initial[field] for field in ("preparation_id", "artifact_digest")):
                raise ValueError("holdout candidate binding changed")
            self._timeline(row, parent, datetime.now(UTC))
            return row["bundle"]

    def revoke(self, holdout_id, *, confirm_holdout, connection=None):
        _identifier(holdout_id)
        if confirm_holdout != holdout_id:
            raise ValueError("holdout revocation requires exact confirmation")
        with self._ledger._transaction(connection) as conn:
            row = self._get(conn, holdout_id, lock=True)
            if row["state"] != "revoked":
                conn.execute(update(holdouts).where(holdouts.c.holdout_id == holdout_id).values(
                    state="revoked", author_ref=None, permission_ref=None, independence_ref=None,
                    bundle=None,
                ))
            return _record(self._get(conn, holdout_id))
