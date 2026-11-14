"""Private bounded replay metadata, isolated from detector inputs and model labels."""

from __future__ import annotations

import json
import os
import secrets
from collections import deque
from pathlib import Path


class EpisodeLog:
    def __init__(self, directory: Path, *, max_bytes=1_000_000, backups=2):
        if not 256 <= max_bytes <= 2_000_000 or not 1 <= backups <= 3:
            raise ValueError("Replay log limits are invalid")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / "episodes.jsonl"
        self.max_bytes, self.backups = max_bytes, backups
        self._repair_tail()

    def _repair_tail(self):
        if not self.path.exists() or not self.path.stat().st_size:
            return
        with self.path.open("r+b") as target:
            size = target.seek(0, os.SEEK_END)
            target.seek(max(0, size - self.max_bytes - 1))
            offset = target.tell()
            tail = target.read(self.max_bytes + 1)
            if tail.endswith(b"\n"):
                return
            last = tail.rfind(b"\n")
            if last < 0 and offset:
                raise ValueError("Replay log has an oversized partial record")
            target.truncate(offset + last + 1)

    def append(self, event: dict):
        encoded = (json.dumps(event, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if len(encoded) > min(65_536, self.max_bytes):
            raise ValueError("Replay metadata exceeds its bounded record size")
        if self.path.exists() and self.path.stat().st_size + len(encoded) > self.max_bytes:
            for number in range(self.backups, 1, -1):
                previous = self.directory / f"episodes.jsonl.{number - 1}"
                if previous.exists():
                    previous.replace(self.directory / f"episodes.jsonl.{number}")
            self.path.replace(self.directory / "episodes.jsonl.1")
        with self.path.open("ab") as target:
            os.chmod(self.path, 0o600)
            target.write(encoded)
            target.flush()
            os.fsync(target.fileno())

    def recent_pairs(self, episodes: int | None = None) -> set[tuple[str, str]]:
        if episodes is not None and not 1 <= episodes <= 4096:
            raise ValueError("Recent episode bound is invalid")
        recent: deque[list] = deque(maxlen=episodes)
        paths = [self.directory / f"episodes.jsonl.{n}" for n in range(self.backups, 0, -1)]
        for path in [*paths, self.path]:
            if not path.exists():
                continue
            with path.open("rb") as source:
                source.seek(max(0, path.stat().st_size - self.max_bytes))
                for raw in source.read(self.max_bytes).splitlines():
                    try:
                        item = json.loads(raw)
                    except (ValueError, UnicodeError):
                        continue
                    if not isinstance(item, dict):
                        continue
                    keys = item.get("session_keys")
                    if item.get("type") == "planned" and isinstance(keys, list) and len(keys) <= 24:
                        recent.append(keys)
        return {
            (pair[0], pair[1])
            for keys in recent
            for pair in keys
            if isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(value, str) for value in pair)
        }


def fresh_episode(
    factory, state: EpisodeLog, *, seed_factory=None, base="http://simulation-gateway:8080"
):
    """Recordable fresh entropy plus a restart-aware session-identity exclusion."""
    random_seed = seed_factory or secrets.randbits
    recent = state.recent_pairs()
    for _ in range(32):
        episode = factory(random_seed(128), secrets.token_hex(12), base=base)
        if not recent.intersection((actor.ip, actor.ua) for actor in episode.actors):
            return episode
    raise ValueError("Could not allocate a fresh episode without reference-label collisions")
