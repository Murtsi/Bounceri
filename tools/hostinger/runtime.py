"""Bounded private simulation and local detection; never trains or calls paid models."""

from __future__ import annotations

import argparse
import os
import signal
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlsplit

from bouncer.db.store import traffic_repository, traffic_retention, traffic_source
from bouncer.ingest.worker import Worker
from bouncer.investigations import InvestigationStore
from bouncer.network import find_campaigns
from bouncer.network.live import LiveIntel
from bouncer.review import ReviewSettings, capabilities
from tools.sim.run import run


def simulation_target(url: str) -> str:
    parts = urlsplit(url)
    if (
        (parts.scheme, parts.hostname, parts.port, parts.path, parts.query, parts.fragment)
        != ("http", "simulation-gateway", 8080, "", "", "")
        or parts.username
        or parts.password
    ):
        raise ValueError("The simulator may target only the private simulation-gateway:8080")
    return url


def bounded_records(
    records: list[dict], now: float, *, max_records=6000, window_seconds=1800
) -> list[dict]:
    retained = []
    for record in records:
        timestamp = record.get("ts")
        if isinstance(timestamp, (int, float)) and now - window_seconds <= timestamp <= now + 60:
            retained.append(record)
    return retained[-max_records:]


def selected_session_snapshot(snapshot: dict, index: int) -> dict:
    """A scoped case contains an entire retained session, never a truncated large packet.

    Alternate local findings with controls, round-robin within those buckets,
    independently of simulator truth. This is a selected review sample, not a
    population accuracy estimate. The full snapshot remains separately available.
    """
    verdicts = snapshot.get("verdicts", {})
    findings = [
        s for s in snapshot["sessions"] if verdicts.get(s["id"], {}).get("label") == "bad_bot"
    ]
    controls = [s for s in snapshot["sessions"] if s not in findings]
    findings.sort(key=lambda s: verdicts.get(s["id"], {}).get("rule_id") != "vuln_paths")
    bucket = (findings if index % 2 == 0 else controls) or findings or controls
    session = bucket[(index // 2) % len(bucket)]
    selected_ids = {session["id"]}
    available = {item["id"] for item in snapshot["sessions"]}
    campaigns = snapshot.get("campaigns", [])
    while True:
        expanded = selected_ids | {sid for campaign in campaigns
                                   if selected_ids.intersection(campaign.get("session_ids", []))
                                   for sid in campaign.get("session_ids", [])}
        if len(expanded) > 32 or not expanded <= available:
            # Keep the limitation visible; never truncate a relation and call it complete.
            selected_ids = {session["id"]}
            break
        if expanded == selected_ids:
            break
        selected_ids = expanded
    selected_sessions = [item for item in snapshot["sessions"] if item["id"] in selected_ids]
    selected_ips = {item.get("ip") for item in selected_sessions}
    return {
        "synthetic": snapshot["synthetic"],
        **({"traffic_source_id": snapshot["traffic_source_id"]}
           if snapshot.get("traffic_source_id") else {}),
        "sessions": selected_sessions,
        "verdicts": {sid: snapshot.get("verdicts", {}).get(sid, {}) for sid in selected_ids},
        "rule_observations": {sid: value for sid, value in snapshot.get(
            "rule_observations", {}
        ).items() if sid in selected_ids},
        "ip_evidence": {ip: value for ip, value in snapshot.get("ip_evidence", {}).items()
                        if ip in selected_ips},
        "campaigns": [c for c in campaigns if selected_ids.intersection(c.get("session_ids", []))],
        "ingest": {k: v for k, v in snapshot.get("ingest", {}).items()
                   if k in {"updated_at", "rotation_gaps", "discarded_by_retention"}},
    }


def ingest(stop: threading.Event) -> None:
    store = InvestigationStore(os.environ["BOUNCER_DATABASE_URL"])
    worker = Worker(
        Path("/logs/access.log"),
        Path("/data/store.json"),
        secret=os.environ["SIM_RUN_SECRET"],
        intel_fn=LiveIntel(),
        campaigns_fn=find_campaigns,
        synthetic=True,
        max_records=6000,
        window_seconds=1800,
        repository=traffic_repository(),
        source_key=traffic_source(),
        history_retention_seconds=traffic_retention(),
    )
    last_evidence = None
    last_capture = 0.0
    selection = 0
    while not stop.is_set():
        # Keep at most 30 minutes/6000 records in memory. No real-user source is published.
        snapshot = worker.cycle()
        if snapshot["sessions"] and time.monotonic() - last_capture >= 120:
            case = store.create_from_legacy(
                snapshot, source_key="private-simulation", public_demo=True
            )
            if case["id"] != last_evidence:
                print(f"[investigation] published synthetic case {case['id']}", flush=True)
                last_evidence = case["id"]
            scoped = selected_session_snapshot(snapshot, selection)
            selection += 1
            session_id = scoped["sessions"][0]["id"]
            targeted = store.create_from_legacy(
                scoped, source_key=f"simulation-session/{session_id}", public_demo=True
            )
            # Only an explicitly enabled, independently configured deployment queues
            # asynchronous reviews. Never train on model output or review per request.
            settings = ReviewSettings.from_env()
            maximum = min(100, max(0, int(os.getenv("BOUNCERI_AUTO_REVIEW_MAX_EXECUTIONS", "20"))))
            if (
                os.getenv("BOUNCERI_AUTO_REVIEW", "false").lower() == "true"
                and capabilities(settings)["enabled"]
                and store.usage()["executions"] < maximum
            ):
                try:
                    job = store.enqueue_review(
                        targeted["id"],
                        settings.config_key,
                        settings.maximum_cost_microusd,
                        max_requests=2,
                    )
                    print(
                        f"[review-queue] synthetic case {targeted['id']}: {job['status']}",
                        flush=True,
                    )
                except ValueError:
                    print("[review-queue] deferred: evidence or spending gate", flush=True)
            last_capture = time.monotonic()
        stop.wait(5)


def simulate(stop: threading.Event) -> None:
    base = simulation_target(os.getenv("SIMULATION_TARGET", "http://simulation-gateway:8080"))
    secret = os.environ["SIM_RUN_SECRET"]
    # At most 21 actors / 235 requests each round; no user-controlled target or arbitrary payload.
    # A nonzero round cap can stop an overnight run without removing the dashboard.
    cap = max(0, int(os.getenv("SIMULATION_MAX_ROUNDS", "240")))
    # More than the five-minute session idle window keeps signed truth labels from
    # separate runs from conflicting in one session. Runs remain independent tests.
    interval = max(360, int(os.getenv("SIMULATION_INTERVAL_SECONDS", "360")))
    humans = min(12, max(1, int(os.getenv("SIMULATION_HUMANS", "12"))))
    round_number = 0
    while not stop.is_set() and (cap == 0 or round_number < cap):
        round_number += 1
        started = time.monotonic()
        results = run(
            base, secret, f"hostinger-{int(time.time())}", seed=round_number, humans=humans
        )
        failures = sum(not isinstance(r[3], int) for r in results)
        print(
            f"[simulator] round={round_number} requests={len(results)} network_errors={failures}",
            flush=True,
        )
        stop.wait(max(0, interval - (time.monotonic() - started)))
    # Stay healthy after the bounded run so restart policies cannot restart an endless run.
    while not stop.wait(30):
        pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ingest", "simulate", "init"))
    args = parser.parse_args(argv)
    if args.mode == "init":
        InvestigationStore(os.environ["BOUNCER_DATABASE_URL"])
        # Enforcement owns an additive schema; initialize once if installed.
        try:
            from bouncer.enforcement import EnforcementStore
        except ImportError:
            pass
        else:
            EnforcementStore(os.environ["BOUNCER_DATABASE_URL"])
        return 0
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    (ingest if args.mode == "ingest" else simulate)(stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
