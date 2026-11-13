"""Hakukonebottien varmistus: käänteinen DNS + eteenpäin-DNS (C-2).

Google: https://developers.google.com/search/docs/crawling-indexing/verifying-googlebot
Bing: hostname päättyy `.search.msn.com`, forward confirm samaan IP:hen.

`VERIFIABLE_CRAWLER_TOKENS` PITÄÄ pysyä samana kuin B:n
`session.rules.VERIFIABLE_CRAWLER_TOKENS` (päätös 026).
"""

from __future__ import annotations

import socket
from dataclasses import dataclass

#: UA-/DNS-varmistettavat crawlerit. Synkassa B:n fake-crawler -säännön kanssa.
VERIFIABLE_CRAWLER_TOKENS = ("googlebot", "bingbot")

_GOOGLE_SUFFIXES = (".googlebot.com", ".google.com")
_BING_SUFFIXES = (".search.msn.com",)


@dataclass(frozen=True, slots=True)
class BotCheck:
    """verified: True=varmistettu botti, False=tarkistettu eikä ole, None=DNS epäonnistui."""

    verified: bool | None
    name: str | None = None  # googlebot | bingbot | None
    reverse_host: str | None = None


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
    """Varmista, onko IP oikea Googlebot/Bingbot (ei UA-huijaus).

    DNS-virhe (timeout / herror / gaierror) → `verified=None` (ei tarkistettu),
    jotta B:n fake-crawler -sääntö ei leimaa oikeaa Googlebottia väärennökseksi
    (S4 / päätökset 020 + 027).
    """
    try:
        reverse_host, _aliases, _ = socket.gethostbyaddr(ip)
    except (socket.herror, socket.gaierror, OSError):
        return BotCheck(verified=None)

    host = _normalize_host(reverse_host)

    if _suffix_match(host, _GOOGLE_SUFFIXES):
        if _forward_resolves_to(host, ip):
            return BotCheck(verified=True, name="googlebot", reverse_host=host)
        # PTR näyttää Googlebotilta mutta forward ei täsmää → väärennös
        return BotCheck(verified=False, name=None, reverse_host=host)

    if _suffix_match(host, _BING_SUFFIXES):
        if _forward_resolves_to(host, ip):
            return BotCheck(verified=True, name="bingbot", reverse_host=host)
        return BotCheck(verified=False, name=None, reverse_host=host)

    # PTR saatiin, mutta ei hakukonebottia → tarkistettu, ei verified bot
    return BotCheck(verified=False, reverse_host=host)
