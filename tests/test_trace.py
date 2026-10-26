"""Image Trace engine: the Illustrator → potrace mapping, the bitmap
prep, and the potrace round trips (skipped where potrace isn't installed)."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from mediasmith import trace
from mediasmith.trace import TraceSettings

needs_potrace = pytest.mark.skipif(trace.find_potrace() is None,
                                   reason="potrace not installed")


def _disc(path, size=(120, 80), mode="RGB"):
    """A black ellipse on white — one shape to trace."""
    image = Image.new(mode, size, "white")
    ImageDraw.Draw(image).ellipse((10, 10, size[0] - 10, size[1] - 10),
                                  fill="black")
    image.save(path)
    return path


# -- settings ----------------------------------------------------------------


def test_defaults_are_potraces_defaults():
    settings = TraceSettings()
    assert settings.turdsize == 2
    assert settings.alphamax == 1.0
    assert settings.opttolerance == 0.2


def test_corners_and_paths_map_across_their_whole_range():
    assert TraceSettings(corners=0).alphamax == pytest.approx(4 / 3, abs=1e-3)
    assert TraceSettings(corners=100).alphamax == 0
    assert TraceSettings(paths=100).opttolerance == 0
    assert TraceSettings(paths=0).opttolerance == 1.0


def test_steppers_clamp_to_their_range():
    settings = TraceSettings(threshold=250)
    assert settings.nudged("threshold", 10).threshold == 255
    assert TraceSettings(noise=1).nudged("noise", -10).noise == 1


def test_toggles_flip_and_format_cycles_both_ways():
    settings = TraceSettings()
    assert settings.nudged("invert", 1).invert is True
    assert settings.nudged("ignore_white", -1).ignore_white is False
    assert settings.nudged("format", 1).format == "eps"
    assert settings.nudged("format", -1).format == "pdf"


def test_display_prints_units_and_switches():
    settings = TraceSettings()
    assert settings.display("paths") == "80%"
    assert settings.display("noise") == "2 px"
    assert settings.display("threshold") == "128"
    assert settings.display("invert") == "off"
    assert settings.display("format") == "svg"


def test_every_control_has_a_row():
    names = [name for name, _ in trace.CONTROLS]
    assert names == ["threshold", "paths", "corners", "noise", "invert",
                     "ignore_white", "format"]


def test_potrace_args_use_potrace_names_and_opaque_only_for_vectors():
    args = trace.potrace_args(TraceSettings(ignore_white=False), "svg")
    assert args[:2] == ["-b", "svg"] and "--opaque" in args
    preview = trace.potrace_args(TraceSettings(ignore_white=False), "pgm",
                                 (40, 30))
    assert "--opaque" not in preview
    assert preview[-4:] == ["-W", "40", "-H", "30"]


# -- bitmap prep ---------------------------------------------------------------


def test_bitmap_thresholds_and_inverts(tmp_path):
    gray = Image.new("L", (2, 1))
    gray.putpixel((0, 0), 100)
    gray.putpixel((1, 0), 200)

    def pixels(settings):
        import io
        return list(Image.open(io.BytesIO(trace.bitmap(gray, settings)))
                    .convert("L").tobytes())

    assert pixels(TraceSettings(threshold=150)) == [0, 255]
    assert pixels(TraceSettings(threshold=250)) == [0, 0]
    assert pixels(TraceSettings(threshold=150, invert=True)) == [255, 0]


def test_transparency_lays_over_white(tmp_path):
    path = tmp_path / "logo.png"
    Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(path)     # fully clear
    assert set(trace.load_gray(path).tobytes()) == {255}


def test_fit_keeps_the_aspect_and_fills_one_side():
    assert trace.fit(300, 200, 150, 150) == (150, 100)
    assert trace.fit(200, 300, 150, 150) == (100, 150)
    assert trace.fit(8, 8, 400, 100) == (100, 100)     # scales up, too
    assert trace.fit(1000, 1, 10, 10) == (10, 1)       # never below 1


# -- potrace round trips ------------------------------------------------------


@needs_potrace
def test_preview_renders_at_the_requested_size(tmp_path):
    gray = trace.load_gray(_disc(tmp_path / "disc.png"))
    image = trace.preview(gray, TraceSettings(), (60, 40))
    assert image.size == (60, 40)
    assert image.mode == "L"
    assert min(image.tobytes()) < 50            # the disc is there


@needs_potrace
@pytest.mark.parametrize("fmt,magic", [("svg", b"<?xml"),
                                       ("eps", b"%!PS-Adobe"),
                                       ("pdf", b"%PDF")])
def test_trace_writes_each_format_beside_the_source(tmp_path, fmt, magic):
    source = _disc(tmp_path / "disc.jpg")
    target = trace.trace(source, TraceSettings(format=fmt))
    assert target == tmp_path / f"disc.{fmt}"
    assert target.read_bytes().startswith(magic)
    assert [p.name for p in tmp_path.iterdir()
            if p.name.startswith(".trace-tmp")] == []


@needs_potrace
def test_trace_refuses_to_overwrite(tmp_path):
    source = _disc(tmp_path / "disc.png")
    existing = tmp_path / "disc.svg"
    existing.write_text("precious")
    with pytest.raises(FileExistsError):
        trace.trace(source, TraceSettings())
    assert existing.read_text() == "precious"
    trace.trace(source, TraceSettings(), overwrite=True)
    assert existing.read_bytes().startswith(b"<?xml")


def test_trace_without_potrace_says_how_to_install(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "find_potrace", lambda: None)
    with pytest.raises(RuntimeError, match="brew install potrace"):
        trace.trace(_disc(tmp_path / "disc.png"), TraceSettings())
