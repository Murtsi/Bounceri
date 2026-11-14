"""Integraatio: C:n `ip_intel_contract()` + `find_campaigns()` → B:n `score()`.

DNS-haut korvataan mockilla (ei verkkoa). Aineistot: A:n näyte (S1) ja C:n
tunnusten kokeilun fixture, jotka luetaan A:n parserilla.
"""

import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from bouncer.contracts import IpIntel
from bouncer.eval.run import network_signals
from bouncer.ingest.sample import load_sample_data
from bouncer.network import find_campaigns, ip_intel_contract, network_pass
from bouncer.session import score

STUFFING = Path(__file__).resolve().parents[1] / "c" / "fixtures" / "stuffing_access.jsonl"
GB_HOST = "crawl-192-0-2-15.googlebot.com"


def _no_ptr(*_a, **_k):
    raise OSError("offline")


@pytest.fixture(scope="module")
def stuffing():
    sessions, labels = load_sample_data(STUFFING)
    with patch("bouncer.network.bots.socket.gethostbyaddr", side_effect=_no_ptr):
        intel, camps = network_signals(sessions, ip_intel_contract, find_campaigns)
    return sessions, labels, intel, camps


def test_c_intel_is_contract_type(stuffing):
    _, _, intel, _ = stuffing
    assert intel and all(type(i) is IpIntel for i in intel.values())
    assert all(i.verified_bot is None for i in intel.values())  # DNS-virhe → ei tarkistettu (040)


def test_c_campaign_reaches_every_stuffing_session(stuffing):
    sessions, labels, _, camps = stuffing
    stuffed = {lab.session_id for lab in labels if lab.sim_class == "credential_stuffing"}
    assert stuffed and stuffed <= set(camps)
    assert {c.kind for c in camps.values()} == {"credential_stuffing"}


def test_b_scores_with_c_signals(stuffing):
    sessions, _, intel, camps = stuffing
    for s in sessions:
        v = score(s, intel.get(s.ip), camps.get(s.id))
        assert v.label in {"human", "good_bot", "bad_bot", "uncertain"}
        assert 1 <= len(v.reasons) <= 3


def test_raw_network_pass_keys_are_strings_while_a_ids_are_int():
    """Dokumentoi integraatioriskin A:n workerille: C:n `campaign_by_session` on
    str-avaiminen, A:n lukija antaa vielä int-ID:t → suora haku `s.id`:llä ei osu.
    B:n `network_signals` yhdistää ID:t merkkijonoina, joten B ei ole altis tälle."""
    sessions, _ = load_sample_data(STUFFING)
    with patch("bouncer.network.bots.socket.gethostbyaddr", side_effect=_no_ptr):
        res = network_pass(sessions, include_behavior=False)
    by_sess = res["campaign_by_session"]
    assert by_sess and all(isinstance(k, str) for k in by_sess)
    if all(isinstance(s.id, int) for s in sessions):  # poistuu kun A korjaa ID:t
        assert not any(s.id in by_sess for s in sessions)
        assert any(str(s.id) in by_sess for s in sessions)


def test_verified_googlebot_from_a_sample_is_good_bot():
    sessions, _ = load_sample_data()
    gb = next(s for s in sessions if "Googlebot" in s.user_agent)
    with (
        patch("bouncer.network.bots.socket.gethostbyaddr", return_value=(GB_HOST, [], [gb.ip])),
        patch(
            "bouncer.network.bots.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (gb.ip, 0))],
        ),
    ):
        intel = ip_intel_contract(gb.ip)
    assert intel.verified_bot is True
    assert score(gb, intel, None).label == "good_bot"


def test_spoofed_googlebot_from_a_sample_is_bad_bot():
    sessions, _ = load_sample_data()
    gb = next(s for s in sessions if "Googlebot" in s.user_agent)
    with (
        patch("bouncer.network.bots.socket.gethostbyaddr", return_value=(GB_HOST, [], [gb.ip])),
        patch(
            "bouncer.network.bots.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))],
        ),
    ):
        intel = ip_intel_contract(gb.ip)
    assert intel.verified_bot is False  # PTR näyttää Googlelta, forward ei täsmää
    assert score(gb, intel, None).label == "bad_bot"
