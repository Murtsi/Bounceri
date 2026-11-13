import json
import math

import pytest

from bouncer.session import features as f

from .synthetic import (
    CHROME_PAGE_HEADERS,
    CHROME_UA,
    CURL_UA,
    EDGE_UA,
    FIREFOX_UA,
    GOOGLEBOT_UA,
    SAFARI_UA,
    curl_scanner_session,
    googlebot_session,
    human_session,
    req,
    scraper_session,
    session,
)

# --- tahti ---------------------------------------------------------------------


def test_duration_and_rate_single_request():
    s = session([req(0, "/")])
    assert f.duration_s(s) == 0.0
    assert f.requests_per_min(s) == 0.0
    assert f.peak_requests_per_min(s) == 1
    assert f.interarrival_cv(s) is None


def test_requests_per_min_uses_gaps_not_count():
    # 11 pyyntöä 10 s välein = 100 s, 10 väliä → 6 / min
    s = session([req(10 * i, f"/{i}") for i in range(11)])
    assert f.duration_s(s) == 100.0
    assert f.requests_per_min(s) == pytest.approx(6.0)


def test_requests_per_min_same_timestamp_does_not_divide_by_zero():
    s = session([req(0, "/a"), req(0, "/b"), req(0, "/c")])
    assert f.requests_per_min(s) == pytest.approx(120.0)  # 2 väliä / 1 s minimikesto
    assert f.interarrival_cv(s) == 0.0


def test_peak_window_catches_burst_inside_long_session():
    burst = [req(600 + 0.1 * i, f"/b{i}") for i in range(50)]
    s = session([req(0, "/"), *burst, req(1200, "/end")])
    assert f.peak_requests_per_min(s) == 50
    assert f.requests_per_min(s) < 3


def test_unsorted_requests_are_handled():
    s = session([req(20, "/c"), req(0, "/a"), req(10, "/b")])
    assert f.duration_s(s) == 20.0
    assert f.interarrival_cv(s) == 0.0


def test_interarrival_cv_bot_vs_human():
    assert f.interarrival_cv(scraper_session()) == pytest.approx(0.0)
    human_cv = f.interarrival_cv(human_session())
    assert human_cv is not None and human_cv > 1.5


# --- sisältö -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "ct", "static", "html"),
    [
        ("/static/app.css", None, True, False),
        ("/img/a.WEBP", None, True, False),
        ("/fonts/x.woff2", None, True, False),
        ("/", None, False, True),
        ("/products/42", None, False, True),
        ("/index.php", None, False, True),
        ("/robots.txt", None, False, False),
        ("/api/data", "application/json", False, False),
        ("/render", "image/png", True, False),
        ("/page.json", "text/html", False, True),  # Content-Type voittaa päätteen
    ],
)
def test_static_and_html_classification(path, ct, static, html):
    r = req(0, path, content_type=ct)
    assert f.is_static(r) is static
    assert f.is_html(r) is html


def test_human_has_static_assets_scraper_does_not():
    h, s = human_session(), scraper_session()
    assert f.static_share(h) == pytest.approx(0.75)
    assert f.html_share(h) == pytest.approx(0.25)
    assert f.static_share(s) == 0.0
    assert f.html_share(s) == 1.0


def test_path_diversity():
    s = session([req(i, "/same") for i in range(4)] + [req(5, "/other")])
    assert f.unique_paths(s) == 2
    assert f.path_diversity(s) == pytest.approx(0.4)
    assert f.path_diversity(scraper_session()) == 1.0


def test_robots_txt():
    assert f.robots_txt_fetched(googlebot_session())
    assert not f.robots_txt_fetched(human_session())


def test_empty_session_is_safe():
    s = session([])
    feats = f.compute_features(s)
    assert feats.n_requests == 0
    assert feats.static_share == 0.0
    assert feats.error_4xx_share == 0.0
    assert feats.interarrival_cv is None


# --- virheet -------------------------------------------------------------------


def test_error_shares():
    s = session(
        [req(0, "/", status=200), req(1, "/x", status=404), req(2, "/y", status=403),
         req(3, "/z", status=500)]
    )  # fmt: skip
    assert f.error_4xx_share(s) == pytest.approx(0.5)
    assert f.not_found_share(s) == pytest.approx(0.25)


@pytest.mark.parametrize(
    "path",
    [
        "/.env", "/.env.production", "/.git/config", "/.git/HEAD", "/wp-login.php",
        "/wp-admin/", "/WP-ADMIN/setup-config.php", "/xmlrpc.php", "/phpmyadmin/",
        "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php", "/backup.sql",
        "/cgi-bin/luci", "/actuator/env", "/server-status", "/.aws/credentials",
        "/index.php.bak", "/config.json",
    ],
)  # fmt: skip
def test_vuln_paths_detected(path):
    assert f.is_vuln_path(path)


