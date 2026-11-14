"""Rebuild a recorded private plan; playback requires an explicit --play flag."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from tools.sim.dynamic import generate_episode
from tools.sim.player import play_episode


def rebuild_episode(log_path: Path, episode_id: str):
    with Path(log_path).open("rb") as source:
        encoded = source.read(2_000_001)
    if len(encoded) > 2_000_000:
        raise ValueError("Replay log exceeds bounded size")
    selected = None
    for line in encoded.splitlines():
        try:
            record = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(record, dict) or record.get("type") != "planned":
            continue
        plan = record.get("plan")
        if isinstance(plan, dict) and plan.get("episode_id") == episode_id:
            selected = plan
    if selected is None or selected.get("generator_version") != "dynamic-v1":
        raise ValueError("Episode or supported generator version is unavailable")
    config = selected.get("config", {})
    if not isinstance(config, dict) or set(config) != {
        "base",
        "max_actors",
        "max_requests",
        "max_duration_seconds",
    }:
        raise ValueError("Recorded generation configuration is invalid")
    episode = generate_episode(selected.get("seed"), episode_id, **config)
    if episode.replay_manifest()["plan_fingerprint"] != selected.get("plan_fingerprint"):
        raise ValueError("Recorded plan does not match the current generator")
    return episode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("/simulation/episodes.jsonl"))
    parser.add_argument("--episode", required=True)
    parser.add_argument("--play", action="store_true", help="Issue actual private demo requests")
    args = parser.parse_args(argv)
    try:
        episode = rebuild_episode(args.log, args.episode)
        if args.play:
            secret = os.getenv("SIM_RUN_SECRET", "")
            if not secret:
                raise ValueError("Simulation signing key is unavailable")
            result = asdict(play_episode(episode, secret))
        else:
            manifest = episode.replay_manifest()
            result = {
                key: manifest[key]
                for key in (
                    "episode_id",
                    "generator_version",
                    "plan_fingerprint",
                    "behavior_fingerprint",
                    "n_actors",
                    "n_requests",
                    "duration_seconds",
                )
            }
            result["matches_record"] = True
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, TypeError, ValueError, KeyError):
        # Private reference metadata and signing credentials never enter diagnostics.
        print(
            "Replay is unavailable: check the episode, generator version and private configuration."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
