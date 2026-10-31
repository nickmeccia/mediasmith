import pytest

from .mediafactory import make_media_tree


@pytest.fixture()
def media_tree(tmp_path):
    return make_media_tree(tmp_path / "media")


@pytest.fixture(autouse=True)
def _config_home(tmp_path, monkeypatch):
    """No test touches the real ~/.config/mediasmith.

    The app READS prefs at startup and WRITES them on ^. (todo-6), so
    without this a suite run would rewrite Nick's own switches — and a
    test's result would depend on them.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
