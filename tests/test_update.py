"""Self-update for the people Nick hands this to (todo-6).

The module shells out, so every test here puts a seam in front of the
subprocess: what is being tested is the DECISION, not git.
"""
import json

import pytest

from mediasmith import prefs, update


@pytest.fixture()
def installed(tmp_path, monkeypatch):
    """Pose as a copy `uv tool install` put in place."""
    tools = tmp_path / "tools"
    prefix = tools / "mediasmith"
    info = prefix / "lib" / "mediasmith-0.1.dist-info"
    info.mkdir(parents=True)
    (info / "direct_url.json").write_text(json.dumps(
        {"url": update.REMOTE, "vcs_info": {"commit_id": "a" * 40}}))
    monkeypatch.setenv("UV_TOOL_DIR", str(tools))
    monkeypatch.setattr(update.sys, "prefix", str(prefix))
    monkeypatch.setattr(update, "_dist_info", lambda: info)
    monkeypatch.delenv(update.OFFLINE_ENV, raising=False)
    monkeypatch.delenv(update.DISABLE_ENV, raising=False)
    return info


def test_a_checkout_is_never_touched(monkeypatch, tmp_path):
    """Nick's own repo is a working tree, not a release."""
    monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "tools"))
    assert update.managed_install() is False


def test_an_installed_copy_knows_its_commit(installed):
    assert update.managed_install() is True
    assert update.installed_commit() == "a" * 40


def test_an_env_switch_turns_it_off(installed, monkeypatch):
    monkeypatch.setenv(update.DISABLE_ENV, "1")
    assert update.managed_install() is False


def test_remote_commit_reads_the_first_field(monkeypatch):
    monkeypatch.setattr(update, "_run",
                        lambda argv, timeout: "b" * 40 + "\trefs/heads/main\n")
    assert update.remote_commit() == "b" * 40


def test_a_failed_ls_remote_is_not_an_update(monkeypatch):
    monkeypatch.setattr(update, "_run", lambda argv, timeout: None)
    assert update.remote_commit() is None


def test_it_upgrades_when_the_remote_has_moved(installed, monkeypatch):
    ran = []
    monkeypatch.setattr(update, "remote_commit", lambda *a, **k: "b" * 40)
    monkeypatch.setattr(update, "upgrade",
                        lambda: ran.append("upgrade") or True)
    assert update.check() == "b" * 7
    assert ran == ["upgrade"]


def test_it_does_nothing_when_it_is_current(installed, monkeypatch):
    monkeypatch.setattr(update, "remote_commit", lambda *a, **k: "a" * 40)
    monkeypatch.setattr(update, "upgrade",
                        lambda: pytest.fail("upgraded while current"))
    assert update.check() is None


def test_a_failed_upgrade_says_nothing_happened(installed, monkeypatch):
    monkeypatch.setattr(update, "remote_commit", lambda *a, **k: "b" * 40)
    monkeypatch.setattr(update, "upgrade", lambda: False)
    assert update.check() is None


def test_offline_skips_the_network(installed, monkeypatch):
    monkeypatch.setenv(update.OFFLINE_ENV, "1")
    monkeypatch.setattr(update, "remote_commit",
                        lambda *a, **k: pytest.fail("asked the network"))
    assert update.check() is None


def test_it_asks_once_a_day(installed, monkeypatch):
    calls = []
    monkeypatch.setattr(update, "remote_commit",
                        lambda *a, **k: calls.append(1) or "a" * 40)
    assert update.due() is True
    update.check()
    assert update.due() is False
    update.check()
    assert calls == [1]
    # …and it asks again once the day is up
    prefs.save(update_checked=0.0)
    assert update.due() is True


def test_a_failed_check_still_costs_the_day(installed, monkeypatch):
    """Otherwise a remote that is down is asked on every launch."""
    monkeypatch.setattr(update, "remote_commit", lambda *a, **k: None)
    update.check()
    assert update.due() is False


def test_it_follows_the_url_it_was_installed_from(installed):
    """Public over HTTPS or private over SSH — whichever the friend
    used is the one their credentials already work with."""
    (installed / "direct_url.json").write_text(json.dumps(
        {"url": "git+ssh://git@github.com/nickmeccia/mediasmith.git@main",
         "vcs_info": {"commit_id": "a" * 40}}))
    assert update.installed_remote() == (
        "ssh://git@github.com/nickmeccia/mediasmith.git")


def test_a_copy_with_no_metadata_falls_back(monkeypatch):
    monkeypatch.setattr(update, "_dist_info", lambda: None)
    assert update.installed_remote() == update.REMOTE
