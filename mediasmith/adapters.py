"""Metadata adapters: filesystem in, plain dataclasses out — and back.

This is the engine/frontend seam. Nothing here knows about widgets;
everything returns data the UI can render or a later engine can consume,
and the write half takes plain field dicts back.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import epub as epublib
from . import fs, kinds, posters

AUDIO_FIELDS = ['title', 'artist', 'albumartist', 'album', 'genre',
                'date', 'tracknumber', 'discnumber', 'composer']
BOOK_FIELDS = ['title', 'author', 'author sort', 'series', 'series number',
               'publisher', 'language', 'date']

# Display labels for fields whose internal key isn't what we want on screen.
# The keys stay as-is (audio keys double as mutagen tag names); only the
# rendered label differs. See EditForm.set_fields.
FIELD_LABELS = {'tracknumber': 'track no.', 'discnumber': 'disc no.',
                'series number': 'series no.'}


@dataclass(frozen=True)
class AudioDetails:
    fields: dict[str, str]
    length_seconds: float
    size: int
    cover: bytes | None


@dataclass(frozen=True)
class VideoDetails:
    size: int
    container: str              # suffix name ("mkv") — free, no ffprobe
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
    width: int      # 0 when Pillow can't parse the file
    height: int


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

    def joined(values) -> str:
        return "; ".join(str(v) for v in values)

    # The standard fields always show (empty when absent, so they can be
    # filled in); whatever else the file carries follows.
    fields = {name: joined(tags.get(name, [])) for name in AUDIO_FIELDS}
    for name in sorted(set(tags.keys()) - set(AUDIO_FIELDS)):
        fields[name] = joined(tags.get(name, []))
    length = float(getattr(getattr(audio, "info", None), "length", 0) or 0)
    return AudioDetails(fields=fields, length_seconds=length,
                        size=path.stat().st_size, cover=cover_bytes(path))


def _read_video(path: Path) -> VideoDetails:
    subtitle = next((path.with_suffix(sfx).name
                     for sfx in kinds.SUBTITLE_SUFFIXES
                     if path.with_suffix(sfx).exists()), None)
    # the poster ladder lives with the poster engine (posters.find_poster);
    # a poster inside its own folder shows as "Alien (1979)/poster.jpg"
    poster = posters.find_poster(path)
    return VideoDetails(
        size=path.stat().st_size,
        container=path.suffix.lstrip(".").lower(),
        subtitle_name=subtitle,
        poster_name=_relative_name(poster, path.parent) if poster else None,
        poster_bytes=_read_bytes(poster) if poster else None,
    )


def _relative_name(path: Path, root: Path) -> str:
    """A sibling's display name: bare when it sits beside the video,
    "folder/name.jpg" when it sits one level down."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_book(path: Path) -> BookDetails:
    fields = {name: "" for name in BOOK_FIELDS}
    if path.suffix.lower() == ".epub":
        _, opf = epublib.read_opf(path)
        if opf:
            fields["title"] = epublib.dc_field(opf, "dc:title") or ""
            fields["author"] = epublib.dc_field(opf, "dc:creator") or ""
            fields["author sort"] = epublib.creator_file_as(opf) or ""
            fields["series"] = epublib.calibre_meta(opf, "calibre:series") or ""
            fields["series number"] = (
                epublib.calibre_meta(opf, "calibre:series_index") or "")
            fields["publisher"] = epublib.dc_field(opf, "dc:publisher") or ""
            fields["language"] = epublib.dc_field(opf, "dc:language") or ""
            fields["date"] = epublib.dc_field(opf, "dc:date") or ""
    return BookDetails(fields=fields, size=path.stat().st_size,
                       cover=cover_bytes(path))


def _read_image(path: Path) -> ImageDetails:
    data = path.read_bytes()
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size    # header only — no pixel decode
    except Exception:
        width = height = 0
    return ImageDetails(size=path.stat().st_size, data=data,
                        width=width, height=height)


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


# -- bulk (multi-file) details --------------------------------------------------


