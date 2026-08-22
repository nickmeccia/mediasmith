"""Container metadata reads, without ffprobe.

The only thing mediasmith ever asked ffprobe for was the container's
embedded ``title`` tag — the release name that survives renaming the
file (what VLC shows in its title bar). That is a header read, not a
decode, so it does not need a 60 MB toolchain or a subprocess:

  - ``.mp4`` / ``.m4v`` — mutagen's MP4 parser, the ``©nam`` atom
    (mutagen is already a dependency, for audio tags);
  - ``.mkv`` — enzyme parses the EBML header (arrives with subliminal).

``.avi`` and ``.mov`` are deliberately unhandled. mutagen does not find
QuickTime's title atom, and nothing here reads RIFF INFO — but measured
against Nick's library (2026-08-22), 0 of 40 sampled ``.avi`` and 0 of
31 ``.mov`` files carry a title tag at all, so ffprobe returned None for
them too. Unhandled and "handled, always None" are the same answer.

Faster than the subprocess it replaces by roughly two orders of
magnitude: 10–50 ms over SMB against ~1 s to spawn ffprobe.
"""

from __future__ import annotations

from pathlib import Path


def _mp4_title(path: Path) -> str | None:
    from mutagen.mp4 import MP4

    tags = MP4(path).tags
    if not tags:
        return None
    values = tags.get("\xa9nam")
    return str(values[0]) if values else None


def _mkv_title(path: Path) -> str | None:
    from enzyme import MKV

    with path.open("rb") as handle:
        return MKV(handle).info.title


_READERS = {
    ".mp4": _mp4_title,
    ".m4v": _mp4_title,
    ".mkv": _mkv_title,
}


def read_title(path: Path) -> str | None:
    """The container's embedded title tag, or None.

    Never raises: a junk file, a truncated download, or an unreadable
    NAS path is a None, exactly as a failed ffprobe was. The parsers
    raise a wide zoo of exceptions on malformed input (mutagen's
    MP4StreamInfoError, enzyme's MalformedMKVError, plain OSError from
    the mount), and every one of them means the same thing here.
    """
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        return None
    try:
        return reader(path) or None
    except Exception:
        return None
