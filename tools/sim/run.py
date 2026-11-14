"""MVP:n simulaattorit (A-4/A-8): liikennettä demosivulle Caddyn läpi.

    uv run python tools/sim/run.py --base-url http://127.0.0.1:8080
    uv run python tools/sim/run.py --dry-run          # suunnitelma ilman verkkoa

Skenaariot (docs/MVP.md, kriteerit 1–4). Jokainen toimija lähettää
allekirjoitetun `X-Sim-Run`-merkinnän (päätös 046) ja oman IP:nsä
`X-Forwarded-For`-otsakkeessa, johon vain paikallinen Caddy luottaa (päätös 050).

| toimija | luokka | mitä tekee |
|---|---|---|
| human-N | human | sivut + CSS/JS/kuva, selaimen otsakkeet, Referer, lukutauot |
| scraper | scraper | Chrome-UA ilman selaimen otsakkeita, kaikki tuotesivut tasaisella tahdilla |
| scanner | scanner | curl, haavoittuvuuspolut nopeasti |
| stuff-N | credential_stuffing | sama tunnus, eri IP, hidas tahti (sama kampanja) |
| fakebot | scraper | Googlebot-UA IP:stä, joka ei ole Googlen (C:n DNS-varmistus epäonnistuu) |

Kaikki tämä liikenne on synteettistä: sen luvuilla ei ole todistusarvoa (S8).
"""

from __future__ import annotations

import argparse
import random
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field

from bouncer.ingest import simrun

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
VULN_PATHS = ("/.env", "/.git/config", "/wp-login.php", "/xmlrpc.php", "/phpmyadmin/",
              "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php", "/backup.sql")  # fmt: skip
ASSETS = (("/static/app.css", "style"), ("/static/app.js", "script"), ("/static/logo.svg", "image"))
#: Julkinen IP, jolla on PTR-tietue, joka ei ole Googlen → C:n varmistus = False.
FAKE_GOOGLEBOT_IP = "1.1.1.1"


@dataclass(frozen=True, slots=True)
class Step:
    at: float  # sekuntia ajon alusta
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    data: str | None = None


@dataclass(slots=True)
class Actor:
    name: str
    ip: str
    ua: str
    sim_class: str
    campaign: str | None = None
    steps: list[Step] = field(default_factory=list)

    def marker(self, run_id: str) -> str:
        return f"{run_id}-{self.name}:{self.sim_class}:{self.campaign or '-'}"


def _browser_page(referer: str | None, first: bool) -> dict[str, str]:
    h = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if first else "same-origin",
        "Sec-Fetch-Dest": "document",
        "Sec-CH-UA": '"Chromium";v="131", "Google Chrome";v="131"',
    }
    if referer:
        h["Referer"] = referer
    return h


def human(i: int, rng: random.Random, base: str) -> Actor:
    a = Actor(f"human{i}", f"198.51.100.{10 + i}", CHROME_UA, "human")
    pages = [
        "/",
        "/products",
        f"/products/{rng.randint(1, 12)}",
        rng.choice(["/about", "/products"]),
    ]
    t, prev = rng.uniform(0, 5), None
    for n, page in enumerate(pages):
        a.steps.append(Step(t, "GET", page, _browser_page(prev and base + prev, n == 0)))
        for k, (asset, dest) in enumerate(ASSETS):
            hdr = {"Accept": "*/*", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": dest,
                   "Referer": base + page}  # fmt: skip
            a.steps.append(Step(t + 0.05 * (k + 1), "GET", asset, hdr))
        prev = page
        t += rng.uniform(3, 9)  # lukutauko
    return a


def scraper() -> Actor:
    a = Actor("scraper", "203.0.113.30", CHROME_UA, "scraper")
    a.steps = [
        Step(0.3 * i, "GET", f"/products/{i % 12 + 1}", {"Accept": "*/*"}) for i in range(24)
    ]
    return a


