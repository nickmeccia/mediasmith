"""The handful of choices that outlive a session.

Small on purpose: this is not configuration, it is the state of a few
switches the user has already flipped once and should not have to flip
again (Nick, todo-6 — ``^.`` toggle hidden files).

The file is JSON in the user's config directory — LOCAL disk, never the
library's volume. Rule 4 (no filesystem call on the event loop) is about
the NAS; even so, the write goes through a thread in app.py, because the
rule is easier to keep than to qualify.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["path", "load", "save"]

DEFAULTS: dict[str, object] = {
    "show_hidden": True,
    "update_checked": 0.0,      # when update.py last asked the remote
}
"""Every key this module knows, with the value a fresh install gets."""


def _usable(value: object, default: object) -> bool:
    """Whether a stored value is the right shape for its default.

    Numbers are compared loosely (a whole-second timestamp comes back
    as an int), booleans strictly — `True` is an int to Python, and a
    switch is not a timestamp.
    """
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def path() -> Path:
    """Where the file lives — XDG if the environment asks for it."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "mediasmith" / "prefs.json"


def load() -> dict:
    """The saved values, with defaults filled in.

    Anything unreadable — missing, truncated, hand-edited into invalid
    JSON, owned by someone else — is not an error worth a dialog: the
    app opens with its defaults, which is what the file is for.
    """
    values = dict(DEFAULTS)
    try:
        stored = json.loads(path().read_text())
    except (OSError, ValueError):
        return values
    if isinstance(stored, dict):
        for key in DEFAULTS:
            if key in stored and _usable(stored[key], DEFAULTS[key]):
                values[key] = stored[key]
    return values


def save(**values) -> None:
    """Merge ``values`` into the file. Thread-only (it touches the disk).

    Written through a temporary file in the same directory and renamed,
    so an interrupted write leaves the previous file rather than half of
    this one. Failure is silent for the same reason as ``load``.
    """
    unknown = set(values) - set(DEFAULTS)
    assert not unknown, f"unknown preference(s): {sorted(unknown)}"
    merged = load() | values
    target = path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.new")
        temporary.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
        temporary.replace(target)
    except OSError:
        pass
