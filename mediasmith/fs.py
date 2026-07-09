"""Cached directory listings — the NAS-performance layer.

Two rules (measured in v1 against the SMB library — 7.7s vs 0.01s for a
3,000-entry folder):

1. List with ``os.scandir`` and use the DirEntry's own type information;
   never issue one ``stat`` per entry.
2. Cache listings for the life of the process, keyed by the directory's
   mtime signature. A revisit costs one ``stat``; any change to the
   directory's contents changes its signature, so staleness is impossible.

``CachedPath`` closes the loop for widgets that call ``Path.is_dir()`` per
entry (Textual's DirectoryTree does, twice): it answers from the listing
instead of the filesystem.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_cache: dict[str, tuple[tuple[int, int, int], tuple["Entry", ...]]] = {}

_digit_runs = re.compile(r"(\d+)")


def sort_key(name: str) -> tuple:
    """Finder-style ordering: case-insensitive, digit runs compare as numbers
    ("2 Song" before "10 Song"), files and folders interleaved.

    Splitting on a captured digit run alternates text/digit chunks starting
    with text, so same-index chunks always share a type and tuples compare.
    """
    return tuple(int(chunk) if chunk.isdigit() else chunk.lower()
                 for chunk in _digit_runs.split(name))


@dataclass(frozen=True, slots=True)
class Entry:
    name: str
    is_dir: bool


def clear_cache() -> None:
    _cache.clear()


def list_dir(path: Path | str) -> tuple[Entry, ...]:
    """Entries of ``path`` in ``sort_key`` order. Raises OSError."""
    path = Path(path)
    st = path.stat()
    sig = (st.st_mtime_ns, st.st_ino, st.st_nlink)
    key = str(path)
    hit = _cache.get(key)
    if hit is not None and hit[0] == sig:
        return hit[1]

    entries: list[Entry] = []
    with os.scandir(path) as it:
        for e in sorted(it, key=lambda e: sort_key(e.name)):
            try:
                is_dir = e.is_dir()   # DirEntry type info — no stat round trip
            except OSError:
                is_dir = False
            entries.append(Entry(e.name, is_dir))
    result = tuple(entries)
    _cache[key] = (sig, result)
    return result


class CachedPath(Path):
    """A Path whose ``is_dir()`` answers from the listing, not the disk."""

    _ms_is_dir: bool

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return self._ms_is_dir


def cached_children(path: Path | str) -> list[CachedPath]:
    """Children of ``path`` as CachedPaths; empty list if unreadable."""
    path = Path(path)
    try:
        entries = list_dir(path)
    except OSError:
        return []
    children = []
    for entry in entries:
        child = CachedPath(path / entry.name)
        child._ms_is_dir = entry.is_dir
        children.append(child)
    return children
