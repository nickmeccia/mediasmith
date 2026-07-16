"""Standardize ebook formatting: strip calibre/source cruft from an
epub and rebuild it with one clean stylesheet.

Faithful port of v1's standardize-formatting tool. The extractors and
the style detection are EMPIRICALLY TUNED on Nick's library (Wildbow's
calibre exports especially) — port-level changes to their behavior
need his re-QA, so they are verbatim. What the port adds is what the
app owes that the CLI didn't: the source's metadata (series,
publisher, date, language) and its cover survive the rebuild instead
of being dropped.

House rules: output is a sibling ("Name (clean).epub"), never in
place and never overwritten — a whole-book rewrite is not an edit.

v1's performance notes, still binding:
- always ``body.decode_contents()`` after BeautifulSoup manipulation
  (``str(body)`` slicing breaks when <body> has attributes);
- never an unbounded ``[^"']*`` group in a regex applied to full
  chapter text (catastrophic backtracking) — keep image-path regexes
  anchored to attribute context.
"""

from __future__ import annotations

import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterator

from . import epub as epublib

CLEAN_SUFFIX = " (clean)"

DEFAULT_STYLESHEET = """\
body {
  font-family: Georgia, serif;
  font-size: 1em;
  line-height: 1.6;
  margin: 1.5em 2em;
  color: #111;
}
h1 { font-size: 1.4em; margin-bottom: 0.2em; text-indent: 0; }
h2 { font-size: 1.1em; margin-top: 2em; color: #333; text-indent: 0; }
p { margin: 0.6em 0; text-indent: 1.5em; }
p:first-of-type { text-indent: 0; }
hr { border: none; border-top: 1px solid #aaa; margin: 2em auto; width: 40%; }
em { font-style: italic; }
strong { font-weight: bold; }
img { max-width: 100%; display: block; margin: 1em auto; }
svg { max-width: 100%; display: block; margin: 1em auto; }
"""


def clean_target(path: Path) -> Path:
    return path.with_name(f"{path.stem}{CLEAN_SUFFIX}.epub")


# -- HTML cleaning utilities (v1 verbatim) ---------------------------------------


def strip_classes_regex(html: str) -> str:
    """Remove class= and calibre-style id= attributes via regex — much
    faster than tree-walking for large documents."""
    html = re.sub(r'\s+class="[^"]*"', "", html)
    html = re.sub(r"\s+class='[^']*'", "", html)
    html = re.sub(r'\s+id="(?:filepos|calibre_pb|anchor)[^"]*"', "", html)
    return html


def flatten_image_paths(html: str) -> str:
    """Reduce image paths like ../Images/foo.png to just foo.png (the
    flat layout the builder writes)."""
    html = re.sub(r'(?:OEBPS/)?Images/', "", html)
    html = re.sub(r'(?<=src=")(?:\.\.\/)+(?:[^"/]+/)*', "", html)
    html = re.sub(r"(?<=src=')(?:\.\.\/)+(?:[^'/]+/)*", "", html)
    html = re.sub(r'(?<=href=")(?:\.\.\/)+(?:[^"/]+/)*', "", html)
    return html


# -- extractors, one per source HTML style (v1 verbatim) -------------------------


def extract_calibre_h1(raw_html: str, toc_title: str) -> str:
    """<h1 class='calibreX'> headings, <p class='calibreX'> body.
    (Ward style)"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw_html, "lxml")
    body = soup.find("body")
    if not body:
        return ""
    first_h1 = body.find("h1")
    if first_h1:
        first_h1.decompose()
    return strip_classes_regex(body.decode_contents())


def extract_calibre_bold(raw_html: str, toc_title: str) -> str:
    """Chapter title as a bold span in the first paragraph.
    (Worm/Twig style)"""
    from bs4 import BeautifulSoup, Tag
    soup = BeautifulSoup(raw_html, "lxml")
    body = soup.find("body")
    if not body:
        return ""
    for span in body.find_all("span"):
        if "bold" in " ".join(span.get("class", [])):
            span.name = "strong"
    children = [c for c in body.children if isinstance(c, Tag)]
    if children:
        first = children[0]
        if first.find("strong") and len(first.get_text(strip=True)) < 80:
            first.decompose()
    for span in body.find_all("span"):
        span.unwrap()
    return strip_classes_regex(body.decode_contents())


def extract_calibre_h2(raw_html: str, toc_title: str) -> str:
    """Garbled <h2 class='p-p1'> headings with internal spans.
    (Pact style)"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw_html, "lxml")
    body = soup.find("body")
    if not body:
        return ""
    for h2 in body.find_all("h2"):
        h2.decompose()
    for span in body.find_all("span"):
        if not span.get_text(strip=True):
            span.decompose()
    for p in body.find_all("p"):
        if not p.get_text(strip=True):
            p.decompose()
    return strip_classes_regex(body.decode_contents())


