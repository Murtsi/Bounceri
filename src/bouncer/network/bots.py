"""Hakukonebottien varmistus: käänteinen DNS + eteenpäin-DNS (C-2).

Google: https://developers.google.com/search/docs/crawling-indexing/verifying-googlebot
Bing: hostname päättyy `.search.msn.com`, forward confirm samaan IP:hen.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BotCheck:
    verified: bool
    name: str | None = None  # googlebot | bingbot | None
    reverse_host: str | None = None


_GOOGLE_SUFFIXES = (".googlebot.com", ".google.com")
_BING_SUFFIXES = (".search.msn.com",)


def _normalize_host(host: str) -> str:
    return host.lower().rstrip(".")


def _suffix_match(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == s[1:] or host.endswith(s) for s in suffixes)


def _forward_resolves_to(host: str, ip: str) -> bool:
    try:
        _hostname, _aliases, addresses = socket.gethostbyname_ex(host)
    except (socket.gaierror, socket.herror, OSError):
        return False
    return ip in addresses


def verify_search_bot(ip: str) -> BotCheck:
    """Varmista, onko IP oikea Googlebot/Bingbot (ei UA-huijaus)."""
    try:
        reverse_host, _aliases, _ = socket.gethostbyaddr(ip)
    except (socket.herror, socket.gaierror, OSError):
        return BotCheck(verified=False)

    host = _normalize_host(reverse_host)

    if _suffix_match(host, _GOOGLE_SUFFIXES):
        if _forward_resolves_to(host, ip):
            return BotCheck(verified=True, name="googlebot", reverse_host=host)
        return BotCheck(verified=False, name=None, reverse_host=host)

    if _suffix_match(host, _BING_SUFFIXES):
        if _forward_resolves_to(host, ip):
            return BotCheck(verified=True, name="bingbot", reverse_host=host)
        return BotCheck(verified=False, name=None, reverse_host=host)

    return BotCheck(verified=False, reverse_host=host)
