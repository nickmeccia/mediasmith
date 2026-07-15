"""Omnibus splitter engine: one epub in, its constituent books out.

Ported from mediasmith-v1 ``tools/booksmith/omnibus-splitter`` (571
lines, logic kept faithfully) minus the interactive CLI: the confirm/
rename conversation is replaced by the plan-preview pattern — probe →
``build_plan`` → the UI previews → ``execute``. v1's flat-NCX manual
boundary entry and title renaming are NOT ported (they need input the
plan preview doesn't collect); a flat-TOC omnibus simply won't offer
the button. Bring them back as a wizard div if Nick ever hits one.

How a split works (v1's model, unchanged):
  - book boundaries are the top-level NCX navPoints that have children
    (structural containers), minus boilerplate labels (cover, preface…);
  - each output epub gets the omnibus front matter (everything in the
    spine before the first boundary), plus its own spine slice;
  - assets (images/CSS/fonts) referenced from a book's HTML are found
    by scanning src/href attributes and carried along;
  - the sliced NCX drops the book-title level: its chapters become
    root entries.

Output epubs land beside the source, "Author Sort - Title.epub",
refuse-overwrite per book.
"""

from __future__ import annotations

import re
import uuid
import zipfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

from .text import infer_author_sort, sanitize_filename

# top-level navPoint labels that are front/back matter, never books
BOILERPLATE = {
    'cover', 'copyright', 'copyright page', 'title', 'title page',
    'half title', 'half-title', 'dedication', 'epigraph', 'about',
    'acknowledgment', 'acknowledgments', 'acknowledgements',
    'contents', 'table of contents', 'foreword', 'preface',
    'introduction', 'index', 'colophon', 'author', 'about the author',
    'also by', 'newsletter', 'excerpt', 'bonus', 'preview',
}


# ─────────────────────────────────────────────────────────────────────────────
# The plan
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BookSplit:
    label: str                  # the book's title (its navPoint label)
    chapters: int               # leaf navPoints beneath it
    filename: str               # "Author Sort - Title.epub"
    spine: tuple[str, ...]      # zip-absolute hrefs, front matter included
    toc: tuple[dict, ...]       # navPoint dicts for the sliced NCX


@dataclass(frozen=True)
class OmnibusPlan:
    source: Path
    title: str                  # the omnibus's own title
    author: str
    author_sort: str
    language: str
    opf_dir: str
    manifest: dict              # id -> {href, media_type}
    books: tuple[BookSplit, ...]

    @property
    def empty(self) -> bool:
        return len(self.books) < 2


# ─────────────────────────────────────────────────────────────────────────────
# Epub parsing (v1, verbatim behavior)
# ─────────────────────────────────────────────────────────────────────────────

def parse_container(z: zipfile.ZipFile) -> str:
    """The OPF path from META-INF/container.xml."""
    try:
        container = z.read('META-INF/container.xml').decode(
            'utf-8', errors='ignore')
    except KeyError:
        raise ValueError("missing META-INF/container.xml — not a valid epub")
    m = re.search(r'full-path="([^"]+)"', container)
    if not m:
        raise ValueError("cannot find OPF path in container.xml")
    return m.group(1)


def parse_opf(z: zipfile.ZipFile, opf_path: str) -> dict:
    """Metadata, manifest, spine, and NCX href out of the OPF."""
    opf = z.read(opf_path).decode('utf-8', errors='ignore')
    opf_dir = opf_path.rsplit('/', 1)[0] if '/' in opf_path else ''

    def get(pattern: str) -> str:
        m = re.search(pattern, opf)
        return m.group(1).strip() if m else ''

    manifest: dict[str, dict] = {}
    for m in re.finditer(r'<(?:\w+:)?item\b[^>]+>', opf):
        tag = m.group(0)
        mid = re.search(r'\bid="([^"]+)"', tag)
        href = re.search(r'\bhref="([^"]+)"', tag)
        mtype = re.search(r'\bmedia-type="([^"]+)"', tag)
        if mid and href:
            manifest[mid.group(1)] = {
                'href': href.group(1),
                'media_type': (mtype.group(1) if mtype
                               else 'application/octet-stream'),
            }

    spine_ids = re.findall(r'<(?:\w+:)?itemref\b[^>]*\bidref="([^"]+)"', opf)

    ncx_href = None
    toc_attr = re.search(r'<(?:\w+:)?spine\b[^>]*\btoc="([^"]+)"', opf)
    if toc_attr and toc_attr.group(1) in manifest:
        ncx_href = manifest[toc_attr.group(1)]['href']
    if not ncx_href:
        for item in manifest.values():
            if ('ncx' in item['media_type']
                    or item['href'].endswith('.ncx')):
                ncx_href = item['href']
                break

    return {
        'title': get(r'<dc:title[^>]*>([^<]+)'),
        'author': get(r'<dc:creator[^>]*>([^<]+)'),
        'author_sort': get(r'opf:file-as="([^"]+)"'),
        'language': get(r'<dc:language[^>]*>([^<]+)') or 'en',
        'manifest': manifest,
        'spine_ids': spine_ids,
        'ncx_href': ncx_href,
        'opf_dir': opf_dir,
    }


