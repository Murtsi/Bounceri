import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from bouncer.ingest.simrun import verify
from tools.sim.player import play_episode
from tools.sim.run import Actor, Step


@dataclass
class Plan:
    actors: tuple
    duration_seconds: float = 5
    episode_id: str = "test-episode"


def actor(count=1, **kwargs):
    return Actor(
        "opaque",
        "198.18.0.1",
        "test-client",
        "human",
        steps=[Step(0, "GET", "/products") for _ in range(count)],
        **kwargs,
    )


def test_only_private_target_and_safe_relative_paths_can_receive_signed_requests():
    sent = []
    transport = httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(200))
    for base in (
        "https://example.com",
        "http://user@simulation-gateway:8080",
        "http://simulation-gateway:8080/path",
        "http://127.0.0.1:1234",
    ):
        with pytest.raises(ValueError):
            play_episode(Plan((actor(),)), "secret", base=base, transport=transport)
    for path in ("//example.com/collect", "https://example.com", "/bad\r\npath", "/bad\x7fpath"):
        bad = actor()
        bad.steps = [Step(0, "GET", path)]
        with pytest.raises(ValueError):
            play_episode(Plan((bad,)), "secret", transport=transport)
    assert sent == []


def test_real_http_requests_have_global_pacing_and_valid_signatures():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((time.monotonic(), dict(self.headers)))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = play_episode(
            Plan((actor(6),)),
            "secret",
            base=f"http://127.0.0.1:{server.server_port}",
            allow_loopback_for_tests=True,
            requests_per_second=4,
            burst=2,
        )
        assert result.attempted_requests == result.completed_requests == len(received) == 6
        assert result.network_errors == 0 and result.status_counts == {"200": 6}
        assert received[-1][0] - received[0][0] >= 0.85
        for _, headers in received:
            lowered = {k.lower(): v for k, v in headers.items()}
            assert verify(lowered["x-sim-run"], lowered["x-sim-sig"], "secret")
    finally:
        server.shutdown()
        server.server_close()


def test_stop_and_episode_deadline_prevent_further_dispatch():
    stop = threading.Event()
    stop.set()
    sent = []
    transport = httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(200))
    result = play_episode(Plan((actor(3),)), "secret", stop=stop, transport=transport)
    assert result.stopped and result.attempted_requests == 0 and sent == []

    async def stalled(_):
        import asyncio

        await asyncio.sleep(2)
        return httpx.Response(200)

    started = time.monotonic()
    result = play_episode(
        Plan((actor(3),), duration_seconds=0.15),
        "secret",
        transport=httpx.MockTransport(stalled),
        request_timeout=2,
    )
    assert time.monotonic() - started < 0.6
    assert result.attempted_requests == 1 and result.dropped_requests == 2
    assert result.deadline_reached and result.network_errors == 1


def test_redirects_are_not_followed_and_overload_slows_future_steps():
    requests = []

    def redirect(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://example.org/collect"})

    result = play_episode(Plan((actor(),)), "secret", transport=httpx.MockTransport(redirect))
    assert len(requests) == 1 and result.status_counts == {"302": 1}

    times = []

    def overloaded(_):
        times.append(time.monotonic())
        return httpx.Response(429 if len(times) == 1 else 200)

    result = play_episode(Plan((actor(2),)), "secret", transport=httpx.MockTransport(overloaded))
    assert times[1] - times[0] >= 0.45
    assert result.status_counts == {"429": 1, "200": 1}


def test_reference_headers_and_session_collisions_are_rejected_before_dispatch():
    sent = []
    transport = httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(200))
    forged = actor()
    forged.steps = [Step(0, "GET", "/", {"X-Sim-Run": "forged:human"})]
    for plan in (Plan((forged,)), Plan((actor(), actor())), Plan((actor(241),))):
        with pytest.raises(ValueError):
            play_episode(plan, "secret", transport=transport)
    assert sent == []


def test_overload_cooldown_starts_after_the_response_not_the_planned_request_time():
    import asyncio

    times = []
    finished = []

    async def overloaded(_):
        times.append(time.monotonic())
        if len(times) == 1:
            await asyncio.sleep(0.65)
            finished.append(time.monotonic())
            return httpx.Response(429, headers={"Retry-After": "0.5"})
        return httpx.Response(200)

    result = play_episode(Plan((actor(2),)), "secret", transport=httpx.MockTransport(overloaded))
    assert result.completed_requests == 2
    assert times[1] - finished[0] >= 0.45


def test_explicit_retry_after_is_honored_even_when_it_exceeds_local_backoff(monkeypatch):
    from tools.sim import player

    requested_waits = []

    async def observe_wait(target, stop, deadline):
        delay = target - time.monotonic()
        if delay > 0.1:
            requested_waits.append(delay)
            return False  # Observe scheduling without sleeping for twenty seconds.
        return True

    monkeypatch.setattr(player, "_wait", observe_wait)
    result = play_episode(
        Plan((actor(2),), duration_seconds=30),
        "secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"Retry-After": "20"})
        ),
    )
    assert result.attempted_requests == 1
    assert requested_waits[0] >= 19.9
