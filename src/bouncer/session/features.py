"""Session piirteet (B-2). Puhtaita funktioita: `Session` sisään, luku ulos.

Jokainen piirre on selitettävissä yhdellä lauseella (ARCHITECTURE.md §2), koska
`score()`:n `reasons` ja C:n `explain()` rakentuvat näiden päälle.

`None` tarkoittaa "ei tarpeeksi dataa" (esim. variaatiokerroin alle 3 pyynnöstä),
ei nollaa. Malli (B-6) päättää, miten `None` käsitellään.

Valinnat (ikkunat, polkulistat, otsakesäännöt): `docs/DECISIONS.md` 015–018.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from bouncer.session._provisional_types import Request, Session

# --- vakiot -------------------------------------------------------------------

#: Lyhin kesto, jolla pyyntötahti jaetaan (s). Estää jakamisen nollalla, kun
#: monta pyyntöä tulee samalla aikaleimalla.
MIN_DURATION_S = 1.0

#: Liukuvan ikkunan pituus huipputahdille (s).
PEAK_WINDOW_S = 60.0

STATIC_EXTENSIONS = frozenset(
    {
        "css", "js", "mjs", "map",
        "png", "jpg", "jpeg", "gif", "webp", "avif", "svg", "ico", "bmp",
        "woff", "woff2", "ttf", "otf", "eot",
        "mp4", "webm", "mp3", "wav",
    }
)  # fmt: skip

HTML_EXTENSIONS = frozenset({"html", "htm", "php", "asp", "aspx", "jsp"})

#: Tunnettujen haavoittuvuus-/skannauspolkujen alut ja kuviot. Pienillä kirjaimilla.
#: Tämä on *piirre*, ei ansa: ansat tulevat A:n `deploy/traps.txt`:stä (S11).
VULN_PATH_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^/\.env(\.|$|/)",
        r"^/\.git(/|$)",
        r"^/\.svn(/|$)",
        r"^/\.hg(/|$)",
        r"^/\.aws(/|$)",
        r"^/\.ssh(/|$)",
        r"^/\.ds_store$",
        r"^/\.htaccess$",
        r"^/\.htpasswd$",
        r"^/wp-login\.php$",
        r"^/wp-admin(/|$)",
        r"^/wp-content/plugins/",
        r"^/wp-includes/",
        r"^/wp-config\.php",
        r"^/xmlrpc\.php$",
        r"^/(phpmyadmin\d*|pma|myadmin)(/|$)",
        r"^/(admin|administrator)/(config|setup|install)",
        r"^/vendor/phpunit/",
        r"^/cgi-bin/",
        r"^/actuator(/|$)",
        r"^/server-status$",
        r"^/(boaform|goform|hnap1)(/|$)",
        r"^/(shell|cmd|c99|r57|eval-stdin)\.php$",
        r"^/config\.(php|json|ya?ml|js)$",
        r"^/(backup|db|dump|database)\.(sql|zip|tar|tar\.gz|tgz)$",
        r"\.(bak|old|swp|sql)$",
        r"^/solr/",
    )
)

#: User-Agentin osat, jotka paljastavat työkalun tai skriptin.
TOOL_UA_TOKENS = (
    "curl/", "wget/", "python-requests", "python-urllib", "aiohttp", "httpx",
    "go-http-client", "java/", "okhttp", "libwww-perl", "node-fetch", "axios/",
    "scrapy", "masscan", "zgrab", "nmap", "nikto", "sqlmap", "nuclei", "gobuster",
    "headlesschrome", "phantomjs",
)  # fmt: skip

#: User-Agentin osat, joilla kävijä *väittää* olevansa botti. Väite varmistetaan
#: C:n `ip_intel().verified_bot`:lla, ei täällä.
BOT_UA_TOKENS = ("bot", "crawl", "spider", "slurp", "fetcher")

_CHROME_RE = re.compile(r"\b(?:chrome|crios)/(\d+)")
_EDGE_RE = re.compile(r"\bedg(?:e|a|ios)?/(\d+)")
_FIREFOX_RE = re.compile(r"\b(?:firefox|fxios)/(\d+)")
_SAFARI_RE = re.compile(r"\bversion/(\d+)(?:\.(\d+))?.*\bsafari/")

# --- apufunktiot ---------------------------------------------------------------


def _sorted(session: Session) -> Sequence[Request]:
    return sorted(session.requests, key=lambda r: r.ts)


def _extension(path: str) -> str:
    last = path.rsplit("/", 1)[-1]
    if "." not in last:
        return ""
    return last.rsplit(".", 1)[-1].lower()


def is_static(req: Request) -> bool:
    """Staattinen resurssi: CSS/JS/kuva/fontti/media (Content-Type tai pääte)."""
    ct = (req.content_type or "").lower()
    if ct:
        if ct.startswith(("image/", "font/", "video/", "audio/")):
            return True
        if ct in {"text/css", "application/javascript", "text/javascript"}:
            return True
    return _extension(req.path) in STATIC_EXTENSIONS


def is_html(req: Request) -> bool:
    """HTML-sivu. Content-Type voittaa; muuten pääte tai päätteetön polku."""
    ct = (req.content_type or "").lower()
    if ct:
        return ct in {"text/html", "application/xhtml+xml"}
    ext = _extension(req.path)
    return ext in HTML_EXTENSIONS or ext == ""


def is_vuln_path(path: str) -> bool:
    p = path.lower()
    return any(rx.search(p) for rx in VULN_PATH_PATTERNS)


def _share(n: int, total: int) -> float:
    return n / total if total else 0.0


# --- tahti ---------------------------------------------------------------------


def duration_s(session: Session) -> float:
    """Ensimmäisen ja viimeisen pyynnön väli sekunteina."""
    reqs = _sorted(session)
    if len(reqs) < 2:
        return 0.0
    return (reqs[-1].ts - reqs[0].ts).total_seconds()


def requests_per_min(session: Session) -> float:
    """Keskitahti: (n − 1) aikaväliä jaettuna kestolla. Alle 2 pyyntöä → 0."""
    n = len(session.requests)
    if n < 2:
        return 0.0
    return 60.0 * (n - 1) / max(duration_s(session), MIN_DURATION_S)


def peak_requests_per_min(session: Session, window_s: float = PEAK_WINDOW_S) -> int:
    """Suurin pyyntömäärä missä tahansa `window_s`-pituisessa ikkunassa."""
    ts = [r.ts.timestamp() for r in _sorted(session)]
    best = 0
    lo = 0
    for hi, t in enumerate(ts):
        while t - ts[lo] >= window_s:
            lo += 1
        best = max(best, hi - lo + 1)
    return best


def interarrival_cv(session: Session) -> float | None:
    """Pyyntöjen välisten aikojen variaatiokerroin (keskihajonta / keskiarvo).

    Botit ovat usein liian tasaisia (CV ≈ 0); ihmisen selaus on purskeista
    (sivu + resurssit heti, sitten lukutauko) → CV ≫ 1. Alle 3 pyyntöä → None.
    Kaikki samalla aikaleimalla → 0.0.
    """
    reqs = _sorted(session)
    if len(reqs) < 3:
        return None
    gaps = [(b.ts - a.ts).total_seconds() for a, b in zip(reqs, reqs[1:], strict=False)]
    mean = statistics.fmean(gaps)
    if mean == 0:
        return 0.0
    return statistics.pstdev(gaps) / mean


# --- sisältö -------------------------------------------------------------------


def static_share(session: Session) -> float:
    return _share(sum(is_static(r) for r in session.requests), len(session.requests))


def html_share(session: Session) -> float:
    return _share(sum(is_html(r) for r in session.requests), len(session.requests))


def unique_paths(session: Session) -> int:
    return len({r.path for r in session.requests})


def path_diversity(session: Session) -> float:
    """Eri polkujen osuus pyynnöistä (1 = jokainen pyyntö eri polkuun)."""
    return _share(unique_paths(session), len(session.requests))


def robots_txt_fetched(session: Session) -> bool:
    return any(r.path.lower() == "/robots.txt" for r in session.requests)


# --- virheet -------------------------------------------------------------------


def error_4xx_share(session: Session) -> float:
    return _share(sum(400 <= r.status < 500 for r in session.requests), len(session.requests))


def not_found_share(session: Session) -> float:
    return _share(sum(r.status == 404 for r in session.requests), len(session.requests))


def vuln_path_hits(session: Session) -> int:
    """Tunnettujen haavoittuvuuspolkujen osumien määrä (sama polku lasketaan kerran)."""
    return sum(is_vuln_path(p) for p in {r.path for r in session.requests})


# --- otsakkeet -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BrowserClaim:
    family: str  # "chrome" | "edge" | "firefox" | "safari" | ""
    major: int


def browser_claim(user_agent: str) -> BrowserClaim:
    """Mikä selain UA väittää olevansa. Ei-selain → family="" ."""
    ua = user_agent.lower()
    if not ua.startswith("mozilla/"):
        return BrowserClaim("", 0)
    if m := _EDGE_RE.search(ua):
        return BrowserClaim("edge", int(m.group(1)))
    if m := _FIREFOX_RE.search(ua):
        return BrowserClaim("firefox", int(m.group(1)))
    if m := _CHROME_RE.search(ua):
        return BrowserClaim("chrome", int(m.group(1)))
    if m := _SAFARI_RE.search(ua):
        return BrowserClaim("safari", int(m.group(1)))
    return BrowserClaim("", 0)


def _expects_sec_fetch(claim: BrowserClaim) -> bool:
    # Sec-Fetch-*: Chrome/Edge 76+, Firefox 90+, Safari 16.4+ (major 17+ varmasti).
    return (
        (claim.family in {"chrome", "edge"} and claim.major >= 76)
        or (claim.family == "firefox" and claim.major >= 90)
        or (claim.family == "safari" and claim.major >= 17)
    )


def _expects_client_hints(claim: BrowserClaim) -> bool:
    # Sec-CH-UA: Chromium 89+ (vain HTTPS:llä — demosivu on HTTPS:llä Caddyn takana).
    return claim.family in {"chrome", "edge"} and claim.major >= 89


def header_issues(req: Request, user_agent: str) -> tuple[str, ...]:
    """Otsakkeet, jotka selaimeksi esittäytyvältä pyynnöltä puuttuvat.

    Tarkistetaan vain HTML-sivupyynnöt: niissä oikea selain lähettää aina
    `Accept`, `Accept-Language` ja (uusissa selaimissa) `Sec-Fetch-*`.
    """
    claim = browser_claim(user_agent)
    if not claim.family or not is_html(req):
        return ()
    h = req.headers
    issues = []
    if "accept" not in h:
        issues.append("accept")
    if "accept-language" not in h:
        issues.append("accept-language")
    if _expects_sec_fetch(claim) and "sec-fetch-mode" not in h:
        issues.append("sec-fetch")
    if _expects_client_hints(claim) and "sec-ch-ua" not in h:
        issues.append("sec-ch-ua")
    return tuple(issues)


def header_inconsistency_share(session: Session) -> float:
    """Selaimeksi esittäytyvän session HTML-pyynnöistä se osuus, josta puuttuu
    selaimelle pakollisia otsakkeita. Ei-selain-UA → 0 (ks. `ua_is_tool`)."""
    pages = [r for r in session.requests if is_html(r)]
    if not browser_claim(session.user_agent).family:
        return 0.0
    return _share(sum(bool(header_issues(r, session.user_agent)) for r in pages), len(pages))


def missing_referer_share(session: Session) -> float:
    """Session *sisäsivuista* (HTML, ei ensimmäinen) se osuus, jolta puuttuu Referer."""
    pages = [r for r in _sorted(session) if is_html(r)][1:]
    return _share(sum("referer" not in r.headers for r in pages), len(pages))


def ua_is_tool(user_agent: str) -> bool:
    """Tyhjä UA tai tunnettu työkalu/kirjasto (curl, python-requests, …)."""
    ua = user_agent.strip().lower()
    return not ua or any(t in ua for t in TOOL_UA_TOKENS)


def ua_claims_bot(user_agent: str) -> bool:
    """UA *väittää* olevansa botti/crawler. Ei varmistettu."""
    ua = user_agent.lower()
    return any(t in ua for t in BOT_UA_TOKENS)


# --- kaikki yhdessä ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionFeatures:
    n_requests: int
    duration_s: float
    requests_per_min: float
    peak_requests_per_min: int
    interarrival_cv: float | None
    static_share: float
    html_share: float
    unique_paths: int
    path_diversity: float
    robots_txt_fetched: bool
    error_4xx_share: float
    not_found_share: float
    vuln_path_hits: int
    header_inconsistency_share: float
    missing_referer_share: float
    ua_is_tool: bool
    ua_claims_bot: bool

    def to_dict(self) -> dict[str, Any]:
        """JSON-kelpoinen muoto (`sessions.features`-sarakkeeseen)."""
        return asdict(self)


def compute_features(session: Session) -> SessionFeatures:
    return SessionFeatures(
        n_requests=len(session.requests),
        duration_s=duration_s(session),
        requests_per_min=requests_per_min(session),
        peak_requests_per_min=peak_requests_per_min(session),
        interarrival_cv=interarrival_cv(session),
        static_share=static_share(session),
        html_share=html_share(session),
        unique_paths=unique_paths(session),
        path_diversity=path_diversity(session),
        robots_txt_fetched=robots_txt_fetched(session),
        error_4xx_share=error_4xx_share(session),
        not_found_share=not_found_share(session),
        vuln_path_hits=vuln_path_hits(session),
        header_inconsistency_share=header_inconsistency_share(session),
        missing_referer_share=missing_referer_share(session),
        ua_is_tool=ua_is_tool(session.user_agent),
        ua_claims_bot=ua_claims_bot(session.user_agent),
    )