def zip_path(href: str, base_dir: str) -> str:
    """The zip-absolute path for a manifest href."""
    if not base_dir or href.startswith(base_dir + '/'):
        return href
    return base_dir + '/' + href


def parse_ncx(z: zipfile.ZipFile, ncx_href: str, opf_dir: str) -> list[dict]:
    """Top-level navPoint dicts: {label, src (zip-absolute, no
    fragment), children: [...same...]}."""
    ncx_zip = zip_path(ncx_href, opf_dir)
    try:
        raw = z.read(ncx_zip).decode('utf-8', errors='ignore')
    except KeyError:
        try:
            raw = z.read(ncx_href).decode('utf-8', errors='ignore')
            ncx_zip = ncx_href
        except KeyError:
            return []

    ncx_dir = ncx_zip.rsplit('/', 1)[0] if '/' in ncx_zip else ''

    def resolve_src(src: str) -> str:
        s = src.split('#')[0]
        if not s:
            return ''
        if ncx_dir and not s.startswith(ncx_dir + '/'):
            return ncx_dir + '/' + s
        return s

    # strip namespaces so ElementTree can handle any NCX flavor
    clean = re.sub(r'\bxmlns(?::\w+)?="[^"]*"', '', raw)
    clean = re.sub(r'<\?xml[^>]*\?>', '', clean).strip()
    clean = re.sub(r'<(/?)(?:ncx|daisy):', r'<\1', clean)

    try:
        root = ET.fromstring(clean)
    except ET.ParseError:
        return []

    navmap = root.find('navMap')
    if navmap is None:
        navmap = next((c for c in root if 'navmap' in c.tag.lower()), root)

    def parse_np(elem) -> dict:
        lbl = elem.find('.//navLabel/text')
        label = (lbl.text or '').strip() if lbl is not None else ''
        content = elem.find('content')
        src = resolve_src(content.get('src', '')
                          if content is not None else '')
        children = [parse_np(c) for c in elem if 'navPoint' in c.tag]
        return {'label': label, 'src': src, 'children': children}

    return [parse_np(np) for np in navmap if 'navPoint' in np.tag]


def detect_books(navpoints: list[dict]) -> list[dict]:
    """Top-level navPoints that look like constituent books: prefer the
    ones with children (structural containers), drop boilerplate."""
    with_children = [np for np in navpoints if np['children']]
    candidates = with_children or navpoints
    filtered = [np for np in candidates
                if np['label'].lower().strip() not in BOILERPLATE]
    return filtered if len(filtered) >= 2 else candidates


def leaf_count(np: dict) -> int:
    if not np['children']:
        return 1
    return sum(leaf_count(c) for c in np['children'])


# ─────────────────────────────────────────────────────────────────────────────
# probe / build_plan / execute
# ─────────────────────────────────────────────────────────────────────────────

def probe(path: Path) -> bool:
    """Cheap detection for button visibility: does this epub hold ≥2
    books? One zip read; anything malformed is simply not an omnibus.
    v1's flat-TOC fallback (childless top-level navPoints as candidate
    books) needed the interactive boundary conversation, so v2 only
    offers structural omnibuses — boundaries with children."""
    try:
        with zipfile.ZipFile(path) as z:
            data = parse_opf(z, parse_container(z))
            if not data['ncx_href']:
                return False
            navpoints = parse_ncx(z, data['ncx_href'], data['opf_dir'])
        books = detect_books(navpoints)
        return (len(books) >= 2
                and all(np['children'] for np in books))
    except Exception:
        return False


