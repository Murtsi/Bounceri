"""Kohdat 4–5: allekirjoitetut `X-Sim-Run`-merkinnät ja kirjautumistunnus lokista."""

from __future__ import annotations

from bouncer.db import load_sessions
from bouncer.db.store import _serialize_session, _write_raw
from bouncer.ingest import simrun
from bouncer.ingest.sample import parse_access_record, parse_access_records
from bouncer.ingest.simrun import IngestStats
from bouncer.network import find_campaigns

SECRET = "test-secret"  # testiarvo, ei oikea avain


def _rec(ts, ip="203.0.113.9", method="GET", uri="/", status=200, headers=None, resp=None):
    return {
        "ts": ts,
        "request": {
            "remote_ip": ip,
            "method": method,
            "uri": uri,
            "proto": "HTTP/2.0",
            "headers": {"User-Agent": ["curl/8.5.0"], **(headers or {})},
        },
        "status": status,
        "size": 10,
        "resp_headers": {"Content-Type": ["text/plain"], **(resp or {})},
    }


def _signed(marker, secret=SECRET):
    return {"X-Sim-Run": [marker], "X-Sim-Sig": [simrun.sign(marker, secret)]}


# --- kohta 4: allekirjoitus -------------------------------------------------------


def test_sign_and_verify():
    sig = simrun.sign("run-1:scanner", SECRET)
    assert simrun.verify("run-1:scanner", sig, SECRET)
    assert simrun.verify("run-1:scanner", sig.upper(), SECRET)
    assert not simrun.verify("run-1:human", sig, SECRET)  # eri merkintä
    assert not simrun.verify("run-1:scanner", sig, "other")  # eri avain
    assert not simrun.verify("run-1:scanner", "", SECRET)


def test_signed_marker_is_accepted_and_headers_are_stripped():
    req, marker = parse_access_record(
        _rec("2026-11-14T12:00:00Z", headers=_signed("r1:scanner")), secret=SECRET
    )
    assert marker == "r1:scanner"
    assert "x-sim-run" not in req.headers and "x-sim-sig" not in req.headers


def test_forged_or_unsigned_marker_is_ignored_when_secret_is_set():
    stats = IngestStats()
    forged = {"X-Sim-Run": ["x:human"], "X-Sim-Sig": ["00" * 32]}
    _, m1 = parse_access_record(
        _rec("2026-11-14T12:00:00Z", headers=forged), secret=SECRET, stats=stats
    )
    _, m2 = parse_access_record(
        _rec("2026-11-14T12:00:01Z", headers={"X-Sim-Run": ["x:human"]}), secret=SECRET, stats=stats
    )
    assert m1 is None and m2 is None
    assert stats.unsigned_markers == 2


def test_without_secret_unsigned_markers_work_for_local_dev():
    _, marker = parse_access_record(
        _rec("2026-11-14T12:00:00Z", headers={"X-Sim-Run": ["r:scanner"]}), secret=None
    )
    assert marker == "r:scanner"


def test_secret_is_read_from_env(monkeypatch):
    monkeypatch.setenv(simrun.SECRET_ENV, SECRET)
    _, unsigned = parse_access_record(
        _rec("2026-11-14T12:00:00Z", headers={"X-Sim-Run": ["x:human"]})
    )
    _, signed = parse_access_record(_rec("2026-11-14T12:00:00Z", headers=_signed("r:scanner")))
    assert unsigned is None and signed == "r:scanner"


def test_invalid_marker_does_not_stop_ingest():
    stats = IngestStats()
    records = [
        _rec("2026-11-14T12:00:00Z", ip="198.51.100.1", headers={"X-Sim-Run": ["just-a-run"]}),
        _rec("2026-11-14T12:00:00Z", ip="198.51.100.2", headers={"X-Sim-Run": ["r2:scanner"]}),
    ]
    sessions, labels = parse_access_records(records, secret=None, stats=stats)
    assert len(sessions) == 2
    assert [lab.sim_class for lab in labels] == ["scanner"]
    assert stats.invalid_markers == 1


# --- kohta 5: kirjautumistunnus --------------------------------------------------


def test_login_username_comes_from_site_response_header_only_on_post_login():
    login = _rec(
        "2026-11-14T12:00:00Z",
        method="POST",
        uri="/login",
        status=401,
        resp={"X-Login-User": ["Admin"]},
    )
    other = _rec(
        "2026-11-14T12:00:01Z", method="GET", uri="/login", resp={"X-Login-User": ["admin"]}
    )
    stats = IngestStats()
    r1, _ = parse_access_record(login, stats=stats)
    r2, _ = parse_access_record(other, stats=stats)
    assert r1.username == "Admin" and r2.username is None
    assert stats.login_events == 1
    assert "x-login-user" not in r1.headers  # vastausotsake ei päädy pyynnön otsakkeisiin


def test_username_survives_the_store(tmp_path):
    rec = _rec(
        "2026-11-14T12:00:00Z",
        method="POST",
        uri="/login",
        status=401,
        resp={"X-Login-User": ["admin"]},
    )
    sessions, _ = parse_access_records([rec], secret=None)
    path = tmp_path / "store.json"
    _write_raw(
        {"sessions": [_serialize_session(s) for s in sessions], "labels": [], "synthetic": True},
        path,
    )
    loaded = load_sessions(path=path)
    assert loaded[0].requests[0].username == "admin"


def test_c_finds_stuffing_when_username_is_only_in_the_site_response():
    """Oikea hyökkääjä ei lähetä tunnusta otsakkeessa: se on lomakkeen rungossa, jota
    Caddy ei lokita. Demosivu kertoo sen vastausotsakkeessa → C löytää kampanjan."""
    records = [
        _rec(
            f"2026-11-14T13:00:{10 * i:02d}Z",
            ip=f"203.0.113.{i + 1}",
            method="POST",
            uri="/login",
            status=401,
            resp={"X-Login-User": ["admin"]},
        )
        for i in range(4)
    ]
    sessions, _ = parse_access_records(records, secret=None)
    assert all(s.requests[0].username == "admin" for s in sessions)
    assert all("x-login-user" not in s.requests[0].headers for s in sessions)
    camps = find_campaigns(sessions, include_behavior=False)
    stuffing = [c for c in camps if c.kind == "credential_stuffing"]
    assert stuffing and set(stuffing[0].session_ids) == {s.id for s in sessions}
