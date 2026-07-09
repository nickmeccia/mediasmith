"""Builders for tiny-but-valid media files.

Shared by the pytest fixtures and the fuzz harness. Never point tests at the
real library — build scratch trees with these instead.
"""

from __future__ import annotations

import io
import zipfile
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
              series: str | None = "Dune", cover: bytes | None = None) -> Path:
    series_meta = (f'<meta name="calibre:series" content="{series}"/>'
                   if series else "")
    cover_manifest = ('<item id="cover-image" href="cover.png" '
                      'media-type="image/png"/>' if cover is not None else "")
    cover_meta = '<meta name="cover" content="cover-image"/>' if cover is not None else ""
    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:publisher>Chilton Books</dc:publisher>
    <dc:language>en</dc:language>
    <dc:date>1965-08-01</dc:date>
    {series_meta}
    {cover_meta}
  </metadata>
  <manifest>{cover_manifest}</manifest>
  <spine/>
</package>"""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="content.opf"
    media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), b"application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("content.opf", opf)
        if cover is not None:
            z.writestr("cover.png", cover)
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
