"""Operator-approved, actor-scoped enforcement for the isolated demo route only."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from collections.abc import Callable

from sqlalchemy import JSON, Column, Float, Integer, MetaData, String, Table, insert, select, update

from bouncer.investigations import InvestigationStore

ACTORS = frozenset({"attack", "benign"})
SCOPE = "/enforcement-demo"
BURST = 3.0
REFILL_PER_SECOND = 10.0 / 60.0
metadata = MetaData()
policies = Table(
    "demo_enforcement_policies",
    metadata,
    Column("id", String, primary_key=True),
    Column("case_id", String, nullable=False),
    Column("evidence_hash", String, nullable=False),
    Column("evidence_version", Integer, nullable=False),
    Column("actor_id", String, nullable=False),
    Column("scope", String, nullable=False),
    Column("action", String, nullable=False),
    Column("ttl_seconds", Integer, nullable=False),
    Column("created_at", Float, nullable=False),
    Column("expires_at", Float, nullable=False),
    Column("revoked_at", Float),
    Column("expired_at", Float),
    Column("approver", String, nullable=False),
    Column("affected_requests", Integer, nullable=False),
    Column("allowed_requests", Integer, nullable=False),
    Column("tokens", Float, nullable=False),
    Column("token_updated_at", Float, nullable=False),
)
audit = Table(
    "demo_enforcement_audit",
    metadata,
    Column("id", String, primary_key=True),
    Column("policy_id", String, nullable=False),
    Column("event", String, nullable=False),
    Column("at", Float, nullable=False),
    Column("details", JSON, nullable=False),
)


def actor_secret(secret: str | None = None) -> str:
    value = os.getenv("BOUNCER_DEMO_ACTOR_SECRET", "") if secret is None else secret
    if len(value) < 32:
        raise ValueError("Demo actor secret is not configured securely")
    return value


def issue_token(actor_id: str, secret: str | None = None) -> str:
    """Private provisioning helper; never exposed through a public HTTP endpoint."""
    if actor_id not in ACTORS:
        raise ValueError("Unknown registered demo actor")
    key = actor_secret(secret)
    signature = hmac.new(
        key.encode(), ("bounceri-demo-v1:" + actor_id).encode(), hashlib.sha256
    ).hexdigest()
    return actor_id + "." + signature


def verify_token(actor_id: str, token: str, secret: str | None = None) -> bool:
    if actor_id not in ACTORS:
        return False
    expected = issue_token(actor_id, secret)
    return hmac.compare_digest(expected, token)


class EnforcementRuntime:
    def __init__(self, store: InvestigationStore, clock: Callable[[], float] = time.time):
        self.store = store
        self.clock = clock
        metadata.create_all(store.engine)

    def _event(self, conn, policy_id, event, at, details=None):
        conn.execute(
            insert(audit).values(
                id=str(uuid.uuid4()), policy_id=policy_id, event=event, at=at, details=details or {}
            )
        )

    def _expire(self, conn, current_time):
        expired = (
            conn.execute(
                select(policies).where(
                    policies.c.revoked_at.is_(None),
                    policies.c.expired_at.is_(None),
                    policies.c.expires_at <= current_time,
                )
            )
            .mappings()
            .all()
        )
        for policy in expired:
            conn.execute(
                update(policies)
                .where(policies.c.id == policy["id"])
                .values(expired_at=policy["expires_at"])
            )
            self._event(conn, policy["id"], "expired", current_time)

    def approve(
        self,
        case_id,
        evidence_hash,
        evidence_version,
        actor_id,
        action,
        ttl_seconds=60,
        approver="configured_administrator",
    ):
        if (
            actor_id not in ACTORS
            or action not in {"rate_limit", "temporary_block"}
            or type(ttl_seconds) is not int
            or not 1 <= ttl_seconds <= 300
            or type(evidence_version) is not int
            or evidence_version < 1
        ):
            raise ValueError("Unsupported actor, action, evidence version or duration")
        with self.store.transaction() as conn:
            current_time = self.clock()
            self._expire(conn, current_time)
            active = (
                conn.execute(
                    select(policies)
                    .where(
                        policies.c.actor_id == actor_id,
                        policies.c.scope == SCOPE,
                        policies.c.revoked_at.is_(None),
                        policies.c.expired_at.is_(None),
                        policies.c.expires_at > current_time,
                    )
                    .order_by(policies.c.created_at.desc())
                )
                .mappings()
                .first()
            )
            if active:
                if all(
                    active[key] == value
                    for key, value in (
                        ("case_id", case_id),
                        ("evidence_hash", evidence_hash),
                        ("evidence_version", evidence_version),
                        ("action", action),
                        ("ttl_seconds", ttl_seconds),
                    )
                ):
                    return self._public(dict(active), current_time)
                conn.execute(
                    update(policies)
                    .where(policies.c.id == active["id"])
                    .values(revoked_at=current_time)
                )
                self._event(conn, active["id"], "replaced", current_time)
            policy = dict(
                id=str(uuid.uuid4()),
                case_id=case_id,
                evidence_hash=evidence_hash,
                evidence_version=evidence_version,
                actor_id=actor_id,
                scope=SCOPE,
                action=action,
                ttl_seconds=ttl_seconds,
                created_at=current_time,
                expires_at=current_time + ttl_seconds,
                revoked_at=None,
                expired_at=None,
                approver=approver,
                affected_requests=0,
                allowed_requests=0,
                tokens=BURST,
                token_updated_at=current_time,
            )
            conn.execute(insert(policies).values(**policy))
            self._event(
                conn,
                policy["id"],
                "approved",
                current_time,
                {
                    "action": action,
                    "actor_id": actor_id,
                    "ttl_seconds": ttl_seconds,
                    "approval_basis": "manual_demo_override",
                },
            )
            return self._public(policy, current_time)

    def _public(self, policy, current_time, admin=False):
        status = (
            "revoked"
            if policy["revoked_at"] is not None
            else "expired"
            if policy["expired_at"] is not None or policy["expires_at"] <= current_time
            else "active"
        )
        keys = (
            "id",
            "case_id",
            "evidence_hash",
            "evidence_version",
            "actor_id",
            "scope",
            "action",
            "ttl_seconds",
            "created_at",
            "expires_at",
            "revoked_at",
            "expired_at",
            "affected_requests",
            "allowed_requests",
        )
        result = {key: policy[key] for key in keys}
        result["status"] = status
        # The operator enrolls this test actor. Aggregate traffic evidence does not
        # establish its identity, so never present this as automatic model enforcement.
        result["approval_basis"] = "manual_demo_override"
        if admin:
            result["approver"] = policy["approver"]
        return result

    def list_policies(self, case_id, admin=False):
        with self.store.transaction() as conn:
            current_time = self.clock()
            self._expire(conn, current_time)
            rows = conn.execute(
                select(policies)
                .where(policies.c.case_id == case_id)
                .order_by(policies.c.created_at.desc())
            ).mappings()
            result = []
            for row in rows:
                record = self._public(dict(row), current_time, admin)
                record["audit"] = [
                    dict(event)
                    for event in conn.execute(
                        select(audit.c.event, audit.c.at, audit.c.details)
                        .where(audit.c.policy_id == row["id"])
                        .order_by(audit.c.at)
                    ).mappings()
                ]
                result.append(record)
            return result

    def revoke(self, policy_id):
        with self.store.transaction() as conn:
            policy = (
                conn.execute(select(policies).where(policies.c.id == policy_id)).mappings().first()
            )
            if policy is None:
                raise ValueError("Policy not found")
            current_time = self.clock()
            if policy["revoked_at"] is None:
                conn.execute(
                    update(policies)
                    .where(policies.c.id == policy_id)
                    .values(revoked_at=current_time)
                )
                self._event(conn, policy_id, "revoked", current_time)
                policy = {**dict(policy), "revoked_at": current_time}
            return self._public(dict(policy), current_time)

    def probe(self, actor_id):
        if actor_id not in ACTORS:
            raise ValueError("Unknown registered demo actor")
        with self.store.transaction() as conn:
            current_time = self.clock()
            self._expire(conn, current_time)
            policy = (
                conn.execute(
                    select(policies)
                    .where(
                        policies.c.actor_id == actor_id,
                        policies.c.scope == SCOPE,
                        policies.c.revoked_at.is_(None),
                        policies.c.expired_at.is_(None),
                        policies.c.expires_at > current_time,
                    )
                    .order_by(policies.c.created_at.desc())
                )
                .mappings()
                .first()
            )
            if policy is None:
                return {
                    "status_code": 200,
                    "policy_id": None,
                    "actor_id": actor_id,
                    "scope": SCOPE,
                    "status": "allowed",
                }
            policy = dict(policy)
            status_code, event, retry_after = 200, "allowed", None
            values = {}
            if policy["action"] == "temporary_block":
                status_code, event = 403, "blocked"
            else:
                elapsed = max(0, current_time - policy["token_updated_at"])
                tokens = min(BURST, policy["tokens"] + elapsed * REFILL_PER_SECOND)
                if tokens + 1e-9 >= 1.0:
                    tokens = max(0.0, tokens - 1.0)
                else:
                    status_code, event = 429, "rate_limited"
                    retry_after = max(1, int((1.0 - tokens) / REFILL_PER_SECOND + 0.999))
                values.update(
                    tokens=tokens, token_updated_at=max(current_time, policy["token_updated_at"])
                )
            if status_code == 200:
                values["allowed_requests"] = policy["allowed_requests"] + 1
            else:
                values["affected_requests"] = policy["affected_requests"] + 1
            conn.execute(update(policies).where(policies.c.id == policy["id"]).values(**values))
            self._event(conn, policy["id"], event, current_time)
            return {
                "status_code": status_code,
                "policy_id": policy["id"],
                "actor_id": actor_id,
                "scope": SCOPE,
                "status": event,
                "retry_after": retry_after,
            }


class EnforcementStore(EnforcementRuntime):
    """Convenience schema/runtime initialization from the shared database URL."""

    def __init__(self, database_url: str, clock: Callable[[], float] = time.time):
        super().__init__(InvestigationStore(database_url), clock=clock)
