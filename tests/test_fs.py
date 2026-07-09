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
