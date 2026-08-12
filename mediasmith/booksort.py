"""Sort a folder of loose book files into per-book folders.

Nick's convention (2026-07-16, claude-TODO "Sort" folders): every file
belonging to one book — epub, mobi, azw3, plus the metadata.opf and
cover.* sidecars — wraps into ONE folder named "Author Sort - Title",
or "Author Sort - Series - NN - Title" for a book in a series (Nick's
spec, 2026-08-07: e.g. "Jemisin, N. K. - The Broken Earth - 01 - The
Fifth Season"). The book files are renamed to match the folder
("<name>.epub"); sidecars keep their canonical names. A single ebook
can be sorted on its own (plan_for_book) through the same execute —
that is the ebook-pane "sort" button.

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
from .text import compose_book_name, infer_author_sort

BOOK_SUFFIXES = (".epub", ".mobi", ".azw3")
SIDECAR_NAMES = ("metadata.opf", "cover.jpg", "cover.jpeg", "cover.png")


def _dest_name(source: Path, folder_name: str) -> str:
    """The name a file takes inside its wrapper folder: book files are
    renamed to match the folder ("Author Sort - Title.epub"), keeping
    only their suffix; sidecars (metadata.opf, cover.*) keep their
    canonical names — Calibre and readers look them up by name."""
    if source.suffix.lower() in BOOK_SUFFIXES:
        return folder_name + source.suffix
    return source.name


def sorted_path(book: Path, folder_name: str) -> Path:
    """Where ``book`` lands after being wrapped into ``folder_name`` — the
    renamed file inside the new directory, beside where it started."""
    return book.parent / folder_name / _dest_name(book, folder_name)


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
    """The wrapper-folder (and file) name a book's metadata earns it, or
    None when the metadata can't be read (only epubs have a reader). The
    naming convention itself lives in ``text.compose_book_name`` — series
    books get "Author Sort - Series - NN - Title", others "Author Sort -
    Title"."""
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
    return compose_book_name(
        author_sort, title,
        epublib.calibre_meta(opf, "calibre:series"),
        epublib.calibre_meta(opf, "calibre:series_index"))


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


def probe_book(book: Path) -> bool:
    """Single-book visibility: this epub earns a wrapper name that isn't
    the folder it already sits in — so sorting it does real work. One opf
    read; only epubs carry readable metadata."""
    if book.suffix.lower() != ".epub":
        return False
    name = folder_name_for(book)
    return name is not None and name != book.parent.name


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


def plan_for_book(book: Path) -> SortPlan | None:
    """A one-file sort plan: wrap just ``book`` into its earned folder,
    leaving any stem-siblings behind (single-book intent). None when the
    metadata can't be read. Shares ``execute`` with the folder-wide sort,
    so the file is renamed to the folder name the same way."""
    name = folder_name_for(book)
    if name is None:
        return None
    return SortPlan(root=book.parent,
                    groups=[BookGroup(folder_name=name, files=(book,))])


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
            dest = target_dir / _dest_name(source, group.folder_name)
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
