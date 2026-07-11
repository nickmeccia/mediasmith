"""Folderize engine: plans, probes, and execution on scratch trees."""

from pathlib import Path

from mediasmith import folderize
from tests.mediafactory import make_mp3


def _messy_tree(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    make_mp3(root / "one.mp3",
             tags={"title": "One", "artist": "The Band", "album": "Alpha"})
    make_mp3(root / "two.mp3",
             tags={"title": "Two", "artist": "The Band", "album": "Alpha"})
    make_mp3(root / "three.mp3",
             tags={"title": "Three", "artist": "Other Act", "album": "Beta"})
    make_mp3(root / "untagged.mp3", tags={"title": "Mystery"})
    return root


def test_plan_groups_by_artist_album(tmp_path):
    root = _messy_tree(tmp_path / "m")
    plan = folderize.build_plan(root)
    targets = {m.source.name: m.target for m in plan.moves}
    assert targets["one.mp3"] == root / "The Band" / "Alpha" / "one.mp3"
    assert targets["three.mp3"] == root / "Other Act" / "Beta" / "three.mp3"
    assert [s.source.name for s in plan.skips] == ["untagged.mp3"]
    assert "artist" in plan.skips[0].reason


def test_organized_files_are_not_moves(tmp_path):
    root = tmp_path / "m"
    (root / "The Band" / "Alpha").mkdir(parents=True)
    make_mp3(root / "The Band" / "Alpha" / "one.mp3",
             tags={"title": "One", "artist": "The Band", "album": "Alpha"})
    plan = folderize.build_plan(root)
    assert plan.empty


def test_organized_album_deep_root_is_no_op(tmp_path):
    # highlighting the album folder itself must not plan Album/Artist/Album
    root = tmp_path / "m" / "The Band" / "Alpha"
    root.mkdir(parents=True)
    make_mp3(root / "one.mp3",
             tags={"title": "One", "artist": "The Band", "album": "Alpha"})
    assert folderize.build_plan(root).empty
    assert folderize.probe(root) is False


def test_misfiled_track_still_moves(tmp_path):
    root = tmp_path / "m"
    (root / "Wrong Guy" / "Alpha").mkdir(parents=True)
    make_mp3(root / "Wrong Guy" / "Alpha" / "one.mp3",
             tags={"title": "One", "artist": "The Band", "album": "Alpha"})
    plan = folderize.build_plan(root)
    assert [m.target for m in plan.moves] == [
        root / "The Band" / "Alpha" / "one.mp3"]


def test_execute_moves_skips_and_prunes(tmp_path):
    root = _messy_tree(tmp_path / "m")
    (root / "leftover").mkdir()                  # becomes empty → pruned? no:
    plan = folderize.build_plan(root)            # it was always empty → pruned
    moved, skipped, errors = folderize.execute(plan)
    assert (moved, skipped, errors) == (3, 1, [])
    assert (root / "The Band" / "Alpha" / "one.mp3").exists()
    assert (root / "Other Act" / "Beta" / "three.mp3").exists()
    assert (root / "* Skipped" / "untagged.mp3").exists()
    assert not (root / "leftover").exists()      # empty dirs pruned
    # a second pass has nothing left to do
    assert folderize.build_plan(root).empty
    assert folderize.probe(root) is False


def test_filename_collisions_get_suffixes(tmp_path):
    root = tmp_path / "m"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir(parents=True)
    tags = {"title": "One", "artist": "X", "album": "Y"}
    make_mp3(root / "a" / "one.mp3", tags=tags)
    make_mp3(root / "b" / "one.mp3", tags=tags)
    plan = folderize.build_plan(root)
    names = sorted(m.target.name for m in plan.moves)
    assert names == ["one (1).mp3", "one.mp3"]
    moved, skipped, errors = folderize.execute(plan)
    assert moved == 2 and not errors


def test_sanitized_folder_names(tmp_path):
    root = tmp_path / "m"
    root.mkdir()
    make_mp3(root / "one.mp3",
             tags={"title": "One", "artist": "AC/DC", "album": "Live: 1979"})
    plan = folderize.build_plan(root)
    target = plan.moves[0].target
    assert target.parent.parent.name == "AC-DC"
    assert target.parent.name == "Live- 1979"


def test_skipped_dir_is_not_reskipped(tmp_path):
    root = tmp_path / "m"
    skipdir = root / folderize.SKIPPED_DIR_NAME
    skipdir.mkdir(parents=True)
    make_mp3(skipdir / "untagged.mp3", tags={"title": "Mystery"})
    assert folderize.build_plan(root).empty
    assert folderize.probe(root) is False


def test_probe_finds_action_and_respects_budget(tmp_path):
    root = _messy_tree(tmp_path / "m")
    assert folderize.probe(root) is True
    assert folderize.probe(root, budget=0) is False   # budget exhausted
    assert folderize.probe(tmp_path / "nowhere") is False
