"""Transactional case snapshots and conservative shared application budget."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.pool import StaticPool

from .evidence import now, traffic_packet

metadata = MetaData()
cases = Table(
    "investigation_cases",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_key", String, nullable=False),
    Column("evidence_hash", String, nullable=False),
    Column("public", Boolean, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", String, nullable=False),
    UniqueConstraint("source_key", "evidence_hash"),
)
assessments = Table(
    "investigation_assessments",
    metadata,
    Column("id", String, primary_key=True),
    Column("case_id", String, nullable=False),
    Column("job_id", String),
    Column("stage", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("metadata", JSON, nullable=False),
    Column("created_at", String, nullable=False),
)
jobs = Table(
    "investigation_jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("case_id", String, nullable=False),
    Column("evidence_hash", String, nullable=False),
    Column("config_key", String, nullable=False),
    Column("status", String, nullable=False),
    Column("remaining", Integer, nullable=False),
    Column("max_requests", Integer, nullable=False),
    Column("request_count", Integer, nullable=False),
    Column("worker_id", String),
    Column("reason", String, nullable=False),
    Column("created_at", String, nullable=False),
    UniqueConstraint("evidence_hash", "config_key"),
)
budget = Table(
    "investigation_budget",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("spent", Integer, nullable=False),
    Column("reserved", Integer, nullable=False),
    Column("executions", Integer, nullable=False),
    Column("requests", Integer, nullable=False),
)
reservations = Table(
    "investigation_reservations",
    metadata,
    Column("id", String, primary_key=True),
    Column("job_id", String, nullable=False),
    Column("stage", String, nullable=False),
    Column("provider", String, nullable=False),
    Column("model", String, nullable=False),
    Column("maximum", Integer, nullable=False),
    Column("actual", Integer),
    Column("state", String, nullable=False),
    Column("usage", JSON, nullable=False),
    Column("provider_request_id", String),
    Column("pricing_version", String, nullable=False),
)


def identifier() -> str:
    return str(uuid.uuid4())


def row(conn, table, record_id):
    result = conn.execute(select(table).where(table.c.id == record_id)).mappings().first()
    if result is None:
        raise ValueError("record not found")
    return dict(result)


class ReviewIneligible(ValueError):
    """The immutable source snapshot cannot form an accepted bounded model packet."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__("review_ineligible: " + reason)


def model_packet(payload: dict) -> dict:
    return {
        key: payload[key]
        for key in (
            "evidence_hash",
            "evidence_version",
            "synthetic",
            "complete",
            "evidence",
            "local_assessment",
            "missing_information",
            "distinct_client_count",
        )
    } | {"case_id": payload["id"]}


def review_eligibility(payload: dict) -> dict:
    # Source completeness and model eligibility are separate. Preserve the source and
    # validate the exact model view, rather than truncating evidence to buy a review.
    if payload.get("complete") is not True:
        return {"eligible": False, "reason": "Evidence snapshot is incomplete."}
    try:
        from bouncer.review.validation import validate_packet
    except ModuleNotFoundError as exc:
        if exc.name not in {"bouncer.review", "bouncer.review.validation"}:
            raise
        return {"eligible": False, "reason": "The bounded review validator is unavailable."}
    try:
        validate_packet(model_packet(payload))
    except (ValueError, TypeError, KeyError, OverflowError):
        return {
            "eligible": False,
            "reason": (
                "Model packet exceeds size/item limits or fails evidence validation. "
                "Create a smaller scoped case; the source snapshot has been preserved."
            ),
        }
    return {"eligible": True, "reason": None}


