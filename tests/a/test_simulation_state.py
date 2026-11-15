import json
from types import SimpleNamespace

from tools.sim.run import Actor
from tools.sim.state import EpisodeLog, fresh_episode


def test_private_replay_log_rotates_and_recovers_recent_session_keys(tmp_path):
    state = EpisodeLog(tmp_path, max_bytes=450, backups=2)
    for index in range(8):
        state.append(
            {
                "type": "planned",
                "episode_id": str(index),
                "session_keys": [[f"198.18.0.{index + 1}", "browser"]],
                "padding": "x" * 110,
            }
        )
    files = list(tmp_path.glob("episodes.jsonl*"))
    assert 1 <= len(files) <= 3
    assert all(path.stat().st_size <= 450 for path in files)
    with (tmp_path / "episodes.jsonl").open("ab") as target:
        target.write(b'{"partial":')
    restored = EpisodeLog(tmp_path, max_bytes=450, backups=2)
    assert ("198.18.0.8", "browser") in restored.recent_pairs()
    assert len(restored.recent_pairs()) <= 6
    restored.append({"type": "planned", "session_keys": [["198.18.0.99", "browser"]]})
    assert ("198.18.0.99", "browser") in restored.recent_pairs()


def test_corrupted_nonobject_log_lines_are_skipped(tmp_path):
    (tmp_path / "episodes.jsonl").write_text('[]\n"unexpected"\n')
    assert EpisodeLog(tmp_path).recent_pairs() == set()


def test_fresh_seed_and_identity_do_not_reuse_a_recent_ip_user_agent_pair(tmp_path):
    state = EpisodeLog(tmp_path)
    state.append({"type": "planned", "session_keys": [["198.18.0.1", "browser"]]})
    seeds = iter((1, 2, 3))
    created = []

    def factory(seed, episode_id, **_):
        created.append((seed, episode_id))
        return SimpleNamespace(
            seed=seed,
            episode_id=episode_id,
            actors=(Actor("opaque", f"198.18.0.{seed}", "browser", "human"),),
        )

    result = fresh_episode(factory, state, seed_factory=lambda bits: next(seeds))
    assert result.seed == 2 and len(created) == 2
    assert created[0][1] != created[1][1]
    assert (result.actors[0].ip, result.actors[0].ua) not in state.recent_pairs()


def test_recording_a_plan_never_needs_a_provider_or_detector_result(tmp_path):
    state = EpisodeLog(tmp_path)
    state.append(
        {
            "type": "planned",
            "seed": 123,
            "episode_id": "opaque",
            "generator_version": "dynamic-v1",
            "session_keys": [],
        }
    )
    stored = json.loads((tmp_path / "episodes.jsonl").read_text())
    assert stored["seed"] == 123
    assert not {"verdicts", "provider", "api_key"}.intersection(stored)


def test_recent_identity_protection_does_not_expire_after_sixteen_fast_episodes(tmp_path):
    state = EpisodeLog(tmp_path)
    for index in range(17):
        state.append({"type": "planned", "session_keys": [[f"198.18.0.{index + 1}", "browser"]]})
    assert ("198.18.0.1", "browser") in state.recent_pairs()
