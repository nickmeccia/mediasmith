"""Sort a folder of loose book files into per-book folders.

Nick's convention (2026-07-16, claude-TODO "Sort" folders): every file
belonging to one book — epub, mobi, azw3, plus the metadata.opf and
cover.* sidecars — wraps into ONE folder named "Author Sort - Title"
(the v1 standardize-metadata output shape, confirmed against the live
BOOKS volume's 03 Tag & Convert).

Folderize's shape: probe → plan → preview → execute. Formats group by
stem (conversions land beside their source under the same stem, so the
stem IS the book identity); the folder name comes from the group's
epub — a group with no epub has no readable metadata and is skipped,
never guessed. A book already sitting in its own correctly-named
folder is in place, so sorting a wrapper folder is a no-op, not a
nesting accident (folderize's rule).
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import epub as epublib
from .text import infer_author_sort, sanitize_filename

BOOK_SUFFIXES = (".epub", ".mobi", ".azw3")
SIDECAR_NAMES = ("metadata.opf", "cover.jpg", "cover.jpeg", "cover.png")


@dataclass(frozen=True)
class BookGroup:
    folder_name: str            # "Author Sort - Title"
    files: tuple[Path, ...]     # everything that moves into it


@dataclass(frozen=True)
class SortSkip:
    source: Path
    reason: str


@dataclass
class SortPlan:
    root: Path
    groups: list[BookGroup] = field(default_factory=list)
    skips: list[SortSkip] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.groups

    @property
    def file_count(self) -> int:
        return sum(len(g.files) for g in self.groups)


def _loose_books(root: Path) -> dict[str, list[Path]]:
    """Direct-child book files, grouped by stem (the book identity)."""
    groups: dict[str, list[Path]] = {}
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError:
        return {}
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            continue
        path = Path(entry.path)
        if path.suffix.lower() in BOOK_SUFFIXES:
            groups.setdefault(path.stem, []).append(path)
    return groups


def folder_name_for(book: Path) -> str | None:
    """The wrapper-folder name a book's metadata earns it, or None when
    the metadata can't be read (only epubs have a reader)."""
    if book.suffix.lower() != ".epub":
        return None
    try:
        _, opf = epublib.read_opf(book)
    except Exception:
        return None
    if not opf:
        return None
    title = epublib.dc_field(opf, "dc:title") or book.stem
    author = epublib.dc_field(opf, "dc:creator") or ""
    file_as = re.search(r'opf:file-as="([^"]+)"', opf)
    author_sort = (file_as.group(1) if file_as
                   else infer_author_sort(author)) or "Unknown"
    return sanitize_filename(f"{author_sort} - {title}")


def probe(root: Path) -> bool:
    """Cheap visibility probe: any direct-child epub whose earned
    folder name isn't the folder it already sits in. Direct children
    only — one opf read per loose epub."""
    for files in _loose_books(root).values():
        epub = next((f for f in files if f.suffix.lower() == ".epub"), None)
        if epub is None:
            continue
        name = folder_name_for(epub)
        if name is not None and name != root.name:
            return True
    return False


def build_plan(root: Path) -> SortPlan:
    plan = SortPlan(root=root)
    groups = _loose_books(root)
    for stem in sorted(groups, key=str.lower):
        files = groups[stem]
        epub = next((f for f in files if f.suffix.lower() == ".epub"), None)
        if epub is None:
            plan.skips.append(SortSkip(files[0], "no epub — metadata "
                                                 "unreadable"))
            continue
        name = folder_name_for(epub)
        if name is None:
            plan.skips.append(SortSkip(epub, "unreadable metadata"))
            continue
        if name == root.name:       # already in its own wrapper folder
            continue
        plan.groups.append(BookGroup(folder_name=name, files=tuple(files)))
    # sidecars ride along only when they're unambiguous: one book in
    # the folder means the loose cover/opf are that book's
    if len(plan.groups) == 1:
        sidecars = tuple(root / n for n in SIDECAR_NAMES
                         if (root / n).is_file())
        if sidecars:
            only = plan.groups[0]
            plan.groups[0] = BookGroup(only.folder_name,
                                       only.files + sidecars)
    elif len(plan.groups) > 1:
        for n in SIDECAR_NAMES:
            if (root / n).is_file():
                plan.skips.append(SortSkip(
                    root / n, "left behind — several books share this "
                              "folder"))
    return plan


def execute(plan: SortPlan) -> tuple[int, list[tuple[Path, str]]]:
    """Wrap every group. Existing wrapper folders are reused;
    refuse-overwrite per file. Returns (files moved, errors)."""
    moved = 0
    errors: list[tuple[Path, str]] = []
    for group in plan.groups:
        target_dir = plan.root / group.folder_name
        try:
            target_dir.mkdir(exist_ok=True)
        except OSError as error:
            errors.append((target_dir, str(error)))
            continue
        for source in group.files:
            dest = target_dir / source.name
            if dest.exists():
                errors.append((source, f"{dest.name} already exists in "
                                       f"{group.folder_name}/"))
                continue
            try:
                shutil.move(str(source), str(dest))
                moved += 1
            except OSError as error:
                errors.append((source, str(error)))
    return moved, errors