def scanner() -> Actor:
    a = Actor("scanner", "203.0.113.24", "curl/8.5.0", "scanner")
    a.steps = [Step(0.2 * i, "GET", p, {"Accept": "*/*"}) for i, p in enumerate(VULN_PATHS)]
    return a


def stuffing(run_id: str, n: int = 6, gap_s: float = 5.0) -> list[Actor]:
    camp = f"camp-stuff-{run_id}"
    out = []
    for i in range(n):
        a = Actor(f"stuff{i}", f"203.0.113.{100 + i}", "curl/8.5.0", "credential_stuffing", camp)
        a.steps = [Step(2 + gap_s * i, "POST", "/login",
                        {"Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded"},
                        f"username=admin&password=guess{i}")]  # fmt: skip
        out.append(a)
    return out


def fake_googlebot() -> Actor:
    a = Actor("fakebot", FAKE_GOOGLEBOT_IP, GOOGLEBOT_UA, "scraper")
    paths = ["/robots.txt", "/", "/products", "/products/1", "/products/2", "/about"]
    a.steps = [Step(1.0 * i, "GET", p, {"Accept": "*/*"}) for i, p in enumerate(paths)]
    return a


def plan(
    run_id: str, seed: int = 1, humans: int = 6, base: str = "http://127.0.0.1:8080"
) -> list[Actor]:
    rng = random.Random(seed)
    return [*(human(i, rng, base) for i in range(humans)), scraper(), scanner(),
            *stuffing(run_id), fake_googlebot()]  # fmt: skip


def build_request(
    base: str, actor: Actor, step: Step, run_id: str, secret: str
) -> urllib.request.Request:
    marker = actor.marker(run_id)
    headers = {"User-Agent": actor.ua, "X-Forwarded-For": actor.ip, **step.headers,
               "X-Sim-Run": marker, "X-Sim-Sig": simrun.sign(marker, secret)}  # fmt: skip
    data = step.data.encode() if step.data is not None else None
    return urllib.request.Request(base + step.path, data=data, headers=headers, method=step.method)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A simulator label/signature must never follow a redirect to another service.
        return None


def _play(base: str, actor: Actor, run_id: str, secret: str, t0: float, results: list) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    for step in actor.steps:
        time.sleep(max(0.0, t0 + step.at - time.monotonic()))
        req = build_request(base, actor, step, run_id, secret)
        try:
            with opener.open(req, timeout=10) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except OSError as e:
            status = f"virhe: {e}"
        results.append((actor.name, step.method, step.path, status))


def run(base: str, secret: str, run_id: str, seed: int = 1, humans: int = 6) -> list[tuple]:
    actors = plan(run_id, seed, humans, base)
    results: list[tuple] = []
    t0 = time.monotonic()
    threads = [threading.Thread(target=_play, args=(base, a, run_id, secret, t0, results))
               for a in actors]  # fmt: skip
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return results


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bouncerin MVP-simulaattorit")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--run-id", default=f"mvp{int(time.time())}")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--humans", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true", help="tulosta suunnitelma, älä lähetä")
    a = ap.parse_args(argv)
    secret = simrun.secret_from_env()
    if not secret:
        print(f"{simrun.SECRET_ENV} puuttuu: merkintöjä ei voi allekirjoittaa (päätös 046)")
        return 1
    actors = plan(a.run_id, a.seed, a.humans, a.base_url)
    if a.dry_run:
        for act in actors:
            print(f"{act.name:9} {act.ip:15} {act.sim_class:20} {len(act.steps):3} pyyntöä  "
                  f"{act.marker(a.run_id)}")  # fmt: skip
        return 0
    results = run(a.base_url, secret, a.run_id, a.seed, a.humans)
    errors = [r for r in results if not isinstance(r[3], int)]
    print(f"ajo {a.run_id}: {len(results)} pyyntöä, {len(errors)} verkkovirhettä")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
