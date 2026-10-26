import os
import time

import pytest

from mediasmith import fs


@pytest.fixture(autouse=True)
def fresh_cache():
    fs.clear_cache()
    yield
    fs.clear_cache()


def build(tmp_path):
    (tmp_path / "b_dir").mkdir()
    (tmp_path / "a_file.txt").write_text("x")
    (tmp_path / "C_dir").mkdir()
    return tmp_path


def test_listing_names_and_types(tmp_path):
    build(tmp_path)
    entries = fs.list_dir(tmp_path)
    assert [e.name for e in entries] == ["a_file.txt", "b_dir", "C_dir"]
    assert [e.is_dir for e in entries] == [False, True, True]


def test_sort_key_is_case_insensitive():
    names = ["banana", "Apple", "cherry"]
    assert sorted(names, key=fs.sort_key) == ["Apple", "banana", "cherry"]


def test_sort_key_orders_digit_runs_numerically():
    names = ["10 Ten", "2 Two", "1 One"]
    assert sorted(names, key=fs.sort_key) == ["1 One", "2 Two", "10 Ten"]


def test_sort_key_mixed_text_and_digits():
    names = ["track", "track 10", "track 2", "Track 1"]
    assert sorted(names, key=fs.sort_key) == [
        "track", "Track 1", "track 2", "track 10"]


def test_listing_interleaves_files_and_dirs(tmp_path):
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha.txt").write_text("x")
    (tmp_path / "gamma").mkdir()
    (tmp_path / "delta.txt").write_text("x")
    entries = fs.list_dir(tmp_path)
    assert [e.name for e in entries] == [
        "alpha.txt", "beta", "delta.txt", "gamma"]


def test_listing_is_cached(tmp_path):
    build(tmp_path)
    first = fs.list_dir(tmp_path)
    second = fs.list_dir(tmp_path)
    assert first is second   # cache hit returns the same object


def test_cache_invalidates_on_change(tmp_path):
    build(tmp_path)
    first = fs.list_dir(tmp_path)
    time.sleep(0.01)
    (tmp_path / "new.txt").write_text("y")
    second = fs.list_dir(tmp_path)
    assert second is not first
    assert "new.txt" in [e.name for e in second]


def test_unreadable_dir_raises(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores permissions")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)
    try:
        with pytest.raises(OSError):
            fs.list_dir(locked)
    finally:
        locked.chmod(0o755)


def test_cached_children_answer_is_dir_without_stat(tmp_path):
    build(tmp_path)
    children = fs.cached_children(tmp_path)
    by_name = {p.name: p for p in children}
    # Remove the underlying entries: cached answers must survive.
    (tmp_path / "a_file.txt").unlink()
    (tmp_path / "b_dir").rmdir()
    assert by_name["a_file.txt"].is_dir() is False
    assert by_name["b_dir"].is_dir() is True


def test_cached_children_unreadable_is_empty(tmp_path):
    assert fs.cached_children(tmp_path / "missing") == []


# -- the async front door (fs rule 3: nothing here is event-loop safe) -------


async def test_alist_dir_matches_list_dir(tmp_path):
    build(tmp_path)
    assert await fs.alist_dir(tmp_path) == fs.list_dir(tmp_path)


async def test_acached_children_matches_cached_children(tmp_path):
    build(tmp_path)
    assert ([str(p) for p in await fs.acached_children(tmp_path)]
            == [str(p) for p in fs.cached_children(tmp_path)])


async def test_ais_dir(tmp_path):
    build(tmp_path)
    assert await fs.ais_dir(tmp_path / "b_dir") is True
    assert await fs.ais_dir(tmp_path / "a_file.txt") is False
    assert await fs.ais_dir(tmp_path / "missing") is False


async def test_ais_dir_of_a_cached_path_never_touches_the_disk(tmp_path):
    build(tmp_path)
    by_name = {p.name: p for p in fs.cached_children(tmp_path)}
    (tmp_path / "b_dir").rmdir()          # gone from the filesystem
    assert await fs.ais_dir(by_name["b_dir"]) is True


async def test_anode_type(tmp_path):
    build(tmp_path)
    assert await fs.anode_type(tmp_path / "b_dir") == "dir"
    assert await fs.anode_type(tmp_path / "a_file.txt") == "file"
    assert await fs.anode_type(tmp_path / "missing") == "missing"



# -- recursive totals (todo-5: how many files, how many bytes) ---------------


def tree(root):
    """A nested tree with a dotfile, a nested folder, and known bytes."""
    (root / "top.txt").write_bytes(b"a" * 10)
    (root / ".hidden").write_bytes(b"b" * 100)
    nested = root / "sub" / "deeper"
    nested.mkdir(parents=True)
    (nested / "one.bin").write_bytes(b"c" * 5)
    (nested / "two.bin").write_bytes(b"d" * 7)
    return root


def test_totals_count_the_whole_subtree(tmp_path):
    totals = fs.tree_totals(tree(tmp_path))
    assert (totals.files, totals.bytes) == (3, 22)
    assert totals.complete is True


def test_totals_skip_dot_entries(tmp_path):
    """Same rule as the ``contains`` counts: a dotfile isn't the user's."""
    tree(tmp_path)
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "big").write_bytes(b"x" * 1000)
    totals = fs.tree_totals(tmp_path)
    assert (totals.files, totals.bytes) == (3, 22)


