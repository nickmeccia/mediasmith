"""Calibre CLI adapter: locate and drive ``ebook-convert`` (and, later,
its siblings). Ported from mediasmith-v1 ``smithkit.calibre``; the
discovery order (app bundle, then PATH) is unchanged.

Conversions are slow (seconds to minutes) — always run them in a thread
worker.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

EBOOK_FORMATS = ("epub", "mobi", "azw3")
"""The formats the convert actions offer, in button order."""

_APP_BIN = Path("/Applications/calibre.app/Contents/MacOS")


def find_tool(name: str) -> Path | None:
    """Path to a Calibre CLI tool, or None if Calibre isn't installed."""
    default = _APP_BIN / name
    if default.exists():
        return default
    found = shutil.which(name)
    return Path(found) if found else None


def find_ebook_convert() -> Path | None:
    return find_tool("ebook-convert")


def convert(src: Path, dst: Path) -> None:
    """Convert ``src`` → ``dst`` (format inferred from the suffixes).

    Writes to a hidden sibling and renames into place, so a failed or
    interrupted conversion never leaves a partial ``dst``. May raise.
    """
    tool = find_ebook_convert()
    if tool is None:
        raise RuntimeError("Calibre not found — install it from "
                           "https://calibre-ebook.com")
    tmp = dst.parent / (".convert-tmp-" + dst.name)
    try:
        result = subprocess.run([str(tool), str(src), str(tmp)],
                                capture_output=True)
        if result.returncode != 0:
            snippet = (result.stderr or b"").decode(
                errors="ignore")[-300:].strip()
            raise RuntimeError(f"ebook-convert failed: {snippet}")
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)
