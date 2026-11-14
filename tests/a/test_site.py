"""Demosivu (A-3): reitit, kirjautumisotsake (047) ja ansat (S11)."""

import pytest
from fastapi.testclient import TestClient

from bouncer.session.rules import load_traps
from bouncer.site.app import app, clean_username


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "status"),
    [("/", 200), ("/products", 200), ("/products/3", 200), ("/products/99", 404),
     ("/about", 200), ("/login", 200), ("/static/app.css", 200), ("/static/app.js", 200),
     ("/static/logo.svg", 200), ("/healthz", 200)],
)  # fmt: skip
def test_routes(client, path, status):
    assert client.get(path).status_code == status


def test_pages_load_assets_like_a_real_site(client):
    page = client.get("/").text
    assert "/static/app.css" in page and "/static/app.js" in page and "/static/logo.svg" in page


def test_login_returns_username_header_and_never_echoes_password(client):
    r = client.post("/login", data={"username": " Admin ", "password": "hunter2-secret"})
    assert r.status_code == 401
    assert r.headers["X-Login-User"] == "Admin"
    assert "hunter2-secret" not in r.text
    assert all("hunter2-secret" not in v for v in r.headers.values())


def test_login_without_username_sets_no_header(client):
    r = client.post("/login", data={"password": "x"})
    assert r.status_code == 401 and "X-Login-User" not in r.headers


def test_username_is_sanitised_for_a_header():
    assert clean_username("ad\r\nmin<script>") == "adminscript"
    assert len(clean_username("a" * 500)) == 64


def test_traps_are_hidden_and_disallowed(client):
    traps = load_traps()
    assert traps
    robots = client.get("/robots.txt").text
    assert all(f"Disallow: {t}" in robots for t in traps)
    page = client.get("/").text
    assert 'style="display:none"' in page and any(t in page for t in traps)