def build_plan(path: Path) -> OmnibusPlan:
    """May raise ValueError (not an epub / no NCX). An un-splittable
    book comes back as an empty plan, not an error."""
    with zipfile.ZipFile(path) as z:
        data = parse_opf(z, parse_container(z))
        opf_dir = data['opf_dir']
        if not data['ncx_href']:
            raise ValueError("no NCX found — cannot detect book boundaries")
        navpoints = parse_ncx(z, data['ncx_href'], opf_dir)

    books = detect_books(navpoints)
    if not all(np['children'] for np in books):
        books = []                      # flat TOC: see probe's docstring

    author = data['author'] or 'Unknown'
    author_sort = data['author_sort'] or infer_author_sort(author)

    # the full spine as zip-absolute hrefs, in reading order
    all_spine = [zip_path(data['manifest'][sid]['href'], opf_dir)
                 for sid in data['spine_ids'] if sid in data['manifest']]

    def spine_index(src: str) -> int:
        target = src.split('#')[0]
        for i, href in enumerate(all_spine):
            if href == target or (opf_dir
                                  and href == zip_path(target, opf_dir)):
                return i
        return -1

    starts, located = [], []
    for np in books:
        idx = spine_index(np['src'])
        if idx >= 0:                    # a boundary outside the spine is
            starts.append(idx)          # dropped, exactly like v1
            located.append(np)

    ends = starts[1:] + [len(all_spine)]
    front_matter = all_spine[:starts[0]] if starts else []

    splits = tuple(
        BookSplit(
            label=np['label'],
            chapters=leaf_count(np),
            filename=(sanitize_filename(f"{author_sort} - {np['label']}")
                      + ".epub"),
            spine=tuple(front_matter + all_spine[start:end]),
            toc=tuple(np['children'] if np['children'] else [np]),
        )
        for np, start, end in zip(located, starts, ends))

    return OmnibusPlan(
        source=path, title=data['title'], author=author,
        author_sort=author_sort, language=data['language'],
        opf_dir=opf_dir, manifest=data['manifest'], books=splits)


def execute(plan: OmnibusPlan) -> tuple[list[Path], list[tuple[str, str]]]:
    """Write one epub per book beside the source. Refuse-overwrite per
    book. Returns (written paths, [(filename, reason), …])."""
    written: list[Path] = []
    errors: list[tuple[str, str]] = []
    with zipfile.ZipFile(plan.source) as z:
        for book in plan.books:
            target = plan.source.parent / book.filename
            if target.exists():
                errors.append((book.filename, "already exists"))
                continue
            try:
                _write_book_epub(z, plan, book, target)
                written.append(target)
            except (OSError, ValueError, zipfile.BadZipFile) as error:
                errors.append((book.filename, str(error)))
    return written, errors


# ─────────────────────────────────────────────────────────────────────────────
# Epub writing (v1, verbatim behavior)
# ─────────────────────────────────────────────────────────────────────────────

_OPF = '''\
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{title}</dc:title>
    <dc:creator opf:file-as="{author_sort}" opf:role="aut">{author}</dc:creator>
    <dc:language>{language}</dc:language>
    <dc:identifier id="BookId">urn:uuid:{uid}</dc:identifier>
  </metadata>
  <manifest>
{manifest_items}    <item id="_ncx_" href="{ncx_name}" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="_ncx_">
{spine_items}  </spine>
</package>'''

_NCX = '''\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
  "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{uid}"/>
    <meta name="dtb:depth" content="2"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
{nav_points}  </navMap>
</ncx>'''

