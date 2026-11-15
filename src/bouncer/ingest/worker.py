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
import json
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
    write_snapshot_health,
)
from bouncer.eval.run import network_signals
from bouncer.explain import explain
from bouncer.ingest import simrun
from bouncer.ingest.continuity import sessionize
from bouncer.ingest.runtime_context import bound_contexts, capture_configuration, capture_session
from bouncer.ingest.sample import _timestamp, parse_access_record, storage_safe_record
from bouncer.ingest.tail import LogTail
from bouncer.session import rules, score
from bouncer.session.actions import recommend
from bouncer.session.features import compute_features

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
        traps: frozenset[str] | None = None,
        rules_only: bool = False,
        max_retained_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        if max_records is not None and (type(max_records) is not int or max_records < 1):
            raise ValueError("max_records must be a positive integer")
        if window_seconds is not None and window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if type(max_retained_bytes) is not int or max_retained_bytes <= 0:
            raise ValueError("retained byte limit must be positive")
        self.max_retained_bytes = max_retained_bytes
        self.retained_bytes = 0
        self.rules_only = rules_only
        self.trap_paths = traps
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
            if resumed.get("deleted"):
                raise ValueError("deleted source cannot be used by a live worker; use a new key")
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
            for record in resumed["records"]:
                try:
                    self.records.append(storage_safe_record(record))
                except (ValueError, TypeError, AttributeError, RecursionError):
                    self.tail.bad_lines += 1
            self.discarded_by_retention = resumed.get("discarded_by_retention", 0)
            saved["session_identity_state"] = resumed.get("session_identity_state", [])
            self.label_state = resumed.get("session_label_state", {})
        elif self.committed_checkpoint is not None:
            raise ValueError("traffic checkpoint has no private worker resume state")
        self.last_event_at = saved.get("ingest", {}).get("last_event_at")
        self.previous_sessions = [
            dataclasses.replace(_session_from_dict(row), requests=())
            for row in saved.get("session_identity_state", saved.get("sessions", []))
        ]

    def _intel(self, ip: str) -> IpIntel:
        if (hasattr(self.intel_fn, "observation") or ip not in self.intel_cache):
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
        kept, size = [], 0
        for record in reversed(self.records):
            encoded = len(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode())
            if size + encoded > self.max_retained_bytes:
                break
            kept.append(record)
            size += encoded
        self.records = list(reversed(kept))
        self.retained_bytes = size
        self.discarded_by_retention += before - len(self.records)

    def cycle(self) -> dict[str, Any]:
        before = (self.tail.checkpoint(), self.records[:], self.discarded_by_retention,
                  dict(self.intel_cache), self.retained_bytes, self.last_event_at)
        try:
            return self._cycle()
        except Exception:
            # A failed transaction must not acknowledge source bytes or mutate the retained window.
            self.tail.restore(before[0])
            (self.records, self.discarded_by_retention, self.intel_cache,
             self.retained_bytes, self.last_event_at) = before[1:]
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
        if history_sessions:
            newest = max(s.ended_at for s in history_sessions).isoformat()
            if self.last_event_at is None or newest > self.last_event_at:
                self.last_event_at = newest
        self._retain()
        known = {s.id: s for s in self.previous_sessions}
        known.update({s.id: s for s in history_sessions})
        sessions, labels, _, _ = sessionize(
            self.records, list(known.values()), self.secret, next_labels
        )
        active_ips = {session.ip for session in sessions}
        self.intel_cache = {
            ip: intel for ip, intel in self.intel_cache.items() if ip in active_ips
        }
        if hasattr(self.intel_fn, "begin_cycle"):
            self.intel_fn.begin_cycle()
        intel, ip_evidence = {}, {}
        for ip in sorted({s.ip for s in sessions}):
            intel[ip] = self._intel(ip)
            if hasattr(self.intel_fn, "observation"):
                # Capture before the bounded resolver cache can evict another active client.
                ip_evidence[ip] = self.intel_fn.observation(ip)
        _, camp_by_session = network_signals(sessions, None, self.campaigns_fn)
        campaigns = {id(c): c for c in camp_by_session.values()}.values()

        verdicts = {}
        rule_observations = {}
        traps = self.trap_paths if self.trap_paths is not None else rules.load_traps()
        trap_version = hashlib.sha256("\n".join(sorted(traps)).encode()).hexdigest()
        runtime_configuration = capture_configuration(traps)
        feature_fields = {
            "duration_s", "requests_per_min", "peak_requests_per_min", "static_share",
            "html_share", "vuln_path_hits", "header_inconsistency_share", "ua_is_tool",
            "ua_claims_bot",
        }
        for s in sessions:
            camp: Campaign | None = camp_by_session.get(s.id)
            v = score(s, intel[s.ip], camp, traps=traps,
                      **({"model": None} if self.rules_only else {}))
            hits = rules.evaluate(s, intel[s.ip], traps, camp)
            rule_id = hits[0].rule_id if hits else None
            rule_observations[s.id] = {
                "version": "bouncer-rule-observations-v1",
                "trap_hits": len({r.path for r in s.requests if rules._normalise(r.path) in traps}),
                "trap_config_version": trap_version,
                "rule_ids": [hit.rule_id for hit in hits],
                "features": {key: value for key, value in dataclasses.asdict(
                    compute_features(s)
                ).items() if key in feature_fields},
            }
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
        captured_at = datetime.now(UTC).isoformat()
        runtime_contexts = bound_contexts({s.id: capture_session(
            s, intel[s.ip], configuration=runtime_configuration, captured_at=captured_at,
            intel_enabled=self.intel_fn is not None, observation=ip_evidence.get(s.ip),
        ) for s in sessions})
        payload = {
            # Private continuity state survives eviction of visible request records.
            "session_identity_state": [_serialize_session(s) for s in identity_state],
            "session_label_state": {s.id: next_labels[s.id] for s in identity_state
                                    if s.id in next_labels},
            "sessions": [_serialize_session(s) for s in sessions],
            "labels": [_serialize_label(lab) for lab in labels],
            "synthetic": self.synthetic,
            "traffic_source_id": self.source_key,
            "source": f"caddy:{self.tail.path}",
            "verdicts": verdicts,
            "ip_evidence": ip_evidence,
            "rule_observations": rule_observations,
            "runtime_configuration": runtime_configuration,
            "runtime_contexts": runtime_contexts,
            "campaigns": [_campaign_dict(c) for c in campaigns],
            "ingest": {
                **stats.as_dict(),
                "bad_lines": self.tail.bad_lines,
                "rotation_gaps": self.tail.rotation_gaps,
                "retained_records": len(self.records),
                "retained_bytes": self.retained_bytes,
                "last_event_at": self.last_event_at,
                "discarded_by_retention": self.discarded_by_retention,
                "updated_at": captured_at,
            },  # fmt: skip
        }
        if self.repository is None:
            payload["worker_resume_state"] = self._resume_state(payload)
            _write_raw(payload, self.store)
            try:
                write_snapshot_health(
                    self.store, payload["ingest"]["updated_at"], self.last_event_at
                )
            except OSError:
                print("Worker health metadata unavailable; source commit preserved.", flush=True)
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
    from bouncer.network import find_campaigns

    campaigns_fn = find_campaigns
    if not a.offline:
        from bouncer.network.live import LiveIntel

        intel_fn = LiveIntel()
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
