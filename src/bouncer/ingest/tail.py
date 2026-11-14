"""Checkpointed JSONL reads, including retained Caddy rotation archives."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class _SourceMoved(Exception):
    pass


class LogTail:
    BATCH_BYTES = 1024 * 1024
    LINE_BYTES = 256 * 1024
    SEGMENTS = 128

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.inode: int | None = None
        self.device: int | None = None
        self.partial = b""
        self.generation = uuid.uuid4().hex
        self.anchor = ""
        self.bad_lines = 0
        self.rotation_gaps = 0
        self.events: list[dict[str, Any]] = []
        self.initialized = False
        self.finished = False
        self.discarding = False
        self.seen: list[dict[str, Any]] = []
        self.pending: list[dict[str, Any]] = []

    def checkpoint(self) -> dict[str, Any]:
        state = {key: copy.deepcopy(getattr(self, key)) for key in (
            "offset", "inode", "device", "generation", "anchor", "bad_lines",
            "rotation_gaps", "initialized", "finished", "discarding", "seen", "pending"
        )}
        state["partial"] = self.partial.hex()
        return state

    def restore(self, state: dict[str, Any]) -> None:
        def require(condition):
            if not condition:
                raise ValueError("invalid log checkpoint")

        try:
            candidate = LogTail(self.path)
            for key in candidate.checkpoint():
                setattr(candidate, key, copy.deepcopy(state[key]))
            candidate.partial = bytes.fromhex(state["partial"])
            uuid.UUID(hex=candidate.generation)
            for key in ("offset", "bad_lines", "rotation_gaps"):
                require(type(getattr(candidate, key)) is int and getattr(candidate, key) >= 0)
            require((candidate.inode is None) == (candidate.device is None))
            for key in ("inode", "device"):
                value = getattr(candidate, key)
                require(value is None or type(value) is int and value >= 0)
            require(len(candidate.partial) <= min(candidate.offset, self.LINE_BYTES))
            require(b"\n" not in candidate.partial)
            for key in ("initialized", "finished", "discarding"):
                require(type(getattr(candidate, key)) is bool)
            require(not candidate.discarding or not candidate.partial)
            require(isinstance(candidate.anchor, str))
            require(not candidate.anchor or len(bytes.fromhex(candidate.anchor)) == 32)
            require(candidate.offset == 0 or candidate.anchor and candidate.inode is not None)
            for entries, completed in ((candidate.seen, True), (candidate.pending, False)):
                require(isinstance(entries, list) and len(entries) <= self.SEGMENTS)
                for entry in entries:
                    require(isinstance(entry, dict) and self._allowed(entry["name"]))
                    require(Path(entry["name"]).name == entry["name"])
                    for key in ("inode", "device"):
                        require(type(entry[key]) is int and entry[key] >= 0)
                    if completed:
                        require(type(entry["offset"]) is int and entry["offset"] >= 0)
                        require(len(bytes.fromhex(entry["anchor"])) == 32)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("invalid log checkpoint") from exc
        self.__dict__.update(candidate.__dict__)

    def _allowed(self, name: str) -> bool:
        return name.startswith(self.path.name) or name.startswith(self.path.stem + "-")

    @staticmethod
    def _name(path: Path) -> str:
        return path.name.removesuffix(".gz")

    @contextmanager
    def _open(self, path: Path):
        if path.is_symlink():
            raise OSError("symlink log sources are not supported")
        with path.open("rb") as raw:
            info = os.fstat(raw.fileno())
            if not stat.S_ISREG(info.st_mode) or path.is_symlink():
                raise OSError("log source must be a regular file")
            if path.suffix == ".gz":
                with gzip.GzipFile(fileobj=raw) as source:
                    yield source, info
            else:
                yield raw, info

    @staticmethod
    def _hash(source, size: int | None = None):
        digest = hashlib.sha256()
        count = 0
        while size is None or count < size:
            chunk = source.read(65536 if size is None else min(65536, size - count))
            if not chunk:
                break
            digest.update(chunk)
            count += len(chunk)
        return digest, count

    def _signature(self, path: Path) -> dict[str, Any]:
        with self._open(path) as (source, info):
            digest, count = self._hash(source)
        return {"name": self._name(path), "inode": info.st_ino, "device": info.st_dev,
                "offset": count, "anchor": digest.hexdigest()}

    def _matches(self, path: Path, entry: dict[str, Any], *, prefix=False) -> bool:
        info = path.stat()
        same_inode = (info.st_ino, info.st_dev) == (entry["inode"], entry["device"])
        if same_inode and (prefix or "anchor" not in entry):
            return True
        if prefix and path == self.path:
            return False
        if not prefix and not same_inode and self._name(path) != entry["name"]:
            return False
        if "anchor" not in entry:
            return self._name(path) == entry["name"]
        if prefix and not entry["offset"]:
            return False
        with self._open(path) as (source, _):
            digest, count = self._hash(source, entry["offset"])
            return (count == entry["offset"] and digest.hexdigest() == entry["anchor"]
                    and (prefix or not source.read(1)))

    def _inventory(self) -> tuple[list[Path], Path | None]:
        archives = []
        current = None
        for path in self.path.parent.iterdir():
            if not self._allowed(path.name) or path.is_symlink() or not path.is_file():
                continue
            if path == self.path:
                current = path
            else:
                archives.append(path)
                if len(archives) > self.SEGMENTS:
                    raise RuntimeError("too many retained log segments")

        def order(path):
            suffix = self._name(path).removeprefix(self.path.name + ".")
            if suffix.isdecimal():
                return (0, -int(suffix), "")
            return (1, 0, self._name(path))

        archives.sort(key=order)
        return archives, current

    def _remember(self, entry: dict[str, Any], archives: list[Path]) -> None:
        self.seen.append(entry)
        if len(self.seen) > self.SEGMENTS:
            drop = next((i for i, item in enumerate(self.seen)
                         if not any(self._matches(path, item) for path in archives)), None)
            if drop is None:
                raise RuntimeError("log segment registry is full")
            self.seen.pop(drop)

    def _new_segment(self) -> None:
        self.offset = 0
        self.partial = b""
        self.anchor = ""
        self.inode = self.device = None
        self.generation = uuid.uuid4().hex
        self.finished = self.discarding = False

    def _read(self, path: Path) -> tuple[list[dict[str, Any]], bool]:
        with self._open(path) as (source, info):
            if (path == self.path and self.inode is not None
                    and (info.st_ino, info.st_dev) != (self.inode, self.device)):
                raise _SourceMoved
            digest, count = self._hash(source, self.offset)
            if count != self.offset or self.anchor and digest.hexdigest() != self.anchor:
                if (path != self.path and self.inode is not None
                        and (info.st_ino, info.st_dev) != (self.inode, self.device)):
                    raise _SourceMoved
                self._new_segment()
                source.seek(0)
                digest = hashlib.sha256()
            chunk = source.read(self.BATCH_BYTES)
            digest.update(chunk)
            new_offset = self.offset + len(chunk)
            # Verify the consumed snapshot before publishing bytes or advancing its checkpoint.
            source.seek(0)
            verified, verified_count = self._hash(source, new_offset)
            if verified_count != new_offset or verified.digest() != digest.digest():
                raise RuntimeError("log changed while being read; retry this checkpoint")
            eof = not source.read(1)
        start = self.offset - len(self.partial)
        data = self.partial + chunk
        self.offset = new_offset
        self.inode, self.device = info.st_ino, info.st_dev
        self.anchor = digest.hexdigest()
        if self.discarding:
            end = data.find(b"\n")
            if end < 0:
                return [], eof
            data = data[end + 1:]
            start += end + 1
            self.discarding = False
        lines = data.split(b"\n")
        self.partial = lines.pop()
        if len(self.partial) > self.LINE_BYTES:
            self.partial = b""
            self.discarding = True
            self.bad_lines += 1
        rows = []
        for raw in lines:
            byte_offset = start
            start += len(raw) + 1
            if len(raw) > self.LINE_BYTES:
                self.bad_lines += 1
                continue
            raw = raw.replace(b"\x00", b"").strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except ValueError:
                self.bad_lines += 1
                continue
            if isinstance(row, dict) and isinstance(row.get("request"), dict):
                rows.append(row)
                self.events.append({"generation": self.generation, "byte_offset": byte_offset,
                                    "record": row})
            else:
                self.bad_lines += 1
        return rows, eof

    def read_new(self) -> list[dict[str, Any]]:
        saved = self.checkpoint()
        self.events = []
        try:
            return self._read_new()
        except Exception:
            self.restore(saved)
            raise

    def _read_new(self, retries=0) -> list[dict[str, Any]]:
        try:
            archives, current = self._inventory()
        except FileNotFoundError:
            if not self.path.parent.exists():
                return []
            raise
        if not self.initialized:
            if current is None:
                return []
            info = current.stat()
            self.inode, self.device = info.st_ino, info.st_dev
            for path in archives:
                self._remember(self._signature(path), archives)
            self.initialized = True
        available = [path for path in archives
                     if not any(self._matches(path, entry) for entry in self.seen)]
        for pending in self.pending[:]:
            if not any(self._matches(path, pending) for path in available):
                self.rotation_gaps += 1
                self.pending.remove(pending)
        for path in available:
            if not any(self._matches(path, entry) for entry in self.pending):
                info = path.stat()
                self.pending.append({"name": self._name(path), "inode": info.st_ino,
                                     "device": info.st_dev})
        if len(self.pending) > self.SEGMENTS:
            raise RuntimeError("too many pending log segments")
        target = None
        if self.inode is not None and not self.finished:
            active = {"inode": self.inode, "device": self.device, "offset": self.offset,
                      "anchor": self.anchor}
            # Prefer the old inode, then its compressed copy, before the current log.
            paths = available + ([current] if current else [])
            target = next((path for path in paths if self._matches(path, active, prefix=True)),
                          None)
            if target is None:
                self.rotation_gaps += 1
        if target is None:
            target = available[0] if available else current
            if target is None:
                return []
            if self.inode is not None:
                self._new_segment()
        try:
            rows, eof = self._read(target)
        except _SourceMoved:
            if retries >= 3:
                raise RuntimeError("log keeps rotating while being opened") from None
            return self._read_new(retries + 1)
        self.pending = [entry for entry in self.pending if not self._matches(target, entry)]
        if target != self.path and eof:
            if self.partial:
                self.bad_lines += 1
                self.partial = b""
            self.discarding = False
            self.finished = True
            self._remember({"name": self._name(target), "inode": self.inode,
                            "device": self.device, "offset": self.offset,
                            "anchor": self.anchor}, archives)
            if not rows:
                return self._read_new()
        return rows
