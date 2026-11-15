import json

import pytest

from tools.sim.dynamic import generate_episode
from tools.sim.replay import rebuild_episode


def test_replay_rebuilds_the_recorded_plan_without_network_or_reference_guessing(tmp_path):
    original = generate_episode(12345, "opaque-episode")
    path = tmp_path / "episodes.jsonl"
    path.write_text(json.dumps({"type": "planned", "plan": original.replay_manifest()}) + "\n")
    replayed = rebuild_episode(path, "opaque-episode")
    assert replayed.replay_manifest() == original.replay_manifest()


def test_tampered_or_unavailable_generator_plan_cannot_be_presented_as_a_replay(tmp_path):
    plan = generate_episode(987, "opaque").replay_manifest()
    path = tmp_path / "episodes.jsonl"
    for changed in ({**plan, "seed": 988}, {**plan, "generator_version": "unknown-version"}):
        path.write_text(json.dumps({"type": "planned", "plan": changed}) + "\n")
        with pytest.raises(ValueError):
            rebuild_episode(path, "opaque")
    with pytest.raises(ValueError):
        rebuild_episode(path, "not-present")
