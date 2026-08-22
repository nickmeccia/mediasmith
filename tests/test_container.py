"""Container title reads — the ffprobe replacement.

Fixtures in tests/fixtures/ are tiny synthetic containers committed to the
repo, so nothing here spawns (or requires) ffmpeg. Parity with the ffprobe
these replaced was checked against Nick's library on 2026-08-22: 12/12
agreement on .mkv, and matching release names on .mp4.
"""

from pathlib import Path

import pytest

from mediasmith import container

FIXTURES = Path(__file__).parent / "fixtures"
RELEASE = "Aliens.1986.SE.1080p.BluRay.x265-RARBG"


@pytest.mark.parametrize("name", ["titled.mkv", "titled.mp4"])
def test_reads_the_container_title(name):
    assert container.read_title(FIXTURES / name) == RELEASE


@pytest.mark.parametrize("name", ["untitled.mkv", "untitled.mp4"])
def test_untagged_is_none_not_empty(name):
    assert container.read_title(FIXTURES / name) is None


def test_unhandled_suffix_is_none(tmp_path):
    """.avi and .mov are deliberately unhandled — 0 of 71 sampled files in
    Nick's library carry a title tag, so ffprobe answered None for them too."""
    for suffix in (".avi", ".mov", ".txt"):
        junk = tmp_path / f"clip{suffix}"
        junk.write_bytes(b"not a real container")
        assert container.read_title(junk) is None


def test_junk_never_raises(tmp_path):
    """A truncated download or an unreadable mount is a None, exactly as a
    failed ffprobe was — never an exception into the details pane."""
    truncated = tmp_path / "half.mkv"
    truncated.write_bytes((FIXTURES / "titled.mkv").read_bytes()[:40])
    assert container.read_title(truncated) is None

    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    assert container.read_title(empty) is None

    assert container.read_title(tmp_path / "does-not-exist.mkv") is None


def test_suffix_match_is_case_insensitive(tmp_path):
    """NAS libraries are full of .MKV and .MP4 from old rippers."""
    for name, source in (("SHOUTY.MKV", "titled.mkv"),
                         ("SHOUTY.MP4", "titled.mp4")):
        loud = tmp_path / name
        loud.write_bytes((FIXTURES / source).read_bytes())
        assert container.read_title(loud) == RELEASE
