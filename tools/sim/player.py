"""Bounded actual HTTP playback for private, labelled synthetic episodes."""

from __future__ import annotations

import asyncio
import ipaddress
import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from tools.sim.run import Actor, build_request

MAX_ACTORS = 24
MAX_REQUESTS = 240
MAX_DURATION = 120
MAX_BODY_BYTES = 65_536
RESERVED_HEADERS = {
    "host",
    "authorization",
    "proxy-authorization",
    "x-sim-run",
    "x-sim-sig",
    "x-forwarded-for",
    "user-agent",
}


class EpisodePlan(Protocol):
    episode_id: str
    actors: tuple[Actor, ...]
    duration_seconds: float


@dataclass(frozen=True)
class PlaybackReport:
    episode_id: str
    planned_requests: int
    attempted_requests: int
    completed_requests: int
    status_counts: dict[str, int]
    network_errors: int
    dropped_requests: int
    elapsed_seconds: float
    stopped: bool
    deadline_reached: bool


def _target(base: str, allow_loopback: bool) -> str:
    url = urlsplit(base)
    if (
        url.scheme != "http"
        or url.username
        or url.password
        or url.path
        or url.query
        or url.fragment
        or url.hostname is None
    ):
        raise ValueError("Only the private simulation gateway is allowed")
    if url.hostname == "simulation-gateway" and url.port == 8080:
        return base
    if (
        allow_loopback
        and url.hostname in {"127.0.0.1", "::1"}
        and url.port is not None
        and 1024 < url.port < 65536
    ):
        return base
    raise ValueError("Only the private simulation gateway is allowed")


def _validate(episode: EpisodePlan) -> int:
    duration = episode.duration_seconds
    if (
        not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or not 0 < duration <= MAX_DURATION
        or len(episode.actors) > MAX_ACTORS
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", episode.episode_id)
    ):
        raise ValueError("Episode exceeds its identity, duration or actor bounds")
    pairs, names = set(), set()
    planned = 0
    for actor in episode.actors:
        ipaddress.ip_address(actor.ip)
        pair = actor.ip, actor.ua
        if (
            pair in pairs
            or actor.name in names
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", actor.name)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", actor.sim_class)
            or actor.campaign is not None
            and not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", actor.campaign)
            or not actor.ua
            or len(actor.ua) > 512
            or any(ord(char) < 32 or ord(char) > 126 for char in actor.ua)
        ):
            raise ValueError("Actor identity is invalid or would merge reference labels")
        pairs.add(pair)
        names.add(actor.name)
        previous = -1.0
        for step in actor.steps:
            if (
                not math.isfinite(step.at)
                or not previous <= step.at < duration
                or step.at < 0
                or step.method not in {"GET", "POST", "HEAD", "OPTIONS"}
                or not step.path.startswith("/")
                or step.path.startswith("//")
                or "\\" in step.path
                or any(ord(char) < 32 or ord(char) == 127 for char in step.path)
                or len(step.path) > 512
                or len(step.headers) > 24
                or step.data is not None
                and len(step.data.encode()) > 2048
            ):
                raise ValueError("Unsafe request or request outside the episode window")
            for key, value in step.headers.items():
                if (
                    key.lower() in RESERVED_HEADERS
                    or len(key) > 80
                    or len(value) > 512
                    or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key)
                    or any(ord(char) < 32 or ord(char) == 127 for char in value)
                ):
                    raise ValueError("Step cannot override identity or reference headers")
            previous = step.at
            planned += 1
    if planned > MAX_REQUESTS:
        raise ValueError("Episode exceeds request bounds")
    return planned


async def _wait(target: float, stop: threading.Event, deadline: float) -> bool:
    while time.monotonic() < min(target, deadline):
        if stop.is_set():
            return False
        await asyncio.sleep(min(0.05, min(target, deadline) - time.monotonic()))
    return not stop.is_set() and time.monotonic() < deadline


