"""Folderize engine: organize audio files into Artist/Album folders.

Evaluated against mediasmith-v1 ``tools/audiosmith/folderize`` rather
than ported: v1's directory resolver refused to reuse a directory that
already existed, so re-running it on an organized library would have
rebuilt everything into ``Artist (1)/``. v2 reuses existing folders and
treats a file already sitting at ``…/Artist/Album/`` (by its own tags)
as in place — which is also what lets the UI show the folderize button
only when there is actually something to do.

Pure logic + filesystem moves; no widgets, no printing. Plans are
data; the pane renders them.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import kinds
from .text import sanitize_component as sanitize

SKIPPED_DIR_NAME = "* Skipped"

PROBE_BUDGET = 200
"""How many tag reads a background probe may spend before assuming an
unscanned subtree is organized (false negatives beat NAS meltdowns)."""


@dataclass(frozen=True)
class Move:
    source: Path
    target: Path


@dataclass(frozen=True)
class Skip:
    source: Path
    reason: str


@dataclass(frozen=True)
class FolderizePlan:
    root: Path
    moves: list[Move] = field(default_factory=list)
    skips: list[Skip] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.moves and not self.skips

    def structure(self) -> dict[str, dict[str, int]]:
        """{artist: {album: file count}} for rendering the preview."""
        out: dict[str, dict[str, int]] = {}
        for move in self.moves:
            album_dir = move.target.parent
            artist = album_dir.parent.name
            out.setdefault(artist, {})
            out[artist][album_dir.name] = out[artist].get(album_dir.name,
                                                          0) + 1
        return out


def read_tags(path: Path) -> dict[str, str]:
    """artist/album (first values, stripped) — empty dict if unreadable."""
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(path), easy=True)
    except Exception:
        return {}
    if audio is None or audio.tags is None:
        return {}

    def first(key: str) -> str:
        values = audio.tags.get(key, [])
        return str(values[0]).strip() if values else ""

    return {name: value
            for name in ("artist", "album") if (value := first(name))}


def find_audio(root: Path) -> list[Path]:
    """Every audio file under ``root``, hidden dirs skipped, sorted."""
    found: list[Path] = []
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append(Path(entry.path))
            elif Path(entry.name).suffix.lower() in kinds.AUDIO_EXTENSIONS:
                found.append(Path(entry.path))
    return sorted(found)


def _placement(file: Path, tags: dict[str, str],
               root: Path) -> tuple[str, Path | str]:
    """Classify one file: ("ok", target) | ("organized", "") |
    ("skip", reason)."""
    artist = tags.get("artist", "")
    album = tags.get("album", "")
    if not artist and not album:
        reason = "no artist or album tag"
    elif not artist:
        reason = "no artist tag"
    elif not album:
        reason = "no album tag"
    else:
        # already at <anything>/Artist/Album/file by its own tags: in
        # place, even when the highlighted root sits deeper or higher
        parent = file.parent
        if (parent.name == sanitize(album)
                and parent.parent.name == sanitize(artist)):
            return "organized", ""
        return "ok", root / sanitize(artist) / sanitize(album) / file.name
    if file.parent.name == SKIPPED_DIR_NAME:
        return "organized", ""      # already skipped: not actionable again
    return "skip", reason


def build_plan(root: Path) -> FolderizePlan:
    """The full folderize plan for ``root``. Reads tags of every audio
    file beneath it — run in a worker."""
    moves: list[Move] = []
    skips: list[Skip] = []
    claimed: set[Path] = set()
    for file in find_audio(root):
        state, result = _placement(file, read_tags(file), root)
        if state == "ok":
            target = _free_name(result, claimed)        # type: ignore[arg-type]
            claimed.add(target)
            moves.append(Move(file, target))
        elif state == "skip":
            skips.append(Skip(file, result))            # type: ignore[arg-type]
    return FolderizePlan(root=root, moves=moves, skips=skips)


def _free_name(target: Path, claimed: set[Path]) -> Path:
    """Dodge collisions with existing files and this plan's own targets
    ('name (1).ext', Chrome convention). Directories are reused."""
    candidate = target
    i = 1
    while candidate in claimed or candidate.exists():
        candidate = target.with_name(f"{target.stem} ({i}){target.suffix}")
        i += 1
    return candidate


def probe(root: Path, budget: int = PROBE_BUDGET) -> bool:
    """Whether folderize has anything to do under ``root`` — the button
    test. Stops at the first actionable file; gives up (False) once the
    budget is spent, so an organized 3,000-file NAS tree costs a bounded
    number of tag reads."""
    spent = 0
    for file in find_audio(root):
        if spent >= budget:
            return False
        spent += 1
        state, _ = _placement(file, read_tags(file), root)
        if state in ("ok", "skip"):
            return True
    return False


def execute(plan: FolderizePlan) -> tuple[int, int, list[tuple[Path, str]]]:
    """Apply the plan: move files, park skips in ``* Skipped``, prune
    empty directories. Returns (moved, skipped, errors)."""
    errors: list[tuple[Path, str]] = []
    moved = 0
    for move in plan.moves:
        try:
            move.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source), str(move.target))
            moved += 1
        except Exception as error:
            errors.append((move.source, str(error)))

    skipped = 0
    if plan.skips:
        skip_dir = plan.root / SKIPPED_DIR_NAME
        try:
            skip_dir.mkdir(exist_ok=True)
        except OSError as error:
            errors.append((skip_dir, str(error)))
        else:
            claimed: set[Path] = set()
            for skip in plan.skips:
                if not skip.source.exists():
                    continue
                target = _free_name(skip_dir / skip.source.name, claimed)
                claimed.add(target)
                try:
                    shutil.move(str(skip.source), str(target))
                    skipped += 1
                except Exception as error:
                    errors.append((skip.source, str(error)))

    _prune_empty_dirs(plan.root)
    return moved, skipped, errors


def _prune_empty_dirs(root: Path) -> None:
    for folder in sorted((p for p in root.rglob("*") if p.is_dir()),
                         key=lambda p: len(p.parts), reverse=True):
        try:
            folder.rmdir()      # only succeeds when empty
        except OSError:
            pass
