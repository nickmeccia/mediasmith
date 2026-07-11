"""ebook-convert adapter. The real-conversion test needs Calibre and a
few seconds — it skips cleanly on machines without it."""

import pytest

from mediasmith import calibre
from tests.mediafactory import make_epub

HAVE_CALIBRE = calibre.find_ebook_convert() is not None


def test_missing_tool_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(calibre, "find_ebook_convert", lambda: None)
    src = make_epub(tmp_path / "b.epub")
    with pytest.raises(RuntimeError, match="Calibre not found"):
        calibre.convert(src, tmp_path / "b.mobi")


@pytest.mark.skipif(not HAVE_CALIBRE, reason="Calibre not installed")
def test_convert_epub_to_mobi(tmp_path):
    src = make_epub(tmp_path / "Dune.epub")
    dst = tmp_path / "Dune.mobi"
    calibre.convert(src, dst)
    assert dst.exists() and dst.stat().st_size > 0
    assert src.exists()                          # source untouched
    assert not list(tmp_path.glob(".convert-tmp-*"))


@pytest.mark.skipif(not HAVE_CALIBRE, reason="Calibre not installed")
def test_failed_convert_leaves_no_partial(tmp_path):
    src = tmp_path / "broken.epub"
    src.write_bytes(b"not an epub at all")
    dst = tmp_path / "broken.azw3"
    with pytest.raises(RuntimeError, match="ebook-convert failed"):
        calibre.convert(src, dst)
    assert not dst.exists()
    assert not list(tmp_path.glob(".convert-tmp-*"))
