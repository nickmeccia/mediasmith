"""Sort folders: wrap each book's files into "Author Sort - Title/"."""

from mediasmith import booksort
from tests.mediafactory import make_epub, make_omnibus, make_png


def test_folder_name_uses_file_as_when_present(tmp_path):
    book = make_omnibus(tmp_path / "o.epub", author_sort="Wildbow")
    assert booksort.folder_name_for(book) == "Wildbow - Omnibus"


def test_folder_name_infers_author_sort(tmp_path):
    book = make_epub(tmp_path / "d.epub", title="Dune",
                     author="Frank Herbert")
    assert booksort.folder_name_for(book) == "Herbert, Frank - Dune"


def test_plan_groups_formats_by_stem(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    (tmp_path / "Dune.mobi").write_bytes(b"mobi")
    (tmp_path / "Dune.azw3").write_bytes(b"azw3")
    plan = booksort.build_plan(tmp_path)
    assert len(plan.groups) == 1
    group = plan.groups[0]
    assert group.folder_name == "Herbert, Frank - Dune"
    assert {f.name for f in group.files} >= {"Dune.epub", "Dune.mobi",
                                             "Dune.azw3"}


def test_single_book_takes_its_sidecars(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    make_png(tmp_path / "cover.jpg")            # png bytes, jpg name — fine
    (tmp_path / "metadata.opf").write_text("<package/>")
    plan = booksort.build_plan(tmp_path)
    names = {f.name for f in plan.groups[0].files}
    assert {"Dune.epub", "cover.jpg", "metadata.opf"} <= names


def test_sidecars_stay_when_books_share_the_folder(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    make_epub(tmp_path / "Solo.epub", title="Solo", author="Plainname")
    make_png(tmp_path / "cover.jpg")
    plan = booksort.build_plan(tmp_path)
    assert len(plan.groups) == 2
    for group in plan.groups:
        assert "cover.jpg" not in {f.name for f in group.files}
    assert any(s.source.name == "cover.jpg" for s in plan.skips)


def test_wrapper_folder_is_a_noop(tmp_path):
    wrapper = tmp_path / "Herbert, Frank - Dune"
    wrapper.mkdir()
    make_epub(wrapper / "Dune.epub")
    assert booksort.probe(wrapper) is False
    assert booksort.build_plan(wrapper).empty


def test_bookless_group_is_skipped_not_guessed(tmp_path):
    (tmp_path / "Mystery.mobi").write_bytes(b"mobi")
    plan = booksort.build_plan(tmp_path)
    assert plan.empty
    assert plan.skips[0].source.name == "Mystery.mobi"


def test_probe_true_only_for_unwrapped_books(tmp_path):
    assert booksort.probe(tmp_path) is False    # nothing here
    make_epub(tmp_path / "Dune.epub")
    assert booksort.probe(tmp_path) is True


def test_execute_wraps_and_reuses_existing_folder(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    (tmp_path / "Dune.mobi").write_bytes(b"mobi")
    (tmp_path / "Herbert, Frank - Dune").mkdir()    # pre-existing: reuse
    plan = booksort.build_plan(tmp_path)
    moved, errors = booksort.execute(plan)
    assert moved == 2 and errors == []
    wrapper = tmp_path / "Herbert, Frank - Dune"
    assert (wrapper / "Dune.epub").exists()
    assert (wrapper / "Dune.mobi").exists()
    assert not (tmp_path / "Dune.epub").exists()


def test_execute_refuses_overwrite_per_file(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    wrapper = tmp_path / "Herbert, Frank - Dune"
    wrapper.mkdir()
    (wrapper / "Dune.epub").write_bytes(b"precious")
    plan = booksort.build_plan(tmp_path)
    moved, errors = booksort.execute(plan)
    assert moved == 0 and len(errors) == 1
    assert (wrapper / "Dune.epub").read_bytes() == b"precious"
    assert (tmp_path / "Dune.epub").exists()        # source untouched
