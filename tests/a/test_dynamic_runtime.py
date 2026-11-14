import json
import threading
from types import SimpleNamespace

from tools.hostinger.package import ROOT, compose
from tools.hostinger.runtime import run_dynamic_episode
from tools.sim.player import PlaybackReport
from tools.sim.run import Actor, Step
from tools.sim.state import EpisodeLog


def test_episode_is_recorded_before_actual_playback_and_truth_stays_private(tmp_path):
    state = EpisodeLog(tmp_path)
    played = []

    def generate(seed, episode_id, **kwargs):
        a = Actor("opaque", "198.18.0.1", "browser", "human", steps=[Step(0, "GET", "/")])
        return SimpleNamespace(
            seed=seed,
            episode_id=episode_id,
            actors=(a,),
            duration_seconds=2,
            replay_manifest=lambda: {
                "seed": seed,
                "episode_id": episode_id,
                "generator_version": "test-v1",
                "plan_fingerprint": "test",
            },
        )

    def play(episode, secret, **kwargs):
        events = [json.loads(line) for line in state.path.read_text().splitlines()]
        assert events[-1]["type"] == "planned"
        assert "private-test-signing-key" not in state.path.read_text()
        played.append(episode)
        return PlaybackReport(episode.episode_id, 1, 1, 1, {"200": 1}, 0, 0, 0.1, False, False)

    result = run_dynamic_episode(
        state, threading.Event(), "private-test-signing-key", generator=generate, player=play
    )
    assert result.completed_requests == 1 and len(played) == 1
    assert json.loads(state.path.read_text().splitlines()[-1])["type"] == "completed"


def test_simulator_replay_volume_isolated_from_analysis_and_provider_credentials():
    env = {
        name: "x" * 64
        for name in (
            "POSTGRES_PASSWORD",
            "BOUNCER_ADMIN_TOKEN",
            "BOUNCER_DEMO_ACTOR_SECRET",
            "SIM_RUN_SECRET",
        )
    }
    config = compose(ROOT, "test.example", env)
    simulator = config["services"]["simulator"]
    assert "simulation:/simulation" in simulator["volumes"]
    assert "data:/data:ro" in simulator["volumes"]
    assert simulator["environment"]["SIMULATION_MODE"] == "dynamic"
    assert simulator["environment"]["SIMULATION_MAX_ROUNDS"] == "0"
    for name in ("api", "ingest", "review", "site"):
        assert not any(
            volume.startswith("simulation:") for volume in config["services"][name]["volumes"]
        )
    assert "FEATHERLESS_API_KEY" not in simulator["environment"]
