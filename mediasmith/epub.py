"""EPUB/OPF read and write primitives.

Ported from mediasmith-v1 ``smithkit.epub``. Regex-based on purpose: OPFs
are small and this must not depend on lxml just to read metadata.
"""

from __future__ import annotations

import os
import re
import zipfile
from html import escape, unescape
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


# -- write half ---------------------------------------------------------------

FIELD_TAGS = {"title": "dc:title", "author": "dc:creator",
              "publisher": "dc:publisher", "language": "dc:language",
              "date": "dc:date"}
"""Editable book fields that map to a Dublin Core element ("series" is the
odd one out: a calibre <meta> tag)."""


def _insert_into_metadata(opf: str, element: str) -> str:
    m = re.search(r"[ \t]*</(?:\w+:)?metadata>", opf)
    if m is None:
        return opf
    return opf[:m.start()] + f"    {element}\n" + opf[m.start():]


def set_dc_field(opf: str, tag: str, value: str) -> str:
    """Set, insert, or (for an empty value) remove a Dublin Core element."""
    pattern = rf"(<{tag}\b[^>]*>)[^<]*(</{tag}>)"
    if not value:
        return re.sub(rf"[ \t]*<{tag}\b[^>]*>[^<]*</{tag}>\n?", "", opf, count=1)
    replacement = escape(value)
    if re.search(pattern, opf):
        return re.sub(pattern,
                      lambda m: m.group(1) + replacement + m.group(2),
                      opf, count=1)
    return _insert_into_metadata(opf, f"<{tag}>{replacement}</{tag}>")


def set_calibre_meta(opf: str, key: str, value: str) -> str:
    """Set, insert, or (for an empty value) remove a calibre <meta> value."""
    esc_key = re.escape(key)
    if not value:
        return re.sub(rf'[ \t]*<meta\b[^>]+(?:name="{esc_key}"[^>]*|'
                      rf'content="[^"]*"[^>]+name="{esc_key}"[^>]*)/?>\n?',
                      "", opf, count=1)
    replacement = escape(value, quote=True)
    pat_nc = rf'(<meta\b[^>]+name="{esc_key}"[^>]+content=")[^"]*(")'
    pat_cn = rf'(<meta\b[^>]+content=")[^"]*("[^>]+name="{esc_key}")'
    for pattern in (pat_nc, pat_cn):
        if re.search(pattern, opf):
            return re.sub(pattern,
                          lambda m: m.group(1) + replacement + m.group(2),
                          opf, count=1)
    return _insert_into_metadata(
        opf, f'<meta name="{key}" content="{replacement}"/>')


def rewrite_epub(src: Path, dst: Path, overrides: dict[str, bytes]) -> None:
    """Copy ``src`` → ``dst`` writing ``mimetype`` first and uncompressed,
    applying ``overrides`` (zip-path → bytes). Keys matching existing entries
    replace them; new keys are appended. Use this for any in-place-style OPF
    or asset edit so the EPUB stays valid. (Ported from v1 ``smithkit.epub``.)
    """
    with zipfile.ZipFile(src, "r") as zin, \
         zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        mimetype = overrides.get("mimetype")
        if mimetype is None:
            try:
                mimetype = zin.read("mimetype")
            except KeyError:
                mimetype = b"application/epub+zip"
        zout.writestr(zipfile.ZipInfo("mimetype"), mimetype,
                      compress_type=zipfile.ZIP_STORED)

        written: set[str] = {"mimetype"}
        for info in zin.infolist():
            name = info.filename
            if name in written:
                continue
            written.add(name)
            if name in overrides:
                zout.writestr(info, overrides[name])
            else:
                zout.writestr(info, zin.read(name))

        for name, data in overrides.items():
            if name not in written:
                zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def write_metadata(path: Path, fields: dict[str, str]) -> None:
    """Write ``fields`` (a subset of the editable book fields) into the OPF.

    The epub is rewritten next to itself and swapped in with ``os.replace``,
    so a failure mid-write never corrupts the original.
    """
    name, opf = read_opf(path)
    if not name or opf is None:
        raise ValueError(f"{path.name}: no OPF metadata found")
    for key, value in fields.items():
        if key == "series":
            opf = set_calibre_meta(opf, "calibre:series", value)
        elif key in FIELD_TAGS:
            opf = set_dc_field(opf, FIELD_TAGS[key], value)
        else:
            raise ValueError(f"unknown book field: {key}")
    tmp = path.with_name(path.name + ".tmp")
    try:
        rewrite_epub(path, tmp, {name: opf.encode("utf-8")})
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def make_metadata_opf(fields: dict[str, str], has_cover: bool = False) -> str:
    """A Calibre-style ``metadata.opf`` sidecar from the standard book
    fields (title/author/series/publisher/language/date). Ported from v1
    standardize-metadata; series never gets the spurious index="0" that
    fix-series-meta existed to clean up."""
    import uuid
    from datetime import datetime, timezone

    from .text import infer_author_sort

    title = fields.get("title", "")
    author = fields.get("author", "")
    series = fields.get("series", "")
    uid = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    cover_guide = (
        '\n    <guide>\n'
        '        <reference type="cover" title="Cover" href="cover.jpg"/>\n'
        '    </guide>'
    ) if has_cover else ''
    series_meta = (f'\n        <meta name="calibre:series" '
                   f'content="{escape(series, quote=True)}"/>'
                   if series else '')
    return f"""\
<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:identifier opf:scheme="uuid" id="uuid_id">{uid}</dc:identifier>
        <dc:title>{escape(title)}</dc:title>
        <dc:creator opf:file-as="{escape(infer_author_sort(author), quote=True)}" opf:role="aut">{escape(author)}</dc:creator>
        <dc:date>{escape(fields.get("date", ""))}</dc:date>
        <dc:publisher>{escape(fields.get("publisher", ""))}</dc:publisher>
        <dc:language>{escape(fields.get("language", "") or "eng")}</dc:language>{series_meta}
        <meta name="calibre:title_sort" content="{escape(title, quote=True)}"/>
        <meta name="calibre:timestamp" content="{timestamp}"/>
    </metadata>{cover_guide}
</package>
"""


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
