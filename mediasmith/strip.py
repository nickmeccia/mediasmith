"""Command Strip: ONE line of keybinding→command pairs below both views,
swapping its contents with state (todo-4 "Command Strip & Keybinding
Refactor"). A keybinding not shown for the current state is not
available in that state — the strip is the contract, not a hint.

Responsive rules (todo-4 "Command Strip Responsive Styles"):
- space-between keeps the logo on the right edge;
- a narrowing viewport wraps the strip onto multiple lines;
- each keybinding entry is an unbreakable unit (white-space: nowrap) —
  lines break only between entries, the separator riding the line end.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.cells import cell_len
from textual.content import Content
from textual.geometry import Size
from textual.widget import Widget

LOGO = "𜵎𜵎▖𜷇🯦𜷇▌𜵅𜷃𜵈𜷓𜴀𜵎𜵎▖𜵅𜶍▐𜶓"
"""Octant-glyph wordmark (see notes/octant.py) — right edge of the
strip. Every glyph is cell-width 1 under Rich (verified)."""


@dataclass(frozen=True)
class Entry:
    """One keybinding→command pair on the strip."""

    key: str            # what the user presses, e.g. "^r", "ENT", "↓↑"
    label: str          # the command word(s), e.g. "refresh"
    primary: bool = False
    """Print in the primary brand color (the clipboard state's cue)."""


# -- the states (todo-4 spec, plus Nick's session decisions) -----------------

_NAVIGATE = [
    Entry("↓↑", "navigate"),
    # TAB is →/← in one key (Nick, todo-5): it expands a closed folder and
    # collapses an open one, so it rides BOTH entries — the strip prints
    # keys per command ("↓↑ navigate"), not commands per key, and a lone
    # "TAB expand/collapse" entry cost the wide strip its single line.
    Entry("→ TAB", "expand"),
    Entry("← TAB", "collapse"),
    Entry("^←", "collapse level"),
]

_TREE_TAIL = [
    Entry("^r", "refresh"),
    Entry("^.", "toggle hidden files"),
    Entry("^n", "new directory"),
]

# What the strip carries, now that the pane's three bars are always on
# show (always-available-actions-3, 2026-10-26): the TREE's own commands
# — how to move, and how to change the tree's shape. Everything that acts
# on the FILE moved to the bars, which print their own chords and are
# visible from here: ^o open, ^x cut, ^y copy, ^DEL delete, and every
# kind action as ^1…^9. So the contract is still "what is printed works",
# it is just printed in two places: the strip for the tree, the bar for
# the file. ^/ left too — the Path Input prints its own chord.
STATE_TREE = [
    *_NAVIGATE,
    # type-jump keeps working but leaves the strip (too hard to say
    # concisely); "→ edit" is gone from the app (⏎ is the one edit key)
    Entry("ENT", "edit"),
    *_TREE_TAIL,
    Entry("^q", "quit"),
]


def tree_state(folderize: bool = False) -> list[Entry]:
    """The tree state. ``folderize`` is vestigial: folderize used to be the
    one action reachable from both views and printed here when the
    selection offered one (2026-08-22). EVERY action is reachable from
    both views now, and each prints its own chord on its own button, so
    the strip no longer speaks for any of them."""
    return STATE_TREE


STATE_PATH = [
    Entry("TAB", "complete"),
    Entry("ENT", "go"),
    Entry("ESC", "cancel"),
    Entry("^q", "quit"),
]

STATE_DETAILS = [
    Entry("↓↑", "navigate"),
    # ^s save left off deliberately: the save button carries it
    Entry("ESC", "close"),
    Entry("^q", "quit"),
]

# the clipboard state is the tree state minus what carrying forbids
# (no edit — ⏎ idles; no second cut) plus the paste pair up front;
# ^/ stays so cut → path-jump → paste survives (Nick, 2026-08-12)
STATE_CLIPBOARD = [
    Entry("^v", "paste", primary=True),
    Entry("ESC", "cancel", primary=True),
    *_NAVIGATE,
    *_TREE_TAIL,
    Entry("^DEL", "delete"),
    Entry("^/", "path"),
    Entry("^q", "quit"),
]


class CommandStrip(Widget):
    """The one strip: wraps its entries to the viewport, logo bottom-right."""

    DEFAULT_CSS = """
    CommandStrip { dock: bottom; width: 100%; height: auto;
                   background: $surface; padding: 0 1; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self._entries: list[Entry] = []

    def set_entries(self, entries: list[Entry]) -> None:
        if entries != self._entries:
            self._entries = list(entries)
            self.refresh(layout=True)   # line count may change

    # -- wrapping ---------------------------------------------------------------

    def _tokens(self) -> list[tuple[str, str]]:
        """(plain, markup) per entry, the ` ·` separator attached to every
        entry but the last — so a wrap leaves the bullet on the line end,
        exactly as the todo-4 examples show."""
        tokens = []
        last = len(self._entries) - 1
        for i, entry in enumerate(self._entries):
            style = "$primary" if entry.primary else "$keybinding"
            plain = f"{entry.key} {entry.label}"
            markup = f"[{style}]{entry.key} {entry.label}[/]"
            if i != last:
                plain += " ·"
                markup += " [$keybinding-bullet]·[/]"
            tokens.append((plain, markup))
        return tokens

    def _lines(self, width: int) -> list[str]:
        """The strip's markup lines for ``width``: entries packed greedily
        (each an unbreakable unit), the logo right-aligned on the last
        line — its own line when the last one has no room."""
        width = max(1, width)
        lines: list[tuple[str, str]] = []
        plain = markup = ""
        for token_plain, token_markup in self._tokens():
            if plain and cell_len(f"{plain} {token_plain}") > width:
                lines.append((plain, markup))
                plain, markup = token_plain, token_markup
            elif plain:
                plain = f"{plain} {token_plain}"
                markup = f"{markup} {token_markup}"
            else:       # a lone entry never wraps
                plain, markup = token_plain, token_markup
        if plain:
            lines.append((plain, markup))
        logo_markup = f"[$logo]{LOGO}[/]"
        if not lines:
            return [" " * max(0, width - cell_len(LOGO)) + logo_markup]
        last_plain, last_markup = lines[-1]
        pad = width - cell_len(last_plain) - cell_len(LOGO)
        if pad >= 2:        # space-between: commands left, logo right
            lines[-1] = (last_plain, last_markup + " " * pad + logo_markup)
        else:               # no room beside the commands: own line
            lines.append(("", " " * max(0, width - cell_len(LOGO))
                          + logo_markup))
        return [m for _, m in lines]

    def render(self) -> Content:
        return Content.from_markup(
            "\n".join(self._lines(self.content_size.width)))

    def get_content_height(self, container: Size, viewport: Size,
                           width: int) -> int:
        return len(self._lines(width))
