"""Builders for tiny-but-valid media files.

Shared by the pytest fixtures and the fuzz harness. Never point tests at the
real library — build scratch trees with these instead.
"""

from __future__ import annotations

import io
import zipfile
import zlib
from pathlib import Path

# A single silent MPEG-1 Layer III frame (128 kbps, 44.1 kHz): enough for
# mutagen to parse stream info and carry ID3 tags.
MP3_FRAME = bytes.fromhex("fffb9000") + bytes(413)


def make_png(path: Path | None = None, size=(8, 8), color=(200, 60, 60)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    data = buf.getvalue()
    if path is not None:
        path.write_bytes(data)
    return data


def make_truncated_jpeg(path: Path | None = None, size=(64, 64),
                        cut: int = 16) -> bytes:
    """A JPEG whose header parses but whose scan ends early — the shape of
    the album art that crashed the pane's render (2026-09-02).

    ``cut`` bytes come off the tail: a small bite ends the scan a few
    pixels short (salvageable), a large one takes the scan's structure
    with it (nothing to show)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 90, 160)).save(buf, format="JPEG", quality=95)
    data = buf.getvalue()[:-cut]
    if path is not None:
        path.write_bytes(data)
    return data


def make_mp3(path: Path, tags: dict[str, str] | None = None,
             cover: bytes | None = None) -> Path:
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import APIC, ID3

    path.write_bytes(MP3_FRAME * 4)
    easy = EasyID3()
    for key, value in (tags or {}).items():
        easy[key] = value
    easy.save(str(path))
    if cover is not None:
        id3 = ID3(str(path))
        id3.add(APIC(encoding=3, mime="image/png", type=3,
                     desc="cover", data=cover))
        id3.save(str(path))
    return path


def make_epub(path: Path, title="Dune", author="Frank Herbert",
              series: str | None = "Dune", cover: bytes | None = None,
              author_sort: str | None = None,
              series_index: str | None = None) -> Path:
    series_meta = (f'<meta name="calibre:series" content="{series}"/>'
                   if series else "")
    if series_index:
        series_meta += (f'<meta name="calibre:series_index" '
                        f'content="{series_index}"/>')
    file_as = f' opf:file-as="{author_sort}"' if author_sort else ""
    cover_manifest = ('<item id="cover-image" href="cover.png" '
                      'media-type="image/png"/>' if cover is not None else "")
    # one real chapter: keeps the epub convertible (ebook-convert rejects
    # an empty spine)
    chapter = ('<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/'
               'xhtml"><head><title>1</title></head>'
               '<body><p>It was a dark and stormy night.</p></body></html>')
    cover_meta = '<meta name="cover" content="cover-image"/>' if cover is not None else ""
    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator{file_as}>{author}</dc:creator>
    <dc:publisher>Chilton Books</dc:publisher>
    <dc:language>en</dc:language>
    <dc:date>1965-08-01</dc:date>
    {series_meta}
    {cover_meta}
  </metadata>
  <manifest>{cover_manifest}
    <item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="chap1"/></spine>
</package>"""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="content.opf"
    media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    # calibre epubs always carry an NCX; standardize-formatting needs one
    ncx = f"""<?xml version="1.0"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="test"/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap><navPoint id="np1" playOrder="1">
    <navLabel><text>Chapter 1</text></navLabel>
    <content src="chap1.xhtml"/></navPoint></navMap>
</ncx>"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), b"application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("content.opf", opf)
        z.writestr("toc.ncx", ncx)
        z.writestr("chap1.xhtml", chapter)
        if cover is not None:
            z.writestr("cover.png", cover)
    return path


def make_omnibus(path: Path, books: int = 2, chapters: int = 2,
                 flat: bool = False, title="Omnibus",
                 author="Frank Herbert",
                 author_sort="Herbert, Frank") -> Path:
    """An omnibus epub: front matter + N books × M chapters, an NCX with
    one navPoint tree per book (or a flat chapter list with ``flat``),
    everything under OEBPS/ so zip-path resolution is exercised. Book
    one's first chapter references style.css and pic.png (the asset
    scan)."""
    def xhtml(text: str, assets: bool = False) -> str:
        head = ('<link rel="stylesheet" href="style.css"/>' if assets else "")
        img = ('<img src="pic.png"/>' if assets else "")
        return ('<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/'
                f'xhtml"><head><title>x</title>{head}</head>'
                f'<body><p>{text}</p>{img}</body></html>')

    manifest, spine, files = [], [], {}
    manifest.append('<item id="titlepage" href="titlepage.xhtml" '
                    'media-type="application/xhtml+xml"/>')
    spine.append('<itemref idref="titlepage"/>')
    files["OEBPS/titlepage.xhtml"] = xhtml("The Omnibus")

    navpoints, order = [], [1]

    def navpoint(label: str, src: str, children: str = "") -> str:
        oid = order[0]
        order[0] += 1
        return (f'<navPoint id="np{oid}" playOrder="{oid}">'
                f'<navLabel><text>{label}</text></navLabel>'
                f'<content src="{src}"/>{children}</navPoint>')

    navpoints.append(navpoint("Cover", "titlepage.xhtml"))
    for b in range(1, books + 1):
        chapter_points = []
        for c in range(1, chapters + 1):
            name = f"b{b}c{c}"
            manifest.append(f'<item id="{name}" href="{name}.xhtml" '
                            'media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{name}"/>')
            files[f"OEBPS/{name}.xhtml"] = xhtml(
                f"Book {b}, chapter {c}.", assets=(b == 1 and c == 1))
            chapter_points.append(navpoint(f"Chapter {c}", f"{name}.xhtml"))
        if flat:
            navpoints.extend(chapter_points)
        else:
            navpoints.append(navpoint(f"Book {b}", f"b{b}c1.xhtml",
                                      "".join(chapter_points)))

    manifest.append('<item id="css" href="style.css" media-type="text/css"/>')
    manifest.append('<item id="pic" href="pic.png" media-type="image/png"/>')
    manifest.append('<item id="ncx" href="toc.ncx" '
                    'media-type="application/x-dtbncx+xml"/>')
    files["OEBPS/style.css"] = "p { margin: 0 }"

    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{title}</dc:title>
    <dc:creator opf:file-as="{author_sort}">{author}</dc:creator>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>{''.join(manifest)}</manifest>
  <spine toc="ncx">{''.join(spine)}</spine>
</package>"""
    ncx = f"""<?xml version="1.0"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="test"/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>{''.join(navpoints)}</navMap>
</ncx>"""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf"
    media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), b"application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/toc.ncx", ncx)
        z.writestr("OEBPS/pic.png", make_png())
        for name, content in files.items():
            z.writestr(name, content)
    return path


