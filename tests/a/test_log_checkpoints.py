import json

import pytest

from bouncer.ingest.worker import LogTail


def line(ts):
    return json.dumps({"ts": ts, "request": {"remote_ip": "192.0.2.1"}}).encode() + b"\n"


def test_resume_partial_line_keeps_event_identity(tmp_path):
    path = tmp_path / "access.log"
    raw = line(1)
    path.write_bytes(raw[:-2])
    tail = LogTail(path)
    assert tail.read_new() == []
    saved = tail.checkpoint()
    resumed = LogTail(path)
    resumed.restore(saved)
    with path.open("ab") as f:
        f.write(raw[-2:])
    assert resumed.read_new()[0]["ts"] == 1
    event = resumed.events[0]
    assert event["generation"] == saved["generation"]
    assert event["byte_offset"] == 0
    assert resumed.read_new() == []


def test_rotation_drains_old_inode_before_new_file_after_restart(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    saved = tail.checkpoint()
    with path.open("ab") as f:
        f.write(line(2))
    path.rename(tmp_path / "access.log.1")
    path.write_bytes(line(3))
    resumed = LogTail(path)
    resumed.restore(saved)
    rows = resumed.read_new() + resumed.read_new()
    assert [row["ts"] for row in rows] == [2, 3]
    assert resumed.checkpoint()["generation"] != saved["generation"]


def test_copy_truncate_regrowth_does_not_skip_new_prefix(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    saved = tail.checkpoint()
    path.write_bytes(line(222) + line(333))
    resumed = LogTail(path)
    resumed.restore(saved)
    rows = resumed.read_new()
    assert [row["ts"] for row in rows] == [222, 333]
    assert resumed.events[0]["byte_offset"] == 0
    assert resumed.events[0]["generation"] != saved["generation"]


def test_invalid_checkpoint_is_rejected_without_mutating_tail(tmp_path):
    tail = LogTail(tmp_path / "access.log")
    original = tail.checkpoint()
    with pytest.raises(ValueError):
        tail.restore(original | {"offset": -1})
    assert tail.checkpoint() == original


def drain(tail, cycles=8):
    rows = []
    events = []
    for _ in range(cycles):
        rows.extend(tail.read_new())
        events.extend(tail.events)
    return rows, events


def test_multiple_rotations_recover_every_retained_segment(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    saved = tail.checkpoint()
    with path.open("ab") as source:
        source.write(line(2))
    path.rename(tmp_path / "access.log.2")
    path.write_bytes(line(3))
    path.rename(tmp_path / "access.log.1")
    path.write_bytes(line(4))
    tail.restore(saved)
    rows, _ = drain(tail)
    assert [row["ts"] for row in rows] == [2, 3, 4]
    assert tail.rotation_gaps == 0


def test_gzip_rotation_keeps_old_generation_and_byte_offset(tmp_path):
    import gzip

    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    saved = tail.checkpoint()
    (tmp_path / "access-2026-11-14T01-00-00.log.gz").write_bytes(
        gzip.compress(line(1) + line(2))
    )
    path.unlink()
    path.write_bytes(line(3))
    resumed = LogTail(path)
    resumed.restore(saved)
    rows, events = drain(resumed)
    assert [row["ts"] for row in rows] == [2, 3]
    assert events[0]["generation"] == saved["generation"]
    assert events[0]["byte_offset"] == len(line(1))
    assert resumed.rotation_gaps == 0


def test_initial_archives_are_ignored_across_restart(tmp_path):
    import gzip

    (tmp_path / "access-2026-11-13T01-00-00.log.gz").write_bytes(gzip.compress(line(0)))
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    assert [row["ts"] for row in tail.read_new()] == [1]
    saved = tail.checkpoint()
    path.rename(tmp_path / "access-2026-11-14T01-00-00.log")
    path.write_bytes(line(2))
    resumed = LogTail(path)
    resumed.restore(saved)
    rows, _ = drain(resumed)
    assert [row["ts"] for row in rows] == [2]


def test_copytruncate_detects_change_before_identical_last_64_bytes(tmp_path):
    def padded(ts):
        return json.dumps({"ts": ts, "request": {}, "padding": "x" * 100}).encode() + b"\n"

    path = tmp_path / "access.log"
    path.write_bytes(padded(1))
    tail = LogTail(path)
    tail.read_new()
    path.write_bytes(padded(2))
    assert [row["ts"] for row in tail.read_new()] == [2]


def test_rotation_between_discovery_and_open_does_not_duplicate(tmp_path, monkeypatch):
    from pathlib import Path

    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    original = Path.open
    rotated = False

    def rotating_open(target, *args, **kwargs):
        nonlocal rotated
        if target == path and not rotated:
            rotated = True
            path.rename(tmp_path / "access.log.1")
            path.write_bytes(line(2))
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", rotating_open)
    rows, events = drain(LogTail(path))
    assert [row["ts"] for row in rows] == [1, 2]
    assert len({(event["generation"], event["byte_offset"]) for event in events}) == 2


def test_missing_saved_rotation_counts_gap(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    path.rename(tmp_path / "removed.log")
    path.write_bytes(line(2))
    rows, _ = drain(tail)
    assert [row["ts"] for row in rows] == [2]
    assert tail.rotation_gaps == 1


def test_copytruncate_during_snapshot_rolls_back_and_retries(tmp_path, monkeypatch):
    from contextlib import contextmanager

    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    original = tail._open
    changed = False

    class MutatingReader:
        def __init__(self, source):
            self.source = source

        def read(self, size=-1):
            nonlocal changed
            data = self.source.read(size)
            if data and not changed:
                changed = True
                path.write_bytes(line(2))
            return data

        def seek(self, *args):
            return self.source.seek(*args)

    @contextmanager
    def mutate(target):
        with original(target) as (source, info):
            yield MutatingReader(source), info

    saved = tail.checkpoint()
    monkeypatch.setattr(tail, "_open", mutate)
    with pytest.raises(RuntimeError, match="changed while"):
        tail.read_new()
    assert tail.checkpoint() == saved
    assert tail.events == []
    assert [row["ts"] for row in tail.read_new()] == [2]


def test_bounded_batches_and_oversized_partial_resume(tmp_path, monkeypatch):
    path = tmp_path / "access.log"
    path.write_bytes(b"x" * 100 + b"\n" + line(7))
    monkeypatch.setattr(LogTail, "BATCH_BYTES", 20)
    monkeypatch.setattr(LogTail, "LINE_BYTES", 64)
    tail = LogTail(path)
    for _ in range(4):
        assert tail.read_new() == []
        assert len(tail.partial) <= 64
    resumed = LogTail(path)
    resumed.restore(tail.checkpoint())
    rows, events = drain(resumed)
    assert [row["ts"] for row in rows] == [7]
    assert events[0]["byte_offset"] == 101
    assert resumed.bad_lines == 1


def test_pending_disappeared_rotation_counts_gap_once(tmp_path, monkeypatch):
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    with path.open("ab") as source:
        source.write(line(2) + line(3))
    path.rename(tmp_path / "access.log.2")
    (tmp_path / "access.log.1").write_bytes(line(4))
    path.write_bytes(line(5))
    monkeypatch.setattr(LogTail, "BATCH_BYTES", len(line(2)))
    assert [row["ts"] for row in tail.read_new()] == [2]
    (tmp_path / "access.log.1").unlink()
    rows, _ = drain(tail)
    assert [row["ts"] for row in rows] == [3, 5]
    assert tail.rotation_gaps == 1


def test_completed_rotation_survives_gzip_replacement_without_replay(tmp_path):
    import gzip

    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    with path.open("ab") as source:
        source.write(line(2))
    archive = tmp_path / "access-2026-11-14T01-00-00.log"
    path.rename(archive)
    path.write_bytes(line(3))
    assert [row["ts"] for row in tail.read_new()] == [2]
    saved = tail.checkpoint()
    (tmp_path / (archive.name + ".gz")).write_bytes(gzip.compress(archive.read_bytes()))
    archive.unlink()
    resumed = LogTail(path)
    resumed.restore(saved)
    rows, _ = drain(resumed)
    assert [row["ts"] for row in rows] == [3]
    assert resumed.rotation_gaps == 0


def test_missing_partly_drained_active_rotation_counts_one_gap(tmp_path, monkeypatch):
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    with path.open("ab") as source:
        source.write(line(2) + line(3))
    archive = tmp_path / "access.log.1"
    path.rename(archive)
    path.write_bytes(line(4))
    monkeypatch.setattr(LogTail, "BATCH_BYTES", len(line(2)))
    assert [row["ts"] for row in tail.read_new()] == [2]
    archive.unlink()
    rows, _ = drain(tail)
    assert [row["ts"] for row in rows] == [4]
    assert tail.rotation_gaps == 1


def test_registry_expires_removed_numeric_rotations(tmp_path, monkeypatch):
    path = tmp_path / "access.log"
    path.write_bytes(line(0))
    monkeypatch.setattr(LogTail, "SEGMENTS", 3)
    tail = LogTail(path)
    tail.read_new()
    for ts in range(1, 8):
        older = tmp_path / "access.log.2"
        older.unlink(missing_ok=True)
        recent = tmp_path / "access.log.1"
        if recent.exists():
            recent.rename(older)
        path.rename(recent)
        path.write_bytes(line(ts))
        rows, _ = drain(tail)
        assert [row["ts"] for row in rows] == [ts]
        assert len(tail.checkpoint()["seen"]) <= 3


def test_missing_log_directory_waits_without_advancing_checkpoint(tmp_path):
    tail = LogTail(tmp_path / "not-created" / "access.log")
    saved = tail.checkpoint()
    assert tail.read_new() == []
    assert tail.checkpoint() == saved


def test_missing_rotation_with_identical_current_prefix_starts_new_generation(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(line(1))
    tail = LogTail(path)
    tail.read_new()
    original_identity = (tail.events[0]["generation"], tail.events[0]["byte_offset"])
    path.rename(tmp_path / "removed.log")
    path.write_bytes(line(1) + line(2))
    resumed = LogTail(path)
    resumed.restore(tail.checkpoint())

    rows, events = drain(resumed)

    assert [row["ts"] for row in rows] == [1, 2]
    assert resumed.rotation_gaps == 1
    assert len(events) == 2
    assert all((event["generation"], event["byte_offset"]) != original_identity
               for event in events)
    assert len({(event["generation"], event["byte_offset"]) for event in events}) == 2


def test_copytruncate_reused_archive_inode_recovers_every_unread_row(tmp_path):
    path = tmp_path / "access.log"
    archive = tmp_path / "access.log.1"
    path.write_bytes(line(1))
    tail = LogTail(path)
    assert [row["ts"] for row in tail.read_new()] == [1]
    identities = []

    for unread, current in ((2, 3), (4, 5)):
        with path.open("ab") as source:
            source.write(line(unread))
        archive.write_bytes(path.read_bytes())
        path.write_bytes(line(current))
        rows, events = drain(tail)
        assert [row["ts"] for row in rows] == [unread, current]
        identities.extend((event["generation"], event["byte_offset"]) for event in events)

    assert tail.rotation_gaps == 0
    assert len(identities) == len(set(identities)) == 4