class InvestigationStore:
    LIMIT = 5_000_000

    def __init__(self, database_url: str):
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        options: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in database_url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(database_url, **options)
        if self.engine.dialect.name == "sqlite":
            metadata.create_all(self.engine)
        else:
            from bouncer.db.migrate import run_migrations

            run_migrations(self.engine)
        # PostgreSQL/SQLite conflict-safe singleton initialization across processes.
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        statement = sqlite_insert if self.engine.dialect.name == "sqlite" else pg_insert
        with self.engine.begin() as conn:
            conn.execute(
                statement(budget)
                .values(id=1, spent=0, reserved=0, executions=0, requests=0)
                .on_conflict_do_nothing()
            )

    @contextmanager
    def transaction(self):
        with self.engine.connect() as conn:
            if self.engine.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                conn.begin()
                conn.execute(select(budget).where(budget.c.id == 1).with_for_update())
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def create_from_legacy(
        self, snapshot: dict, source_key: str = "overview", public_demo: bool = False
    ) -> dict:
        packet = traffic_packet(snapshot)
        if public_demo and not packet["synthetic"]:
            raise ValueError("only synthetic snapshots can be public demos")
        with self.transaction() as conn:
            case_id = self._create_case(conn, packet, source_key, public_demo)
        return self.get_case(case_id, False)

    def create_traffic_import(
        self, snapshot: dict, *, source_key: str, report: dict, provenance: dict,
        public_demo: bool = False,
    ) -> dict:
        """Atomically retain a private uploaded source and its redacted local case."""
        from bouncer.db.traffic import TrafficRepository

        if snapshot.get("labels"):
            raise ValueError("uploaded traffic cannot supply trusted labels")
        if type(snapshot.get("synthetic")) is not bool:
            raise ValueError("traffic source synthetic provenance must be a boolean")
        private_snapshot = snapshot | {
            "import_report": report, "source_provenance": provenance,
            "trap_policy": "unavailable_for_import",
        }
        packet = traffic_packet(private_snapshot)
        if public_demo and not packet["synthetic"]:
            raise ValueError("only synthetic snapshots can be public demos")
        # Schema initialization/migrations must finish before acquiring the shared budget lock.
        repository = TrafficRepository(self.engine)
        with self.transaction() as conn:
            repository._freeze_snapshot(conn, private_snapshot, source_key=source_key)
            case_id = self._create_case(conn, packet, source_key, public_demo, "uploaded_log")
        return self.get_case(case_id, False)

    def _create_case(self, conn, packet, source_key, public_demo, source_kind=None):
        digest = hashlib.sha256(
            json.dumps(
                {"source_scope": source_key, "packet": packet},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        existing = conn.execute(
            select(cases.c.id).where(
                cases.c.source_key == source_key, cases.c.evidence_hash == digest
            )
        ).scalar()
        if existing:
            return existing
        case_id = identifier()
        payload = {
            "id": case_id,
            "module": "clean_the_traffic",
            "source": {
                "kind": source_kind or (
                    "fixture" if source_key == "fixture" else "monitored_traffic"
                ),
                "synthetic": packet["synthetic"],
            },
            "created_at": now(),
            "evidence_version": 1,
            "evidence_hash": digest,
            **packet,
        }
        conn.execute(
            insert(cases).values(
                id=case_id,
                source_key=source_key,
                evidence_hash=digest,
                public=public_demo,
                payload=payload,
                created_at=payload["created_at"],
            )
        )
        self._append(conn, case_id, None, "local", packet["local_assessment"], {})
        return case_id

    def list_cases(
        self, public_only: bool = True, *, limit=100, offset=0, origin="all"
    ) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError("invalid pagination")
        if origin not in {"all", "real", "synthetic"}:
            raise ValueError("invalid origin")
        with self.engine.connect() as conn:
            statement = select(cases).order_by(cases.c.created_at.desc(), cases.c.id.desc())
            if public_only:
                statement = statement.where(cases.c.public.is_(True))
            if origin != "all":
                statement = statement.where(
                    cases.c.payload["synthetic"].as_boolean() == (origin == "synthetic")
                )
            if origin == "real":
                statement = statement.where(
                    cases.c.payload["source"]["kind"].as_string().in_(
                        ("monitored_traffic", "uploaded_log")
                    )
                )
            page = list(conn.execute(statement.limit(limit).offset(offset)).mappings())
            if not page:
                return []
            latest_jobs = {}
            for job in conn.execute(
                select(jobs).where(jobs.c.evidence_hash.in_([c["evidence_hash"] for c in page]))
                .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
            ).mappings():
                latest_jobs.setdefault(job["evidence_hash"], job)
            results = {
                (a["case_id"], a["job_id"]): a["payload"]
                for a in conn.execute(
                    select(assessments).where(
                        assessments.c.case_id.in_([c["id"] for c in page]),
                        assessments.c.stage == "reviewer",
                    ).order_by(assessments.c.created_at, assessments.c.id)
                ).mappings()
            }
            return [self._case_view(c["payload"], latest_jobs.get(c["evidence_hash"]), results)
                    for c in page]

    @staticmethod
    def _case_view(source, job, results):
        payload = dict(source)
        payload["review_eligibility"] = review_eligibility(payload)
        payload["review"] = {
            "status": job["status"] if job else "not_requested",
            "job_id": job["id"] if job else None,
            "result": results.get((payload["id"], job["id"] if job else None)),
            "reason": job["reason"] if job else "",
        }
        return payload

    def get_case(self, case_id, public_only=True):
        with self.engine.connect() as conn:
            statement = select(cases).where(cases.c.id == case_id)
            if public_only:
                statement = statement.where(cases.c.public.is_(True))
            case = conn.execute(statement).mappings().first()
            if case is None:
                return None
            payload = dict(case["payload"])
            job = (
                conn.execute(
                    select(jobs)
                    .where(jobs.c.evidence_hash == case["evidence_hash"])
                    .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
                )
                .mappings()
                .first()
            )
            result = conn.execute(
                select(assessments.c.payload)
                .where(
                    assessments.c.case_id == case_id,
                    assessments.c.stage == "reviewer",
                    assessments.c.job_id == (job["id"] if job else None),
                )
                .order_by(assessments.c.created_at.desc(), assessments.c.id.desc())
            ).scalar()
            return self._case_view(
                payload, job, {(case_id, job["id"] if job else None): result}
            )

    def list_assessments(self, case_id):
        with self.engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(assessments)
                    .where(assessments.c.case_id == case_id)
                    .order_by(assessments.c.created_at)
                ).mappings()
            ]

    def _halt_reason(self, conn, ledger):
        # An observed pricing-ceiling breach invalidates the verified billing contract.
        # Derive this durable circuit breaker from retained settlement rows; reopening
        # the store or releasing other jobs cannot silently authorize more calls.
        overcharged = conn.execute(
            select(reservations.c.id).where(reservations.c.actual > reservations.c.maximum).limit(1)
        ).first()
        if overcharged:
            return "provider_charge_exceeded_reservation"
        if ledger["spent"] + ledger["reserved"] > self.LIMIT:
            return "project_budget_exceeded"
        return None

    def enqueue_review(self, case_id, config_key, maximum_cost_microusd, max_requests=2):
        if (
            type(maximum_cost_microusd) is not int
            or maximum_cost_microusd <= 0
            or type(max_requests) is not int
            or not 1 <= max_requests <= 200
            or not isinstance(config_key, str)
            or not config_key
        ):
            raise ValueError("invalid review limits or configuration")
        with self.transaction() as conn:
            case = row(conn, cases, case_id)
            eligibility = review_eligibility(case["payload"])
            if not eligibility["eligible"]:
                raise ReviewIneligible(eligibility["reason"])
            existing = (
                conn.execute(
                    select(jobs).where(
                        jobs.c.evidence_hash == case["evidence_hash"],
                        jobs.c.config_key == config_key,
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                return dict(existing)
            b = row(conn, budget, 1)
            if (
                self._halt_reason(conn, b) is not None
                or b["spent"] + b["reserved"] + maximum_cost_microusd > self.LIMIT
                or b["executions"] >= 100
                or b["requests"] + max_requests > 200
            ):
                raise ValueError("deferred_budget")
            job = dict(
                id=identifier(),
                case_id=case_id,
                evidence_hash=case["evidence_hash"],
                config_key=config_key,
                status="queued",
                remaining=maximum_cost_microusd,
                max_requests=max_requests,
                request_count=0,
                worker_id=None,
                reason="",
                created_at=now(),
            )
            conn.execute(insert(jobs).values(**job))
            conn.execute(
                update(budget)
                .where(budget.c.id == 1)
                .values(
                    reserved=b["reserved"] + maximum_cost_microusd, executions=b["executions"] + 1
                )
            )
            return job

    def claim_job(self, worker_id):
        with self.transaction() as conn:
            job = (
                conn.execute(
                    select(jobs)
                    .where(jobs.c.status == "queued")
                    .order_by(jobs.c.created_at)
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if job is None:
                return None
            conn.execute(
                update(jobs)
                .where(jobs.c.id == job["id"])
                .values(status="running", worker_id=worker_id)
            )
            return {**dict(job), "status": "running", "worker_id": worker_id}

    def review_packet(self, job_id):
        with self.engine.connect() as conn:
            job = row(conn, jobs, job_id)
            payload = row(conn, cases, job["case_id"])["payload"]
            return model_packet(payload)

    def start_request(self, job_id, stage, provider, model, maximum_cost_microusd, pricing_version):
        if (
            type(maximum_cost_microusd) is not int
            or maximum_cost_microusd < 0
            or not provider
            or not model
            or not pricing_version
            or stage not in {"decision_model", "reviewer"}
        ):
            raise ValueError("unverified request cost, stage or identity")
        with self.transaction() as conn:
            job, b = row(conn, jobs, job_id), row(conn, budget, 1)
            halt_reason = self._halt_reason(conn, b)
            if halt_reason is not None:
                raise ValueError("paid execution halted: " + halt_reason)
            if (
                job["status"] != "running"
                or job["remaining"] < maximum_cost_microusd
                or job["request_count"] >= job["max_requests"]
                or b["requests"] >= 200
            ):
                raise ValueError("request is not permitted by reserved job limits")
            already_sent = conn.execute(
                select(reservations.c.id).where(
                    reservations.c.job_id == job_id, reservations.c.stage == stage
                )
            ).first()
            if already_sent:
                raise ValueError("automatic retries are disabled for this job stage")
            reservation = dict(
                id=identifier(),
                job_id=job_id,
                stage=stage,
                provider=provider,
                model=model,
                maximum=maximum_cost_microusd,
                actual=None,
                state="pending",
                usage={},
                provider_request_id=None,
                pricing_version=pricing_version,
            )
            conn.execute(insert(reservations).values(**reservation))
            conn.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(
                    remaining=job["remaining"] - maximum_cost_microusd,
                    request_count=job["request_count"] + 1,
                )
            )
            conn.execute(update(budget).where(budget.c.id == 1).values(requests=b["requests"] + 1))
            return reservation

    def settle_request(self, reservation_id, actual_cost_microusd, usage, provider_request_id):
        if actual_cost_microusd is not None and (
            type(actual_cost_microusd) is not int or actual_cost_microusd < 0
        ):
            raise ValueError("invalid actual cost")
        with self.transaction() as conn:
            r, b = row(conn, reservations, reservation_id), row(conn, budget, 1)
            if r["state"] == "settled":
                if r["actual"] == actual_cost_microusd:
                    return
                raise ValueError("reservation already settled")
            if actual_cost_microusd is not None:
                # Record actual over-ceiling charges; the cap prevents further spending.
                conn.execute(
                    update(budget)
                    .where(budget.c.id == 1)
                    .values(
                        spent=b["spent"] + actual_cost_microusd,
                        reserved=b["reserved"] - r["maximum"],
                    )
                )
            conn.execute(
                update(reservations)
                .where(reservations.c.id == reservation_id)
                .values(
                    actual=actual_cost_microusd,
                    state="unknown" if actual_cost_microusd is None else "settled",
                    usage=usage,
                    provider_request_id=provider_request_id,
                )
            )

    def _append(self, conn, case_id, job_id, stage, payload, meta):
        conn.execute(
            insert(assessments).values(
                id=identifier(),
                case_id=case_id,
                job_id=job_id,
                stage=stage,
                payload=payload,
                metadata=meta,
                created_at=now(),
            )
        )

    def append_assessment(self, job_id, stage, payload: dict, metadata: dict):
        if stage not in {"decision_model", "reviewer"}:
            raise ValueError("unsupported assessment stage")
        with self.transaction() as conn:
            job = row(conn, jobs, job_id)
            if job["status"] != "running":
                raise ValueError("job is not running")
            self._append(conn, job["case_id"], job_id, stage, payload, metadata)

    def finish_job(self, job_id, status, reason=""):
        status = "completed" if status == "complete" else status
        if status not in {"completed", "failed", "unavailable", "deferred_budget"}:
            raise ValueError("unsupported terminal status")
        with self.transaction() as conn:
            job, b = row(conn, jobs, job_id), row(conn, budget, 1)
            if job["status"] not in {"queued", "running"}:
                return
            conn.execute(
                update(budget)
                .where(budget.c.id == 1)
                .values(reserved=b["reserved"] - job["remaining"])
            )
            conn.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(status=status, reason=reason, remaining=0)
            )

    def close_interrupted_job(self, job_id, worker_id):
        """Close one job after its operator has confirmed the owning worker stopped."""
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("expected worker owner is required")
        with self.transaction() as conn:
            job, b = row(conn, jobs, job_id), row(conn, budget, 1)
            if job["status"] != "running":
                raise ValueError("job is not running")
            if job["worker_id"] != worker_id:
                raise ValueError("job worker owner does not match")
            # Dispatched pending/unknown charges have already left job.remaining.
            conn.execute(
                update(budget)
                .where(budget.c.id == 1)
                .values(reserved=b["reserved"] - job["remaining"])
            )
            conn.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(status="unavailable", reason="interrupted", remaining=0)
            )

    def usage(self):
        with self.engine.connect() as conn:
            b = row(conn, budget, 1)
            halt_reason = self._halt_reason(conn, b)
            return {
                "execution_halted": halt_reason is not None,
                "halt_reason": halt_reason,
                "limit_usd": 5,
                "spent_usd": b["spent"] / 1_000_000,
                "reserved_usd": b["reserved"] / 1_000_000,
                "available_usd": max(0, self.LIMIT - b["spent"] - b["reserved"]) / 1_000_000,
                "executions": b["executions"],
                "requests": b["requests"],
                "max_executions": 100,
                "max_requests": 200,
            }
