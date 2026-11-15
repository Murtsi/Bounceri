"""Pure stochastic private-traffic plans; no network, detector feedback or model calls.

Reference profiles live only in Actor.sim_class (signed by the player) and the
private replay manifest. Procedural variety is not independent real-world evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlencode, urlsplit

from tools.sim.run import ASSETS, CHROME_UA, VULN_PATHS, Actor, Step

PRIVATE_BASE = "http://simulation-gateway:8080"
BROWSER_UAS = (
    CHROME_UA,
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
    "Version/18.1 Safari/605.1.15",
    CHROME_UA + " Edg/131.0.0.0",
)
UA_POOL = (*BROWSER_UAS, "curl/8.5.0", "python-requests/2.32.3")
HUMAN_PROFILES = frozenset(
    {
        "browse",
        "quick_cached",
        "assetless_browser",
        "privacy_headers",
        "login_mistakes",
        "shared_nat",
    }
)
HOSTILE_PROFILES = frozenset({"scanner", "login_coordinated", "login_dispersed"})
BENIGN_POOL = (
    "browse",
    "quick_cached",
    "assetless_browser",
    "privacy_headers",
    "login_mistakes",
    "legitimate_monitor",
)


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _intent(profile: str) -> dict:
    if profile in HUMAN_PROFILES:
        return {
            "automation": "human_like",
            "maliciousness": "benign",
            "traffic_truth": "human",
            "dns_verified": None,
        }
    if profile == "legitimate_monitor":
        return {
            "automation": "automated",
            "maliciousness": "benign",
            "traffic_truth": None,
            "dns_verified": None,
        }
    if profile in HOSTILE_PROFILES:
        return {
            "automation": "automated",
            "maliciousness": "hostile_fixture",
            "traffic_truth": "bad_bot",
            "dns_verified": None,
        }
    return {
        "automation": "automated" if profile != "unspecified" else "unknown",
        "maliciousness": "unknown",
        "traffic_truth": None,
        "dns_verified": None,
    }


@dataclass(frozen=True)
class Episode:
    episode_id: str
    seed: int
    actors: tuple[Actor, ...]
    duration_seconds: float
    generator_version: str = "dynamic-v1"
    mix: str = "mixed"
    actor_profiles: tuple[tuple[str, str], ...] = ()
    generation_config: tuple[tuple[str, object], ...] = field(default_factory=tuple)

    def replay_manifest(self) -> dict:
        """Private plan receipt. Never serve this reference-intent sidecar publicly."""
        profiles = dict(self.actor_profiles)
        plans = [asdict(actor) for actor in self.actors]
        config = dict(self.generation_config)
        structural = []
        for actor in self.actors:
            structural.append(
                _digest(
                    [
                        (
                            round(step.at, 3),
                            step.method,
                            step.path,
                            sorted(step.headers),
                            step.data is not None,
                        )
                        for step in actor.steps
                    ]
                )
            )
        return {
            "episode_id": self.episode_id,
            "seed": self.seed,
            "generator_version": self.generator_version,
            "config": config,
            "mix": self.mix,
            "duration_seconds": self.duration_seconds,
            "synthetic": True,
            "n_actors": len(self.actors),
            "n_requests": sum(len(a.steps) for a in self.actors),
            "plan_fingerprint": _digest(
                {
                    "id": self.episode_id,
                    "seed": self.seed,
                    "version": self.generator_version,
                    "config": config,
                    "actors": plans,
                }
            ),
            "behavior_fingerprint": _digest(sorted(structural)),
            "actors": [
                {
                    "id": a.name,
                    "ip": a.ip,
                    "ua": a.ua,
                    "profile": profiles.get(a.name, "unspecified"),
                    "reference_intent": _intent(profiles.get(a.name, "unspecified")),
                    "sim_class": a.sim_class,
                    "campaign": a.campaign,
                    "n_requests": len(a.steps),
                }
                for a in self.actors
            ],
            "limitations": [
                "Generated reference intent is not verified human identity.",
                "Varied known behaviors do not establish novel-attack accuracy.",
                "Mock login POSTs always fail; no login success is fabricated.",
            ],
        }


def _profiles(rng: random.Random, n: int, mix: str) -> list[str]:
    if mix == "benign_only":
        hostile = unknown = 0
    elif mix == "attack_heavy":
        hostile = rng.randint(math.ceil(n * 0.55), min(n - 1, math.ceil(n * 0.85)))
        unknown = rng.randint(0, n - hostile - 1)
    else:
        hostile = rng.randint(1, max(1, n // 2))
        unknown = rng.randint(1, max(1, min(n - hostile - 1, n // 3)))
    benign = n - hostile - unknown
    profiles = [rng.choice(BENIGN_POOL) for _ in range(benign)]
    if benign >= 2 and rng.random() < 0.45:
        for index in rng.sample(range(benign), rng.randint(2, min(4, benign))):
            profiles[index] = "shared_nat"
    coordinated = rng.randint(3, hostile) if hostile >= 3 and rng.random() < 0.65 else 0
    profiles += ["login_coordinated"] * coordinated
    profiles += [rng.choice(("scanner", "login_dispersed")) for _ in range(hostile - coordinated)]
    profiles += [rng.choice(("scraping_unknown", "browserlike_unknown")) for _ in range(unknown)]
    rng.shuffle(profiles)
    return profiles


def _page_headers(rng, base, previous, privacy=False):
    headers = {
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": rng.choice(("en-US,en;q=.9", "fi-FI,fi;q=.9", "en-GB,en;q=.8")),
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if previous else "none",
        "Sec-Fetch-Dest": "document",
        "Sec-CH-UA": '"Chromium";v="131"',
    }
    if previous:
        headers["Referer"] = base + previous
    if privacy:
        headers = {key: value for key, value in headers.items() if key in {"Accept", "Referer"}}
    return headers


def _next_page(rng, previous):
    if previous.startswith("/products/"):
        return rng.choice(("/products", "/about", "/", f"/products/{rng.randint(1, 12)}"))
    if previous.startswith("/products"):
        return rng.choice(
            (
                f"/products/{rng.randint(1, 12)}",
                f"/products?page={rng.randint(1, 8)}",
                "/about",
                "/",
            )
        )
    return rng.choice(
        ("/", "/products", "/about", f"/products/{rng.randint(1, 12)}", "/robots.txt")
    )


def _human_journey(rng, quota, profile, base):
    steps = []
    at = rng.uniform(0, 8)
    previous = ""
    cached = profile in {"quick_cached", "assetless_browser"} or rng.random() < 0.35
    privacy = profile == "privacy_headers" or rng.random() < 0.12
    rapid = profile in {"quick_cached", "assetless_browser", "browserlike_unknown"}
    if profile == "login_mistakes" and quota >= 3:
        steps.append(Step(at, "GET", "/login", _page_headers(rng, base, "", privacy)))
        username = "u-" + f"{rng.getrandbits(40):010x}"
        for _ in range(min(rng.randint(2, 3), quota - 1)):
            at += rng.uniform(0.6, 5)
            headers = _page_headers(rng, base, "/login", privacy)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            steps.append(
                Step(
                    at,
                    "POST",
                    "/login",
                    headers,
                    urlencode(
                        {"username": username, "password": "demo-" + f"{rng.getrandbits(32):08x}"}
                    ),
                )
            )
        previous = "/login"
    while len(steps) < quota:
        path = _next_page(rng, previous)
        headers = _page_headers(rng, base, previous, privacy)
        steps.append(Step(at, "GET", path, headers))
        if not cached and rng.random() < 0.65 and len(steps) < quota:
            assets = rng.sample(ASSETS, rng.randint(1, len(ASSETS)))
            for asset, dest in assets[: quota - len(steps)]:
                at += rng.uniform(0.025, 0.16)
                steps.append(
                    Step(
                        at,
                        "GET",
                        asset,
                        {
                            "Accept": "*/*",
                            "Sec-Fetch-Mode": "no-cors",
                            "Sec-Fetch-Dest": dest,
                            "Referer": base + path,
                        },
                    )
                )
        at += rng.uniform(0.03, 0.45) if rapid else rng.uniform(0.8, 8)
        if rng.random() < 0.13:
            at += rng.uniform(3, 10)
        previous = path
    return steps


def _automated_journey(rng, quota, profile, base, campaign_user):
    if profile == "browserlike_unknown":
        return _human_journey(rng, quota, profile, base)
    steps = []
    at = rng.uniform(0, 10)
    probes = rng.sample(
        (*VULN_PATHS, "/admin/config", "/server-status", "/config.json"), rng.randint(2, 9)
    )
    order = rng.sample(range(1, 13), 12)
    for index in range(quota):
        headers = {"Accept": rng.choice(("*/*", "text/html", "application/json"))}
        method = "GET"
        data = None
        if profile == "legitimate_monitor":
            path = rng.choice(("/", "/products", "/robots.txt", "/about", "/static/app.css"))
            method = rng.choice(("GET", "GET", "HEAD"))
            gap = rng.uniform(1, 12)
        elif profile == "scanner":
            path = rng.choice(probes)
            gap = rng.uniform(0.03, 0.5) if rng.random() < 0.8 else rng.uniform(1, 5)
        elif profile in {"login_coordinated", "login_dispersed"}:
            path = "/login"
            method = "POST"
            username = (
                campaign_user
                if profile == "login_coordinated"
                else "u-" + f"{rng.getrandbits(40):010x}"
            )
            data = urlencode(
                {"username": username, "password": "demo-" + f"{rng.getrandbits(32):08x}"}
            )
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            gap = rng.uniform(0.2, 2) if profile == "login_coordinated" else rng.uniform(1, 9)
            if profile == "login_coordinated" and index == 0:
                at = rng.uniform(0.5, 2)
        else:
            path = (
                f"/products/{order[index % len(order)]}"
                if rng.random() < 0.8
                else f"/products?page={rng.randint(1, 12)}&view=compact"
            )
            gap = rng.uniform(0.04, 0.65)
            if rng.random() < 0.15:
                gap += rng.uniform(1, 4)
        steps.append(Step(at, method, path, headers, data))
        at += gap
    return steps


def generate_episode(
    seed: int,
    episode_id: str,
    *,
    base=PRIVATE_BASE,
    max_actors=24,
    max_requests=240,
    max_duration_seconds=120,
) -> Episode:
    """Compose one deterministic bounded plan, without issuing any request."""
    if (
        type(seed) is not int
        or not isinstance(episode_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", episode_id)
    ):
        raise ValueError("integer seed and safe episode ID are required")
    if type(max_actors) is not int or not 6 <= max_actors <= 24:
        raise ValueError("max_actors must be in 6..24")
    if type(max_requests) is not int or not 6 <= max_requests <= 240:
        raise ValueError("max_requests must be in 6..240")
    if (
        type(max_duration_seconds) not in (int, float)
        or not math.isfinite(max_duration_seconds)
        or not 0 < max_duration_seconds <= 120
    ):
        raise ValueError("max_duration_seconds must be finite and in (0,120]")
    target = urlsplit(base)
    if base != PRIVATE_BASE or target.username or target.password:
        raise ValueError("only the private simulation gateway is a supported base")
    rng = random.Random(f"behavior:{seed}:{episode_id}:dynamic-v1")
    identity_rng = random.Random(f"identities:{seed}:{episode_id}:dynamic-v1")
    n = rng.randint(6, min(max_actors, max_requests))
    mix = rng.choices(("benign_only", "mixed", "attack_heavy"), weights=(0.22, 0.53, 0.25))[0]
    profiles = _profiles(rng, n, mix)
    minimum = [3 if p == "login_mistakes" else 2 for p in profiles]
    floor = min(max_requests, max(40, sum(minimum)))
    budget = (
        rng.randint(floor, max_requests) if max_requests >= 40 else rng.randint(n, max_requests)
    )
    quotas = [1] * n
    remaining = budget - n
    for index, wanted in enumerate(minimum):
        add = min(remaining, wanted - 1)
        quotas[index] += add
        remaining -= add
    weights = [rng.lognormvariate(0, 0.7) for _ in profiles]
    for _ in range(remaining):
        quotas[rng.choices(range(n), weights=weights)[0]] += 1
    # Benchmark addresses are sampled without role-specific ranges; UAs stay realistic.
    addresses = identity_rng.sample(range(1, 2**17 - 1), n)
    nat = [i for i, p in enumerate(profiles) if p == "shared_nat"]
    if nat:
        for index in nat:
            addresses[index] = addresses[nat[0]]
    ua_used = {}
    actors = []
    references = []
    campaign = "c-" + _digest((seed, episode_id, "cohort"))[:16]
    campaign_user = "u-" + _digest((seed, episode_id, "account"))[:12]
    for index, (profile, quota) in enumerate(zip(profiles, quotas, strict=True)):
        number = (198 << 24) + (18 << 16) + addresses[index]
        ip = ".".join(str((number >> shift) & 255) for shift in (24, 16, 8, 0))
        pool = (
            BROWSER_UAS
            if profile in HUMAN_PROFILES or profile == "browserlike_unknown"
            else UA_POOL
        )
        choices = [ua for ua in pool if ua not in ua_used.setdefault(ip, set())]
        ua = identity_rng.choice(choices)
        if (
            profile == "legitimate_monitor"
            and identity_rng.random() < 0.5
            and "curl/8.5.0" in choices
        ):
            ua = "curl/8.5.0"
        ua_used[ip].add(ua)
        name = "a-" + _digest((seed, episode_id, index))[:16]
        sim_class = (
            "human"
            if profile in HUMAN_PROFILES
            else "scanner"
            if profile == "scanner"
            else "brute_force"
            if profile.startswith("login_")
            else "legitimate_automation"
            if profile == "legitimate_monitor"
            else "unknown_automation"
        )
        steps = (
            _human_journey(rng, quota, profile, base)
            if profile in HUMAN_PROFILES
            else _automated_journey(rng, quota, profile, base, campaign_user)
        )
        actors.append(
            Actor(
                name, ip, ua, sim_class, campaign if profile == "login_coordinated" else None, steps
            )
        )
        references.append((name, profile))
    raw_end = max(step.at for actor in actors for step in actor.steps)
    margin = min(2.0, max_duration_seconds * 0.1)
    desired = max(raw_end, budget * rng.uniform(0.18, 0.35))
    latest = min(max_duration_seconds - margin, desired)
    scale = latest / raw_end if raw_end else 1.0
    for actor in actors:
        actor.steps = [
            Step(step.at * scale, step.method, step.path, step.headers, step.data)
            for step in actor.steps
        ]
    duration = min(max_duration_seconds, max(s.at for a in actors for s in a.steps) + margin)
    config = (
        ("base", base),
        ("max_actors", max_actors),
        ("max_requests", max_requests),
        ("max_duration_seconds", max_duration_seconds),
    )
    return Episode(
        episode_id,
        seed,
        tuple(actors),
        duration,
        mix=mix,
        actor_profiles=tuple(references),
        generation_config=config,
    )
