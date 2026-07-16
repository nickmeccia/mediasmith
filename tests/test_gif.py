"""Video → GIF engine: argv construction through the runner seam."""

import pytest

from mediasmith import gif


def _video(tmp_path):
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"not a real video")
    return video


def test_two_passes_palette_then_render(tmp_path):
    video = _video(tmp_path)
    calls = []
    gif.make_gif(video, runner=calls.append)
    assert len(calls) == 2
    palette_pass, render_pass = calls
    assert any("palettegen" in part for part in palette_pass)
    assert any("paletteuse" in part for part in render_pass)
    assert render_pass[-1] == str(tmp_path / "clip.gif")


def test_defaults_are_the_tasty_ones(tmp_path):
    video = _video(tmp_path)
    calls = []
    gif.make_gif(video, runner=calls.append)
    filters = calls[0][calls[0].index("-vf") + 1]
    assert "fps=12" in filters
    assert "scale=480:-1:flags=lanczos" in filters


def test_options_thread_through(tmp_path):
    video = _video(tmp_path)
    calls = []
    gif.make_gif(video, fps=24, width=320, start=1.5, duration=3.0,
                 runner=calls.append)
    for argv in calls:
        joined = " ".join(argv)
        assert "fps=24" in joined and "scale=320" in joined
        assert "-ss 1.5" in joined and "-t 3.0" in joined


def test_refuses_existing_target(tmp_path):
    video = _video(tmp_path)
    (tmp_path / "clip.gif").write_bytes(b"precious")
    with pytest.raises(FileExistsError):
        gif.make_gif(video, runner=lambda argv: None)
    assert (tmp_path / "clip.gif").read_bytes() == b"precious"


def test_rejects_nonpositive_dimensions(tmp_path):
    video = _video(tmp_path)
    with pytest.raises(ValueError):
        gif.make_gif(video, fps=0, runner=lambda argv: None)
    with pytest.raises(ValueError):
        gif.make_gif(video, width=0, runner=lambda argv: None)
