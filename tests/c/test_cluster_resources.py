"""Behavior clustering retains its graph while reusing repeated path evidence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import combinations
from random import Random
from unittest.mock import patch

import pytest

from bouncer.network import cluster
from bouncer.network.session_view import SessionView
from bouncer.network.types import make_campaign

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _session(index, *, paths=("/a", "/b", "/c"), header="bot", start=0, end=1):
    return SessionView(
        id=str(index),
        ip=f"203.0.113.{index % 250}",
        ua="bot",
        started_at=None if start is None else NOW + timedelta(minutes=start),
        ended_at=None if end is None else NOW + timedelta(minutes=end),
        paths=paths,
        header_fingerprint=header,
        logins=(),
        raw=None,
    )


def _reference(sessions, cfg):
    """Original pairwise edge rules, with independent graph traversal/output order."""
    edges = {i: set() for i in range(len(sessions))}
    shingles = [cluster._shingles(s.paths, cfg.shingle_size) for s in sessions]
    signatures = [cluster.minhash_signature(sh, cfg.minhash_perms) for sh in shingles]
    for i, j in combinations(range(len(sessions)), 2):
        if cfg.require_same_header_fp and (
            not sessions[i].header_fingerprint
            or sessions[i].header_fingerprint != sessions[j].header_fingerprint
        ):
            continue
        if not cluster._overlap(sessions[i], sessions[j], cfg.max_time_gap):
            continue
        if cluster.minhash_approx_jaccard(signatures[i], signatures[j]) < (
            cfg.path_jaccard_min * 0.5
        ):
            continue
        if cluster.jaccard(shingles[i], shingles[j]) >= cfg.path_jaccard_min:
            edges[i].add(j)
            edges[j].add(i)
    unseen = set(edges)
    result = []
    while unseen:
        stack = [min(unseen)]
        members = set()
        while stack:
            current = stack.pop()
            if current in members:
                continue
            members.add(current)
            stack.extend(edges[current] - members)
        unseen -= members
        ordered = [sessions[i] for i in sorted(members)]
        ips = {s.ip for s in ordered}
        if len(ordered) < cfg.min_sessions or len(ips) < 2:
            continue
        result.append(
            make_campaign(
                id=f"behavior:{ordered[0].id}-{len(ordered)}",
                kind="behavior_cluster",
                session_ids=sorted(s.id for s in ordered),
                reasons=[
                    f"{len(ordered)} sessions, {len(ips)} IPs, same header fingerprint",
                    f"path Jaccard ≥ {cfg.path_jaccard_min}",
                    f"sample paths: {' → '.join(ordered[0].paths[:5]) or '(none)'}",
                ],
            )
        )
    return result


def test_repeated_path_evidence_is_compared_once():
    sessions = [_session(i) for i in range(600)]
    with (
        patch.object(cluster, "minhash_signature", wraps=cluster.minhash_signature) as signature,
        patch.object(
            cluster, "minhash_approx_jaccard", wraps=cluster.minhash_approx_jaccard
        ) as approx,
        patch.object(cluster, "jaccard", wraps=cluster.jaccard) as exact,
    ):
        campaigns = cluster.find_behavior_campaigns(sessions)
    assert len(campaigns) == 1
    assert len(campaigns[0].session_ids) == len(sessions)
    assert signature.call_count == 1
    assert approx.call_count == 1
    assert exact.call_count == 1


def test_disjoint_times_keep_the_cheap_precheck_before_path_comparison():
    sessions = [_session(i, paths=(f"/{i}",), start=i * 100, end=i * 100) for i in range(40)]
    with patch.object(
        cluster, "minhash_approx_jaccard", wraps=cluster.minhash_approx_jaccard
    ) as approx:
        assert cluster.find_behavior_campaigns(sessions) == []
    assert approx.call_count == 0


def test_pair_order_is_preserved_for_reversed_imported_time_spans():
    sessions = [
        _session(0, paths=("/a",), start=100, end=100),
        _session(1, paths=("/b",), start=10, end=0),
        _session(2, paths=("/a",), start=9, end=8),
    ]
    cfg = cluster.ClusterConfig(
        path_jaccard_min=0, max_time_gap=timedelta(minutes=2), min_sessions=2
    )
    assert cluster.find_behavior_campaigns(sessions, cfg) == _reference(sessions, cfg)


@pytest.mark.parametrize("seed", range(20))
def test_grouping_matches_original_pair_graph_with_partial_and_missing_times(seed):
    rng = Random(seed)
    paths = [(), ("/a",), ("/a", "/b", "/c"), ("/a", "/b", "/d"), ("/x", "/y")]
    sessions = []
    for i in range(35):
        start = rng.choice([None, 0, 1, 4, 8, 40, 100])
        end = None if rng.random() < 0.3 else (start or 0) + rng.choice([0, 1, 10])
        sessions.append(
            _session(
                i, paths=rng.choice(paths), header=rng.choice(["", "a", "b"]), start=start, end=end
            )
        )
    for cfg in (
        cluster.ClusterConfig(),
        cluster.ClusterConfig(require_same_header_fp=False),
        cluster.ClusterConfig(max_time_gap=timedelta(minutes=2), min_sessions=2),
        cluster.ClusterConfig(path_jaccard_min=0, minhash_perms=0, shingle_size=1),
        cluster.ClusterConfig(path_jaccard_min=1, minhash_perms=1),
        cluster.ClusterConfig(path_jaccard_min=1.1),
        cluster.ClusterConfig(max_time_gap=timedelta(minutes=-1), min_sessions=1),
    ):
        assert cluster.find_behavior_campaigns(sessions, cfg) == _reference(sessions, cfg)


def test_repeated_paths_preserve_time_chains_unknown_bridges_and_nat_filter():
    sessions = [
        _session(0, start=10, end=11),
        _session(1, start=0, end=1),
        _session(2, start=5, end=6),
        _session(3, start=100, end=101),
    ]
    cfg = cluster.ClusterConfig(max_time_gap=timedelta(minutes=4))
    campaigns = cluster.find_behavior_campaigns(sessions, cfg)
    assert campaigns[0].session_ids == ("0", "1", "2")
    assert campaigns == _reference(sessions, cfg)
    sessions.append(_session(4, start=None, end=None))
    assert len(cluster.find_behavior_campaigns(sessions, cfg)[0].session_ids) == 5
    assert cluster.find_behavior_campaigns(sessions, cfg) == _reference(sessions, cfg)
    assert cluster.find_behavior_campaigns([replace(s, ip="203.0.113.1") for s in sessions]) == []
