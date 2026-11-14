"""Pure variable episode plans: bounded, replayable and independent of detector output."""

import ipaddress
import json
from collections import Counter
from dataclasses import FrozenInstanceError
from urllib.parse import parse_qs, urlsplit

import pytest

from tools.sim.dynamic import generate_episode


def episodes():
    return [generate_episode(seed, f"development-{seed}") for seed in range(64)]


def test_replay_is_deterministic_and_contains_actual_configuration():
    first = generate_episode(
        91, "replay-a", max_actors=12, max_requests=100, max_duration_seconds=45
    )
    second = generate_episode(
        91, "replay-a", max_actors=12, max_requests=100, max_duration_seconds=45
    )
    assert first.replay_manifest() == second.replay_manifest()
    manifest = first.replay_manifest()
    assert manifest["config"] == {
        "base": "http://simulation-gateway:8080",
        "max_actors": 12,
        "max_requests": 100,
        "max_duration_seconds": 45,
    }
    assert len(manifest["plan_fingerprint"]) == 64
    assert manifest["generator_version"] == "dynamic-v1"
    replay = generate_episode(manifest["seed"], manifest["episode_id"], **manifest["config"])
    assert replay.replay_manifest()["plan_fingerprint"] == manifest["plan_fingerprint"]
    with pytest.raises(FrozenInstanceError):
        first.seed = 3


def test_many_seeds_change_structure_counts_mixes_and_journeys():
    suite = episodes()
    manifests = [episode.replay_manifest() for episode in suite]
    assert {m["mix"] for m in manifests} == {"benign_only", "mixed", "attack_heavy"}
    assert len({len(episode.actors) for episode in suite}) >= 10
    assert len({sum(len(actor.steps) for actor in episode.actors) for episode in suite}) >= 25
    assert len({m["behavior_fingerprint"] for m in manifests}) == len(suite)
    assert (
        len({tuple(step.path for step in actor.steps) for e in suite for actor in e.actors}) > 150
    )
    for episode, manifest in zip(suite, manifests, strict=True):
        assert 6 <= len(episode.actors) <= 24
        assert 40 <= sum(len(actor.steps) for actor in episode.actors) <= 240
        if manifest["mix"] == "benign_only":
            assert all(
                a["reference_intent"]["maliciousness"] == "benign" for a in manifest["actors"]
            )
        if manifest["mix"] == "attack_heavy":
            hostile = sum(
                a["reference_intent"]["maliciousness"] == "hostile_fixture"
                for a in manifest["actors"]
            )
            assert hostile / len(episode.actors) >= 0.5


def test_caps_paths_header_safety_and_deadline_margin():
    for seed in range(25):
        episode = generate_episode(
            seed, f"bounded-{seed}", max_actors=9, max_requests=45, max_duration_seconds=30
        )
        assert len(episode.actors) <= 9
        assert sum(len(actor.steps) for actor in episode.actors) <= 45
        assert 0 < episode.duration_seconds <= 30
        pairs = {(actor.ip, actor.ua) for actor in episode.actors}
        assert len(pairs) == len(episode.actors)
        final = max(step.at for actor in episode.actors for step in actor.steps)
        assert episode.duration_seconds - final >= 0.99
        for actor in episode.actors:
            assert actor.steps
            assert [step.at for step in actor.steps] == sorted(step.at for step in actor.steps)
            assert actor.sim_class != "good_bot"
            for step in actor.steps:
                parts = urlsplit(step.path)
                assert step.path.startswith("/") and not step.path.startswith("//")
                assert not parts.scheme and not parts.netloc and ".." not in parts.path
                assert (
                    step.method in {"GET", "HEAD", "POST"}
                    and 0 <= step.at < episode.duration_seconds
                )
                assert not {
                    "authorization",
                    "host",
                    "cookie",
                    "x-forwarded-for",
                    "x-sim-run",
                    "x-sim-sig",
                } & {k.lower() for k in step.headers}
                assert all("\r" not in v and "\n" not in v for v in step.headers.values())
                if step.method == "POST":
                    assert parts.path == "/login" and parse_qs(step.data or "").get("username")


def test_identity_pool_does_not_encode_intent_and_ephemeral_pairs_change():
    browser_mimics = monitor_curl = shared_role_ua = nat_examples = 0
    for episode in episodes():
        manifest = episode.replay_manifest()
        references = {row["id"]: row for row in manifest["actors"]}
        benign = set()
        hostile = set()
        for actor in episode.actors:
            assert ipaddress.ip_address(actor.ip) in ipaddress.ip_network("198.18.0.0/15")
            assert actor.name.startswith("a-")
            assert not any(
                word in actor.name.lower() or word in actor.ua.lower()
                for word in ("human", "scanner", "scraper", "benign", "attack")
            )
            row = references[actor.name]
            assert row["reference_intent"]["dns_verified"] is None
            if row["reference_intent"]["maliciousness"] == "benign":
                benign.add(actor.ua)
            if row["reference_intent"]["maliciousness"] == "hostile_fixture":
                hostile.add(actor.ua)
            if row["profile"] == "browserlike_unknown":
                browser_mimics += 1
                assert "Mozilla" in actor.ua
            if row["profile"] == "legitimate_monitor" and actor.ua.startswith("curl/"):
                monitor_curl += 1
        shared_role_ua += bool(benign & hostile)
        nat_examples += any(n > 1 for n in Counter(actor.ip for actor in episode.actors).values())
    assert browser_mimics and monitor_curl and shared_role_ua and nat_examples
    first = generate_episode(31, "identity-before")
    second = generate_episode(31, "identity-after")
    assert {(a.ip, a.ua) for a in first.actors}.isdisjoint((a.ip, a.ua) for a in second.actors)


