"""Omnibus engine tests: tiny generated omnibuses in, split epubs out."""

import zipfile

import pytest

from mediasmith import omnibus

from .mediafactory import make_epub, make_omnibus


@pytest.fixture()
def omni(tmp_path):
    return make_omnibus(tmp_path / "Herbert, Frank - Omnibus.epub")


# -- detection ----------------------------------------------------------------


def test_probe_true_on_an_omnibus(omni):
    assert omnibus.probe(omni) is True


def test_probe_false_on_a_plain_book(tmp_path):
    assert omnibus.probe(make_epub(tmp_path / "Dune.epub")) is False


def test_probe_false_on_a_flat_toc(tmp_path):
    # chapters at top level, no structural book containers: v2 doesn't
    # offer the split (v1's manual boundary conversation is not ported)
    flat = make_omnibus(tmp_path / "flat.epub", flat=True)
    assert omnibus.probe(flat) is False


def test_probe_false_on_garbage(tmp_path):
    bad = tmp_path / "bad.epub"
    bad.write_bytes(b"not a zip at all")
    assert omnibus.probe(bad) is False


def test_detect_books_skips_boilerplate():
    nps = [
        {"label": "Cover", "src": "c.xhtml", "children": []},
        {"label": "Book 1", "src": "1.xhtml",
         "children": [{"label": "Ch", "src": "1.xhtml", "children": []}]},
        {"label": "Book 2", "src": "2.xhtml",
         "children": [{"label": "Ch", "src": "2.xhtml", "children": []}]},
    ]
    assert [np["label"] for np in omnibus.detect_books(nps)] \
        == ["Book 1", "Book 2"]


# -- planning -------------------------------------------------------------------


def test_build_plan_two_books(omni):
    plan = omnibus.build_plan(omni)
    assert not plan.empty
    assert [b.label for b in plan.books] == ["Book 1", "Book 2"]
    assert [b.chapters for b in plan.books] == [2, 2]
    assert [b.filename for b in plan.books] == [
        "Herbert, Frank - Book 1.epub",
        "Herbert, Frank - Book 2.epub"]


def test_plan_spines_share_front_matter_not_chapters(omni):
    plan = omnibus.build_plan(omni)
    one, two = plan.books
    assert "OEBPS/titlepage.xhtml" in one.spine     # front matter for both
    assert "OEBPS/titlepage.xhtml" in two.spine
    assert "OEBPS/b1c1.xhtml" in one.spine
    assert "OEBPS/b1c1.xhtml" not in two.spine      # chapters don't leak
    assert "OEBPS/b2c1.xhtml" not in one.spine


def test_plan_author_sort_inferred_when_missing(tmp_path):
    omni = make_omnibus(tmp_path / "o.epub", author="Frank Herbert",
                        author_sort="")
    plan = omnibus.build_plan(omni)
    assert plan.author_sort == "Herbert, Frank"


def test_build_plan_flat_toc_is_empty(tmp_path):
    flat = make_omnibus(tmp_path / "flat.epub", flat=True)
    assert omnibus.build_plan(flat).empty


# -- execution -------------------------------------------------------------------


def test_execute_writes_valid_epubs(omni, tmp_path):
    written, errors = omnibus.execute(omnibus.build_plan(omni))
    assert errors == []
    assert [p.name for p in written] == [
        "Herbert, Frank - Book 1.epub",
        "Herbert, Frank - Book 2.epub"]
    for out in written:
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            assert names[0] == "mimetype"           # first and stored
            assert z.getinfo("mimetype").compress_type \
                == zipfile.ZIP_STORED
            # the output is itself parseable as an epub
            data = omnibus.parse_opf(z, omnibus.parse_container(z))
        assert data["ncx_href"]
    with zipfile.ZipFile(written[0]) as z:
        names = set(z.namelist())
        assert "OEBPS/b1c1.xhtml" in names
        assert "OEBPS/b2c1.xhtml" not in names      # other book excluded
        assert "OEBPS/style.css" in names           # scanned assets ride
        assert "OEBPS/pic.png" in names


def test_execute_output_toc_promotes_chapters(omni):
    written, _ = omnibus.execute(omnibus.build_plan(omni))
    with zipfile.ZipFile(written[0]) as z:
        data = omnibus.parse_opf(z, omnibus.parse_container(z))
        nps = omnibus.parse_ncx(z, data["ncx_href"], data["opf_dir"])
        assert data["title"] == "Book 1"
    # the book-title level is dropped: chapters are root entries
    assert [np["label"] for np in nps] == ["Chapter 1", "Chapter 2"]


def test_execute_refuses_overwrite(omni):
    plan = omnibus.build_plan(omni)
    blocker = omni.parent / plan.books[0].filename
    blocker.write_bytes(b"precious")
    written, errors = omnibus.execute(plan)
    assert [p.name for p in written] == ["Herbert, Frank - Book 2.epub"]
    assert errors == [("Herbert, Frank - Book 1.epub", "already exists")]
    assert blocker.read_bytes() == b"precious"


def test_three_book_omnibus_splits_three_ways(tmp_path):
    omni = make_omnibus(tmp_path / "trilogy.epub", books=3, chapters=1)
    plan = omnibus.build_plan(omni)
    written, errors = omnibus.execute(plan)
    assert errors == [] and len(written) == 3