@dataclass(frozen=True)
class BulkDetails:
    kind: str
    fields: dict[str, str]      # union of every file's tags; "" where mixed
    mixed: frozenset[str]       # field names whose values diverge
    cover: bytes | None         # the common cover, when unanimous
    cover_mixed: bool
    length_seconds: float       # totals across the selection
    size: int


def read_bulk(paths: list[Path]) -> BulkDetails:
    """Merge ``read_details`` over same-kind ``paths``. May raise."""
    kind = kinds.kind_of(paths[0])
    standard = AUDIO_FIELDS if kind == kinds.AUDIO else BOOK_FIELDS
    all_details = [read_details(p) for p in paths]
    names = list(standard) + sorted(
        {n for d in all_details for n in d.fields} - set(standard))
    fields: dict[str, str] = {}
    mixed: set[str] = set()
    for name in names:
        values = {d.fields.get(name, "") for d in all_details}
        if len(values) == 1:
            fields[name] = values.pop()
        else:
            fields[name] = ""
            mixed.add(name)
    covers = [getattr(d, "cover", None) for d in all_details]
    cover_mixed = any(c != covers[0] for c in covers)
    return BulkDetails(
        kind=kind, fields=fields, mixed=frozenset(mixed),
        cover=None if cover_mixed else covers[0], cover_mixed=cover_mixed,
        length_seconds=sum(getattr(d, "length_seconds", 0.0)
                           for d in all_details),
        size=sum(getattr(d, "size", 0) for d in all_details))


def save_bulk(paths: list[Path], fields: dict[str, str],
              art: bytes | None = None) -> list[tuple[Path, Exception]]:
    """Write ``fields`` (and ``art``) to every path; carries on past
    failures and returns them as (path, error) pairs."""
    errors: list[tuple[Path, Exception]] = []
    for path in paths:
        try:
            if art is not None:
                write_cover(path, art)
            if fields:
                write_details(path, fields)
        except Exception as error:
            errors.append((path, error))
    return errors


def bulk_paths_for_folder(path: Path) -> list[Path] | None:
    """The folder's bulk-editable children, or None when the folder
    doesn't qualify. Rules (Nick's artist/album/track layout): leaf
    folders only — any subfolder disqualifies ("album" yes, "artist" no) —
    and the writable children must all share one kind; unwritable files
    (cover.jpg, .nfo, …) are ignored."""
    try:
        entries = fs.list_dir(path)
    except OSError:
        return None
    by_kind: dict[str, list[Path]] = {}
    for entry in entries:
        if entry.is_dir:
            return None
        if entry.name.startswith("."):
            continue
        child = path / entry.name
        if can_write(child):
            by_kind.setdefault(kinds.kind_of(child, is_dir=False),
                               []).append(child)
    if len(by_kind) != 1:
        return None
    return next(iter(by_kind.values()))


# -- write half ---------------------------------------------------------------


def can_write(path: Path) -> bool:
    """True when ``write_details`` has a writer for this path."""
    kind = kinds.kind_of(path)
    if kind == kinds.AUDIO:
        return True
    if kind == kinds.BOOK:
        return path.suffix.lower() == ".epub"
    return False


def write_details(path: Path, fields: dict[str, str]) -> None:
    """Write metadata ``fields`` back to ``path``. May raise."""
    kind = kinds.kind_of(path)
    if kind == kinds.AUDIO:
        _write_audio(path, fields)
    elif kind == kinds.BOOK and path.suffix.lower() == ".epub":
        epublib.write_metadata(path, fields)
    else:
        raise ValueError(f"{path.name}: no metadata writer for this kind")


def _write_audio(path: Path, fields: dict[str, str]) -> None:
    from mutagen import File as MutagenFile
    audio = MutagenFile(str(path), easy=True)
    if audio is None:
        raise ValueError(f"{path.name}: unrecognized audio file")
    if audio.tags is None:
        audio.add_tags()
    for name, value in fields.items():
        if value:
            audio[name] = [value]
        elif name in audio:
            del audio[name]
    audio.save()


