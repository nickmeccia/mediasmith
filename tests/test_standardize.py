"""standardize-formatting: detection, extractors, and the rebuild."""

import zipfile

import pytest

from mediasmith import adapters, standardize
from tests.mediafactory import make_epub, make_png

# -- style detection (markers are v1's, tuned on real exports) -----------------


def test_detects_pale_from_svg_markers():
    assert standardize.detect_style('<div class="svg_outer">…') == "pale"


def test_detects_calibre_h2_from_p_p1():
    assert standardize.detect_style("<h2 class='p-p1'>Ch</h2>") == "calibre-h2"


def test_detects_calibre_bold_from_bold_span():
    html = '<p class="calibre_"><span class="bold">1.01</span></p>'
    assert standardize.detect_style(html) == "calibre-bold"


def test_detects_calibre_h1():
    assert standardize.detect_style(
        '<h1 class="calibre5">Ch</h1>') == "calibre-h1"


def test_detection_falls_back_to_generic():
    assert standardize.detect_style("<p>plain text</p>") == "generic"


# -- extractors ------------------------------------------------------------------


def test_calibre_h1_drops_heading_and_classes():
    html = ('<html><body><h1 class="calibre4">Title</h1>'
            '<p class="calibre1">Body text here.</p></body></html>')
    out = standardize.extract_calibre_h1(html, "Title")
    assert "<h1" not in out
    assert "class=" not in out
    assert "Body text here." in out


def test_calibre_bold_promotes_spans_and_drops_title_para():
    html = ('<html><body>'
            '<p class="c"><span class="c1"><span class="bold">1.01</span>'
            '</span></p>'
            '<p class="c">Real <span class="bold">bold</span> body.</p>'
            '</body></html>')
    out = standardize.extract_calibre_bold(html, "1.01")
    assert "1.01" not in out                     # title paragraph dropped
    assert "<strong>bold</strong>" in out        # bold spans became strong
    assert "<span" not in out                    # remaining spans unwrapped


def test_generic_strips_attributes_and_first_heading():
    html = ('<html><body><h1 style="color:red">Ch</h1>'
            '<p class="x" style="margin:0">Long enough body text.</p>'
            '</body></html>')
    out = standardize.extract_generic(html, "Ch")
    assert "<h1" not in out
    assert "class=" not in out and "style=" not in out
    assert "Long enough body text." in out


# -- the rebuild -----------------------------------------------------------------


def test_standardize_round_trip_carries_metadata_and_cover(tmp_path):
    cover = make_png()
    source = make_epub(tmp_path / "Dune.epub", cover=cover)
    target = standardize.clean_target(source)
    style, chapters = standardize.standardize(source, target)
    assert target.name == "Dune (clean).epub"
    assert style == "generic" and chapters == 1
    details = adapters.read_details(target)
    assert details.fields["title"] == "Dune"
    assert details.fields["author"] == "Frank Herbert"
    assert details.fields["series"] == "Dune"           # v1 dropped this
    assert details.fields["publisher"] == "Chilton Books"
    assert details.cover == cover                       # and this
    with zipfile.ZipFile(target) as z:
        assert "stylesheet.css" in z.namelist()
        chapter = z.read("chapter_0000.xhtml").decode()
    assert "dark and stormy" in chapter


def test_standardize_refuses_existing_target(tmp_path):
    source = make_epub(tmp_path / "Dune.epub")
    target = standardize.clean_target(source)
    target.write_bytes(b"precious")
    with pytest.raises(FileExistsError):
        standardize.standardize(source, target)
    assert target.read_bytes() == b"precious"


def test_standardize_requires_an_ncx(tmp_path):
    bad = tmp_path / "NoToc.epub"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("content.opf", "<package/>")
    with pytest.raises(ValueError):
        standardize.standardize(bad, standardize.clean_target(bad))


# -- folder mode -----------------------------------------------------------------


def test_folder_books_skips_clean_outputs_and_dirs(tmp_path):
    make_epub(tmp_path / "A.epub")
    make_epub(tmp_path / "A (clean).epub")
    (tmp_path / "sub").mkdir()
    (tmp_path / "notes.txt").write_text("x")
    assert standardize.folder_books(tmp_path) == [tmp_path / "A.epub"]


def test_probe_true_only_while_work_remains(tmp_path):
    source = make_epub(tmp_path / "A.epub")
    assert standardize.probe_folder(tmp_path) is True
    standardize.standardize(source, standardize.clean_target(source))
    assert standardize.probe_folder(tmp_path) is False


def test_run_carries_on_past_failures(tmp_path):
    good = make_epub(tmp_path / "Good.epub")
    blocked = make_epub(tmp_path / "Blocked.epub")
    standardize.clean_target(blocked).write_bytes(b"precious")
    events = list(standardize.run([blocked, good]))
    assert isinstance(events[0], standardize.BookFailed)
    assert isinstance(events[1], standardize.BookDone)
    assert standardize.clean_target(good).exists()
