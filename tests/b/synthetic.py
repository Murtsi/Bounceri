"""Käsin rakennetut synteettiset sessiot B:n yksikkötesteihin.

Nämä EIVÄT ole arviointidataa eivätkä A:n simulaattoreita — vain tunnettuja
tapauksia, joilla piirrefunktioiden logiikka testataan. Arviointi tehdään A:n
lokinäytteillä ja `labels`-taululla (B-3, B-5).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bouncer.session._provisional_types import Request, Session

T0 = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
FIREFOX_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0"
SAFARI_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)
EDGE_UA = CHROME_UA + " Edg/131.0.0.0"
CURL_UA = "curl/8.5.0"
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

CHROME_PAGE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "accept-language": "fi-FI,fi;q=0.9,en;q=0.8",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-dest": "document",
    "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131"',
}

IP = "203.0.113.7"


def req(
    t: float,
    path: str,
    *,
    status: int = 200,
    method: str = "GET",
    ua: str = CHROME_UA,
    headers: dict[str, str] | None = None,
    content_type: str | None = None,
) -> Request:
    return Request(
        ts=T0 + timedelta(seconds=t),
        ip=IP,
        method=method,
        path=path,
        status=status,
        user_agent=ua,
        headers=dict(headers or {}),
        content_type=content_type,
    )


def session(requests: list[Request], ua: str = CHROME_UA, sid: str = "s1") -> Session:
    ts = [r.ts for r in requests] or [T0]
    return Session(
        id=sid,
        ip=IP,
        user_agent=ua,
        started_at=min(ts),
        ended_at=max(ts),
        requests=tuple(requests),
    )


def human_session() -> Session:
    """Chrome-käyttäjä: 3 sivua, jokaisen perään resurssit, lukutaukoja välissä."""
    rs: list[Request] = []
    pages = [(0.0, "/"), (35.0, "/products"), (102.0, "/products/42")]
    prev = None
    for t, path in pages:
        h = dict(CHROME_PAGE_HEADERS)
        if prev:
            h["referer"] = f"https://shop.example{prev}"
        rs.append(req(t, path, headers=h, content_type="text/html"))
        for i, asset in enumerate(("/static/app.css", "/static/app.js", "/img/logo.png")):
            rs.append(req(t + 0.05 * (i + 1), asset, headers={"accept": "*/*"}))
        prev = path
    return session(rs)


def curl_scanner_session() -> Session:
    """curl-skanneri: haavoittuvuuspolkuja tasaisella 0,5 s tahdilla, lähes kaikki 404."""
    paths = [
        "/.env", "/.git/config", "/wp-login.php", "/xmlrpc.php", "/phpmyadmin/",
        "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php", "/backup.sql", "/",
    ]  # fmt: skip
    rs = [req(0.5 * i, p, ua=CURL_UA, status=200 if p == "/" else 404) for i, p in enumerate(paths)]
    return session(rs, ua=CURL_UA)


def scraper_session(n: int = 120, gap_s: float = 1.0) -> Session:
    """Chrome-UA:lla esiintyvä scraper: vain HTML-sivuja, tasainen tahti, ei otsakkeita."""
    rs = [req(gap_s * i, f"/products/{i}", headers={"accept": "*/*"}) for i in range(n)]
    return session(rs)


def googlebot_session() -> Session:
    rs = [req(0.0, "/robots.txt", ua=GOOGLEBOT_UA, content_type="text/plain")]
    rs += [req(3.0 * i + 1, f"/p/{i}", ua=GOOGLEBOT_UA) for i in range(5)]
    return session(rs, ua=GOOGLEBOT_UA)