def extract_pale(raw_html: str, toc_title: str) -> str:
    """calibre-h1 plus SVG practice-log images; the second <h1> is a
    character name that becomes <h2>. (Pale style)"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw_html, "lxml")
    body = soup.find("body")
    if not body:
        return ""
    h1s = body.find_all("h1")
    if h1s:
        h1s[0].decompose()
    for h1 in body.find_all("h1"):
        h1.name = "h2"
    for a in body.find_all("a", href=re.compile(r"http")):
        a.unwrap()
    result = strip_classes_regex(body.decode_contents())
    return flatten_image_paths(result)


def extract_generic(raw_html: str, toc_title: str) -> str:
    """Fallback: strip all class/style/id attributes, keep semantic
    tags. Works on any well-structured epub."""
    html = strip_classes_regex(raw_html)
    html = re.sub(r'\s+style="[^"]*"', "", html)
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html,
                       re.DOTALL | re.IGNORECASE)
    if body_m:
        html = body_m.group(1)
    # drop the first heading — the builder prepends its own from the TOC
    html = re.sub(r"^\s*<h[12][^>]*>.*?</h[12]>", "", html, count=1,
                  flags=re.DOTALL)
    return html.strip()


EXTRACTORS = {
    "calibre-h1":    extract_calibre_h1,
    "calibre-bold":  extract_calibre_bold,
    "calibre-h2":    extract_calibre_h2,
    "pale":          extract_pale,
    "generic":       extract_generic,
}


def detect_style(sample_html: str) -> str:
    """Guess the extractor style from a sample chapter's raw HTML
    (v1 verbatim — the markers are tuned to real exports)."""
    if (re.search(r'class="svg_outer"', sample_html)
            or re.search(r'xlink:href.*\.png', sample_html)):
        return "pale"
    if re.search(r"class=['\"]p-p1['\"]", sample_html):
        return "calibre-h2"
    if (re.search(r"class=['\"]bold['\"]", sample_html)
            or re.search(r"<span[^>]*bold", sample_html)):
        return "calibre-bold"
    if re.search(r"<h1[^>]*class=['\"]calibre", sample_html):
        return "calibre-h1"
    return "generic"


# -- the clean-epub writer (v1's EpubBuilder, folded in) -------------------------
# Differences from v1: the metadata block carries whatever the source
# had (series/publisher/date/language, via ``fields``), and a PNG cover
# stays a PNG instead of png bytes inside "cover.jpg".


@dataclass
class _Chapter:
    title: str
    body_html: str
    filename: str
    file_id: str


_IMAGE_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "gif": "image/gif",
                "svg": "image/svg+xml"}

_CONTAINER_XML = """\
<?xml version='1.0' encoding='utf-8'?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _cover_name(data: bytes) -> str:
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    return f"cover{ext}"


def _cover_xhtml(cover_name: str) -> str:
    return f"""\
<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Cover</title>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
  <style type="text/css">body {{ margin: 0; padding: 0; }} img {{ max-width: 100%; display: block; margin: 0 auto; }}</style>
</head>
<body><img src="{cover_name}" alt="Cover"/></body>
</html>
"""


def _chapter_xhtml(title: str, body_html: str) -> str:
    safe = escape(title)
    return f"""\
<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>{safe}</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
</head>
<body>
<h1>{safe}</h1>
{body_html}
</body>
</html>
"""