def test_totals_are_cached_against_the_folders_own_signature(tmp_path):
    tree(tmp_path)
    first = fs.tree_totals(tmp_path)
    assert fs.tree_totals(tmp_path) is first          # hit: no second walk
    time.sleep(0.01)
    (tmp_path / "another.txt").write_bytes(b"e" * 3)  # a DIRECT child changes
    second = fs.tree_totals(tmp_path)                 # the signature
    assert (second.files, second.bytes) == (4, 25)


def test_a_deep_change_needs_the_cache_dropped(tmp_path):
    """Documented limit: the key is the top folder's own signature, so a
    file buried below it goes unnoticed until ^r clears the cache."""
    tree(tmp_path)
    stale = fs.tree_totals(tmp_path)
    (tmp_path / "sub" / "deeper" / "three.bin").write_bytes(b"f" * 9)
    assert fs.tree_totals(tmp_path) is stale
    fs.clear_cache()
    assert fs.tree_totals(tmp_path).files == 4


def test_an_exhausted_budget_reports_a_floor(tmp_path):
    """A walk that runs out of time says so instead of lying — and a
    floor is never cached."""
    for i in range(600):                    # past the clock-check interval
        (tmp_path / f"f{i}.txt").write_bytes(b"x")
    totals = fs.tree_totals(tmp_path, budget=-1)
    assert totals.complete is False
    assert str(tmp_path) not in fs._totals


def test_an_unreadable_subfolder_costs_accuracy_not_the_number(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores permissions")
    tree(tmp_path)
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "inside.bin").write_bytes(b"z" * 50)
    locked.chmod(0o000)
    try:
        totals = fs.tree_totals(tmp_path)
    finally:
        locked.chmod(0o755)
    assert (totals.files, totals.bytes) == (3, 22)


def test_totals_of_a_missing_folder_raise(tmp_path):
    with pytest.raises(OSError):
        fs.tree_totals(tmp_path / "missing")


def test_totals_never_descend_a_symlink_loop(tmp_path):
    tree(tmp_path)
    (tmp_path / "loop").symlink_to(tmp_path)      # would never terminate
    totals = fs.tree_totals(tmp_path)
    assert totals.files == 4                      # the link counts once


def test_a_walk_gives_up_when_the_selection_moves(tmp_path):
    """A thread worker can't be cancelled from outside, so the walk asks
    whether anyone still wants the answer (details._probe_totals)."""
    for i in range(600):
        (tmp_path / f"f{i}.txt").write_bytes(b"x")
    totals = fs.tree_totals(tmp_path, should_stop=lambda: True)
    assert totals.complete is False
    assert totals.files < 600
    assert str(tmp_path) not in fs._totals
