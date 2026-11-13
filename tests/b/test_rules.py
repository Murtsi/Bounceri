import pytest

from bouncer.session import rules, score
from bouncer.session._provisional_types import IpIntel
from bouncer.session.score import NO_SIGNAL_REASON

from .synthetic import (
    CURL_UA,
    GOOGLEBOT_UA,
    curl_scanner_session,
    googlebot_session,
    human_session,
    req,
    scraper_session,
    session,
)

TRAPS = rules.parse_traps(
    ["# ansat", "/wp-admin/", "/hidden-link  # piilolinkki", "", "/Admin-Old"]
)
NO_TRAPS: frozenset[str] = frozenset()


# --- ansalista -----------------------------------------------------------------


def test_parse_traps_normalises():
    assert frozenset({"/wp-admin", "/hidden-link", "/admin-old"}) == TRAPS


def test_load_traps_missing_file_is_empty(tmp_path):
    assert rules.load_traps(tmp_path / "nope.txt") == frozenset()


def test_load_traps_reads_file(tmp_path):
    p = tmp_path / "traps.txt"
    p.write_text("/trap-a\n/trap-b/\n", "utf-8")
    assert rules.load_traps(p) == frozenset({"/trap-a", "/trap-b"})


# --- säännöt -------------------------------------------------------------------


def test_trap_hit_is_bad_bot():
    s = session([req(0, "/"), req(1, "/hidden-link/")])
    v = score(s, None, None, traps=TRAPS)
    assert v.label == "bad_bot" and v.score == 1.0
    assert "/hidden-link/" in v.reasons[0]


def test_two_vuln_paths_is_bad_bot():
    v = score(curl_scanner_session(), None, None, traps=NO_TRAPS)
    assert v.label == "bad_bot"
    assert v.reasons[0].startswith("Kokeili 7 tunnettua haavoittuvuuspolkua")
    assert len(v.reasons) == 3


def test_single_vuln_path_is_not_certain():
    s = session([req(0, "/"), req(5, "/.env", status=404)])
    v = score(s, None, None, traps=NO_TRAPS)
    assert v.label == "uncertain"
    assert "Kokeili yhtä tunnettua haavoittuvuuspolkua" in v.reasons


def test_verified_crawler_is_good_bot():
    v = score(googlebot_session(), IpIntel(verified_bot=True), None, traps=NO_TRAPS)
    assert v.label == "good_bot" and v.score == 1.0


def test_verified_crawler_wins_over_trap():
    s = session([req(0, "/hidden-link", ua=GOOGLEBOT_UA)], ua=GOOGLEBOT_UA)
    v = score(s, IpIntel(verified_bot=True), None, traps=TRAPS)
    assert v.label == "good_bot"
    assert any("ansapolun" in r for r in v.reasons)  # ristiriita näkyy syissä


def test_fake_googlebot_is_bad_bot():
    v = score(googlebot_session(), IpIntel(verified_bot=False), None, traps=NO_TRAPS)
    assert v.label == "bad_bot"
    assert "googlebot" in v.reasons[0]


@pytest.mark.parametrize("intel", [None, IpIntel()])
def test_unchecked_googlebot_is_not_judged(intel):
    # C:n stub (verified_bot=None) ei saa leimata oikeaa Googlebotia väärennökseksi.
    v = score(googlebot_session(), intel, None, traps=NO_TRAPS)
    assert v.label == "uncertain"


def test_non_crawler_ua_with_failed_verification_is_not_fake_crawler():
    s = session([req(0, "/", ua=CURL_UA)], ua=CURL_UA)
    assert rules.fake_crawler_rule(s, IpIntel(verified_bot=False)) is None


# --- ei sääntöosumaa -----------------------------------------------------------


def test_human_is_uncertain_never_human_by_rules():
    v = score(human_session(), IpIntel(), None, traps=NO_TRAPS)
    assert v.label == "uncertain" and v.score == 0.5
    assert v.reasons == (NO_SIGNAL_REASON,)


def test_scraper_is_uncertain_with_observations():
    v = score(scraper_session(), None, None, traps=NO_TRAPS)
    assert v.label == "uncertain"
    assert 1 <= len(v.reasons) <= 3
    assert any("otsakkeita" in r for r in v.reasons)
    assert any("CSS/JS" in r for r in v.reasons)


@pytest.mark.parametrize(
    "make", [human_session, curl_scanner_session, scraper_session, googlebot_session]
)
def test_verdict_shape(make):
    v = score(make(), None, None, traps=NO_TRAPS)
    assert v.label in {"human", "good_bot", "bad_bot", "uncertain"}
    assert 0.0 <= v.score <= 1.0
    assert 1 <= len(v.reasons) <= 3
    assert len(set(v.reasons)) == len(v.reasons)
    assert v.model_version == "rules-v1"


def test_score_default_traps_file_missing_is_safe():
    # deploy/traps.txt ei ole vielä olemassa (A, S11) → oletuspolku toimii silti.
    assert score(human_session(), None, None).label == "uncertain"
