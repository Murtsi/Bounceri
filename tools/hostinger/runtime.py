"""Bounded private simulation and local detection; never trains or calls paid models."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import signal
import threading
import time
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from bouncer.db.store import _read_raw
from bouncer.ingest.worker import Worker
from bouncer.investigations import InvestigationStore
from bouncer.network import find_campaigns
from bouncer.review import ReviewSettings, capabilities
from tools.sim.player import play_episode
from tools.sim.run import run
from tools.sim.state import EpisodeLog, fresh_episode


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
    return {
        "synthetic": snapshot["synthetic"],
        "sessions": [session],
        "verdicts": {session["id"]: snapshot.get("verdicts", {}).get(session["id"], {})},
    }


def ingest(stop: threading.Event) -> None:
    store = InvestigationStore(os.environ["BOUNCER_DATABASE_URL"])
    worker = Worker(
        Path("/logs/access.log"),
        Path("/data/store.json"),
        secret=os.environ["SIM_RUN_SECRET"],
        intel_fn=None,
        campaigns_fn=find_campaigns,
        synthetic=True,
        max_records=6000,
        window_seconds=1800,
    )
    last_evidence = None
    last_capture = 0.0
    selection = 0
    while not stop.is_set():
        # Keep at most 30 minutes/6000 records in memory. No real-user source is published.
        worker.cycle()
        # Read the JSON adapter boundary: dataclass.asdict preserves tuple-valued
        # requests in memory, while the persisted legacy contract uses JSON arrays.
        snapshot = _read_raw(worker.store)
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


def run_dynamic_episode(
    state: EpisodeLog,
    stop: threading.Event,
    secret: str,
    *,
    base="http://simulation-gateway:8080",
    generator=None,
    player=None,
):
    """Persist private replay/reference metadata before issuing bounded requests."""
    base = simulation_target(base)
    if generator is None:
        from tools.sim.dynamic import generate_episode

        generator = generate_episode
    player = player or play_episode

    def factory(seed, episode_id, **kwargs):
        return generator(
            seed,
            episode_id,
            **kwargs,
            max_actors=int(os.getenv("SIMULATION_MAX_ACTORS", "24")),
            max_requests=int(os.getenv("SIMULATION_MAX_REQUESTS", "240")),
            max_duration_seconds=float(os.getenv("SIMULATION_MAX_DURATION_SECONDS", "120")),
        )

    episode = fresh_episode(factory, state, base=base)
    manifest = episode.replay_manifest()
    timestamp = lambda: datetime.now(UTC).isoformat()  # noqa: E731
    state.append(
        {
            "type": "planned",
            "timestamp": timestamp(),
            "plan": manifest,
            "session_keys": [[actor.ip, actor.ua] for actor in episode.actors],
        }
    )
    try:
        result = player(
            episode,
            secret,
            base=base,
            stop=stop,
            requests_per_second=float(os.getenv("SIMULATION_REQUESTS_PER_SECOND", "4")),
        )
    except Exception as error:
        state.append(
            {
                "type": "failed",
                "timestamp": timestamp(),
                "episode_id": episode.episode_id,
                "error_type": type(error).__name__,
            }
        )
        raise
    state.append({"type": "completed", "timestamp": timestamp(), "playback": asdict(result)})
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    print(
        "[simulator] "
        + json.dumps(
            {
                "episode": episode.episode_id,
                "fingerprint": fingerprint[:16],
                "actors": len(episode.actors),
                "planned_requests": result.planned_requests,
                "requests": result.attempted_requests,
                "responses": result.completed_requests,
                "network_errors": result.network_errors,
                "dropped_requests": result.dropped_requests,
                "elapsed_seconds": round(result.elapsed_seconds, 3),
                "mode": "dynamic",
            }
        ),
        flush=True,
    )
    return result


def simulate(stop: threading.Event) -> None:
    mode = os.getenv("SIMULATION_MODE", "dynamic")
    if mode == "legacy":
        _simulate_legacy(stop)
        return
    if mode != "dynamic":
        raise ValueError("Simulation mode must be dynamic or legacy")
    base = simulation_target(os.getenv("SIMULATION_TARGET", "http://simulation-gateway:8080"))
    state = EpisodeLog(Path(os.getenv("SIMULATION_STATE_DIR", "/simulation")))
    secret = os.environ["SIM_RUN_SECRET"]
    cap = max(0, int(os.getenv("SIMULATION_MAX_ROUNDS", "0")))
    episodes = 0
    while not stop.is_set() and (cap == 0 or episodes < cap):
        run_dynamic_episode(state, stop, secret, base=base)
        episodes += 1
        stop.wait(1 + secrets.randbelow(5000) / 1000)
    while not stop.wait(30):
        pass


def _simulate_legacy(stop: threading.Event) -> None:
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
