"""Malformed JSON text cannot stall durable log ingestion or poison simulator truth."""

import json

import pytest
from sqlalchemy import update

from bouncer.db.traffic import TrafficRepository, sources
from bouncer.ingest.sample import parse_access_record
from bouncer.ingest.simrun import IngestStats
from bouncer.ingest.tail import LogTail
from tests.a.test_migrations import engine, postgres_url  # noqa: F401
from tests.a.test_worker import SECRET, _rec
from tests.a.test_worker_durability import worker


@pytest.mark.parametrize("backend", ["json", "sqlite", "postgresql"])
def test_unsafe_text_advances_checkpoint_preserves_valid_traffic_and_restarts(
    tmp_path, request, backend
):
    repo = None
    if backend == "sqlite":
        repo = TrafficRepository(f"sqlite:///{tmp_path / 'traffic.db'}")
    elif backend == "postgresql":
        repo = TrafficRepository(request.getfixturevalue("engine"))
    rows, rejected, unsigned = [], 0, 0
    for unsafe in ("\ud800", "\0"):
        for location in ("unknown_value", "unknown_key", "uri", "header"):
            row = _rec(1000 + len(rows), "192.0.2.1")
            if location == "unknown_value":
                row["extra"] = unsafe
            elif location == "unknown_key":
                row[unsafe] = "extra"
            elif location == "uri":
                row["request"]["uri"] = "/" + unsafe
            else:
                row["request"]["headers"]["X-Extra"] = [unsafe]
            rows.append(row)
            rejected += 1
        for header in ("X-Sim-Run", "X-Sim-Sig"):
            row = _rec(1000 + len(rows), "192.0.2.1", marker="fixture:human")
            row["request"]["headers"][header] = [unsafe]
            rows.append(row)
            unsigned += 1
    row = _rec(1099, "192.0.2.1")
    row["extra"] = float("nan")
    rows.append(row)
    rejected += 1
    rows.append(_rec(1100, "192.0.2.2", uri="/valid-later"))
    rows.append(_rec(1101, "192.0.2.2", uri="/caf\u00e9/\U0001f916"))
    log = tmp_path / "access.log"
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    try:
        instance = worker(tmp_path, repo)
        result = instance.cycle()
        assert instance.tail.offset == log.stat().st_size
        assert result["ingest"]["bad_lines"] == rejected
        assert result["ingest"]["unsigned_markers"] == unsigned
        assert result["labels"] == []
        assert sum(len(s["requests"]) for s in result["sessions"]) == len(rows) - rejected
        assert any(r["path"] == "/valid-later"
                   for s in result["sessions"] for r in s["requests"])
        resumed = worker(tmp_path, repo)
        again = resumed.cycle()
        assert resumed.tail.offset == log.stat().st_size
        assert again["sessions"] == result["sessions"]
        assert again["ingest"]["unsigned_markers"] == unsigned
        if repo is not None:
            assert sum(len(s.requests) for s in repo.load_sessions(source_key="test")) == 6
    finally:
        if repo is not None:
            repo.engine.dispose()


@pytest.mark.parametrize("unsafe", ["\ud800", "\0"])
@pytest.mark.parametrize("header", ["X-Sim-Run", "X-Sim-Sig"])
@pytest.mark.parametrize("secret", [None, SECRET])
def test_direct_parser_rejects_unsafe_auth_without_losing_request(unsafe, header, secret):
    row = _rec(1000, "192.0.2.1", marker="fixture:human")
    row["request"]["headers"][header] = [unsafe]
    stats = IngestStats()
    observed, marker = parse_access_record(row, secret=secret, stats=stats)
    assert observed.ip == "192.0.2.1"
    assert marker is None
    assert stats.records == stats.unsigned_markers == 1


@pytest.mark.parametrize("unsafe", ["\ud800", "\0"])
def test_direct_parser_rejects_unsafe_core_text(unsafe):
    row = _rec(1000, "192.0.2.1", uri="/" + unsafe)
    with pytest.raises(ValueError):
        parse_access_record(row, secret=SECRET)


def test_literal_nul_in_request_is_rejected_without_changing_the_path(tmp_path):
    log = tmp_path / "access.log"
    bad = json.dumps(_rec(1000, "192.0.2.1", uri="/bad\0path")).encode()
    bad = bad.replace(b"\\u0000", b"\0")
    good = json.dumps(_rec(1001, "192.0.2.2", uri="/valid-later")).encode()
    log.write_bytes(bad + b"\n" + good + b"\n")
    tail = LogTail(log)
    rows = tail.read_new()
    assert tail.bad_lines == 1
    assert len(rows) == 1 and rows[0]["request"]["uri"] == "/valid-later"
    assert tail.offset == log.stat().st_size


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_legacy_resume_is_validated_before_records_can_be_retained_again(tmp_path, backend):
    repo = TrafficRepository(f"sqlite:///{tmp_path / 'legacy.db'}") if backend == "sqlite" else None
    log = tmp_path / "access.log"
    rows = [_rec(1000, "192.0.2.1"), _rec(1001, "192.0.2.2")]
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    try:
        before = worker(tmp_path, repo).cycle()
        path = tmp_path / "offline.json"
        saved = json.loads(path.read_text()) if repo is None else None
        state = saved["worker_resume_state"] if repo is None else repo.load_resume_state("test")
        state["records"][0]["unsafe-old-metadata"] = "\ud800"
        state["records"][1]["request"]["headers"]["X-Sim-Run"] = ["bad\0:human"]
        if repo is None:
            path.write_text(json.dumps(saved), encoding="utf-8")
        else:
            with repo.engine.begin() as conn:
                conn.execute(update(sources).where(sources.c.source_key == "test").values(
                    resume_state=state,
                ))
        instance = worker(tmp_path, repo)
        after = instance.cycle()
        assert after["ingest"]["bad_lines"] == after["ingest"]["unsigned_markers"] == 1
        assert after["labels"] == []
        assert len(after["sessions"]) == 1
        assert after["sessions"][0] == before["sessions"][1]
        assert instance.tail.offset == log.stat().st_size
        assert worker(tmp_path, repo).cycle()["sessions"] == after["sessions"]
    finally:
        if repo is not None:
            repo.engine.dispose()
