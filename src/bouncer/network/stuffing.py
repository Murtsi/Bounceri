"""C-3: tunnusten kokeilu sessioiden yli.

Signaalit:
1. Sama käyttäjätunnus ≥ N eri IP:stä aikaikkunassa (classic stuffing)
2. Hajautetut epäonnistuneet kirjautumiset: monta IP:tä, vähän yrityksiä/IP
3. Hidas tahti: pitkä aikaikkuna, matala rate (low-and-slow)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from bouncer.network.session_view import LoginEvent, SessionView
from bouncer.network.types import Campaign, make_campaign


@dataclass(frozen=True, slots=True)
class StuffingConfig:
    window: timedelta = timedelta(minutes=30)
    min_ips_per_username: int = 3
    min_failed_for_username: int = 3
    spray_min_ips: int = 5
    spray_max_attempts_per_ip: int = 3
    slow_window: timedelta = timedelta(hours=6)
    slow_min_ips: int = 4
    slow_max_rate_per_hour: float = 2.0


def _failed(events: list[LoginEvent]) -> list[LoginEvent]:
    return [e for e in events if not e.success]


def _campaign_id(kind: str, key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in key.lower()).strip("-")[:48]
    return f"{kind}:{safe or 'unknown'}"


def detect_username_stuffing(
    sessions: list[SessionView],
    cfg: StuffingConfig | None = None,
) -> list[Campaign]:
    cfg = cfg or StuffingConfig()
    by_user: dict[str, list[LoginEvent]] = defaultdict(list)
    for session in sessions:
        for login in session.logins:
            if not login.success:
                by_user[login.username].append(login)

    campaigns: list[Campaign] = []
    for username, events in by_user.items():
        if len(events) < cfg.min_failed_for_username:
            continue
        events = sorted(events, key=lambda e: e.ts)
        # Sliding window by time
        left = 0
        best_ips: set[str] = set()
        best_sessions: set[str] = set()
        best_span = (events[0].ts, events[0].ts)
        for right, _event in enumerate(events):
            while events[right].ts - events[left].ts > cfg.window:
                left += 1
            window_events = events[left : right + 1]
            ips = {e.ip for e in window_events}
            if len(ips) >= cfg.min_ips_per_username and len(ips) >= len(best_ips):
                best_ips = ips
                best_sessions = {e.session_id for e in window_events}
                best_span = (window_events[0].ts, window_events[-1].ts)

        if len(best_ips) < cfg.min_ips_per_username:
            continue

        span_min = max((best_span[1] - best_span[0]).total_seconds() / 60.0, 0.01)
        campaigns.append(
            make_campaign(
                id=_campaign_id("stuffing", username),
                kind="credential_stuffing",
                session_ids=sorted(best_sessions),
                reasons=[
                    f"username '{username}' failed from {len(best_ips)} IPs",
                    f"window {span_min:.1f} min",
                    f"{len(best_sessions)} sessions involved",
                ],
            )
        )
    return campaigns


def detect_distributed_spray(
    sessions: list[SessionView],
    cfg: StuffingConfig | None = None,
) -> list[Campaign]:
    """Monta IP:tä, vähän epäonnistumisia per IP → password spray / distributed."""
    cfg = cfg or StuffingConfig()
    failed: list[LoginEvent] = []
    for session in sessions:
        failed.extend(_failed(list(session.logins)))
    if not failed:
        return []

    failed = sorted(failed, key=lambda e: e.ts)
    left = 0
    campaigns: list[Campaign] = []
    seen: set[tuple[str, ...]] = set()

    for right in range(len(failed)):
        while failed[right].ts - failed[left].ts > cfg.window:
            left += 1
        window = failed[left : right + 1]
        per_ip: dict[str, int] = defaultdict(int)
        for event in window:
            per_ip[event.ip] += 1
        if len(per_ip) < cfg.spray_min_ips:
            continue
        if any(count > cfg.spray_max_attempts_per_ip for count in per_ip.values()):
            continue
        session_ids = tuple(sorted({e.session_id for e in window}))
        if session_ids in seen:
            continue
        seen.add(session_ids)
        users = sorted({e.username for e in window})
        campaigns.append(
            make_campaign(
                id=_campaign_id("spray", f"{len(per_ip)}ips-{session_ids[0]}"),
                kind="distributed_login_spray",
                session_ids=session_ids,
                reasons=[
                    f"{len(per_ip)} IPs with ≤{cfg.spray_max_attempts_per_ip} failures each",
                    f"{len(users)} usernames targeted",
                    f"{len(window)} failed POSTs /login in window",
                ],
            )
        )
    return campaigns


def detect_slow_stuffing(
    sessions: list[SessionView],
    cfg: StuffingConfig | None = None,
) -> list[Campaign]:
    cfg = cfg or StuffingConfig()
    by_user: dict[str, list[LoginEvent]] = defaultdict(list)
    for session in sessions:
        for login in _failed(list(session.logins)):
            by_user[login.username].append(login)

    campaigns: list[Campaign] = []
    for username, events in by_user.items():
        if len(events) < cfg.slow_min_ips:
            continue
        events = sorted(events, key=lambda e: e.ts)
        span = events[-1].ts - events[0].ts
        if span < timedelta(minutes=30):
            continue
        if span > cfg.slow_window * 2:
            # still ok — long campaigns allowed
            pass
        hours = max(span.total_seconds() / 3600.0, 0.01)
        rate = len(events) / hours
        ips = {e.ip for e in events}
        if len(ips) < cfg.slow_min_ips:
            continue
        if rate > cfg.slow_max_rate_per_hour:
            continue
        campaigns.append(
            make_campaign(
                id=_campaign_id("slow-stuffing", username),
                kind="slow_credential_stuffing",
                session_ids=sorted({e.session_id for e in events}),
                reasons=[
                    f"username '{username}' slow-tested from {len(ips)} IPs",
                    f"rate {rate:.2f} failures/hour over {hours:.1f}h",
                    "low-and-slow pattern",
                ],
            )
        )
    return campaigns


def detect_credential_stuffing(
    sessions: list[SessionView],
    cfg: StuffingConfig | None = None,
) -> list[Campaign]:
    cfg = cfg or StuffingConfig()
    found = (
        detect_username_stuffing(sessions, cfg)
        + detect_distributed_spray(sessions, cfg)
        + detect_slow_stuffing(sessions, cfg)
    )
    # De-dupe by id, keep first (more specific detectors first)
    out: list[Campaign] = []
    seen: set[str] = set()
    for camp in found:
        if camp.id in seen:
            continue
        seen.add(camp.id)
        out.append(camp)
    return out
