"""Live-worker (MVP vaihe 3): lokin seuraus, vakaat ID:t, C+B-päätökset storeen."""

import json

from bouncer.contracts import IpIntel
from bouncer.ingest import simrun
from bouncer.ingest.worker import LogTail, Worker, main
from bouncer.network import find_campaigns

SECRET = "test-secret"  # testiarvo


def _rec(ts, ip, method="GET", uri="/", status=200, ua="curl/8.5.0", marker=None, resp=None):
    headers = {"User-Agent": [ua]}
    if marker:
        headers["X-Sim-Run"] = [marker]
        headers["X-Sim-Sig"] = [simrun.sign(marker, SECRET)]
    return {"ts": ts, "request": {"remote_ip": "172.18.0.1", "client_ip": ip, "method": method,
            "uri": uri, "headers": headers}, "status": status, "size": 1,
            "resp_headers": resp or {}}  # fmt: skip


def _write(path, rows, mode="a"):
    with path.open(mode) as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# --- LogTail --------------------------------------------------------------------


def test_tail_reads_increments_and_keeps_partial_line(tmp_path):
    log = tmp_path / "access.log"
    _write(log, [_rec(1.0, "198.51.100.1")], "w")
    with log.open("a") as f:
        f.write('{"ts": 2.0, "request": {"remote_ip"')  # kesken
    t = LogTail(log)
    assert len(t.read_new()) == 1
    with log.open("a") as f:
        f.write(': "1.2.3.4", "headers": {}}}\n')
    assert len(t.read_new()) == 1
    assert t.read_new() == []


def test_tail_skips_garbage_and_nul_bytes(tmp_path):
    log = tmp_path / "access.log"
    log.write_bytes(
        b"\x00\x00not json\n" + b"\x00" + json.dumps(_rec(1.0, "198.51.100.1")).encode() + b"\n{}\n"
    )
    t = LogTail(log)
    assert len(t.read_new()) == 1
    assert t.bad_lines == 2


def test_tail_handles_truncation_and_rotation(tmp_path):
    log = tmp_path / "access.log"
    _write(log, [_rec(1.0, "198.51.100.1"), _rec(2.0, "198.51.100.1")], "w")
    t = LogTail(log)
    assert len(t.read_new()) == 2
    _write(log, [_rec(3.0, "198.51.100.2")], "w")  # katkaistu ja kirjoitettu uudelleen
    assert len(t.read_new()) == 1
    log.rename(tmp_path / "access.log.1")
    _write(log, [_rec(4.0, "198.51.100.3")], "w")  # rotaatio: uusi tiedosto
    assert len(t.read_new()) == 1


# --- Worker ---------------------------------------------------------------------


def _worker(tmp_path, calls):
    def intel_fn(ip):
        calls.append(ip)
        return IpIntel(asn_type="datacenter")

    return Worker(tmp_path / "access.log", tmp_path / "store.json", secret=SECRET,
                  intel_fn=intel_fn, campaigns_fn=find_campaigns, synthetic=True)  # fmt: skip


def test_session_ids_are_stable_when_new_sessions_arrive(tmp_path):
    calls: list[str] = []
    log = tmp_path / "access.log"
    _write(log, [_rec(100.0, "203.0.113.50", uri="/a")], "w")
    w = _worker(tmp_path, calls)
    first = {s["ip"]: s["id"] for s in w.cycle()["sessions"]}
    _write(log, [_rec(101.0, "198.51.100.1", uri="/b")])  # lajittuu ennen ensimmäistä
    second = {s["ip"]: s["id"] for s in w.cycle()["sessions"]}
    assert second["203.0.113.50"] == first["203.0.113.50"]
    assert len(second) == 2


def test_cycle_scores_stuffing_and_caches_intel(tmp_path):
    calls: list[str] = []
    log = tmp_path / "access.log"
    rows = [_rec(200.0 + 5 * i, f"203.0.113.{100 + i}", method="POST", uri="/login", status=401,
                 marker="r1-stuff:credential_stuffing:camp-1", resp={"X-Login-User": ["admin"]})
            for i in range(6)]  # fmt: skip
    rows.append(_rec(300.0, "198.51.100.9", marker="x:human"))  # väärennetty: ei allekirjoitusta
    rows[-1]["request"]["headers"]["X-Sim-Sig"] = ["00"]
    _write(log, rows, "w")
    w = _worker(tmp_path, calls)
    p = w.cycle()
    w.cycle()
    assert len(calls) == len(set(calls)) == 7  # yksi C:n haku per IP, ei uudelleen
    labels = {lab["session_id"]: lab["sim_class"] for lab in p["labels"]}
    stuffed = [sid for sid, c in labels.items() if c == "credential_stuffing"]
    assert len(stuffed) == 6 and all(p["verdicts"][sid]["label"] == "bad_bot" for sid in stuffed)
    assert p["ingest"]["unsigned_markers"] == 1
    assert "x:human" not in json.dumps(p["labels"])
    v = p["verdicts"][stuffed[0]]
    assert v["campaign_id"] and v["explanation"].startswith("Verdict: bad_bot")
    assert json.loads((tmp_path / "store.json").read_text())["synthetic"] is True


def test_cli_requires_secret(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(simrun.SECRET_ENV, raising=False)
    assert (
        main(["--log", str(tmp_path / "x.log"), "--store", str(tmp_path / "s.json"), "--once"]) == 1
    )
    assert simrun.SECRET_ENV in capsys.readouterr().out


def test_worker_continues_after_invalid_record(tmp_path):
    rows = [_rec(100, "192.0.2.1"), _rec(101, "192.0.2.1"),
            _rec(102, "192.0.2.1", uri="/about")]
    rows[1]["status"] = "broken"
    _write(tmp_path / "access.log", rows, "w")
    worker = _worker(tmp_path, [])
    for _ in range(2):
        snapshot = worker.cycle()
        assert len(snapshot["sessions"][0]["requests"]) == 2
        assert snapshot["ingest"]["invalid_records"] == 1


def test_worker_preserves_double_slash_request_target(tmp_path):
    _write(tmp_path / "access.log", [_rec(100, "192.0.2.1", uri="//[")], "w")
    result = _worker(tmp_path, []).cycle()
    assert result["sessions"][0]["requests"][0]["path"] == "//["


def test_session_identity_survives_eviction_and_restart(tmp_path):
    log = tmp_path / "access.log"
    def worker():
        return Worker(log, tmp_path / "store.json", secret=SECRET, intel_fn=None,
                      campaigns_fn=None, synthetic=True, max_records=2)
    _write(log, [_rec(1000, "192.0.2.1"), _rec(1001, "192.0.2.1")], "w")
    w = worker()
    original = w.cycle()["sessions"][0]["id"]
    _write(log, [_rec(1002, "192.0.2.1")])
    assert w.cycle()["sessions"][0]["id"] == original
    w = worker()
    assert w.cycle()["sessions"][0]["id"] == original
    _write(log, [_rec(1400, "192.0.2.1")])
    latest = w.cycle()["sessions"][-1]
    assert latest["id"] != original
