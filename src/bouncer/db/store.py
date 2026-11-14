"""Traffic readers with explicit SQL selection and a private JSON compatibility adapter."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from bouncer.contracts import Request, Session, SessionLabel
from bouncer.ingest.sample import SAMPLE_PATH, canonical_ip, load_sample_data

DEFAULT_STORE = Path(__file__).resolve().parents[3] / ".bouncer_store.json"


def store_path() -> Path:
    raw = os.getenv("BOUNCER_STORE_PATH")
    return Path(raw) if raw else DEFAULT_STORE



def traffic_source() -> str:
    return os.getenv("BOUNCER_TRAFFIC_SOURCE", "monitored")


def traffic_retention() -> float:
    seconds = float(os.getenv("BOUNCER_TRAFFIC_RETENTION_SECONDS", "86400"))
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("traffic retention must be a finite positive number of seconds")
    return seconds


@lru_cache(maxsize=8)
def _traffic_database(url: str):
    from bouncer.db.traffic import TrafficRepository
    return TrafficRepository(url)


def traffic_repository():
    url = os.getenv("BOUNCER_TRAFFIC_DATABASE_URL", "").strip()
    return _traffic_database(url) if url else None


def read_snapshot(*, path: Path | None = None) -> dict[str, Any]:
    repository = traffic_repository() if path is None else None
    return repository.load_snapshot(traffic_source()) if repository else _read_raw(path)


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    text = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _request_from_dict(row: dict[str, Any]) -> Request:
    return Request(
        ts=_dt(row["ts"]),
        ip=canonical_ip(row["ip"]),
        method=str(row["method"]),
        path=str(row["path"]),
        status=int(row["status"]),
        user_agent=str(row.get("user_agent") or ""),
        query=str(row.get("query") or ""),
        bytes=int(row.get("bytes") or 0),
        headers=dict(row.get("headers") or {}),
        content_type=row.get("content_type"),
        username=row.get("username"),
    )


def _session_from_dict(row: dict[str, Any]) -> Session:
    return Session(
        id=str(row["id"]),
        ip=canonical_ip(row["ip"]),
        user_agent=str(row["user_agent"]),
        started_at=_dt(row["started_at"]),
        ended_at=_dt(row["ended_at"]),
        requests=tuple(_request_from_dict(r) for r in row.get("requests") or ()),
    )


def _label_from_dict(row: dict[str, Any]) -> SessionLabel:
    return SessionLabel(
        session_id=str(row["session_id"]),
        run_id=str(row["run_id"]),
        sim_class=str(row["sim_class"]),
        campaign_id=row.get("campaign_id"),
    )


def _serialize_session(session: Session) -> dict[str, Any]:
    data = asdict(session)
    data["id"] = str(session.id)
    data["started_at"] = session.started_at.isoformat()
    data["ended_at"] = session.ended_at.isoformat()
    data["requests"] = list(data["requests"])
    for req in data["requests"]:
        req["ts"] = _dt(req["ts"]).isoformat()
    return data


def _serialize_label(label: SessionLabel) -> dict[str, Any]:
    return {
        "session_id": str(label.session_id),
        "run_id": label.run_id,
        "sim_class": label.sim_class,
        "campaign_id": label.campaign_id,
    }


def _read_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or store_path()
    if not target.exists():
        return {"sessions": [], "labels": [], "synthetic": False}
    return json.loads(target.read_text(encoding="utf-8"))


def _write_raw(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = path or store_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atominen: worker kirjoittaa samalla kun API lukee → ei koskaan puolikasta JSONia.
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def clear_store(path: Path | None = None) -> None:
    target = path or store_path()
    if target.exists():
        target.unlink()


def seed_from_sample(
    sample: Path = SAMPLE_PATH,
    *,
    path: Path | None = None,
) -> tuple[int, int]:
    """Lataa synteettinen fixture storeen (idempotentti: korvaa sisällön)."""
    sessions, labels = load_sample_data(sample)
    payload = {
        "sessions": [_serialize_session(s) for s in sessions],
        "labels": [_serialize_label(lab) for lab in labels],
        "synthetic": True,
        "source": str(sample.as_posix()),
    }
    _write_raw(payload, path)
    return len(sessions), len(labels)


def load_sessions(
    since: datetime | None = None,
    *,
    path: Path | None = None,
) -> list[Session]:
    """S3: sessiot alkaen ``since`` (inklusiivinen). Tyhjä store → []."""
    repository = traffic_repository() if path is None else None
    if repository is not None:
        return repository.load_sessions(since, source_key=traffic_source())
    raw = _read_raw(path)
    sessions = [_session_from_dict(row) for row in raw.get("sessions") or []]
    if since is not None:
        since_utc = _dt(since)
        sessions = [s for s in sessions if s.started_at >= since_utc]
    sessions.sort(key=lambda s: (s.started_at, s.id))
    return sessions


def load_labels(*, path: Path | None = None) -> list[SessionLabel]:
    """S3: kaikki simulaattorilabelit (session_id = str)."""
    repository = traffic_repository() if path is None else None
    if repository is not None:
        return repository.load_labels(source_key=traffic_source())
    raw = _read_raw(path)
    labels = [_label_from_dict(row) for row in raw.get("labels") or []]
    labels.sort(key=lambda lab: lab.session_id)
    return labels


def is_synthetic(*, path: Path | None = None) -> bool:
    origin = read_snapshot(path=path).get("synthetic")
    if type(origin) is not bool:
        raise ValueError("traffic source provenance is unknown; classify the source explicitly")
    return origin
