"""Wrap a single video into a folder named after it — folderize, on a
video file.

Nick's spec (2026-08-22): the gesture the ebook pane calls "folderize",
applied to a video. Create a directory beside the video, named after the
filename minus its extension, and move the video into it.

The video does not travel alone (Nick's call, same session). A subtitle
is found only as ``<video stem>.srt`` beside its video (``subsync
.find_subtitle``, ``adapters._read_video``), so wrapping the video by
itself would silently orphan its subtitles and blank the details pane's
subtitles/posters rows the moment the wrap finished. What rides along:

1. **The film's own files** — anything sharing the video's stem:
   ``<stem>.srt``, ``<stem>.en.srt``, ``<stem>.nfo``, and a poster
   folder named ``<stem>/``.
2. **The film's art**, but only when this is the folder's ONLY video —
   then the folder is about this one film, so loose images and
   image-only subfolders (``posters.run`` names its folder after TMDB's
   title, not after the file) come too.

Anything else stays where it is. A video already sitting in a folder
named after it is in place, so the button never offers a nesting
accident (folderize's rule).

Pure logic + filesystem moves; no widgets, no printing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import casing, fs, kinds, posters


def wrap_dir(video: Path) -> Path:
    """The folder ``video`` wraps into — beside it, named after the
    filename without its extension."""
    return video.parent / video.stem


def wrapped_path(video: Path) -> Path:
    """Where ``video`` lands once wrapped."""
    return wrap_dir(video) / video.name


def probe(video: Path) -> bool:
    """Whether wrapping does real work — the button test. Free: a name
    comparison, no filesystem read (NAS rule), so the video pane can ask
    on every selection."""
    if video.suffix.lower() not in kinds.VIDEO_EXTENSIONS:
        return False
    return video.parent.name != video.stem


def companions(video: Path) -> tuple[Path, ...]:
    """The siblings that belong to ``video`` and move with it (the two
    rules in the module docstring), in listing order. Reads one
    directory — run it in a worker."""
    parent = video.parent
    target = wrap_dir(video)
    stem = video.stem.lower()
    try:
        entries = fs.list_dir(parent)
    except OSError:
        return ()
    videos = sum(1 for e in entries
                 if not e.is_dir
                 and Path(e.name).suffix.lower() in kinds.VIDEO_EXTENSIONS)
    sole = videos == 1
    found: list[Path] = []
    for entry in entries:
        path = parent / entry.name
        name = entry.name.lower()
        if path == video or path == target:
            continue        # the wrapper folder may already exist (a
                            # poster folder named after the file): it is
                            # reused, never moved into itself
        if (entry.is_dir and name == target.name.lower()
                and casing.same_dir(path, target)):
            # …and on a case-blind volume "the matrix/" IS "The Matrix/",
            # so it is the wrapper wearing another spelling. Moving it
            # into itself orphaned the folder AND the video (2026-08-25).
            # The name test comes first: samefile is a stat, and one stat
            # per directory entry is the NAS rule's cardinal sin.
            continue
        if name == stem or name.startswith(f"{stem}."):
            found.append(path)                          # rule 1
        elif not sole:
            continue
        elif entry.is_dir:
            if posters.image_only_folder(path):
                found.append(path)                      # rule 2 (folder)
        elif Path(entry.name).suffix.lower() in kinds.IMAGE_EXTENSIONS:
            found.append(path)                          # rule 2 (loose art)
    return tuple(found)


def execute(video: Path) -> tuple[Path, int, list[tuple[Path, str]]]:
    """Wrap ``video`` and its companions. An existing wrapper folder is
    reused; every move refuses to overwrite (cookbook rule 5). Returns
    (where the video landed, files moved, errors)."""
    target_dir = wrap_dir(video)
    errors: list[tuple[Path, str]] = []
    try:
        target_dir.mkdir(exist_ok=True)
    except OSError as error:
        return video, 0, [(target_dir, str(error))]

    moved = 0
    landed = video
    for source in (video, *companions(video)):
        dest = target_dir / source.name
        if dest.exists():
            errors.append((source, f"{dest.name} already exists in "
                                   f"{target_dir.name}/"))
            continue
        try:
            shutil.move(str(source), str(dest))
        except OSError as error:
            errors.append((source, str(error)))
            continue
        moved += 1
        if source == video:
            landed = dest
    return landed, moved, errors