def test_hard_negatives_and_unknown_authorization_remain_separate():
    found = {}
    for episode in episodes():
        by_id = {a.name: a for a in episode.actors}
        for metadata in episode.replay_manifest()["actors"]:
            profile = metadata["profile"]
            found.setdefault(profile, (by_id[metadata["id"]], metadata))
    assert {
        "quick_cached",
        "assetless_browser",
        "privacy_headers",
        "login_mistakes",
        "shared_nat",
        "legitimate_monitor",
        "scraping_unknown",
        "browserlike_unknown",
        "scanner",
        "login_coordinated",
        "login_dispersed",
    } <= found.keys()
    for profile in ("legitimate_monitor", "scraping_unknown", "browserlike_unknown"):
        assert found[profile][0].sim_class in {"legitimate_automation", "unknown_automation"}
        assert found[profile][1]["reference_intent"]["traffic_truth"] is None
    assert not any(step.path.startswith("/static/") for step in found["assetless_browser"][0].steps)
    assert any(step.method == "POST" for step in found["login_mistakes"][0].steps)


def test_current_signed_parser_strips_truth_and_provider_packet_has_no_identifiers():
    from bouncer.db.store import _serialize_session
    from bouncer.ingest.sample import parse_access_records
    from bouncer.ingest.simrun import IngestStats
    from bouncer.investigations import InvestigationStore
    from tools.sim.run import build_request

    episode = generate_episode(4, "parser-isolation")
    records = []
    for actor in episode.actors:
        for step in actor.steps:
            request = build_request(
                "http://simulation-gateway:8080", actor, step, episode.episode_id, "fixture-key"
            )
            headers = {key: [value] for key, value in request.header_items()}
            username = parse_qs(step.data or "").get("username", [None])[0]
            records.append(
                {
                    "ts": 1767225600 + step.at,
                    "request": {
                        "client_ip": actor.ip,
                        "remote_ip": actor.ip,
                        "method": step.method,
                        "uri": step.path,
                        "headers": headers,
                    },
                    "status": 401 if step.method == "POST" else 200,
                    "resp_headers": {"X-Login-User": [username]} if username else {},
                }
            )
    stats = IngestStats()
    sessions, labels = parse_access_records(records, secret="fixture-key", stats=stats)
    assert len(sessions) == len(labels) == len(episode.actors)
    assert not stats.conflicting_sessions and stats.unsigned_markers == 0
    assert all(
        not {"x-sim-run", "x-sim-sig"} & req.headers.keys() for s in sessions for req in s.requests
    )
    case = InvestigationStore("sqlite:///:memory:").create_from_legacy(
        json.loads(
            json.dumps({"synthetic": True, "sessions": [_serialize_session(s) for s in sessions]})
        )
    )
    public = json.dumps(case)
    assert all(
        actor.ip not in public and actor.ua not in public and actor.name not in public
        for actor in episode.actors
    )
    assert "reference_intent" not in public and "unknown_automation" not in public


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_actors": 5},
        {"max_actors": 25},
        {"max_requests": 5},
        {"max_requests": 241},
        {"max_duration_seconds": 0},
        {"max_duration_seconds": 121},
        {"base": "https://example.com"},
        {"base": "http://simulation-gateway:8080/path"},
    ],
)
def test_unsupported_bounds_and_targets_are_rejected(kwargs):
    with pytest.raises(ValueError):
        generate_episode(1, "invalid", **kwargs)


def test_user_agents_are_only_shared_realistic_pool_values_without_replay_tags():
    from tools.sim.dynamic import UA_POOL

    episode = generate_episode(491, "private-replay-identity-never-in-headers")
    assert all(actor.ua in UA_POOL for actor in episode.actors)
    for actor in episode.actors:
        for step in actor.steps:
            normal = json.dumps(step.headers)
            assert episode.episode_id not in normal and actor.name not in normal
            assert "reference_intent" not in normal and "profile" not in normal


@pytest.mark.parametrize("requests,duration", [(6, 0.1), (12, 1), (40, 10)])
def test_smaller_request_and_time_caps_remain_valid(requests, duration):
    episode = generate_episode(
        55, "small-cap", max_requests=requests, max_duration_seconds=duration
    )
    assert 6 <= len(episode.actors) <= requests
    assert sum(len(actor.steps) for actor in episode.actors) <= requests
    assert 0 < episode.duration_seconds <= duration
    assert (
        max(step.at for actor in episode.actors for step in actor.steps) < episode.duration_seconds
    )