class _RateLimit:
    def __init__(self, rate: float, burst: int):
        self.rate, self.burst = rate, burst
        self.tokens = float(burst)
        self.updated = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self, stop: threading.Event, deadline: float) -> bool:
        while not stop.is_set() and time.monotonic() < deadline:
            async with self.lock:
                current = time.monotonic()
                self.tokens = min(self.burst, self.tokens + (current - self.updated) * self.rate)
                self.updated = current
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
                wait = (1 - self.tokens) / self.rate
            if not await _wait(time.monotonic() + wait, stop, deadline):
                return False
        return False


def play_episode(
    episode: EpisodePlan,
    secret: str,
    *,
    base="http://simulation-gateway:8080",
    stop: threading.Event | None = None,
    requests_per_second=4,
    burst=4,
    request_timeout=2,
    transport: httpx.AsyncBaseTransport | None = None,
    allow_loopback_for_tests=False,
) -> PlaybackReport:
    base = _target(base, allow_loopback_for_tests)
    planned = _validate(episode)
    if (
        not secret
        or not 0 < requests_per_second <= 8
        or not math.isfinite(requests_per_second)
        or type(burst) is not int
        or not 1 <= burst <= 8
        or not 0 < request_timeout <= 5
        or not math.isfinite(request_timeout)
    ):
        raise ValueError("Playback limits are invalid")
    return asyncio.run(
        _play(
            episode,
            secret,
            base,
            stop or threading.Event(),
            planned,
            requests_per_second,
            burst,
            request_timeout,
            transport,
        )
    )


async def _play(episode, secret, base, stop, planned, rate, burst, timeout, transport):
    started = time.monotonic()
    deadline = started + episode.duration_seconds
    attempted = completed = errors = 0
    statuses: dict[str, int] = {}
    limiter = _RateLimit(rate, burst)
    semaphore = asyncio.Semaphore(8)
    limits = httpx.Limits(max_connections=8, max_keepalive_connections=8)
    async with httpx.AsyncClient(
        transport=transport or httpx.AsyncHTTPTransport(retries=0, limits=limits),
        follow_redirects=False,
        trust_env=False,
        timeout=timeout,
    ) as client:

        async def actor_run(actor):
            nonlocal attempted, completed, errors
            next_allowed = started
            overloads = 0
            for step in actor.steps:
                if not await _wait(max(started + step.at, next_allowed), stop, deadline):
                    break
                async with semaphore:
                    if not await limiter.acquire(stop, deadline):
                        break
                    if stop.is_set() or time.monotonic() >= deadline:
                        break
                    request = build_request(base, actor, step, episode.episode_id, secret)
                    attempted += 1
                    try:
                        async with (
                            asyncio.timeout(min(timeout, deadline - time.monotonic())),
                            client.stream(
                                request.method,
                                request.full_url,
                                headers=dict(request.header_items()),
                                content=request.data,
                            ) as response,
                        ):
                            size = 0
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > MAX_BODY_BYTES:
                                    raise ValueError("Bounded simulation response exceeded limit")
                            code = response.status_code
                            retry_after = response.headers.get("Retry-After", "0")
                        completed += 1
                        statuses[str(code)] = statuses.get(str(code), 0) + 1
                    except (httpx.HTTPError, TimeoutError, ValueError):
                        errors += 1
                        next_allowed = time.monotonic() + 0.5
                        continue
                if code == 403:
                    break
                if code in {429, 503}:
                    overloads += 1
                    try:
                        retry = float(retry_after)
                        if not math.isfinite(retry):
                            retry = 0
                    except ValueError:
                        retry = 0
                    next_allowed = time.monotonic() + max(
                        min(5, 0.5 * 2 ** min(overloads - 1, 4)), retry
                    )
                else:
                    overloads = 0

        await asyncio.gather(*(actor_run(actor) for actor in episode.actors))
    elapsed = time.monotonic() - started
    return PlaybackReport(
        episode.episode_id,
        planned,
        attempted,
        completed,
        statuses,
        errors,
        planned - attempted,
        elapsed,
        stop.is_set(),
        attempted < planned and elapsed >= episode.duration_seconds - 0.005,
    )
