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


# -- the video codec (todo-5) ------------------------------------------------


@pytest.mark.parametrize("name", ["titled.mkv", "titled.mp4",
                                  "untitled.mkv", "untitled.mp4"])
def test_reads_the_video_codec(name):
    """Both fixtures carry an AVC track; the pane prints the standard's
    name, not the encoder's ("H.264", never "x264")."""
    assert container.read_video_codec(FIXTURES / name) == "H.264"


def _retyped(source: Path, target: Path, fourcc: bytes) -> Path:
    """The fixture .mp4 with its sample-description type swapped — the
    one field ``_sample_format`` reads, so no other box has to move."""
    target.write_bytes((FIXTURES / source).read_bytes()
                       .replace(b"avc1", fourcc))
    return target


def test_hevc_and_av1_mp4s_read_as_their_standards(tmp_path):
    assert container.read_video_codec(
        _retyped("titled.mp4", tmp_path / "h265.mp4", b"hvc1")) == "H.265"
    assert container.read_video_codec(
        _retyped("titled.mp4", tmp_path / "av1.mp4", b"av01")) == "AV1"


def test_an_unknown_codec_prints_raw(tmp_path):
    """A file nothing here has a name for still says something."""
    assert container.read_video_codec(
        _retyped("titled.mp4", tmp_path / "odd.mp4", b"zzzz")) == "zzzz"


def test_mov_reads_a_codec_though_it_has_no_title(tmp_path):
    """QuickTime is the same box layout: .mov is unhandled for the TITLE
    (nothing in Nick's library carries one) but not for the codec."""
    clip = _retyped("titled.mp4", tmp_path / "clip.mov", b"avc1")
    assert container.read_video_codec(clip) == "H.264"
    assert container.read_title(clip) is None


def test_avi_stays_unhandled(tmp_path):
    """Its codec lives in a RIFF stream header — a third format for one
    suffix, deliberately not parsed."""
    clip = tmp_path / "clip.avi"
    clip.write_bytes((FIXTURES / "titled.mp4").read_bytes())
    assert container.read_video_codec(clip) is None


def test_codec_junk_never_raises(tmp_path):
    truncated = tmp_path / "half.mkv"
    truncated.write_bytes((FIXTURES / "titled.mkv").read_bytes()[:40])
    assert container.read_video_codec(truncated) is None

    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    assert container.read_video_codec(empty) is None

    headerless = tmp_path / "junk.mp4"
    headerless.write_bytes(b"not a real container")
    assert container.read_video_codec(headerless) is None

    assert container.read_video_codec(tmp_path / "gone.mkv") is None
