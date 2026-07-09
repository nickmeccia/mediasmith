import pytest

from .mediafactory import make_media_tree


@pytest.fixture()
def media_tree(tmp_path):
    return make_media_tree(tmp_path / "media")
