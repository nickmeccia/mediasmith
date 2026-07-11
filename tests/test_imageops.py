"""Image ops engine: convert, resize math, rotate."""

import pytest
from PIL import Image

from mediasmith import imageops


def _png(path, size=(8, 6), mode="RGB"):
    Image.new(mode, size, (200, 60, 60) if mode == "RGB"
              else (200, 60, 60, 128)).save(path, format="PNG")
    return path


def test_convert_png_to_every_offered_format(tmp_path):
    for fmt in imageops.CONVERT_FORMATS:
        if fmt == "png":
            continue
        src = _png(tmp_path / f"src-{fmt}.png")
        target = imageops.convert(src, fmt)
        assert target == src.with_suffix("." + fmt)
        assert Image.open(target).size == (8, 6)


def test_convert_rgba_to_jpg_flattens(tmp_path):
    src = _png(tmp_path / "a.png", mode="RGBA")
    target = imageops.convert(src, "jpg")
    assert Image.open(target).mode == "RGB"


def test_convert_refuses_same_format_and_overwrite(tmp_path):
    src = _png(tmp_path / "a.png")
    with pytest.raises(ValueError, match="already"):
        imageops.convert(src, "png")
    existing = tmp_path / "a.webp"
    existing.write_bytes(b"precious")
    with pytest.raises(FileExistsError):
        imageops.convert(src, "webp")
    assert existing.read_bytes() == b"precious"


def test_fit_dimensions_linked_and_unlinked():
    fit = imageops.fit_dimensions
    assert fit(800, 600, new_width=400, new_height=None) == (400, 300)
    assert fit(800, 600, new_width=None, new_height=300) == (400, 300)
    assert fit(800, 600, new_width=100, new_height=100) == (100, 100)
    assert fit(800, 600, new_width=None, new_height=None) == (800, 600)
    assert fit(800, 600, new_width=1, new_height=None) == (1, 1)  # floor 1


def test_resize_writes_suffixed_sibling(tmp_path):
    src = _png(tmp_path / "a.png")
    target = imageops.resize(src, 4, 3)
    assert target == tmp_path / "a (4x3).png"
    assert Image.open(target).size == (4, 3)
    assert Image.open(src).size == (8, 6)        # source untouched
    with pytest.raises(FileExistsError):
        imageops.resize(src, 4, 3)
    with pytest.raises(ValueError):
        imageops.resize(src, 0, 3)


def test_rotate_in_place_clockwise(tmp_path):
    src = _png(tmp_path / "a.png")               # 8 wide, 6 high
    path, lossy = imageops.rotate(src)
    assert path == src and lossy is False        # png: lossless
    assert Image.open(src).size == (6, 8)        # one clockwise turn
    imageops.rotate(src, 3)                      # three more = full circle
    assert Image.open(src).size == (8, 6)


def test_rotate_jpeg_reports_lossy(tmp_path):
    src = tmp_path / "a.jpg"
    Image.new("RGB", (8, 6), (1, 2, 3)).save(src, format="JPEG")
    _, lossy = imageops.rotate(src)
    assert lossy is True
    assert Image.open(src).size == (6, 8)
