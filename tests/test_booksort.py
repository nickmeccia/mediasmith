"""Sort folders: wrap each book's files into "Author Sort - Title/"."""

from mediasmith import booksort
from tests.mediafactory import make_epub, make_omnibus, make_png


def test_folder_name_uses_file_as_when_present(tmp_path):
    book = make_omnibus(tmp_path / "o.epub", author_sort="Wildbow")
    assert booksort.folder_name_for(book) == "Wildbow - Omnibus"


def test_folder_name_infers_author_sort(tmp_path):
    book = make_epub(tmp_path / "d.epub", title="Dune",
                     author="Frank Herbert", series=None)
    assert booksort.folder_name_for(book) == "Herbert, Frank - Dune"


def test_folder_name_includes_series_and_two_digit_index(tmp_path):
    book = make_epub(tmp_path / "f.epub", title="The Fifth Season",
                     author="N. K. Jemisin", author_sort="Jemisin, N. K.",
                     series="The Broken Earth", series_index="1")
    assert booksort.folder_name_for(book) == \
        "Jemisin, N. K. - The Broken Earth - 01 - The Fifth Season"


def test_folder_name_keeps_fractional_series_index(tmp_path):
    book = make_epub(tmp_path / "n.epub", title="Novella",
                     author="N. K. Jemisin", author_sort="Jemisin, N. K.",
                     series="The Broken Earth", series_index="2.5")
    assert booksort.folder_name_for(book) == \
        "Jemisin, N. K. - The Broken Earth - 02.5 - Novella"


def test_folder_name_drops_series_without_numeric_index(tmp_path):
    # a series tag but no readable index: can't order it, so fall back
    book = make_epub(tmp_path / "s.epub", title="Solo", author="One Namer",
                     author_sort="Namer, One", series="Some Series",
                     series_index=None)
    assert booksort.folder_name_for(book) == "Namer, One - Solo"


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


def test_execute_renames_books_to_the_folder_name(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    (tmp_path / "Dune.mobi").write_bytes(b"mobi")
    (tmp_path / "Herbert, Frank - Dune").mkdir()    # pre-existing: reuse
    plan = booksort.build_plan(tmp_path)
    moved, errors = booksort.execute(plan)
    assert moved == 2 and errors == []
    wrapper = tmp_path / "Herbert, Frank - Dune"
    assert (wrapper / "Herbert, Frank - Dune.epub").exists()
    assert (wrapper / "Herbert, Frank - Dune.mobi").exists()   # every format
    assert not (tmp_path / "Dune.epub").exists()


def test_execute_keeps_sidecar_names(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    make_png(tmp_path / "cover.jpg")
    (tmp_path / "metadata.opf").write_text("<package/>")
    plan = booksort.build_plan(tmp_path)
    moved, errors = booksort.execute(plan)
    assert errors == []
    wrapper = tmp_path / "Herbert, Frank - Dune"
    assert (wrapper / "Herbert, Frank - Dune.epub").exists()   # book renamed
    assert (wrapper / "cover.jpg").exists()         # sidecars keep their names
    assert (wrapper / "metadata.opf").exists()


def test_execute_refuses_overwrite_per_file(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    wrapper = tmp_path / "Herbert, Frank - Dune"
    wrapper.mkdir()
    (wrapper / "Herbert, Frank - Dune.epub").write_bytes(b"precious")
    plan = booksort.build_plan(tmp_path)
    moved, errors = booksort.execute(plan)
    assert moved == 0 and len(errors) == 1
    assert (wrapper / "Herbert, Frank - Dune.epub").read_bytes() == b"precious"
    assert (tmp_path / "Dune.epub").exists()        # source untouched


# -- single-book sort: the ebook-pane button --------------------------------------


def test_probe_book_true_when_name_differs(tmp_path):
    book = make_epub(tmp_path / "Dune.epub")
    assert booksort.probe_book(book) is True


def test_probe_book_false_when_already_wrapped(tmp_path):
    wrapper = tmp_path / "Herbert, Frank - Dune"
    wrapper.mkdir()
    book = make_epub(wrapper / "Dune.epub")
    assert booksort.probe_book(book) is False       # already in place


def test_probe_book_false_for_non_epub(tmp_path):
    (tmp_path / "Dune.mobi").write_bytes(b"mobi")   # no readable metadata
    assert booksort.probe_book(tmp_path / "Dune.mobi") is False


def test_plan_for_book_renames_and_wraps_one_file(tmp_path):
    book = make_epub(tmp_path / "Dune.epub")
    (tmp_path / "Dune.mobi").write_bytes(b"mobi")   # a sibling, left behind
    plan = booksort.plan_for_book(book)
    assert plan is not None and len(plan.groups) == 1
    assert plan.groups[0].files == (book,)          # only the selected file
    new_path = booksort.sorted_path(book, plan.groups[0].folder_name)
    assert new_path == (tmp_path / "Herbert, Frank - Dune"
                        / "Herbert, Frank - Dune.epub")
    moved, errors = booksort.execute(plan)
    assert moved == 1 and errors == []
    assert new_path.exists()
    assert not book.exists()
    assert (tmp_path / "Dune.mobi").exists()         # sibling untouched


def test_plan_for_book_none_when_metadata_unreadable(tmp_path):
    (tmp_path / "Mystery.mobi").write_bytes(b"mobi")  # only epubs are readable
    assert booksort.plan_for_book(tmp_path / "Mystery.mobi") is None


def test_series_book_folder_and_file_take_full_series_name(tmp_path):
    book = make_epub(tmp_path / "raw name.epub", title="The Fifth Season",
                     author="N. K. Jemisin", author_sort="Jemisin, N. K.",
                     series="The Broken Earth", series_index="1")
    plan = booksort.plan_for_book(book)
    new_path = booksort.sorted_path(book, plan.groups[0].folder_name)
    booksort.execute(plan)
    stem = "Jemisin, N. K. - The Broken Earth - 01 - The Fifth Season"
    assert new_path == tmp_path / stem / (stem + ".epub")   # folder AND file
    assert new_path.exists()
    assert not book.exists()
