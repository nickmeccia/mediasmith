"""Case-only folder collisions (casing.py) — Nick's 2026-08-25 report."""

from pathlib import Path

import pytest

from mediasmith import adapters, booksort, casing, folderize, videofolder

from .mediafactory import make_epub, make_mp3, make_png


def case_insensitive(tmp_path: Path) -> bool:
    (tmp_path / "CaseProbe").mkdir()
    return (tmp_path / "caseprobe").exists()


@pytest.fixture()
def blind(tmp_path):
    """A directory on a case-insensitive volume, or the test is skipped."""
    root = tmp_path / "probe"
    root.mkdir()
    if not case_insensitive(root):
        pytest.skip("case-sensitive filesystem: no collision to resolve")
    work = tmp_path / "work"
    work.mkdir()
    return work


# -- the detector -----------------------------------------------------------


def test_no_clash_when_nothing_is_there(tmp_path):
    assert casing.clash(tmp_path / "The Matrix") is None


def test_no_clash_when_the_spelling_already_matches(tmp_path):
    (tmp_path / "The Matrix").mkdir()
    assert casing.clash(tmp_path / "The Matrix") is None


def test_clash_finds_the_other_spelling(blind):
    (blind / "the matrix").mkdir()
    assert casing.clash(blind / "The Matrix") == blind / "the matrix"


def test_clashes_are_shallowest_first(blind):
    (blind / "the beatles" / "abbey road").mkdir(parents=True)
    pairs = casing.clashes([blind / "The Beatles" / "Abbey Road",
                            blind / "The Beatles"])
    assert [existing.name for existing, _ in pairs] == ["the beatles",
                                                        "abbey road"]


def test_a_file_is_not_a_folder_clash(blind):
    (blind / "the matrix").write_text("not a folder")
    assert casing.clash(blind / "The Matrix") is None


# -- the two answers --------------------------------------------------------


def test_rename_respells_the_folder(blind):
    (blind / "the matrix").mkdir()
    (blind / "the matrix" / "keep.txt").write_text("hi")
    casing.rename(blind / "the matrix", blind / "The Matrix")
    assert casing.spelled_exactly(blind / "The Matrix")
    assert (blind / "The Matrix" / "keep.txt").read_text() == "hi"


def test_resolve_keeps_contents_by_default(blind):
    (blind / "the matrix").mkdir()
    (blind / "the matrix" / "keep.txt").write_text("hi")
    assert casing.resolve([(blind / "the matrix", blind / "The Matrix")]) == []
    assert (blind / "The Matrix" / "keep.txt").is_file()


def test_resolve_purges_contents_to_the_trash(blind, monkeypatch):
    trashed = []
    monkeypatch.setattr(adapters, "trash",
                        lambda p: (trashed.append(p), Path(p).unlink())[0])
    monkeypatch.delenv("MEDIASMITH_OFFLINE", raising=False)
    (blind / "the matrix").mkdir()
    (blind / "the matrix" / "old.txt").write_text("bye")
    errors = casing.resolve([(blind / "the matrix", blind / "The Matrix")],
                            purge=True)
    assert errors == []
    assert [p.name for p in trashed] == ["old.txt"]
    assert casing.spelled_exactly(blind / "The Matrix")
    assert list((blind / "The Matrix").iterdir()) == []


def test_purge_refuses_while_offline(blind, monkeypatch):
    monkeypatch.setenv("MEDIASMITH_OFFLINE", "1")
    (blind / "the matrix").mkdir()
    (blind / "the matrix" / "old.txt").write_text("bye")
    errors = casing.purge_contents(blind / "the matrix")
    assert errors and "OFFLINE" in errors[0][1]
    assert (blind / "the matrix" / "old.txt").is_file()


# -- the engines, once the clash is resolved --------------------------------


def test_video_folderize_never_moves_the_folder_into_itself(blind):
    """The data-loss bug: "the matrix/" IS "The Matrix/" here, so it was
    picked up as a companion and moved inside itself — taking the video
    with it."""
    video = blind / "The Matrix.mkv"
    video.write_bytes(b"not a real video")
    (blind / "the matrix").mkdir()
    make_png(blind / "the matrix" / "poster.jpg")
    assert videofolder.companions(video) == ()
    landed, moved, errors = videofolder.execute(video)
    assert errors == []
    assert landed.is_file() and landed.name == "The Matrix.mkv"
    assert (landed.parent / "poster.jpg").is_file()   # the folder survived


def test_video_folderize_after_the_rename_uses_nicks_casing(blind):
    video = blind / "The Matrix.mkv"
    video.write_bytes(b"not a real video")
    (blind / "the matrix").mkdir()
    casing.resolve(casing.clashes([videofolder.wrap_dir(video)]))
    landed, moved, errors = videofolder.execute(video)
    assert errors == []
    assert landed == blind / "The Matrix" / "The Matrix.mkv"
    assert casing.spelled_exactly(landed.parent)


def test_folderize_does_not_renumber_a_file_that_is_already_there(blind):
    """A file in "the beatles/abbey road/" collided with ITSELF at the
    tagged casing and grew a "(1)" on every run."""
    home = blind / "the beatles" / "abbey road"
    home.mkdir(parents=True)
    song = make_mp3(home / "01 Come Together.mp3",
                    tags={"artist": "The Beatles", "album": "Abbey Road"})
    plan = folderize.build_plan(blind)
    assert [m.target.name for m in plan.moves] == ["01 Come Together.mp3"]
    assert folderize.wanted_dirs(plan) == [blind / "The Beatles",
                                           blind / "The Beatles" / "Abbey Road"]
    casing.resolve(casing.clashes(folderize.wanted_dirs(plan)))
    moved, skipped, errors = folderize.execute(plan)
    assert errors == []
    landed = blind / "The Beatles" / "Abbey Road" / "01 Come Together.mp3"
    assert landed.is_file()
    assert casing.spelled_exactly(landed.parent)
    assert casing.spelled_exactly(landed.parent.parent)
    assert not song.with_name("01 Come Together (1).mp3").exists()


def test_book_sort_wanted_dirs_are_the_wrappers(tmp_path):
    make_epub(tmp_path / "Dune.epub")
    plan = booksort.plan_for_book(tmp_path / "Dune.epub")
    assert booksort.wanted_dirs(plan) == [
        tmp_path / plan.groups[0].folder_name]
