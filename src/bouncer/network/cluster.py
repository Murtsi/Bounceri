"""C-5: kampanjaklusterointi — header FP + polkujärjestys + ajoitus.

Käyttää Jaccard/MinHash-polkusimilaarisuutta ja union-findiä.
DBSCAN jätetään tarvittaessa myöhemmäksi (jos aikaa).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha1

from bouncer.network.session_view import SessionView
from bouncer.network.types import Campaign


@dataclass(frozen=True, slots=True)
class ClusterConfig:
    path_jaccard_min: float = 0.5
    require_same_header_fp: bool = True
    max_time_gap: timedelta = timedelta(minutes=30)
    min_sessions: int = 3
    shingle_size: int = 2
    minhash_perms: int = 32


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def _shingles(paths: tuple[str, ...], size: int) -> set[str]:
    if not paths:
        return set()
    if len(paths) < size:
        return {"|".join(paths)}
    return {"|".join(paths[i : i + size]) for i in range(len(paths) - size + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def minhash_signature(shingles: set[str], perms: int = 32) -> tuple[int, ...]:
    """Yksinkertainen MinHash sha1-pohjaisilla hash-funktioilla."""
    if not shingles:
        return tuple(0 for _ in range(perms))
    sig: list[int] = []
    for seed in range(perms):
        best = min(
            int(sha1(f"{seed}:{s}".encode()).hexdigest(), 16) for s in shingles
        )
        sig.append(best)
    return tuple(sig)


def minhash_approx_jaccard(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    equal = sum(1 for x, y in zip(sig_a, sig_b, strict=True) if x == y)
    return equal / len(sig_a)


def _overlap(a: SessionView, b: SessionView, max_gap: timedelta) -> bool:
    def span(s: SessionView) -> tuple[datetime, datetime] | None:
        if s.started_at and s.ended_at:
            return s.started_at, s.ended_at
        if s.started_at:
            return s.started_at, s.started_at
        if s.ended_at:
            return s.ended_at, s.ended_at
        return None

    sa, sb = span(a), span(b)
    if sa is None or sb is None:
        return True  # unknown times → don't block clustering
    (a0, a1), (b0, b1) = sa, sb
    if a1 < b0:
        return (b0 - a1) <= max_gap
    if b1 < a0:
        return (a0 - b1) <= max_gap
    return True  # intervals overlap


def find_behavior_campaigns(
    sessions: list[SessionView],
    cfg: ClusterConfig | None = None,
) -> list[Campaign]:
    cfg = cfg or ClusterConfig()
    if len(sessions) < cfg.min_sessions:
        return []

    shingles = [_shingles(s.paths, cfg.shingle_size) for s in sessions]
    signatures = [minhash_signature(sh, cfg.minhash_perms) for sh in shingles]
    uf = UnionFind(len(sessions))

    for i in range(len(sessions)):
        for j in range(i + 1, len(sessions)):
            if cfg.require_same_header_fp:
                if sessions[i].header_fingerprint != sessions[j].header_fingerprint:
                    continue
                if not sessions[i].header_fingerprint:
                    continue
            if not _overlap(sessions[i], sessions[j], cfg.max_time_gap):
                continue
            # Exact Jaccard on shingles; MinHash as cheap pre-check
            approx = minhash_approx_jaccard(signatures[i], signatures[j])
            if approx < cfg.path_jaccard_min * 0.5:
                continue
            sim = jaccard(shingles[i], shingles[j])
            if sim >= cfg.path_jaccard_min:
                uf.union(i, j)

    groups: dict[int, list[int]] = {}
    for idx in range(len(sessions)):
        root = uf.find(idx)
        groups.setdefault(root, []).append(idx)

    campaigns: list[Campaign] = []
    for members in groups.values():
        if len(members) < cfg.min_sessions:
            continue
        # Skip groups that are only credential-stuffing logins with no paths —
        # stuffing detector owns those. Still allow if paths exist.
        member_sessions = [sessions[i] for i in members]
        ips = {s.ip for s in member_sessions}
        if len(ips) < 2:
            continue
        path_preview = list(member_sessions[0].paths[:5])
        campaigns.append(
            Campaign(
                id=f"behavior:{member_sessions[0].id}-{len(members)}",
                kind="behavior_cluster",
                session_ids=sorted(s.id for s in member_sessions),
                reasons=[
                    f"{len(members)} sessions, {len(ips)} IPs, same header fingerprint",
                    f"path Jaccard ≥ {cfg.path_jaccard_min}",
                    f"sample paths: {' → '.join(path_preview) or '(none)'}",
                ],
            )
        )
    return campaigns
