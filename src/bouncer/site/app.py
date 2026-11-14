"""Demosivusto (A-3): pieni verkkokauppa, jonka liikennettä Bouncer tarkkailee.

Sivu on tarkoituksella tavallinen: sivuja, CSS/JS/kuvia ja kirjautuminen, jotta
ihmisen ja botin käyttäytyminen eroaa samalla tavalla kuin oikealla sivustolla.

- `POST /login`: ei oikeita tunnuksia, aina 401. Vastaukseen otsake
  `X-Login-User: <syötetty tunnus>`, jonka Caddy lokittaa (päätös 047).
  Salasanaa ei lueta talteen eikä lokiteta.
- Ansapolut (`deploy/traps.txt`, S11): piilolinkki etusivulla, kielletty
  `robots.txt`:ssä. Ihminen ei näe niitä; hyvä botti ei hae niitä.

    uv run uvicorn bouncer.site.app:app --port 8000
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from bouncer.session.rules import TRAPS_PATH, parse_traps

STATIC = Path(__file__).resolve().parent / "static"
LOGIN_USER_HEADER = "X-Login-User"
MAX_USERNAME = 64
_USERNAME_OK = re.compile(r"[^\w.@+\-]")

PRODUCTS = {
    i: name
    for i, name in enumerate(
        [
            "Kahvikuppi", "Teräskattila", "Puulusikka", "Leikkuulauta", "Pellavaliina",
            "Teekannu", "Valurautapannu", "Kakkuvuoka", "Salaattikulho", "Maustemylly",
            "Leipäveitsi", "Kattilanaluset",
        ],
        start=1,
    )
}  # fmt: skip


def _traps() -> list[str]:
    try:
        return sorted(parse_traps(TRAPS_PATH.read_text("utf-8").splitlines()))
    except FileNotFoundError:
        return []


def _page(title: str, body: str) -> HTMLResponse:
    trap = next(iter(_traps()), None)
    hidden = (
        f'<a href="{trap}" style="display:none" tabindex="-1" aria-hidden="true">.</a>'
        if trap
        else ""
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="fi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Keittiökauppa</title>
<link rel="stylesheet" href="/static/app.css">
<script src="/static/app.js" defer></script>
</head>
<body>
<header><a href="/"><img src="/static/logo.svg" alt="Keittiökauppa" width="32" height="32"></a>
<nav><a href="/">Etusivu</a> <a href="/products">Tuotteet</a> <a href="/about">Meistä</a>
<a href="/login">Kirjaudu</a></nav></header>
<main>{body}</main>
{hidden}
</body>
</html>"""
    )


app = FastAPI(title="Bouncer demo site", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return _page("Etusivu", "<h1>Keittiökauppa</h1><p>Laadukkaita keittiötarvikkeita.</p>"
                 '<p><a href="/products">Katso tuotteet</a></p>')  # fmt: skip


@app.get("/products", response_class=HTMLResponse)
def products() -> HTMLResponse:
    items = "".join(
        f'<li><a href="/products/{i}">{html.escape(n)}</a></li>' for i, n in PRODUCTS.items()
    )
    return _page("Tuotteet", f"<h1>Tuotteet</h1><ul>{items}</ul>")


@app.get("/products/{pid}", response_class=HTMLResponse)
def product(pid: int) -> HTMLResponse:
    if pid not in PRODUCTS:
        resp = _page("Ei löytynyt", "<h1>Tuotetta ei löytynyt</h1>")
        resp.status_code = 404
        return resp
    name = html.escape(PRODUCTS[pid])
    return _page(
        name, f"<h1>{name}</h1><p>Hinta: [HINTA]</p><p><a href='/products'>Takaisin</a></p>"
    )


@app.get("/about", response_class=HTMLResponse)
def about() -> HTMLResponse:
    return _page("Meistä", "<h1>Meistä</h1><p>Demosivu Bouncer-tunnistimen testaamiseen.</p>")


@app.get("/login", response_class=HTMLResponse)
def login_form() -> HTMLResponse:
    return _page(
        "Kirjaudu",
        '<h1>Kirjaudu</h1><form method="post" action="/login">'
        '<label>Tunnus <input name="username" autocomplete="username"></label> '
        '<label>Salasana <input name="password" type="password" autocomplete="current-password">'
        "</label> <button>Kirjaudu</button></form>",
    )


def clean_username(raw: str) -> str:
    """Otsakkeeseen kelpaava, lyhyt tunnus. Ei koskaan salasanaa."""
    return _USERNAME_OK.sub("", raw.strip())[:MAX_USERNAME]


@app.post("/login")
async def login(request: Request) -> Response:
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    username = clean_username((form.get("username") or [""])[0])
    # Salasana jätetään tarkoituksella lukematta: sitä ei käsitellä eikä lokiteta.
    resp = _page("Kirjaudu", "<h1>Väärä tunnus tai salasana</h1>")
    resp.status_code = 401
    if username:
        resp.headers[LOGIN_USER_HEADER] = username
    return resp


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    return "User-agent: *\n" + "".join(f"Disallow: {t}\n" for t in _traps())


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"
