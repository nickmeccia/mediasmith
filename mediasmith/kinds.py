"""File-kind detection: one vocabulary for the whole app."""

from __future__ import annotations

from pathlib import Path

FOLDER = "folder"
AUDIO = "audio"
VIDEO = "video"
BOOK = "book"
IMAGE = "image"
OTHER = "other"

AUDIO_EXTENSIONS = {
    '.mp3', '.flac', '.m4a', '.aac', '.ogg', '.opus',
    '.wav', '.aiff', '.aif', '.wma', '.ape', '.alac',
}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.m4v'}
BOOK_EXTENSIONS = {'.epub', '.mobi', '.azw3'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

# Sibling-subtitle suffixes for videos, in preference order.
SUBTITLE_SUFFIXES = ['.en.srt', '.srt', '.en.ass', '.ass', '.en.vtt', '.vtt']

_BY_EXTENSION = {
    **{ext: AUDIO for ext in AUDIO_EXTENSIONS},
    **{ext: VIDEO for ext in VIDEO_EXTENSIONS},
    **{ext: BOOK for ext in BOOK_EXTENSIONS},
    **{ext: IMAGE for ext in IMAGE_EXTENSIONS},
}


def kind_of(path: Path, is_dir: bool | None = None) -> str:
    """Classify a path. Pass ``is_dir`` when known to avoid a stat call."""
    if is_dir if is_dir is not None else path.is_dir():
        return FOLDER
    return _BY_EXTENSION.get(path.suffix.lower(), OTHER)
