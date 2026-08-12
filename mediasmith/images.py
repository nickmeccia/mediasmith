"""Guarded textual-image import.

This module must be imported before the App starts (importing it pulls in
textual-image, which probes the terminal for its cell size — a probe that
is only safe while the terminal is still in cooked mode). Importing lazily
inside a running app races the probe against live keystrokes; that race
killed the v1 prototype. A failed probe degrades to images-off, never to a
dead app.
"""

from __future__ import annotations

import os

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


def image_widget(mode: str, *, id: str, classes: str = "cover"):
    """An image widget for ``mode``, or an empty Static when images are off."""
    if mode == "off" or not IMAGES_OK:
        return Static("", id=id, classes=classes + "-off")
    cls = {"halfcell": _HalfcellImage, "unicode": _UnicodeImage}.get(mode) or _auto_class()
    return cls(None, id=id, classes=classes)