@pytest.mark.parametrize(
    "path",
    ["/", "/products/42", "/environment", "/blog/git-tips", "/static/app.js",
     "/login", "/admin-guide", "/.well-known/acme-challenge/abc", "/configure"],
)  # fmt: skip
def test_ordinary_paths_not_vuln(path):
    assert not f.is_vuln_path(path)


def test_vuln_hits_count_unique_paths():
    assert f.vuln_path_hits(curl_scanner_session()) == 7
    s = session([req(i, "/.env") for i in range(5)])
    assert f.vuln_path_hits(s) == 1
    assert f.vuln_path_hits(human_session()) == 0


# --- otsakkeet -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("ua", "family", "major"),
    [
        (CHROME_UA, "chrome", 131),
        (EDGE_UA, "edge", 131),
        (FIREFOX_UA, "firefox", 133),
        (SAFARI_UA, "safari", 18),
        (CURL_UA, "", 0),
        (GOOGLEBOT_UA, "", 0),
        ("", "", 0),
    ],
)
def test_browser_claim(ua, family, major):
    assert f.browser_claim(ua) == f.BrowserClaim(family, major)


def test_real_chrome_page_has_no_header_issues():
    r = req(0, "/", headers=CHROME_PAGE_HEADERS, content_type="text/html")
    assert f.header_issues(r, CHROME_UA) == ()


def test_chrome_ua_without_browser_headers_is_flagged():
    r = req(0, "/", headers={"accept": "*/*"})
    assert set(f.header_issues(r, CHROME_UA)) == {"accept-language", "sec-fetch", "sec-ch-ua"}


def test_firefox_does_not_need_client_hints():
    h = {k: v for k, v in CHROME_PAGE_HEADERS.items() if k != "sec-ch-ua"}
    assert f.header_issues(req(0, "/", headers=h), FIREFOX_UA) == ()


def test_old_chrome_not_expected_to_send_sec_fetch():
    old = CHROME_UA.replace("Chrome/131", "Chrome/70")
    r = req(0, "/", headers={"accept": "*/*", "accept-language": "en"})
    assert f.header_issues(r, old) == ()


def test_assets_are_not_checked_for_page_headers():
    assert f.header_issues(req(0, "/static/app.js", headers={}), CHROME_UA) == ()


def test_header_inconsistency_share():
    assert f.header_inconsistency_share(human_session()) == 0.0
    assert f.header_inconsistency_share(scraper_session()) == 1.0
    # Ei-selain-UA: otsakesääntö ei koske (tool-piirre hoitaa)
    assert f.header_inconsistency_share(curl_scanner_session()) == 0.0


def test_missing_referer_share():
    assert f.missing_referer_share(human_session()) == 0.0
    assert f.missing_referer_share(scraper_session()) == 1.0
    assert f.missing_referer_share(session([req(0, "/")])) == 0.0  # ensimmäinen sivu ei lasketa


@pytest.mark.parametrize(
    ("ua", "tool", "bot"),
    [
        (CHROME_UA, False, False),
        (CURL_UA, True, False),
        ("python-requests/2.32.3", True, False),
        ("Go-http-client/1.1", True, False),
        ("", True, False),
        ("   ", True, False),
        (GOOGLEBOT_UA, False, True),
        ("Mozilla/5.0 (compatible; bingbot/2.0)", False, True),
        ("Mozilla/5.0 (compatible; AhrefsBot/7.0)", False, True),
        ("facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", False, False),
    ],
)
def test_ua_tool_and_bot_claims(ua, tool, bot):
    assert f.ua_is_tool(ua) is tool
    assert f.ua_claims_bot(ua) is bot


# --- kokonaisuus ---------------------------------------------------------------


def test_compute_features_separates_archetypes():
    h = f.compute_features(human_session())
    c = f.compute_features(curl_scanner_session())
    s = f.compute_features(scraper_session())

    assert h.static_share > 0.5 and h.vuln_path_hits == 0 and h.header_inconsistency_share == 0
    assert not h.ua_is_tool

    assert c.ua_is_tool and c.vuln_path_hits >= 5 and c.not_found_share > 0.8
    assert c.static_share == 0.0

    assert s.static_share == 0.0 and s.header_inconsistency_share == 1.0
    assert s.interarrival_cv == pytest.approx(0.0)


def test_features_are_json_serialisable_and_finite():
    d = f.compute_features(human_session()).to_dict()
    json.dumps(d)
    for k, v in d.items():
        if isinstance(v, float):
            assert math.isfinite(v), k