def make_illustrator(path: Path, artboard=(0, 0, 200, 200),
                     offboard: bool = True, compressed: bool | str = True,
                     gradient: bool = False, placed_image: bool = False,
                     pdf_container: bool = True) -> Path:
    """A tiny .ai in the shape that matters: artwork in the AI private data,
    an artboard in the PDF portion that does not contain all of it.

    ``offboard`` adds a second square past the artboard's right edge — the
    work Illustrator keeps and every other reader drops. ``gradient`` wraps
    the artwork in a group painted by a gradient, which is the construct
    that reads as a clip rather than a fill.
    """
    art = ["20 20 m", "80 20 L", "80 80 L", "20 80 L", "f"]
    if offboard:
        art += ["220 20 m", "280 20 L", "280 80 L", "220 80 L", "f"]
    if placed_image:
        art = ["0 0 0 0 0 0 XI"] + art
    if gradient:
        # The group's own paths, then one more path and the gradient object
        # that paints THROUGH every path the group collected.
        art = ["*u"] + art + [
            "10 10 m", "290 10 L", "290 90 L", "10 90 L",
            "Bb",
            "1 (Ramp) 0 0 0 1 1 0 0 1 0 0 1 Bg",
            "100 0 0 100 20 20 Xm",
            "f",
            "0 BB",
            "*U",
        ]
    right = 280 if offboard else 80
    head = [
        "%!PS-Adobe-3.0 ",
        "%%Creator: Adobe Illustrator(R) 15.0",
        "%%Title: (%s)" % path.stem,
        "%%%%BoundingBox: 20 20 %d 80" % right,
        "%%%%HiResBoundingBox: 20 20 %d 80" % right,
        "%%%%AI3_Cropmarks: %s" % " ".join(str(v) for v in artboard),
        "%%EndComments",
        "%%BeginSetup",
    ]
    if gradient:
        head += [
            "%AI5_BeginGradient: (Ramp)",
            "(Ramp) 0 2 Bd",
            "[",
            "0 0 0 1 1 1 6 50 100 %_BS",
            "1 0 0 0 1 1 6 50 0 %_BS",
            "BD",
            "%AI5_EndGradient",
        ]
    head += ["%%EndSetup", "%AI5_BeginLayer",
             "1 1 1 1 0 0 1 0 79 128 255 0 50 0 Lb", "(Layer 1) Ln",
             "0 A", "0 XR", "0 g"]
    tail = ["LB", "%AI5_EndLayer--", "%%Trailer", "%%EOF", ""]
    stream = "\r".join(head + art + tail).encode("latin-1")

    if compressed == "zstd":            # Illustrator 2020 and later
        from mediasmith.illustrator import zstd
        stream = b"%AI24_ZStandard_Data" + zstd.compress(stream)
    elif compressed:
        stream = b"%AI12_CompressedData" + zlib.compress(stream)
    if not pdf_container:
        path.write_bytes(stream)
        return path

    objects = {
        1: b"<</Type/Catalog/Pages 3 0 R>>",
        3: b"<</Type/Pages/Count 1/Kids[4 0 R]>>",
        4: ("<</Type/Page/Parent 3 0 R/MediaBox[%s]/PieceInfo<</Illustrator "
            "6 0 R>>>>" % " ".join(str(v) for v in artboard)).encode(),
        6: b"<</Private 7 0 R>>",
        7: b"<</AIPrivateData1 8 0 R/NumBlock 1>>",
        8: b"<</Length %d>>stream\r\n%s\rendstream" % (len(stream), stream),
    }
    out = bytearray(b"%PDF-1.5\r")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b"%d 0 obj\r" % number + objects[number] + b"\rendobj\r"
    start = len(out)
    top = max(objects) + 1
    out += b"xref\r\n0 %d\r\n" % top + b"0000000000 65535 f \r\n"
    for number in range(1, top):
        out += b"%010d 00000 n \r\n" % offsets.get(number, 0)
    out += b"trailer\r<</Size %d/Root 1 0 R>>\rstartxref\r%d\r%%%%EOF\r" % (top, start)
    path.write_bytes(bytes(out))
    return path


def make_media_tree(root: Path) -> Path:
    """The standard scratch tree: one of everything, plus edge cases."""
    root.mkdir(parents=True, exist_ok=True)
    cover = make_png()

    music = root / "Music"
    music.mkdir()
    make_mp3(music / "01 Song One.mp3",
             tags={"title": "Song One", "artist": "The Band",
                   "album": "First Album", "albumartist": "The Band"},
             cover=cover)
    make_mp3(music / "02 Song Two.mp3",
             tags={"title": "Song Two", "artist": "The Band"})

    movie = root / "Movies" / "Alien (1979)"
    movie.mkdir(parents=True)
    (movie / "Alien.1979.mkv").write_bytes(b"not a real video")
    (movie / "Alien.1979.srt").write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nhi\n")
    make_png(movie / "poster.jpg")   # png bytes; suffix is what matters here

    books = root / "Books"
    books.mkdir()
    make_epub(books / "Dune.epub", cover=cover)

    pics = root / "Pics"
    pics.mkdir()
    make_png(pics / "photo.png")

    (root / "notes.txt").write_text("plain text\n")
    (root / "Empty").mkdir()
    return root
