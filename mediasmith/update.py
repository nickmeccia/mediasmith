"""Keep someone else's copy current, without asking them to do anything.

Nick's friends want to run mediasmith and get the fixes (todo-6). The
distribution answer in notes/claude/todo-binary.md is `uv tool install
git+…`, which already upgrades with one command — this module is what
makes the command unnecessary.

How it works, and what it refuses to do:

- It only ever touches a copy that ``uv tool install`` put in place.
  A git checkout like Nick's own is DEVELOPMENT: the working tree is
  the source of truth and nothing here may move it.
- The check is one ``git ls-remote`` against the release branch — no
  API, no token, no rate limit, nothing cloned. It runs at most once a
  day (the timestamp lives in prefs.json) and never on the event loop.
- Upgrading cannot change the code that is already running, so the new
  version takes effect on the NEXT launch. The app says so.
- Everything here fails silently into "no update". An app that will not
  start because the network is slow is worse than an old app.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import prefs

__all__ = ["REMOTE", "BRANCH", "managed_install", "installed_commit",
           "installed_remote", "remote_commit", "due", "mark_checked",
           "upgrade", "check"]

REMOTE = "https://github.com/nickmeccia/mediasmith.git"
"""The fallback. The URL actually used is the one the copy was INSTALLED
from (`installed_remote`), which is what makes this work whether the
repo is public over HTTPS or private over SSH — the friend's own
credentials are already whatever `uv tool install` used.

Nick's own remote is an SSH alias (`github_1`) that exists only in his
~/.ssh/config, so it is deliberately not the default here."""

BRANCH = "main"

CHECK_SECONDS = 24 * 60 * 60
"""At most one check a day. This is a convenience, not a security
update; a friend who launches ten times an afternoon should pay for the
network once."""

LS_REMOTE_TIMEOUT = 5.0
UPGRADE_TIMEOUT = 300.0

OFFLINE_ENV = "MEDIASMITH_OFFLINE"
DISABLE_ENV = "MEDIASMITH_NO_UPDATE"


def _run(argv: list[str], timeout: float) -> str | None:
    """stdout of ``argv``, or None for any kind of failure."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _dist_info() -> Path | None:
    """This package's installed metadata directory, if there is one."""
    try:
        from importlib.metadata import distribution
        files = distribution("mediasmith")._path   # type: ignore[attr-defined]
    except Exception:
        return None
    return Path(files) if files else None


def managed_install() -> bool:
    """Whether this copy is one ``uv tool install`` owns.

    A checkout being run through `bin/mediasmith` (`uv run --project`)
    is NOT: its code is someone's working tree, and pulling under it
    would throw away their edits.
    """
    if os.environ.get(DISABLE_ENV):
        return False
    tools = Path(os.environ.get("UV_TOOL_DIR")
                 or Path.home() / ".local" / "share" / "uv" / "tools")
    try:
        prefix = Path(sys.prefix).resolve()
    except OSError:
        return False
    try:
        prefix.relative_to(tools.resolve())
    except (ValueError, OSError):
        return False
    return installed_commit() is not None


def installed_commit() -> str | None:
    """The commit this copy was built from.

    ``uv`` (like pip) records the VCS revision it installed in
    ``direct_url.json`` — so the question "am I current" is answerable
    locally, with no clone and no .git directory.
    """
    info = _dist_info()
    if info is None:
        return None
    try:
        direct = json.loads((info / "direct_url.json").read_text())
    except (OSError, ValueError):
        return None
    commit = direct.get("vcs_info", {}).get("commit_id")
    return commit if isinstance(commit, str) and commit else None


def installed_remote() -> str:
    """Where this copy came from, as git can address it again."""
    info = _dist_info()
    if info is None:
        return REMOTE
    try:
        url = json.loads((info / "direct_url.json").read_text()).get("url")
    except (OSError, ValueError):
        return REMOTE
    if not isinstance(url, str) or not url:
        return REMOTE
    url = url.removeprefix("git+")
    # pip/uv keep the requested ref after an @; ls-remote wants the repo
    at = url.rfind("@")
    if at > url.rfind("/") and "://" in url[:at]:
        url = url[:at]
    return url


def remote_commit(remote: str | None = None,
                  branch: str = BRANCH) -> str | None:
    """The head of ``branch`` on the remote, without cloning it."""
    out = _run(["git", "ls-remote",
                installed_remote() if remote is None else remote,
                f"refs/heads/{branch}"], LS_REMOTE_TIMEOUT)
    if not out:
        return None
    first = out.split("\n", 1)[0].split("\t", 1)
    return first[0].strip() if first and first[0].strip() else None


def due(now: float | None = None) -> bool:
    """Whether enough time has passed since the last check."""
    last = prefs.load()["update_checked"]
    now = time.time() if now is None else now
    return not isinstance(last, (int, float)) or now - last >= CHECK_SECONDS


def mark_checked(now: float | None = None) -> None:
    prefs.save(update_checked=time.time() if now is None else now)


def upgrade() -> bool:
    """Install the newer version. True when uv reports success."""
    return _run(["uv", "tool", "upgrade", "mediasmith"],
                UPGRADE_TIMEOUT) is not None


def check() -> str | None:
    """The whole job, for a thread: upgrade if there is one, and say so.

    Returns the short commit now installed when it upgraded, else None.
    """
    if os.environ.get(OFFLINE_ENV) or not managed_install() or not due():
        return None
    mark_checked()          # a failed check still costs a day, not a loop
    here, there = installed_commit(), remote_commit()
    if not there or not here or here == there:
        return None
    if not upgrade():
        return None
    return there[:7]
