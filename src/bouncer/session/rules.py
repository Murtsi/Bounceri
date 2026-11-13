"""Varmat säännöt (B-4). Pisteytyksen ensimmäinen kerros (ARCHITECTURE.md §3).

Sääntö antaa päätöksen vain, kun väärä positiivinen on käytännössä mahdoton.
Kaikki muu jää malille (B-6). Säännöt eivät koskaan päätä "ihminen" — sen
päättää vasta malli kynnyksineen (päätös 022).

Järjestys ratkaisee: ensimmäinen osuva sääntö voittaa, muut osumat lisätään
syiksi (`reasons`, enintään 3).
"""

from __future__ import annotations

import functools
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from bouncer.session import features as f
from bouncer.session._provisional_types import IpIntel, Label, Session

#: A:n ansalista (S11). Polku per rivi, `#` = kommentti. Puuttuu → ei ansoja.
TRAPS_PATH = Path(__file__).resolve().parents[3] / "deploy" / "traps.txt"

#: Montako *eri* haavoittuvuuspolkua tarvitaan varmaan päätökseen (päätös 019).
VULN_PATHS_CERTAIN = 2

#: Hakukonebotit, jotka C:n `ip_intel()` (S4) oikeasti varmistaa DNS:llä. Lista
#: PITÄÄ pitää samana kuin C:n `network/bots.py`: jos UA on crawler, jota C ei
#: tarkista (esim. Applebot), `verified_bot=False` ei tarkoita väärennöstä.
VERIFIABLE_CRAWLER_TOKENS = ("googlebot", "bingbot")


@dataclass(frozen=True, slots=True)
class RuleHit:
    rule_id: str
    label: Label
    score: float  # 0 = ihminen, 1 = botti
    reason: str


def _normalise(path: str) -> str:
    p = path.strip().lower()
    return p.rstrip("/") or "/"


def parse_traps(lines: Iterable[str]) -> frozenset[str]:
    out = set()
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(_normalise(line))
    return frozenset(out)


@functools.cache
def load_traps(path: Path = TRAPS_PATH) -> frozenset[str]:
    """Lukee A:n `deploy/traps.txt`:n. Ei tiedostoa → tyhjä joukko."""
    try:
        return parse_traps(path.read_text("utf-8").splitlines())
    except FileNotFoundError:
        return frozenset()


# --- yksittäiset säännöt -------------------------------------------------------


def trap_rule(session: Session, traps: frozenset[str]) -> RuleHit | None:
    hits = sorted({r.path for r in session.requests if _normalise(r.path) in traps})
    if not hits:
        return None
    return RuleHit(
        "trap",
        "bad_bot",
        1.0,
        f"Haki ansapolun {hits[0]}, jota ihminen ei näe sivulla"
        + (f" (+{len(hits) - 1} muuta)" if len(hits) > 1 else ""),
    )


def verified_crawler_rule(session: Session, intel: IpIntel | None) -> RuleHit | None:
    if intel is None or intel.verified_bot is not True:
        return None
    return RuleHit(
        "verified_crawler",
        "good_bot",
        1.0,
        "IP varmistettu hakukonebotiksi käänteisellä ja eteenpäin-DNS:llä",
    )


def _claims_verifiable_crawler(user_agent: str) -> str | None:
    ua = user_agent.lower()
    return next((t for t in VERIFIABLE_CRAWLER_TOKENS if t in ua), None)


def fake_crawler_rule(session: Session, intel: IpIntel | None) -> RuleHit | None:
    """UA väittää olevansa esim. Googlebot, mutta C:n DNS-varmistus epäonnistui.

    `verified_bot is None` (ei tarkistettu, esim. C:n stub) EI laukaise sääntöä.
    """
    token = _claims_verifiable_crawler(session.user_agent)
    if token is None or intel is None or intel.verified_bot is not False:
        return None
    return RuleHit(
        "fake_crawler",
        "bad_bot",
        1.0,
        f"User-Agent väittää olevansa {token}, mutta IP:n DNS-varmistus epäonnistui",
    )


def vuln_path_rule(session: Session) -> RuleHit | None:
    paths = sorted({r.path for r in session.requests if f.is_vuln_path(r.path)})
    if len(paths) < VULN_PATHS_CERTAIN:
        return None
    shown = ", ".join(paths[:3])
    return RuleHit(
        "vuln_paths",
        "bad_bot",
        1.0,
        f"Kokeili {len(paths)} tunnettua haavoittuvuuspolkua ({shown})",
    )


def evaluate(
    session: Session, intel: IpIntel | None, traps: frozenset[str] = frozenset()
) -> list[RuleHit]:
    """Kaikki osuvat varmat säännöt prioriteettijärjestyksessä."""
    # Varmistettu hakukonebotti ensin: IP:n DNS-varmistusta ei voi väärentää, mutta
    # oikea crawler voi seurata piilolinkkiä ansaan, jos ansaa ei ole kielletty
    # robots.txt:ssä (päätös 021). Ansaosuma jää silloin lisäsyyksi.
    candidates = (
        verified_crawler_rule(session, intel),
        trap_rule(session, traps),
        fake_crawler_rule(session, intel),
        vuln_path_rule(session),
    )
    return [h for h in candidates if h is not None]


# --- havainnot epävarmoille sessioille -----------------------------------------


def observations(feats: f.SessionFeatures) -> list[str]:
    """Pehmeät havainnot, kun mikään varma sääntö ei osu.

    Nämä EIVÄT ole päätöksiä vaan tosiasioita sessiosta, jotta `uncertain`-
    tuloksellakin on selitys. Järjestys = karkea tärkeysjärjestys.
    """
    out: list[str] = []
    if feats.vuln_path_hits == 1:
        out.append("Kokeili yhtä tunnettua haavoittuvuuspolkua")
    if feats.header_inconsistency_share > 0:
        out.append(
            f"Selaimeksi esittäytyvä, mutta {feats.header_inconsistency_share:.0%} sivupyynnöistä "
            "puuttuu selaimen otsakkeita"
        )
    if feats.ua_is_tool:
        out.append("User-Agent on komentorivityökalu tai ohjelmointikirjasto, ei selain")
    if feats.html_share > 0 and feats.static_share == 0 and feats.n_requests >= 5:
        out.append(f"Haki {feats.n_requests} pyyntöä ilman yhtään CSS/JS/kuvatiedostoa")
    if feats.peak_requests_per_min >= 60:
        out.append(f"Huipputahti {feats.peak_requests_per_min} pyyntöä minuutissa")
    if feats.interarrival_cv is not None and feats.interarrival_cv < 0.1 and feats.n_requests >= 10:
        out.append("Pyyntöjen välit lähes täsmälleen tasaiset")
    if feats.not_found_share >= 0.5 and feats.n_requests >= 5:
        out.append(f"{feats.not_found_share:.0%} pyynnöistä päättyi 404:ään")
    if feats.ua_claims_bot:
        out.append("User-Agent ilmoittaa olevansa botti (ei varmistettu)")
    return out