def write_cover(path: Path, data: bytes) -> None:
    """Embed ``data`` as the (only) cover art. May raise."""
    ext = path.suffix.lower()
    mime = ("image/png" if data[:8] == b"\x89PNG\r\n\x1a\n"
            else "image/jpeg")
    if ext == ".mp3":
        from mutagen.id3 import APIC, ID3, ID3NoHeaderError
        try:
            id3 = ID3(str(path))
        except ID3NoHeaderError:
            id3 = ID3()
        id3.delall("APIC")
        id3.add(APIC(encoding=3, mime=mime, type=3, desc="cover", data=data))
        id3.save(str(path))
    elif ext == ".flac":
        from mutagen.flac import FLAC, Picture
        flac = FLAC(str(path))
        flac.clear_pictures()
        picture = Picture()
        picture.type = 3
        picture.mime = mime
        picture.data = data
        flac.add_picture(picture)
        flac.save()
    elif ext in (".m4a", ".mp4"):
        from mutagen.mp4 import MP4, MP4Cover
        fmt = (MP4Cover.FORMAT_PNG if mime == "image/png"
               else MP4Cover.FORMAT_JPEG)
        mp4 = MP4(str(path))
        mp4["covr"] = [MP4Cover(data, imageformat=fmt)]
        mp4.save()
    else:
        raise ValueError(f"no album-art writer for {ext or path.name}")


def rename(path: Path, new_name: str) -> Path:
    """Rename ``path`` within its directory; returns the new path."""
    new_name = new_name.strip()
    if not new_name or "/" in new_name or new_name in (".", ".."):
        raise ValueError(f"invalid filename: {new_name!r}")
    if new_name == path.name:
        return path
    target = path.with_name(new_name)
    if target.exists():
        raise FileExistsError(f"{new_name} already exists")
    path.rename(target)
    return target


def create_folder(parent: Path, base: str = "untitled folder") -> Path:
    """Finder's flow: mkdir under the first free "untitled folder[ N]"
    name and return it. May raise OSError."""
    target = parent / base
    n = 2
    while target.exists():
        target = parent / f"{base} {n}"
        n += 1
    target.mkdir()
    return target


def trash(path: Path) -> None:
    """Send ``path`` to the macOS Trash. Trash IS the undo — that is the
    design that keeps delete out of the confirm-modal trap. May raise."""
    from send2trash import send2trash
    send2trash(str(path))


def save_details(path: Path, new_name: str, fields: dict[str, str],
                 art: bytes | None = None) -> Path:
    """The pane's save: write ``art`` and ``fields`` (when writable), then
    rename. Writes go to the original path, so the rename comes last;
    returns the (possibly new) path.
    """
    if art is not None:
        write_cover(path, art)
    if fields and can_write(path):
        write_details(path, fields)
    return rename(path, new_name)


def extract_cover(path: Path, overwrite: bool = False) -> Path:
    """Write the book's embedded cover next to it as cover.jpg/.png
    (named for its actual format). Raises when there is no cover or (unless
    ``overwrite``) the target already exists."""
    data = cover_bytes(path)
    if not data:
        raise ValueError(f"{path.name}: no embedded cover")
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    target = path.parent / f"cover{ext}"
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target.name} already exists")
    target.write_bytes(data)
    return target


def create_opf(path: Path, overwrite: bool = False) -> Path:
    """Write a Calibre-style metadata.opf beside the book, from its
    embedded metadata. Raises when the target already exists (unless
    ``overwrite``)."""
    target = path.parent / "metadata.opf"
    if target.exists() and not overwrite:
        raise FileExistsError("metadata.opf already exists")
    details = read_details(path)
    assert isinstance(details, BookDetails)
    has_cover = (path.parent / "cover.jpg").exists()
    target.write_text(epublib.make_metadata_opf(details.fields, has_cover),
                      encoding="utf-8")
    return target


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