def _metadata_block(fields: dict[str, str], uid: str, has_cover: bool) -> str:
    lines = []
    if has_cover:
        lines.append('    <meta name="cover" content="cover-image"/>')
    lines.append(f"    <dc:title>{escape(fields.get('title') or 'Unknown')}"
                 "</dc:title>")
    author = fields.get("author") or "Unknown"
    lines.append(f'    <dc:creator opf:file-as="{escape(author)}" '
                 f'opf:role="aut">{escape(author)}</dc:creator>')
    lines.append(f"    <dc:language>{escape(fields.get('language') or 'en')}"
                 "</dc:language>")
    for name, tag in (("publisher", "dc:publisher"), ("date", "dc:date")):
        if fields.get(name):
            lines.append(f"    <{tag}>{escape(fields[name])}</{tag}>")
    if fields.get("series"):
        lines.append(f'    <meta name="calibre:series" '
                     f'content="{escape(fields["series"])}"/>')
    lines.append(f'    <dc:identifier id="uuid_id" opf:scheme="uuid">{uid}'
                 "</dc:identifier>")
    return "\n".join(lines)


def _write_clean_epub(target: Path, fields: dict[str, str],
                      chapters: list[_Chapter],
                      images: dict[str, bytes],
                      cover: bytes | None) -> None:
    uid = str(uuid.uuid4())
    title = fields.get("title") or "Unknown"
    cover_name = _cover_name(cover) if cover else None
    manifest = ['    <item href="stylesheet.css" id="css" media-type="text/css"/>',
                '    <item href="toc.ncx" id="ncx" media-type="application/x-dtbncx+xml"/>']
    spine = []
    if cover_name:
        manifest.append(f'    <item href="{cover_name}" id="cover-image" '
                        f'media-type="{_IMAGE_TYPES[cover_name.rsplit(".", 1)[-1]]}"/>')
        manifest.append('    <item href="cover.xhtml" id="cover-page" '
                        'media-type="application/xhtml+xml"/>')
        spine.append('    <itemref idref="cover-page"/>')
    for name in images:
        ext = name.rsplit(".", 1)[-1].lower()
        img_id = "img_" + re.sub(r"[^a-zA-Z0-9]", "_", name)
        manifest.append(f'    <item href="{name}" id="{img_id}" '
                        f'media-type="{_IMAGE_TYPES.get(ext, "image/jpeg")}"/>')
    for ch in chapters:
        manifest.append(f'    <item href="{ch.filename}" id="{ch.file_id}" '
                        'media-type="application/xhtml+xml"/>')
        spine.append(f'    <itemref idref="{ch.file_id}"/>')
    nl = "\n"
    opf = f"""\
<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
{_metadata_block(fields, uid, cover_name is not None)}
  </metadata>
  <manifest>
{nl.join(manifest)}
  </manifest>
  <spine toc="ncx">
{nl.join(spine)}
  </spine>
</package>
"""
    points = [f"""\
    <navPoint id="np_{i}" playOrder="{i + 1}">
      <navLabel><text>{escape(ch.title)}</text></navLabel>
      <content src="{ch.filename}"/>
    </navPoint>""" for i, ch in enumerate(chapters)]
    ncx = f"""\
<?xml version='1.0' encoding='utf-8'?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="en">
  <head>
    <meta name="dtb:uid" content="{uid}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{escape(title)}</text></docTitle>
  <navMap>
{nl.join(points)}
  </navMap>
</ncx>
"""
    with zipfile.ZipFile(target, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                    compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        zf.writestr("stylesheet.css", DEFAULT_STYLESHEET)
        zf.writestr("content.opf", opf)
        zf.writestr("toc.ncx", ncx)
        if cover is not None and cover_name is not None:
            zf.writestr("cover.xhtml", _cover_xhtml(cover_name))
            zf.writestr(cover_name, cover,
                        compress_type=zipfile.ZIP_DEFLATED)
        for name, data in images.items():
            zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        for ch in chapters:
            zf.writestr(ch.filename,
                        _chapter_xhtml(ch.title, ch.body_html).encode("utf-8"),
                        compress_type=zipfile.ZIP_DEFLATED)


# -- the reformat itself ----------------------------------------------------------

MIN_CHAPTER_CHARS = 30      # v1: shorter extractions are furniture, not text


def standardize(source: Path, target: Path,
                style: str | None = None) -> tuple[str, int]:
    """Rebuild ``source`` as a clean epub at ``target``. Returns
    (style used, chapter count). Raises on unreadable sources, unknown
    styles, and existing targets."""
    if target.exists():
        raise FileExistsError(f"{target.name} already exists")
    fields = {name: "" for name in
              ("title", "author", "series", "publisher", "language", "date")}
    _, opf = epublib.read_opf(source)
    if opf:
        fields["title"] = epublib.dc_field(opf, "dc:title") or ""
        fields["author"] = epublib.dc_field(opf, "dc:creator") or ""
        fields["series"] = epublib.calibre_meta(opf, "calibre:series") or ""
        fields["publisher"] = epublib.dc_field(opf, "dc:publisher") or ""
        fields["language"] = epublib.dc_field(opf, "dc:language") or ""
        fields["date"] = epublib.dc_field(opf, "dc:date") or ""
    if not fields["title"]:
        fields["title"] = source.stem
    cover = epublib.extract_cover_bytes(source)

    with zipfile.ZipFile(source, "r") as zin:
        ncx_name = next((n for n in zin.namelist() if n.endswith(".ncx")),
                        None)
        if not ncx_name:
            raise ValueError(f"no .ncx found in {source.name}")
        ncx = zin.read(ncx_name).decode("utf-8", errors="ignore")
        ncx_dir = os.path.dirname(ncx_name)
        toc_entries = re.findall(
            r"<navLabel>\s*<text>([^<]+)</text>\s*</navLabel>\s*"
            r"<content src=\"([^#\"]+)", ncx)
        if not toc_entries:
            raise ValueError(f"no TOC entries found in {source.name}")

        def resolve(src: str) -> str:
            src = src.strip()
            if ncx_dir and not src.startswith(ncx_dir):
                return ncx_dir + "/" + src
            return src

        if style is None:       # sample a mid-book chapter (v1 policy)
            mid = len(toc_entries) // 2
            for _, src in toc_entries[mid:mid + 3]:
                try:
                    sample = zin.read(resolve(src)).decode(
                        "utf-8", errors="ignore")
                except KeyError:
                    continue
                style = detect_style(sample)
                break
            if style is None:
                style = "generic"
        extractor = EXTRACTORS.get(style)
        if extractor is None:
            raise ValueError(f"unknown style {style!r}")

        images: dict[str, bytes] = {}
        for name in zin.namelist():
            low = name.lower()
            if (any(low.endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif"))
                    and "cover" not in low.split("/")[-1]):
                images[os.path.basename(name)] = zin.read(name)

        chapters: list[_Chapter] = []
        seen: set[str] = set()
        for toc_label, toc_src in toc_entries:
            full_src = resolve(toc_src)
            if full_src in seen:
                continue
            seen.add(full_src)
            try:
                raw = zin.read(full_src).decode("utf-8", errors="ignore")
            except KeyError:
                continue
            body_html = extractor(raw, toc_label.strip())
            if len(body_html.strip()) < MIN_CHAPTER_CHARS:
                continue
            index = len(chapters)
            chapters.append(_Chapter(
                title=toc_label.strip(), body_html=body_html,
                filename=f"chapter_{index:04d}.xhtml",
                file_id=f"ch_{index:04d}"))
    if not chapters:
        raise ValueError(f"{source.name}: nothing survived extraction "
                         f"(style {style})")
    _write_clean_epub(target, fields, chapters, images, cover)
    return style, len(chapters)


# -- folder mode -------------------------------------------------------------------


def folder_books(root: Path) -> list[Path]:
    """The epubs a folder-level standardize would process: direct
    children only (predictable on a huge NAS tree), skipping files that
    ARE "(clean)" outputs — their sources sit beside them."""
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError:
        return []
    return [Path(e.path) for e in entries
            if not e.is_dir(follow_symlinks=False)
            and e.name.lower().endswith(".epub")
            and not e.name.lower().endswith(f"{CLEAN_SUFFIX}.epub".lower())]


def probe_folder(root: Path) -> bool:
    """Cheap visibility probe: any direct epub child still lacking its
    clean sibling."""
    return any(not clean_target(book).exists() for book in folder_books(root))


@dataclass(frozen=True)
class BookDone:
    source: Path
    target: Path
    style: str
    chapters: int


@dataclass(frozen=True)
class BookFailed:
    source: Path
    reason: str


def run(books: list[Path]) -> Iterator[BookDone | BookFailed]:
    """Standardize each book to its "(clean)" sibling, carrying on past
    failures (refuse-overwrite reports as a failure, not a crash)."""
    for source in books:
        target = clean_target(source)
        try:
            style, chapters = standardize(source, target)
        except Exception as error:
            yield BookFailed(source, str(error))
            continue
        yield BookDone(source, target, style, chapters)
