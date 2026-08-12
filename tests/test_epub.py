"""EPUB write primitives — cover replacement (epub.set_cover)."""

import io

from PIL import Image

from mediasmith import epub as epublib
from tests.mediafactory import make_epub, make_png


def _dims(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_set_cover_replaces_existing(tmp_path):
    book = make_epub(tmp_path / "d.epub", cover=make_png(size=(8, 8)))
    new = make_png(size=(40, 60), color=(10, 20, 30))
    epublib.set_cover(book, new)
    out = epublib.extract_cover_bytes(book)
    assert out is not None
    assert _dims(out) == (40, 60)                # the new image won


def test_set_cover_reencodes_to_existing_format(tmp_path):
    # existing cover is png (make_epub writes cover.png); a jpeg input is
    # re-encoded to png so the manifest's media-type stays valid
    book = make_epub(tmp_path / "d.epub", cover=make_png(size=(8, 8)))
    jpeg = io.BytesIO()
    Image.new("RGB", (30, 30), (200, 50, 50)).save(jpeg, format="JPEG")
    epublib.set_cover(book, jpeg.getvalue())
    out = epublib.extract_cover_bytes(book)
    assert Image.open(io.BytesIO(out)).format == "PNG"
    assert _dims(out) == (30, 30)


def test_set_cover_adds_one_when_absent(tmp_path):
    book = make_epub(tmp_path / "d.epub", cover=None)   # no cover to start
    assert epublib.extract_cover_bytes(book) is None
    epublib.set_cover(book, make_png(size=(50, 70)))
    out = epublib.extract_cover_bytes(book)
    assert out is not None and _dims(out) == (50, 70)
    # the OPF now points at the new cover
    _, opf = epublib.read_opf(book)
    assert 'name="cover"' in opf
    assert epublib.find_cover_href(opf, "content.opf") == "cover.jpg"


def test_set_cover_keeps_a_valid_epub(tmp_path):
    # the book still reads back: metadata intact, chapter preserved
    book = make_epub(tmp_path / "d.epub", title="Dune", cover=None)
    epublib.set_cover(book, make_png())
    _, opf = epublib.read_opf(book)
    assert epublib.dc_field(opf, "dc:title") == "Dune"
    import zipfile
    with zipfile.ZipFile(book) as z:
        assert z.namelist()[0] == "mimetype"
        assert "chap1.xhtml" in z.namelist()


def test_set_cover_rejects_non_image(tmp_path):
    book = make_epub(tmp_path / "d.epub", cover=None)
    try:
        epublib.set_cover(book, b"this is not an image")
    except Exception:
        pass
    else:
        raise AssertionError("expected a decode error on garbage bytes")
    assert (tmp_path / "d.epub.tmp") not in list(tmp_path.iterdir())  # cleaned
