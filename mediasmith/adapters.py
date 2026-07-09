"""Metadata read adapters: filesystem in, plain dataclasses out.

This is the read half of the engine/frontend seam. Nothing here knows about
widgets; everything returns data the UI can render or a later engine can
consume. The write half arrives with the editing slice.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import epub as epublib
from . import fs, kinds

AUDIO_FIELDS = ['title', 'artist', 'albumartist', 'album', 'genre',
                'date', 'tracknumber', 'discnumber', 'composer']
BOOK_FIELDS = ['title', 'author', 'series', 'publisher', 'language', 'date']


@dataclass(frozen=True)
class AudioDetails:
    fields: dict[str, str]
    length_seconds: float
    size: int
    cover: bytes | None


@dataclass(frozen=True)
class VideoDetails:
    size: int
    subtitle_name: str | None
    poster_name: str | None
    poster_bytes: bytes | None


@dataclass(frozen=True)
class BookDetails:
    fields: dict[str, str]
    size: int
    cover: bytes | None


@dataclass(frozen=True)
class ImageDetails:
    size: int
    data: bytes


@dataclass(frozen=True)
class FolderDetails:
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class OtherDetails:
    size: int
    suffix: str


Details = (AudioDetails | VideoDetails | BookDetails | ImageDetails
           | FolderDetails | OtherDetails)


def read_details(path: Path) -> Details:
    """Read display metadata for ``path``. May raise OSError and friends."""
    kind = kinds.kind_of(path)
    return _READERS[kind](path)


def _read_audio(path: Path) -> AudioDetails:
    from mutagen import File as MutagenFile
    audio = MutagenFile(str(path), easy=True)
    tags = (audio.tags or {}) if audio is not None else {}
    fields = {}
    for name in AUDIO_FIELDS:
        values = tags.get(name, [])
        fields[name] = str(values[0]) if values else ""
    length = float(getattr(getattr(audio, "info", None), "length", 0) or 0)
    return AudioDetails(fields=fields, length_seconds=length,
                        size=path.stat().st_size, cover=cover_bytes(path))


def _read_video(path: Path) -> VideoDetails:
    subtitle = next((path.with_suffix(sfx).name
                     for sfx in kinds.SUBTITLE_SUFFIXES
                     if path.with_suffix(sfx).exists()), None)
    poster = next((path.parent / e.name
                   for e in fs.list_dir(path.parent)
                   if not e.is_dir
                   and Path(e.name).suffix.lower() in kinds.IMAGE_EXTENSIONS),
                  None)
    return VideoDetails(
        size=path.stat().st_size,
        subtitle_name=subtitle,
        poster_name=poster.name if poster else None,
        poster_bytes=poster.read_bytes() if poster else None,
    )


def _read_book(path: Path) -> BookDetails:
    fields = {name: "" for name in BOOK_FIELDS}
    if path.suffix.lower() == ".epub":
        _, opf = epublib.read_opf(path)
        if opf:
            fields["title"] = epublib.dc_field(opf, "dc:title") or ""
            fields["author"] = epublib.dc_field(opf, "dc:creator") or ""
            fields["series"] = epublib.calibre_meta(opf, "calibre:series") or ""
            fields["publisher"] = epublib.dc_field(opf, "dc:publisher") or ""
            fields["language"] = epublib.dc_field(opf, "dc:language") or ""
            fields["date"] = epublib.dc_field(opf, "dc:date") or ""
    return BookDetails(fields=fields, size=path.stat().st_size,
                       cover=cover_bytes(path))


def _read_image(path: Path) -> ImageDetails:
    return ImageDetails(size=path.stat().st_size, data=path.read_bytes())


def _read_folder(path: Path) -> FolderDetails:
    counts: dict[str, int] = {}
    for entry in fs.list_dir(path):
        if entry.name.startswith("."):
            continue
        kind = kinds.kind_of(Path(entry.name), is_dir=entry.is_dir)
        counts[kind] = counts.get(kind, 0) + 1
    return FolderDetails(counts=counts)


def _read_other(path: Path) -> OtherDetails:
    return OtherDetails(size=path.stat().st_size, suffix=path.suffix)


_READERS = {
    kinds.AUDIO: _read_audio,
    kinds.VIDEO: _read_video,
    kinds.BOOK: _read_book,
    kinds.IMAGE: _read_image,
    kinds.FOLDER: _read_folder,
    kinds.OTHER: _read_other,
}


def cover_bytes(path: Path) -> bytes | None:
    """Embedded cover art for audio/books, or None."""
    ext = path.suffix.lower()
    try:
        if ext == ".mp3":
            from mutagen.id3 import ID3
            for frame in ID3(str(path)).getall("APIC"):
                return frame.data
        elif ext == ".flac":
            from mutagen.flac import FLAC
            pics = FLAC(str(path)).pictures
            return pics[0].data if pics else None
        elif ext in (".m4a", ".mp4", ".m4v", ".mov"):
            from mutagen.mp4 import MP4
            covr = (MP4(str(path)).tags or {}).get("covr")
            return bytes(covr[0]) if covr else None
        elif ext == ".epub":
            return epublib.extract_cover_bytes(path)
    except Exception:
        return None
    return None


def probe_video_title(path: Path) -> str | None:
    """The container's embedded title tag (what VLC shows), or None.

    Slow (spawns ffprobe) — run it in a worker thread, and check the
    selection hasn't moved before applying the result.
    """
    if not shutil.which("ffprobe"):
        return None
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format_tags=title",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15)
        title = result.stdout.strip()
        return title or None
    except (OSError, subprocess.SubprocessError):
        return None
