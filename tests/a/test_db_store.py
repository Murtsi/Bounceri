"""S3 local store: load_sessions / load_labels."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from bouncer.db import clear_store, load_labels, load_sessions, seed_from_sample


def test_empty_store_returns_empty_lists(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    assert load_sessions(path=path) == []
    assert load_labels(path=path) == []


def test_seed_and_load_string_ids(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    n_s, n_l = seed_from_sample(path=path)
    assert n_s >= 1
    sessions = load_sessions(path=path)
    labels = load_labels(path=path)
    assert len(sessions) == n_s
    assert len(labels) == n_l
    assert all(isinstance(s.id, str) for s in sessions)
    assert all(isinstance(lab.session_id, str) for lab in labels)
    assert {lab.session_id for lab in labels} <= {s.id for s in sessions}


def test_since_filter(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    seed_from_sample(path=path)
    future = datetime(2099, 1, 1, tzinfo=UTC)
    assert load_sessions(since=future, path=path) == []


def test_clear_store(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    seed_from_sample(path=path)
    clear_store(path)
    assert load_sessions(path=path) == []
