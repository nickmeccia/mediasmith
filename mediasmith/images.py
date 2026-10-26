"""Guarded textual-image import.

This module must be imported before the App starts (importing it pulls in
textual-image, which probes the terminal for its cell size — a probe that
is only safe while the terminal is still in cooked mode). Importing lazily
inside a running app races the probe against live keystrokes; that race
killed the v1 prototype. A failed probe degrades to images-off, never to a
dead app.
"""

from __future__ import annotations

import io
import os
import threading

from textual.widgets import Static

try:
    from textual_image.widget import Image as _AutoImage
    from textual_image.widget import HalfcellImage as _HalfcellImage
    from textual_image.widget import UnicodeImage as _UnicodeImage
    IMAGES_OK = True
except Exception:
    IMAGES_OK = False

MODES = ["auto", "halfcell", "unicode", "off"]


def _auto_class():
    """Renderer for ``auto`` mode — halfcell under tmux, best-protocol elsewhere.

    textual-image's auto picks Sixel whenever the terminal answers a sixel
    support query, which Ghostty does even through tmux. But Sixel (and TGP)
    paint into the terminal's pixel layer at absolute positions; Textual only
    rewrites character cells and can't erase those pixels. A direct terminal
    clears the pixels when the cells beneath are overwritten — tmux does not,
    so a cover drawn once stays burned into the screen through every later
    redraw. Halfcell renders images as ordinary colored half-block cells, which
    Textual clears like any other text: the documented tmux fallback.
    """
    if os.environ.get("TMUX"):
        return _HalfcellImage
    return _AutoImage


_truncated_lock = threading.Lock()


def decode(data: bytes):
    """Decode image bytes NOW; returns ``(image, truncated)``.

    PIL decodes LAZILY — ``Image.open`` reads the header only, and the
    pixels are pulled later, inside the widget's ``render()``. That puts
    the decode on Textual's render path, where an OSError is fatal: a
    truncated album cover (a JPEG ending mid-scan) killed the app from
    there (Nick, 2026-09-02). Loading here moves the failure into a
    caller that can catch it.

    A file that ends mid-scan still decodes as far as it got, and showing
    that beats showing nothing — so a strict decode that fails is retried
    with PIL's truncation escape. That flag is PIL-GLOBAL state, and the
    write paths (imageops, epub) must keep refusing damaged input, so it
    is set only around the salvage and put straight back.
    """
    from PIL import Image, ImageFile
    image = Image.open(io.BytesIO(data))
    try:
        image.load()
        return image, False
    except OSError:
        pass                    # a half-decoded image can't be reused
    with _truncated_lock:
        previous = ImageFile.LOAD_TRUNCATED_IMAGES
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        finally:
            ImageFile.LOAD_TRUNCATED_IMAGES = previous
    return image, True


FALLBACK_CELL_PIXELS = (10, 20)


def cell_pixels() -> tuple[int, int]:
    """One terminal cell's (width, height) in pixels — what a picture must
    be rendered at to land 1:1 on screen (Image Trace's preview). The
    probe already ran at import (see the module docstring); this reads
    its cached answer, falling back to a typical 1:2 cell."""
    if not IMAGES_OK:
        return FALLBACK_CELL_PIXELS
    try:
        from textual_image._terminal import get_cell_size
        size = get_cell_size()
        if size.width > 0 and size.height > 0:
            return size.width, size.height
    except Exception:
        pass
    return FALLBACK_CELL_PIXELS


def image_widget(mode: str, *, id: str, classes: str = "cover"):
    """An image widget for ``mode``, or an empty Static when images are off."""
    if mode == "off" or not IMAGES_OK:
        return Static("", id=id, classes=classes + "-off")
    cls = {"halfcell": _HalfcellImage, "unicode": _UnicodeImage}.get(mode) or _auto_class()
    return cls(None, id=id, classes=classes)
