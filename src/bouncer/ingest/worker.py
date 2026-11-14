"""Live-worker (A-5/A-6, MVP vaihe 3): Caddy-loki → sessiot → C → B → store.

    SIM_RUN_SECRET=… uv run python -m bouncer.ingest.worker --log logs/caddy/access.log

Joka kierroksella:
1. lukee lokin uudet rivit (sietää rikkinäiset rivit, katkaisun ja rotaation),
2. sessioi kaikki rivit (parseri, allekirjoitetut merkinnät, päätös 046),
3. hakee C:n IP-tiedot (kerran per IP, välimuistissa) ja kampanjat,
4. pisteyttää jokaisen session B:n `score()`:lla ja selittää C:n `explain()`:lla
   ilman LLM:ää (AI Router -saldoa ei kuluteta silmukassa),
5. kirjoittaa kaiken atomisesti JSON-storeen, josta API lukee.

Session ID on vakaa (`ip|ua|alkuaika` → hash), joten sama sessio pitää ID:nsä,
vaikka uusia sessioita tulee ja parserin juokseva numerointi muuttuu.
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
from collections import defaultdict
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
)
from bouncer.eval.run import network_signals
from bouncer.explain import explain
from bouncer.ingest import simrun
from bouncer.ingest.sample import _timestamp, parse_access_records
from bouncer.ingest.simrun import IngestStats
from bouncer.session import rules, score
from bouncer.session.actions import recommend

IntelFn = Callable[[str], IpIntel]
CampaignsFn = Callable[[Sequence[Session]], list[Any]]


class LogTail:
    """Lukee JSONL-lokia lisäyksinä. Kesken jäänyt viimeinen rivi odottaa seuraavaan kertaan."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.inode: int | None = None
        self.partial = b""
        self.bad_lines = 0

    def read_new(self) -> list[dict[str, Any]]:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return []
        if self.inode is not None and (st.st_ino != self.inode or st.st_size < self.offset):
            self.offset, self.partial = 0, b""  # rotaatio tai katkaisu
        self.inode = st.st_ino
        with self.path.open("rb") as f:
            f.seek(self.offset)
            chunk = f.read()
            self.offset = f.tell()
        data = self.partial + chunk
        lines = data.split(b"\n")
        self.partial = lines.pop()  # tyhjä, jos data päättyi rivinvaihtoon
        out = []
        for raw in lines:
            raw = raw.replace(b"\x00", b"").strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except ValueError:
                self.bad_lines += 1
                continue
            if isinstance(row, dict) and isinstance(row.get("request"), dict):
                out.append(row)
            else:
                self.bad_lines += 1
        return out


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
    ) -> None:
        if max_records is not None and (type(max_records) is not int or max_records < 1):
            raise ValueError("max_records must be a positive integer")
        if window_seconds is not None and window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
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
        saved = _read_raw(store)
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
        self.records.extend(self.tail.read_new())
        # Freshly read restart/rotation batches must be bounded before parsing/scoring.
        self._retain()
        stats = IngestStats()
        sessions, labels = parse_access_records(self.records, secret=self.secret, stats=stats)
        previous_by_client = defaultdict(list)
        for old in self.previous_sessions:
            previous_by_client[(old.ip, old.user_agent)].append(old)
        mapping = {}
        used = set()
        for session in sessions:
            previous = next((old for old in previous_by_client[(session.ip, session.user_agent)]
                             if old.id not in used
                             and old.started_at <= session.started_at
                             <= old.ended_at + timedelta(minutes=5)), None)
            mapping[session.id] = previous.id if previous else stable_id(session)
            used.add(mapping[session.id])
        sessions = [dataclasses.replace(s, id=mapping[s.id]) for s in sessions]
        labels = [dataclasses.replace(lab, session_id=mapping[lab.session_id]) for lab in labels]

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
        for session in sessions:
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
            "sessions": [_serialize_session(s) for s in sessions],
            "labels": [_serialize_label(lab) for lab in labels],
            "synthetic": self.synthetic,
            "source": f"caddy:{self.tail.path}",
            "verdicts": verdicts,
            "campaigns": [_campaign_dict(c) for c in campaigns],
            "ingest": {
                **stats.as_dict(),
                "bad_lines": self.tail.bad_lines,
                "retained_records": len(self.records),
                "discarded_by_retention": self.discarded_by_retention,
                "updated_at": datetime.now(UTC).isoformat(),
            },  # fmt: skip
        }
        _write_raw(payload, self.store)
        self.previous_sessions = identity_state
        return payload

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
               campaigns_fn=campaigns_fn, synthetic=not a.real)  # fmt: skip
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
