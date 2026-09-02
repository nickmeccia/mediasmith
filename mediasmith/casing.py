"""Case-only folder collisions — the wall every folderize hits on macOS.

Nick's report (2026-08-25): folderizing a file whose earned folder name
differs only in CASE from a folder that already exists either refused to
run or quietly did the wrong thing. The cause is the filesystem, not the
plan: APFS (and the SMB share) are case-INSENSITIVE but case-preserving,
so ``Artist/`` and ``artist/`` are one directory with one spelling, and
``mkdir`` silently hands back the spelling that is already there.

The rules, from Nick's spec:

1. **Folderize stays case-sensitive.** ``the beatles/`` is not the folder
   ``The Beatles/`` asks for, so the action is offered, not suppressed.
2. **A second folder is made when the filesystem allows it** — on a
   case-SENSITIVE volume there is no collision to resolve, and
   ``clashes`` returns nothing.
3. **Otherwise the existing folder is renamed** into the wanted spelling,
   with the user choosing (in a modal) whether its contents survive the
   rename or go to the Trash.

Pure filesystem logic; no widgets, no printing. Run it in a worker — it
lists directories.
"""

from __future__ import annotations

import os
from pathlib import Path

TEMP_SUFFIX = ".mediasmith-case"
"""Halfway house for a case-only rename an SMB server treats as a no-op."""


def _entries(folder: Path) -> list[str]:
    try:
        return os.listdir(folder)
    except OSError:
        return []


def spelled_exactly(path: Path) -> bool:
    """Whether ``path``'s own casing is the one on disk."""
    return path.name in _entries(path.parent)


def clash(wanted: Path) -> Path | None:
    """The directory that IS ``wanted`` on this filesystem but wears a
    different spelling, or None.

    None covers both happy cases: nothing is there (``mkdir`` will make
    it with our casing), and the right spelling is already there (an
    existing folder gets reused, as folderize has always done). On a
    case-sensitive volume a differently-cased sibling is a different
    directory, so ``wanted.exists()`` is False and there is no clash.
    """
    if not wanted.exists() or spelled_exactly(wanted):
        return None
    lowered = wanted.name.lower()
    found = next((name for name in _entries(wanted.parent)
                  if name.lower() == lowered), None)
    if found is None:                   # a race, or an unlistable parent
        return None
    existing = wanted.parent / found
    return existing if existing.is_dir() else None


def clashes(wanted: list[Path]) -> list[tuple[Path, Path]]:
    """``[(existing, wanted)]`` for every directory in ``wanted`` that
    collides by case only — deduplicated, shallowest first so renaming
    ``Artist/`` lands before ``Artist/Album/``."""
    seen: set[Path] = set()
    out: list[tuple[Path, Path]] = []
    for target in sorted(set(wanted), key=lambda p: (len(p.parts), str(p))):
        if target in seen:
            continue
        seen.add(target)
        existing = clash(target)
        if existing is not None:
            out.append((existing, target))
    return out


def purge_contents(folder: Path) -> list[tuple[Path, str]]:
    """Send everything inside ``folder`` to the Trash — the "delete
    contents" answer. Trash IS the undo (``adapters.trash``'s design), so
    this choice is recoverable, not final."""
    from . import adapters, artfetch
    if os.environ.get(artfetch.OFFLINE_ENV):
        # same guard as ^del: the fuzz gate presses everything and must
        # not fill the real Trash with scratch files
        return [(folder, "delete disabled (MEDIASMITH_OFFLINE set)")]
    errors: list[tuple[Path, str]] = []
    for name in _entries(folder):
        try:
            adapters.trash(folder / name)
        except Exception as error:      # keep going; report the rest
            errors.append((folder / name, str(error)))
    return errors


def rename(existing: Path, wanted: Path) -> None:
    """Respell ``existing`` as ``wanted``. Raises OSError on failure.

    A case-only rename is a no-op on some servers (SMB among them), so
    the result is verified and retried through a temporary name.
    """
    if existing == wanted and spelled_exactly(wanted):
        return
    os.rename(existing, wanted)
    if spelled_exactly(wanted):
        return
    halfway = wanted.parent / f"{wanted.name}{TEMP_SUFFIX}"
    os.rename(wanted, halfway)
    try:
        os.rename(halfway, wanted)
    except OSError:
        os.rename(halfway, existing)    # put it back under its old name
        raise
    if not spelled_exactly(wanted):
        raise OSError(f"{existing.name} could not be renamed to "
                      f"{wanted.name}")


def resolve(pairs: list[tuple[Path, Path]],
            purge: bool = False) -> list[tuple[Path, str]]:
    """Apply the modal's answer: respell every clashing folder, first
    trashing its contents when ``purge``. Returns the errors, one per
    folder that could not be resolved (the caller reports them the same
    way it reports failed moves)."""
    errors: list[tuple[Path, str]] = []
    for existing, wanted in pairs:
        if purge:
            errors.extend(purge_contents(existing))
        try:
            rename(existing, wanted)
        except OSError as error:
            errors.append((existing, str(error)))
    return errors


def same_dir(a: Path, b: Path) -> bool:
    """Whether two paths are one directory on this filesystem — the guard
    against moving a folder into itself under another spelling (that
    orphaned both the folder and the file being wrapped, 2026-08-25)."""
    try:
        return a.is_dir() and b.is_dir() and os.path.samefile(a, b)
    except OSError:
        return False
