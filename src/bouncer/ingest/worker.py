"""Live-worker (A-5/A-6, MVP vaihe 3): Caddy-loki → sessiot → C → B → store.

    SIM_RUN_SECRET=… uv run python -m bouncer.ingest.worker --log logs/caddy/access.log

Joka kierroksella:
1. lukee lokin uudet rivit (sietää rikkinäiset rivit, katkaisun ja rotaation),
2. sessioi kaikki rivit (parseri, allekirjoitetut merkinnät, päätös 046),
3. hakee C:n IP-tiedot (kerran per IP, välimuistissa) ja kampanjat,
4. pisteyttää jokaisen session B:n `score()`:lla ja selittää C:n `explain()`:lla
   ilman LLM:ää (AI Router -saldoa ei kuluteta silmukassa),
5. commits source events, read models and byte checkpoints together when SQL is selected;
   JSON remains an explicit private compatibility adapter.

Committed event ownership and private continuity state preserve session IDs through
late timestamps, retention, rotation and restart.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
import signal
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import time as _retention_now
from typing import Any

from bouncer.contracts import Campaign, IpIntel, Session, SessionLabel
from bouncer.db.store import (
    _read_raw,
    _serialize_label,
    _serialize_session,
    _session_from_dict,
    _write_raw,
    store_path,
    traffic_repository,
    traffic_retention,
    traffic_source,
)
from bouncer.eval.run import network_signals
from bouncer.explain import explain
from bouncer.ingest import simrun
from bouncer.ingest.continuity import sessionize
from bouncer.ingest.sample import _timestamp, parse_access_record
from bouncer.ingest.tail import LogTail
from bouncer.session import rules, score
from bouncer.session.actions import recommend

IntelFn = Callable[[str], IpIntel]
CampaignsFn = Callable[[Sequence[Session]], list[Any]]




def stable_id(s: Session) -> str:
    key = f"{s.ip}|{s.user_agent}|{s.started_at.isoformat()}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def restamp(
    sessions: list[Session], labels: list[SessionLabel]
) -> tuple[list[Session], list[SessionLabel]]:
    mapping = {s.id: stable_id(s) for s in sessions}
    new_sessions = [dataclasses.replace(s, id=mapping[s.id]) for s in sessions]
    new_labels = [dataclasses.replace(lab, session_id=mapping.get(lab.session_id, lab.session_id))
                  for lab in labels]  # fmt: skip
    return new_sessions, new_labels


def _campaign_dict(c: Any) -> dict[str, Any]:
    return {"id": c.id, "kind": c.kind, "session_ids": [str(x) for x in c.session_ids],
            "reasons": list(c.reasons), "size": len(c.session_ids)}  # fmt: skip


class Worker:
    def __init__(
        self,
        log: Path,
        store: Path,
        *,
        secret: str | None,
        intel_fn: IntelFn | None,
        campaigns_fn: CampaignsFn | None,
        synthetic: bool,
        max_records: int | None = None,
        window_seconds: float | None = None,
        repository=None,
        source_key: str = "monitored",
        history_retention_seconds: float | None = None,
    ) -> None:
        if max_records is not None and (type(max_records) is not int or max_records < 1):
            raise ValueError("max_records must be a positive integer")
        if window_seconds is not None and window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.history_retention_seconds = history_retention_seconds
        self.max_records = max_records
        self.window_seconds = window_seconds
        self.discarded_by_retention = 0
        self.tail = LogTail(log)
        self.store = store
        self.secret = secret
        self.intel_fn = intel_fn
        self.campaigns_fn = campaigns_fn
        self.synthetic = synthetic
        self.records: list[dict[str, Any]] = []
        self.intel_cache: dict[str, IpIntel] = {}
        self.repository = repository
        self.source_key = source_key
        self.committed_checkpoint = None
        self.label_state = {}
        if repository is None:
            saved = _read_raw(store)
            resumed = saved.get("worker_resume_state", {})
        else:
            saved = repository.load_snapshot(source_key)
            self.committed_checkpoint = repository.load_checkpoint(source_key)
            resumed = repository.load_resume_state(source_key) or {}
            if "archive_digest" in resumed:
                raise ValueError("read-only archive cannot be used by a live worker")
            if self.committed_checkpoint is None and store.exists():
                legacy = _read_raw(store)
                if legacy.get("sessions") or legacy.get("worker_resume_state"):
                    with store.open("rb") as original:
                        digest = hashlib.file_digest(original, "sha256").hexdigest()
                    archive = repository.load_resume_state("archive/" + digest)
                    if not archive.get("archive_digest"):
                        raise ValueError("archive the existing JSON snapshot before SQL cutover")
                    if legacy.get("synthetic") is not self.synthetic:
                        raise ValueError("JSON provenance differs from the configured live source")
                    saved = legacy
                    resumed = legacy.get("worker_resume_state", {})
        self.label_state = saved.get("session_label_state", {})
        if resumed:
            self.tail.restore(resumed["tail"])
            self.records = resumed["records"]
            self.discarded_by_retention = resumed.get("discarded_by_retention", 0)
            saved["session_identity_state"] = resumed.get("session_identity_state", [])
            self.label_state = resumed.get("session_label_state", {})
        elif self.committed_checkpoint is not None:
            raise ValueError("traffic checkpoint has no private worker resume state")
        self.previous_sessions = [
            dataclasses.replace(_session_from_dict(row), requests=())
            for row in saved.get("session_identity_state", saved.get("sessions", []))
        ]

    def _intel(self, ip: str) -> IpIntel:
        if ip not in self.intel_cache:
            self.intel_cache[ip] = self.intel_fn(ip) if self.intel_fn else IpIntel()
        return self.intel_cache[ip]

    def _retain(self) -> None:
        before = len(self.records)
        if self.window_seconds is not None:
            current = _retention_now()
            retained = []
            for record in self.records:
                try:
                    timestamp = _timestamp(record.get("ts")).timestamp()
                except (ValueError, TypeError, OverflowError, OSError):
                    continue
                if current - self.window_seconds <= timestamp <= current + 60:
                    retained.append(record)
            self.records = retained
        if self.max_records is not None:
            self.records = self.records[-self.max_records :]
        self.discarded_by_retention += before - len(self.records)

    def cycle(self) -> dict[str, Any]:
        before = (self.tail.checkpoint(), self.records[:], self.discarded_by_retention,
                  dict(self.intel_cache))
        try:
            return self._cycle()
        except Exception:
            # A failed transaction must not acknowledge source bytes or mutate the retained window.
            self.tail.restore(before[0])
            self.records, self.discarded_by_retention, self.intel_cache = before[1:]
            raise

    def _cycle(self) -> dict[str, Any]:
        self.tail.read_new()
        private_keys = {"_session_id", "_source_event"}
        self.records.extend(
            {k: v for k, v in event["record"].items() if k not in private_keys}
            | {"_source_event": {"generation": event["generation"],
                                 "byte_offset": event["byte_offset"]}}
            for event in self.tail.events
        )
        # Persist source history before bounding the expensive detection/read-model window.
        history_records = self.records[:]
        history_sessions, history_labels, stats, next_labels = sessionize(
            history_records, self.previous_sessions, self.secret, self.label_state
        )
        self._retain()
        known = {s.id: s for s in self.previous_sessions}
        known.update({s.id: s for s in history_sessions})
        sessions, labels, _, _ = sessionize(
            self.records, list(known.values()), self.secret, next_labels
        )
        if self.max_records is not None or self.window_seconds is not None:
            active_ips = {session.ip for session in sessions}
            self.intel_cache = {
                ip: intel for ip, intel in self.intel_cache.items() if ip in active_ips
            }
        intel = {s.ip: self._intel(s.ip) for s in sessions}
        _, camp_by_session = network_signals(sessions, None, self.campaigns_fn)
        campaigns = {id(c): c for c in camp_by_session.values()}.values()

        verdicts = {}
        traps = rules.load_traps()
        for s in sessions:
            camp: Campaign | None = camp_by_session.get(s.id)
            v = score(s, intel[s.ip], camp, traps=traps)
            hits = rules.evaluate(s, intel[s.ip], traps, camp)
            rule_id = hits[0].rule_id if hits else None
            verdicts[s.id] = {
                "rule_id": rule_id,
                "action": recommend(v.label, rule_id),
                "label": v.label,
                "score": v.score,
                "reasons": list(v.reasons),
                "model_version": v.model_version,
                "campaign_id": camp.id if camp else None,
                "explanation": explain(v, s, camp, use_llm=False),
                "verified_bot": intel[s.ip].verified_bot,
                "asn_type": intel[s.ip].asn_type,
            }
        identities = {s.id: s for s in self.previous_sessions}
        for session in history_sessions:
            old = identities.get(session.id, session)
            identities[session.id] = dataclasses.replace(
                session, requests=(), started_at=min(old.started_at, session.started_at),
                ended_at=max(old.ended_at, session.ended_at),
            )
        watermark = max((s.ended_at for s in identities.values()), default=None)
        visible_ids = {s.id for s in sessions}
        identity_state = [s for s in identities.values()
                          if s.id in visible_ids or watermark is None
                          or s.ended_at >= watermark - timedelta(minutes=5)]
        payload = {
            # Private continuity state survives eviction of visible request records.
            "session_identity_state": [_serialize_session(s) for s in identity_state],
            "session_label_state": {s.id: next_labels[s.id] for s in identity_state
                                    if s.id in next_labels},
            "sessions": [_serialize_session(s) for s in sessions],
            "labels": [_serialize_label(lab) for lab in labels],
            "synthetic": self.synthetic,
            "source": f"caddy:{self.tail.path}",
            "verdicts": verdicts,
            "campaigns": [_campaign_dict(c) for c in campaigns],
            "ingest": {
                **stats.as_dict(),
                "bad_lines": self.tail.bad_lines,
                "rotation_gaps": self.tail.rotation_gaps,
                "retained_records": len(self.records),
                "discarded_by_retention": self.discarded_by_retention,
                "updated_at": datetime.now(UTC).isoformat(),
            },  # fmt: skip
        }
        if self.repository is None:
            payload["worker_resume_state"] = self._resume_state(payload)
            _write_raw(payload, self.store)
        else:
            self._persist_traffic(payload, history_records, history_sessions, history_labels)
        self.previous_sessions = identity_state
        self.label_state = payload["session_label_state"]
        return payload

    def _resume_state(self, payload):
        return {"tail": self.tail.checkpoint(), "records": self.records,
                "session_identity_state": payload["session_identity_state"],
                "session_label_state": payload["session_label_state"],
                "discarded_by_retention": self.discarded_by_retention}

    def _persist_traffic(self, payload, history_records, history_sessions, history_labels):
        from bouncer.db.traffic import Checkpoint, SourceEvent

        visible_ids = {id(raw) for raw in self.records}
        events, visible_events = [], []
        for raw in history_records:
            try:
                request, _ = parse_access_record(raw, secret=self.secret)
            except (ValueError, TypeError, OverflowError, OSError, AttributeError):
                continue
            position = raw["_source_event"]
            event = SourceEvent(
                generation=position["generation"], byte_offset=position["byte_offset"],
                request=request, session_id=raw["_session_id"],
            )
            events.append(event)
            if id(raw) in visible_ids:
                visible_events.append(event)
        resume_state = self._resume_state(payload)
        self.committed_checkpoint = self.repository.apply_batch(
            self.source_key, events=events, snapshot=payload,
            checkpoint=Checkpoint(generation=self.tail.generation, byte_offset=self.tail.offset),
            expected_checkpoint=self.committed_checkpoint, resume_state=resume_state,
            history_sessions=history_sessions, history_labels=history_labels,
            visible_events=visible_events,
            retention_before=(datetime.fromtimestamp(
                _retention_now() - self.history_retention_seconds, tz=UTC
            ) if self.history_retention_seconds is not None else None),
        )

    def run(self, interval: float, stop: threading.Event) -> None:
        while not stop.is_set():
            p = self.cycle()
            counts: dict[str, int] = {}
            for v in p["verdicts"].values():
                counts[v["label"]] = counts.get(v["label"], 0) + 1
            ing = p["ingest"]
            print(
                f"[worker] {len(p['sessions'])} sessiota {counts} "
                f"kampanjoita {len(p['campaigns'])} ohitettu {ing['unsigned_markers']}",
                flush=True,
            )
            stop.wait(interval)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--log", type=Path, default=Path(os.getenv("CADDY_LOG", "logs/caddy/access.log"))
    )
    ap.add_argument("--store", type=Path, default=None, help="oletus BOUNCER_STORE_PATH")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--once", action="store_true", help="yksi kierros ja lopetus")
    ap.add_argument("--offline", action="store_true", help="ei C:n DNS-hakuja")
    ap.add_argument("--real", action="store_true", help="data ei ole synteettistä (oletus: on)")
    ap.add_argument("--allow-unsigned", action="store_true", help="hyväksy allekirjoittamattomat")
    a = ap.parse_args(argv)

    secret = simrun.secret_from_env()
    if not secret and not a.allow_unsigned:
        print(f"{simrun.SECRET_ENV} puuttuu: labeleita ei voi tarkistaa (päätös 046). "
              "Aseta se tai käytä --allow-unsigned paikallisesti.")  # fmt: skip
        return 1
    intel_fn = campaigns_fn = None
    from bouncer.network import find_campaigns, ip_intel_contract

    campaigns_fn = find_campaigns
    if not a.offline:
        intel_fn = ip_intel_contract
    w = Worker(a.log, a.store or store_path(), secret=secret, intel_fn=intel_fn,
               campaigns_fn=campaigns_fn, synthetic=not a.real,
               repository=traffic_repository(), source_key=traffic_source(),
               history_retention_seconds=traffic_retention())  # fmt: skip
    if a.once:
        w.cycle()
        return 0
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    w.run(a.interval, stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
