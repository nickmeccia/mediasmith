"""Container metadata reads, without ffprobe.

The only thing mediasmith ever asked ffprobe for was the container's
embedded ``title`` tag — the release name that survives renaming the
file (what VLC shows in its title bar). That is a header read, not a
decode, so it does not need a 60 MB toolchain or a subprocess:

  - ``.mp4`` / ``.m4v`` — mutagen's MP4 parser, the ``©nam`` atom
    (mutagen is already a dependency, for audio tags);
  - ``.mkv`` — enzyme parses the EBML header (arrives with subliminal).

``.avi`` and ``.mov`` are deliberately unhandled *for the title*.
mutagen does not find QuickTime's title atom, and nothing here reads
RIFF INFO — but measured against Nick's library (2026-08-22), 0 of 40
sampled ``.avi`` and 0 of 31 ``.mov`` files carry a title tag at all, so
ffprobe returned None for them too. Unhandled and "handled, always None"
are the same answer.

The VIDEO CODEC (Nick, todo-5) is a second header read, and the split
is different: an ``.mp4``, an ``.m4v`` and a ``.mov`` are all ISO base
media files, so the same box walk answers for the three of them, while
mutagen's MP4 parser is no help (it reads the first AUDIO track's
codec and leaves ``info.codec`` empty on a video-only file). ``.avi``
stays unhandled — its codec lives in a RIFF stream header, a third
format for one suffix.

Faster than the subprocess it replaces by roughly two orders of
magnitude: 10–50 ms over SMB against ~1 s to spawn ffprobe.
"""

from __future__ import annotations

import os
import struct
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
    return _read(_READERS, path)


# -- the video codec ---------------------------------------------------------
# Printed as the standard's name ("H.265"), not the encoder's ("x265"):
# x265 is one program that writes HEVC, and the container records the
# format, never the tool. An id nothing here knows prints raw, so an
# unusual file says something instead of "—".

_MP4_CODECS = {
    "avc1": "H.264", "avc3": "H.264", "h264": "H.264",
    "hvc1": "H.265", "hev1": "H.265", "hvc2": "H.265",
    "dvh1": "H.265", "dvhe": "H.265",       # Dolby Vision rides on HEVC
    "dav1": "AV1", "av01": "AV1",
    "vp08": "VP8", "vp09": "VP9",
    "mp4v": "MPEG-4", "divx": "MPEG-4", "xvid": "MPEG-4", "dx50": "MPEG-4",
    "mp1v": "MPEG-1", "mp2v": "MPEG-2", "hdv1": "MPEG-2",
    "s263": "H.263", "h263": "H.263",
    "jpeg": "Motion JPEG", "mjpa": "Motion JPEG", "mjpb": "Motion JPEG",
    "apch": "ProRes", "apcn": "ProRes", "apcs": "ProRes",
    "apco": "ProRes", "ap4h": "ProRes",
}

_MKV_CODECS = {
    "V_MPEG4/ISO/AVC": "H.264",
    "V_MPEGH/ISO/HEVC": "H.265",
    "V_AV1": "AV1",
    "V_VP8": "VP8", "V_VP9": "VP9",
    "V_MPEG4/ISO/SP": "MPEG-4", "V_MPEG4/ISO/ASP": "MPEG-4",
    "V_MPEG4/ISO/AP": "MPEG-4", "V_MPEG4/MS/V3": "MPEG-4",
    "V_MPEG1": "MPEG-1", "V_MPEG2": "MPEG-2",
    "V_THEORA": "Theora",
    "V_UNCOMPRESSED": "uncompressed",
}

_CODEC_CONTAINERS = frozenset({b"moov", b"trak", b"mdia", b"minf", b"stbl"})


def _boxes(handle, start: int, end: int):
    """Walk one level of ISO base media boxes, yielding (type, body start,
    box end). Seeks rather than reads: an mdat is gigabytes, and every
    byte of it would cross SMB."""
    offset = start
    while offset + 8 <= end:
        handle.seek(offset)
        header = handle.read(8)
        if len(header) < 8:
            return
        size, kind = struct.unpack(">I4s", header)
        body = offset + 8
        if size == 1:                       # 64-bit size follows the type
            extended = handle.read(8)
            if len(extended) < 8:
                return
            size = struct.unpack(">Q", extended)[0]
            body = offset + 16
        elif size == 0:                     # the box runs to the end
            size = end - offset
        if size < body - offset:            # malformed: stop, don't loop
            return
        yield kind, body, min(offset + size, end)
        offset += size


def _mp4_codec(path: Path) -> str | None:
    """The first video track's sample format, e.g. "avc1"."""
    with path.open("rb") as handle:
        end = handle.seek(0, os.SEEK_END)
        for kind, body, stop in _boxes(handle, 0, end):
            if kind != b"moov":
                continue
            for track, track_body, track_stop in _boxes(handle, body, stop):
                if track != b"trak":
                    continue
                fourcc = _track_video_format(handle, track_body, track_stop)
                if fourcc:
                    return fourcc
    return None


def _track_video_format(handle, start: int, end: int) -> str | None:
    """A trak's sample format, but only when its handler says "vide" —
    an audio or subtitle track has an stsd too."""
    for kind, body, stop in _boxes(handle, start, end):
        if kind != b"mdia":
            continue
        is_video = False
        fourcc = None
        for box, box_body, box_stop in _boxes(handle, body, stop):
            if box == b"hdlr":
                handle.seek(box_body + 8)   # version/flags, then pre_defined
                is_video = handle.read(4) == b"vide"
            elif box == b"minf":
                fourcc = _sample_format(handle, box_body, box_stop)
        if is_video and fourcc:
            return fourcc
    return None


def _sample_format(handle, start: int, end: int) -> str | None:
    """minf → stbl → stsd → the first entry, whose box type IS the codec."""
    for kind, body, stop in _boxes(handle, start, end):
        if kind != b"stbl":
            continue
        for box, box_body, box_stop in _boxes(handle, body, stop):
            if box != b"stsd":
                continue
            # stsd's payload is version/flags + entry count, then boxes
            for entry, _, _ in _boxes(handle, box_body + 8, box_stop):
                return entry.decode("latin-1").strip()
    return None


def _mkv_codec(path: Path) -> str | None:
    from enzyme import MKV

    with path.open("rb") as handle:
        tracks = MKV(handle).video_tracks
    return tracks[0].codec_id if tracks else None


_CODEC_READERS = {
    ".mp4": _mp4_codec,
    ".m4v": _mp4_codec,
    ".mov": _mp4_codec,     # QuickTime is the same box layout
    ".mkv": _mkv_codec,
}

_CODEC_NAMES = {**_MKV_CODECS, **_MP4_CODECS}


def read_video_codec(path: Path) -> str | None:
    """The video track's codec as the standard names it ("H.265"), or
    None. Never raises, for the same reasons ``read_title`` doesn't."""
    raw = _read(_CODEC_READERS, path)
    if raw is None:
        return None
    return _CODEC_NAMES.get(raw, raw)


def _read(readers: dict, path: Path) -> str | None:
    reader = readers.get(path.suffix.lower())
    if reader is None:
        return None
    try:
        return reader(path) or None
    except Exception:
        return None
