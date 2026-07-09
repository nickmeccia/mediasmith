"""EPUB/OPF read primitives.

Ported from mediasmith-v1 ``smithkit.epub`` (the write half stays there
until the editing slice needs it). Regex-based on purpose: OPFs are small
and this must not depend on lxml just to read metadata.
"""

from __future__ import annotations

import os
import re
import zipfile
from html import unescape
from pathlib import Path


def find_opf_name(z: zipfile.ZipFile) -> str | None:
    """Return the OPF path inside the zip (via container.xml, then fallback)."""
    try:
        container = z.read("META-INF/container.xml").decode("utf-8", errors="ignore")
        m = re.search(r'full-path="([^"]+)"', container)
        if m:
            return m.group(1)
    except KeyError:
        pass
    return next((n for n in z.namelist() if n.endswith(".opf")), None)


def read_opf(path: Path) -> tuple[str | None, str | None]:
    """Open an epub and return ``(opf_name, opf_text)``; ``(None, None)`` on failure."""
    try:
        with zipfile.ZipFile(path) as z:
            name = find_opf_name(z)
            if not name:
                return None, None
            return name, z.read(name).decode("utf-8", errors="ignore")
    except (OSError, zipfile.BadZipFile):
        return None, None


def dc_field(opf: str, tag: str) -> str | None:
    """Extract the text of a Dublin Core element, e.g. ``dc_field(opf, 'dc:title')``."""
    m = re.search(rf"<{tag}\b[^>]*>([^<]+)</{tag}>", opf)
    return unescape(m.group(1).strip()) if m else None


def calibre_meta(opf: str, key: str) -> str | None:
    """Extract a ``<meta name="key" content="..."/>`` value (either attribute order)."""
    m = (re.search(rf'<meta\b[^>]+name="{re.escape(key)}"[^>]+content="([^"]+)"', opf)
         or re.search(rf'<meta\b[^>]+content="([^"]+)"[^>]+name="{re.escape(key)}"', opf))
    return unescape(m.group(1).strip()) if m else None


def find_cover_href(opf: str, opf_name: str) -> str | None:
    """Resolve the cover image's zip-relative href from the OPF, or None."""
    opf_dir = os.path.dirname(opf_name)

    def resolve(href: str) -> str:
        return (opf_dir + "/" + href).lstrip("/") if opf_dir else href

    def get_attr(tag: str, name: str) -> str | None:
        m = re.search(rf'\b{name}="([^"]+)"', tag)
        return m.group(1) if m else None

    all_items = re.findall(r"<(?:\w+:)?item\b[^>]+>", opf)
    # 1. <meta name="cover" content="<id>"/> → manifest item with that id
    for meta_tag in re.findall(r"<meta\b[^>]+>", opf):
        if re.search(r'\bname="cover"', meta_tag):
            cover_id = get_attr(meta_tag, "content")
            if cover_id:
                for item_tag in all_items:
                    if get_attr(item_tag, "id") == cover_id:
                        href = get_attr(item_tag, "href")
                        if href:
                            return resolve(href)
    # 2. Any image item whose id/properties mention "cover"
    for item_tag in all_items:
        ident = (get_attr(item_tag, "id") or "") + (get_attr(item_tag, "properties") or "")
        if re.search(r"cover", ident, re.IGNORECASE) and 'media-type="image/' in item_tag:
            href = get_attr(item_tag, "href")
            if href:
                return resolve(href)
    return None


def extract_cover_bytes(path: Path) -> bytes | None:
    """Return the cover image bytes embedded in an epub, or None."""
    try:
        with zipfile.ZipFile(path) as z:
            name = find_opf_name(z)
            if not name:
                return None
            opf = z.read(name).decode("utf-8", errors="ignore")
            href = find_cover_href(opf, name)
            if href and href in z.namelist():
                return z.read(href)
    except (OSError, zipfile.BadZipFile):
        pass
    return None
