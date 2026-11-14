"""Integraatio: A:n lokinäyte (S1) + lukija (S3) + ansat (S11) → B:n putki.

Näyte on A:n mukaan synteettinen ja pieni (6 riviä, 3 sessiota). Testi varmistaa,
että muodot sopivat yhteen — ei tunnistuksen laatua.
"""

import json

import pytest

from bouncer.contracts import IpIntel
from bouncer.eval.dataset import build_dataset
from bouncer.eval.feature_report import feature_report, to_markdown
from bouncer.ingest.sample import load_sample_data
from bouncer.session import rules, score
from bouncer.session.features import compute_features


@pytest.fixture(scope="module")
def sample():
    return load_sample_data()


def _by_ua(sessions, token):
    return next(s for s in sessions if token in s.user_agent)


def test_sample_loads_into_b_dataset(sample):
    sessions, labels = sample
    ds = build_dataset(sessions, labels, traps=rules.load_traps())
    assert len(sessions) == 3
    assert ds.summary()["by_origin_source_truth"] == {"simulated/sim/bad_bot": 1}
    assert ds.unmapped_classes == {}  # A:n "scanner" tunnetaan
    assert ds.rows[0].campaign_id == "campaign-scan-01"


def test_traps_file_from_a_is_read():
    traps = rules.load_traps()
    assert "/.well-known/bouncer-canary" in traps


def test_sample_verdicts(sample):
    sessions, _ = sample
    curl = score(_by_ua(sessions, "curl/"), None, None)
    assert curl.label == "bad_bot"
    assert curl.reasons[0].startswith("Probed 2 known vulnerability paths")

    gb = _by_ua(sessions, "Googlebot")
    assert score(gb, None, None).label == "uncertain"  # ei C:n tietoa → ei päätöstä
    assert score(gb, IpIntel(verified_bot=True), None).label == "good_bot"
    assert score(gb, IpIntel(verified_bot=False), None).label == "bad_bot"

    chrome = score(_by_ua(sessions, "Chrome/"), None, None)
    assert chrome.label == "uncertain"  # säännöt eivät koskaan päätä "human"


def test_caddy_headers_reach_b_features(sample):
    sessions, _ = sample
    chrome = _by_ua(sessions, "Chrome/")
    f = compute_features(chrome)
    assert f.static_share == pytest.approx(2 / 3)
    # Näytteen Chrome-pyynnöstä puuttuu Sec-CH-UA (oikea Chrome lähettää sen
    # HTTPS:llä) → havainto. Tarkistettava oikeasta lokista B-3:ssa.
    assert f.header_inconsistency_share == 1.0
    page = next(r for r in chrome.requests if r.path == "/")
    assert page.headers["accept-language"].startswith("fi-FI")
    assert page.content_type == "text/html"


def test_feature_report_runs_on_sample(sample):
    sessions, labels = sample
    rep = feature_report(build_dataset(sessions, labels))
    json.dumps(rep)
    assert "## simulated/bad_bot" in to_markdown(rep)


def test_session_ids_are_strings_per_contract(sample):
    sessions, labels = sample
    assert all(isinstance(s.id, str) for s in sessions)
    assert all(isinstance(lab.session_id, str) for lab in labels)