_CONTAINER = '''\
<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''


def _render_navpoints(navpoints, opf_dir: str, order: list[int],
                      depth: int = 0) -> list[str]:
    indent = '    ' + '  ' * depth
    lines = []
    for np in navpoints:
        src = np['src']
        if opf_dir and src.startswith(opf_dir + '/'):
            src = src[len(opf_dir) + 1:]
        oid = order[0]
        order[0] += 1
        lines.append(f'{indent}<navPoint id="np{oid}" playOrder="{oid}">')
        lines.append(f'{indent}  <navLabel><text>{escape(np["label"])}'
                     f'</text></navLabel>')
        lines.append(f'{indent}  <content src="{escape(src)}"/>')
        if np['children']:
            lines += _render_navpoints(np['children'], opf_dir, order,
                                       depth + 1)
        lines.append(f'{indent}</navPoint>')
    return lines


def _write_book_epub(z_in: zipfile.ZipFile, plan: OmnibusPlan,
                     book: BookSplit, output_path: Path) -> None:
    uid = str(uuid.uuid4())
    opf_dir = plan.opf_dir
    manifest_all = plan.manifest

    href_to_id = {zip_path(item['href'], opf_dir): mid
                  for mid, item in manifest_all.items()}

    include_ids = {href_to_id[h] for h in book.spine if h in href_to_id}

    # find assets (images/CSS/fonts) each spine file references
    asset_by_basename: dict[str, str] = {}
    asset_by_href: dict[str, str] = {}
    for mid, item in manifest_all.items():
        mt = item['media_type']
        if not (mt.startswith('application/xhtml')
                or mt.startswith('text/html')
                or mt == 'application/x-dtbncx+xml'):
            asset_by_basename[item['href'].rsplit('/', 1)[-1]] = mid
            asset_by_href[item['href']] = mid
            asset_by_href[zip_path(item['href'], opf_dir)] = mid

    for h in book.spine:
        try:
            html = z_in.read(h).decode('utf-8', errors='ignore')
        except KeyError:
            continue
        for ref in re.findall(r'(?:src|href)="([^"]+)"', html):
            ref_clean = ref.split('?')[0].split('#')[0]
            mid = (asset_by_href.get(ref_clean)
                   or asset_by_href.get(zip_path(ref_clean, opf_dir))
                   or asset_by_basename.get(ref_clean.rsplit('/', 1)[-1]))
            if mid:
                include_ids.add(mid)

    opf_name, ncx_name = 'content.opf', 'toc.ncx'
    opf_out = (opf_dir + '/' + opf_name) if opf_dir else opf_name
    ncx_out = (opf_dir + '/' + ncx_name) if opf_dir else ncx_name

    manifest_lines = [
        f'    <item id="{escape(mid)}" '
        f'href="{escape(manifest_all[mid]["href"])}"'
        f' media-type="{escape(manifest_all[mid]["media_type"])}"/>\n'
        for mid in sorted(include_ids)]

    spine_lines = [f'    <itemref idref="{escape(href_to_id[h])}"/>\n'
                   for h in book.spine if h in href_to_id]

    opf_content = _OPF.format(
        title=escape(book.label), author=escape(plan.author),
        author_sort=escape(plan.author_sort), language=plan.language,
        uid=uid, manifest_items=''.join(manifest_lines),
        spine_items=''.join(spine_lines), ncx_name=ncx_name)

    order = [1]
    nav_lines = _render_navpoints(list(book.toc), opf_dir, order)
    ncx_content = _NCX.format(uid=uid, title=escape(book.label),
                              nav_points='\n'.join(nav_lines) + '\n')

    already: set[str] = set()
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z_out:
        info = zipfile.ZipInfo('mimetype')      # first, uncompressed
        info.compress_type = zipfile.ZIP_STORED
        z_out.writestr(info, 'application/epub+zip')
        already.add('mimetype')

        z_out.writestr('META-INF/container.xml',
                       _CONTAINER.format(opf_path=opf_out))
        already.update({'META-INF/container.xml', opf_out, ncx_out})

        z_out.writestr(opf_out, opf_content)
        z_out.writestr(ncx_out, ncx_content)

        for mid in include_ids:
            item = manifest_all[mid]
            zp = zip_path(item['href'], opf_dir)
            if zp in already:
                continue
            already.add(zp)
            try:
                z_out.writestr(zp, z_in.read(zp))
            except KeyError:
                try:
                    z_out.writestr(zp, z_in.read(item['href']))
                except KeyError:
                    pass    # asset missing from the source epub — skip
