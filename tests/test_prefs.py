"""The switches that outlive a session (todo-6)."""
import json

import pytest

from mediasmith import prefs


@pytest.fixture(autouse=True)
def config_home(tmp_path, monkeypatch):
    """Never the real ~/.config: this test writes."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path / "config"


def test_defaults_when_there_is_no_file():
    assert prefs.load() == prefs.DEFAULTS
    assert prefs.DEFAULTS["show_hidden"] is True


def test_a_saved_value_comes_back():
    prefs.save(show_hidden=False)
    assert prefs.load()["show_hidden"] is False


def test_saving_one_key_keeps_the_others(config_home):
    prefs.save(show_hidden=False)
    stored = json.loads(prefs.path().read_text())
    assert stored == dict(prefs.DEFAULTS, show_hidden=False)
    prefs.save(update_checked=123.0)
    assert prefs.load()["show_hidden"] is False      # the other key survives


def test_a_damaged_file_opens_with_defaults():
    prefs.path().parent.mkdir(parents=True)
    prefs.path().write_text("{not json")
    assert prefs.load() == prefs.DEFAULTS              # no crash, no dialog


def test_a_value_of_the_wrong_type_is_ignored():
    prefs.path().parent.mkdir(parents=True)
    prefs.path().write_text('{"show_hidden": "yes please"}')
    assert prefs.load()["show_hidden"] is True


def test_an_unknown_key_is_a_programming_error():
    with pytest.raises(AssertionError):
        prefs.save(colour_scheme="neon")


def test_an_unwritable_directory_is_survived(monkeypatch, tmp_path):
    victim = tmp_path / "nope"
    victim.write_text("I am a file, not a directory")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(victim))
    prefs.save(show_hidden=False)                      # must not raise
    assert prefs.load() == prefs.DEFAULTS


def test_a_whole_second_timestamp_is_still_a_number():
    """json.dump writes 1.0 as 1.0, but a hand-edited or older file can
    hold an int — and `isinstance(1, float)` is False."""
    prefs.path().parent.mkdir(parents=True)
    prefs.path().write_text('{"update_checked": 1730000000}')
    assert prefs.load()["update_checked"] == 1730000000


def test_true_is_not_a_timestamp():
    prefs.path().parent.mkdir(parents=True)
    prefs.path().write_text('{"update_checked": true}')
    assert prefs.load()["update_checked"] == 0.0
