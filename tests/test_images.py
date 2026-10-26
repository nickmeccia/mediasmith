import io

import pytest

from mediasmith import images

from .mediafactory import make_png, make_truncated_jpeg


def test_decode_intact_image():
    image, truncated = images.decode(make_png(size=(8, 8)))
    assert image.size == (8, 8)
    assert truncated is False


def test_decode_salvages_a_truncated_jpeg():
    image, truncated = images.decode(make_truncated_jpeg(size=(64, 64)))
    assert truncated is True
    assert image.size == (64, 64)
    image.copy()            # what the widget does at render — must not raise


def test_decode_leaves_the_global_truncation_flag_alone():
    from PIL import ImageFile
    images.decode(make_truncated_jpeg())
    assert ImageFile.LOAD_TRUNCATED_IMAGES is False   # write paths stay strict


def test_decode_rejects_bytes_that_are_not_an_image():
    with pytest.raises(Exception):      # the caller catches; nothing renders
        images.decode(b"not an image at all")


def test_decode_raises_when_there_is_nothing_to_salvage():
    """Too much gone to decode: the error must surface HERE, where
    _set_cover can hide the widget, rather than at render time."""
    with pytest.raises(OSError):
        images.decode(make_truncated_jpeg(cut=300))
    from PIL import ImageFile
    assert ImageFile.LOAD_TRUNCATED_IMAGES is False   # even down this path
