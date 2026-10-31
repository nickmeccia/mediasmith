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


# -- crop (todo-6) -------------------------------------------------------------

def _image(tmp_path, name="page.jpg", size=(1200, 1800)):
    from PIL import Image
    path = tmp_path / name
    Image.new("RGB", size, (20, 80, 160)).save(path)
    return path


def test_a_ratio_leaves_the_largest_centred_rectangle():
    edges = imageops.centred_edges(1200, 1800, "1:1")
    assert edges == {"left": 0, "right": 0, "top": 300, "bottom": 300}
    assert imageops.crop_size(1200, 1800, edges) == (1200, 1200)


def test_a_ratio_on_a_wide_image_trims_the_sides():
    edges = imageops.centred_edges(4000, 2000, "1:1")
    assert imageops.crop_size(4000, 2000, edges) == (2000, 2000)


def test_an_odd_remainder_still_lands_on_the_ratio():
    """501 spare pixels cannot be split evenly; the result must still be
    exactly square."""
    edges = imageops.centred_edges(1000, 1501, "1:1")
    assert imageops.crop_size(1000, 1501, edges) == (1000, 1000)


def test_free_means_no_trim():
    assert imageops.centred_edges(1200, 1800, "free") == {
        "left": 0, "top": 0, "right": 0, "bottom": 0}


def test_the_box_never_inverts():
    """A stepper held down stops at the middle rather than turning the
    image inside out."""
    assert imageops.crop_size(100, 100, {"left": 500, "right": 500}) == (1, 100)
    assert imageops.crop_size(100, 100, {"top": 99, "bottom": 99}) == (100, 1)


def test_crop_writes_a_sibling_and_refuses_to_overwrite(tmp_path):
    from PIL import Image
    source = _image(tmp_path)
    target = imageops.crop(source, {"left": 100, "top": 50, "right": 0,
                                    "bottom": 50})
    assert target.name == "page (cropped).jpg"
    with Image.open(target) as image:
        assert image.size == (1100, 1700)
    with pytest.raises(FileExistsError):
        imageops.crop(source, {"left": 1, "top": 0, "right": 0, "bottom": 0})
    assert imageops.crop(source, {"left": 1, "top": 0, "right": 0,
                                  "bottom": 0}, overwrite=True) == target


def test_cropping_nothing_is_an_error(tmp_path):
    source = _image(tmp_path)
    with pytest.raises(ValueError):
        imageops.crop(source, {"left": 0, "top": 0, "right": 0, "bottom": 0})
