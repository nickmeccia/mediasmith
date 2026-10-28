"""Contextual action buttons: the app-wide button pattern.

Every action anywhere in the app renders the same way (claude-TODO
"button pattern"):

- compact buttons, horizontally inlined, wrapping like flexbox when the
  row runs out of width (FlowLayout);
- the keybinding is printed inside the label as ``^x`` in the accent
  color — spliced in front of its own character when that character
  appears in the word (``^save``, ``fe^tch``), prefixed otherwise
  (``^x convert``);
- ↑↓ walk through the buttons (left/right), ←→ move within a bar, and
  the key chord fires the action from anywhere its bar is on show.

An ActionBar is composed once with its full set of Actions; context
never adds or removes buttons, it only shows/hides them
(``set_visible``) — the compose-once rule.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from textual.content import Content
from textual.geometry import NULL_OFFSET, Region, Size
from textual.layout import ArrangeResult, Layout, WidgetPlacement
from textual.layouts.factory import LAYOUT_MAP
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button

# Markup styles for the chord inside a button label — theme tokens
# (theme.py). Which one applies is the BUTTON's own focus and nothing
# else (2026-10-26): a button does not dim because the cursor is in the
# tree, because its chord works from there. Markup can't ride CSS
# pseudo-classes, so the label is recolored from Python
# (watch_has_focus).
KEY_STYLE = "$element-key"
SELECTED_KEY_STYLE = "$element-key-focus"
IDLE_KEY_STYLE = KEY_STYLE
"""Retired name: the idle look was "some other view has focus", which the
path model does not have. Kept so an old import does not break."""

# ctrl+<char> chords the terminal or the app already owns; binding an
# action to one of these would shadow typing or core chrome.
# Audited 2026-07-15 against Textual 8's real bindings (QA-TODO "key
# space", option 1): c/q are App-owned, h/i/j/m are terminal aliases
# for backspace/tab/newline/enter, z is shell suspend muscle memory.
# d and e turned out to be only Input editing chords (delete-right,
# end) — the same class as the already-assigned a/k/u/v/w/x, safe for
# actions whose context has no focusable Input.
RESERVED_KEYS = frozenset("chijmqz")


CONTEXTUAL, FILE, ACTIONS = "contextual", "file", "actions"
"""The three bars (Nick, 2026-10-26 — always-available-actions-3).

- CONTEXTUAL: what the pane's STATE offers — save, a plan's apply/cancel,
  and (slice 4) a micro-modal's choices. It owns focus while it has a
  question to ask.
- FILE: what every file offers whatever it holds — open, cut, copy,
  delete. These are the tree's commands wearing buttons, so they keep
  their LETTER chords (^o ^x ^y ^DEL): one key, one meaning, everywhere.
- ACTIONS: what this KIND offers. Positional chords only (^1…^9): the
  letters ran out and nobody could remember them (Nick's reason), so the
  number is the address.
"""


@dataclass(frozen=True)
class Action:
    """One contextual action: a button plus (optionally) a key chord."""

    name: str                   # dispatch name, unique within its bar
    word: str                   # the label text, e.g. "Save"
    key: str | None = None      # single char, bound as ctrl+<key>
    button_id: str | None = None
    bar: str = ACTIONS          # which of the three bars it lives on
    key_label: str | None = None
    """The printed chord, VERBATIM, when ``key`` cannot express it:
    ``^DEL`` for delete, ``ESC`` for a cancel. Display only — such chords
    are dispatched by the app, not by ``action_for_key``."""

    @property
    def printed_chord(self) -> str | None:
        """What this action's button prints when it wears no number."""
        return f"^{self.key}" if self.key else self.key_label

    def __post_init__(self) -> None:
        if self.key is not None:
            assert len(self.key) == 1, f"{self.name}: key must be one char"
            assert self.key not in RESERVED_KEYS, \
                f"{self.name}: ctrl+{self.key} is reserved"

    @property
    def chord(self) -> str | None:
        return None if self.key is None else f"ctrl+{self.key}"


def _escape(text: str) -> str:
    return text.replace("[", r"\[")


# What a POSITIONAL chord PRINTS, decided once per process. ^1…^9 cannot
# cross tmux — measured 2026-08-25, and the reason is below in
# ALT_GLYPH_ORDINALS — so under tmux the label says ⌥ and means it
# (Nick's call, 2026-10-26: "^N locally and ⌥N under tmux"). Both forms
# are always ACCEPTED (ordinal_for_key); only the printing changes,
# because the label is the contract and it must not lie.
def chord_prefix(env: "dict[str, str] | None" = None) -> str:
    """``^`` normally, ``⌥`` under tmux. A function so it can be tested
    without reloading this module: a reload would hand the suite a second
    ActionBar class, and every isinstance check would start failing.
    """
    env = os.environ if env is None else env
    return "⌥" if env.get("TMUX") else "^"


CHORD_PREFIX = chord_prefix()


def action_markup(word: str, chord: str | None,
                  key_style: str = KEY_STYLE,
                  ordinal: int | None = None) -> str:
    """The label markup: the chord in the accent color, then the word.

    One shape for every button — ``^s Save``, ``^DEL Delete``,
    ``^1 Folderize`` — since the chord stopped being spliced into the
    word (Nick, 2026-10-26: "there are way too many keybindings to
    memorize at this point, and it's easier to just note the position of
    the button"). The words line up, and a word like "fetch subtitles"
    reads as itself instead of as "fetch s^ubtitles".

    An ``ordinal`` is the button's POSITIONAL chord and it WINS: a bar
    that numbers its buttons prints no letters (see the three bars).
    ``key_style`` swaps the chord color (focus recolors it).
    """
    label = _escape(word)
    if ordinal is not None:
        return f"[{key_style}]{CHORD_PREFIX}{ordinal}[/] {label}"
    if chord is None:
        return label
    return f"[{key_style}]{chord}[/] {label}"


ORDINAL_LIMIT = 9
"""How many buttons wear a number: ^1…^9 (^0 would read as tenth-ish)."""


# ⌥+digit, the tmux-proof half of the positional chord (measured
# 2026-08-25, tmux 3.7). Ctrl+digit cannot survive tmux: of ^1…^9 only
# ^1 and ^9 arrive intact even with `extended-keys always`, because the
# rest collapse into their legacy C0 codes — and three of those already
# mean something here (^3 IS escape, ^7 is the app's ^/ path chord, ^8
# is backspace). ⌥+digit crosses tmux untouched in every configuration,
# with no tmux setup at all.
#
# It arrives under two spellings, and both are the same press:
#   · "alt+<digit>" — the kitty form, from a terminal (or tmux) that
#     reports modifiers properly;
#   · the macOS Option GLYPH — what Ghostty types by default, and what
#     Textual decodes ESC+<digit> into, which is how tmux forwards it.
ALT_GLYPH_ORDINALS = {
    "inverted_exclamation_mark": 1,     # ⌥1 ¡
    "trade_mark_sign": 2,               # ⌥2 ™
    "pound_sign": 3,                    # ⌥3 £
    "cent_sign": 4,                     # ⌥4 ¢
    "infinity": 5,                      # ⌥5 ∞
    "section_sign": 6,                  # ⌥6 §
    "pilcrow_sign": 7,                  # ⌥7 ¶
    "bullet": 8,                        # ⌥8 •
    "ª": 9,                             # ⌥9 ª
}


def ordinal_for_key(key: str) -> int | None:
    """The 1-based button position a key names, or None — ``ctrl+<digit>``,
    ``alt+<digit>``, or the Option glyph that stands in for the latter."""
    for prefix in ("ctrl+", "alt+"):
        if key.startswith(prefix):
            digit = key[len(prefix):]
            if len(digit) == 1 and digit.isdigit() and digit != "0":
                return int(digit)
            return None
    return ALT_GLYPH_ORDINALS.get(key)


class FlowLayout(Layout):
    """Left-to-right with wrapping — the flexbox row Textual doesn't
    ship. Children keep their own (auto) size and margins; each visual
    row is as tall as its tallest member."""

    name = "flow"

    def arrange(self, parent: Widget, children: list[Widget],
                size: Size, greedy: bool = True) -> ArrangeResult:
        parent.pre_layout(self)
        viewport = parent.app.viewport_size
        placements: list[WidgetPlacement] = []
        x = y = row_height = 0
        for widget in children:
            styles = widget.styles
            gutter_width, gutter_height = styles.gutter.totals
            margin = styles.margin
            width = widget.get_content_width(size, viewport) + gutter_width
            height = (widget.get_content_height(size, viewport, width)
                      + gutter_height)
            span = margin.left + width + margin.right
            if x and x + span > size.width:     # wrap; a lone widget never does
                x = 0
                y += row_height
                row_height = 0
            placements.append(WidgetPlacement(
                Region(x + margin.left, y + margin.top, width, height),
                NULL_OFFSET, margin, widget))
            x += span
            row_height = max(row_height, height + margin.top + margin.bottom)
        return placements

    def get_content_width(self, widget: Widget, container: Size,
                          viewport: Size) -> int:
        # ideal width shows every child on one line; the parent clamps
        # and arrange() wraps the rest
        total = 0
        for child in widget.displayed_children:
            styles = child.styles
            total += (child.get_content_width(container, viewport)
                      + styles.gutter.totals[0]
                      + styles.margin.left + styles.margin.right)
        return total

    def get_content_height(self, widget: Widget, container: Size,
                           viewport: Size, width: int) -> int:
        if not widget._nodes:
            return 0
        return widget.arrange(Size(width, 0)).total_region.height


# styles.layout resolves layouts by name through the factory, so the
# custom layout has to be registered there
LAYOUT_MAP.setdefault(FlowLayout.name, FlowLayout)


class ActionButton(Button):
    """A Button carrying its Action spec; label per the button pattern.

    Background/foreground come from CSS ($element-bg, and
    $element-bg-focus when this button is the one thing with focus). The
    chord inside the label is markup rather than CSS, so its color is
    applied from Python on the same edge (``watch_has_focus``);
    text-style stays CSS-side.
    """

    DEFAULT_CSS = """
    ActionButton:focus { text-style: bold; }
    """

    _pane_focus = False
    """Whether the owning view is focused — the idle/focus half of the
    chord-color decision (the button's own focus wins over both)."""

    _ordinal: int | None = None
    """This button's place in its bar, printed as ``^N``. Positional, so
    it is assigned by the BAR on every visibility change, never by the
    Action (which knows nothing about who else is on show)."""

    def __init__(self, spec: Action) -> None:
        self.spec = spec
        self._word = spec.word
        super().__init__(self._content(KEY_STYLE),
                         id=spec.button_id or f"act-{spec.name}",
                         compact=True)

    def _key_style(self) -> str:
        return SELECTED_KEY_STYLE if self.has_focus else KEY_STYLE

    def _content(self, key_style: str) -> Content:
        return Content.from_markup(
            action_markup(self._word, self.spec.printed_chord,
                          key_style, self._ordinal))

    def _apply_label(self, key_style: str) -> None:
        # set_reactive + refresh, not `self.label = …`: Content.__eq__
        # compares plain text only, so a recolor of the same word is seen
        # as "no change" by the label reactive and skipped. Bypass it.
        self.set_reactive(Button.label, self._content(key_style))
        self.refresh()

    def set_word(self, word: str) -> None:
        """Relabel with a new word (the move button's lift/place toggle),
        keeping the chord color that matches the current focus state."""
        self._word = word
        self._apply_label(self._key_style())

    @property
    def ordinal(self) -> int | None:
        """The number this button PRINTS — and therefore the only number
        that fires it (the label is the contract)."""
        return self._ordinal

    def set_ordinal(self, value: int | None) -> None:
        """Take (or lose) a positional number — the bar's call."""
        if value != self._ordinal:
            self._ordinal = value
            self._apply_label(self._key_style())

    def set_pane_focus(self, value: bool) -> None:
        """No-op since 2026-10-26: a button's look no longer depends on
        which VIEW has focus. Kept so the owning view can keep calling it
        while the rest of the chrome pass lands."""

    def watch_has_focus(self, value: bool) -> None:
        # super() FIRST: Widget.watch_has_focus is what applies the
        # :focus CSS. Overriding it without the call left the selected
        # button's chrome one keypress stale — the arrow moved focus,
        # the highlight only caught up when the NEXT key happened to
        # restyle the pane, so reversing direction looked like the
        # arrow kept going the old way (Nick, 2026-08-13).
        super().watch_has_focus(value)
        self._apply_label(self._key_style())


class ActionBar(Widget):
    """One wrapping row of ActionButtons. Post a ``Triggered`` on press;
    the owner (DetailsView) maps action names to handlers."""

    DEFAULT_CSS = """
    ActionBar { width: 1fr; height: auto; }
    ActionBar ActionButton { margin-right: 2; }
    """

    class Triggered(Message):
        def __init__(self, action: Action) -> None:
            super().__init__()
            self.action = action

    def __init__(self, *actions: Action, **kwargs) -> None:
        super().__init__(**kwargs)
        self._actions = actions
        self.styles.layout = FlowLayout.name

    def compose(self):
        for spec in self._actions:
            yield ActionButton(spec)

    def on_mount(self) -> None:
        self._number_buttons()      # a bar that never calls set_visible

    def buttons(self) -> list[ActionButton]:
        """The visible buttons, left to right."""
        return [b for b in self.query(ActionButton) if b.display]

    def number_from(self, start: int | None) -> int:
        """Hand out the positional chords: ^N left to right over the
        VISIBLE buttons, counting up from ``start`` (Nick's A/B,
        2026-08-25 — the numbers run beside the letter chords until he
        picks one). ``None`` clears them — a bar that isn't on show
        prints no number. Returns the next free number, so a pane with
        several bars can number them all without a collision."""
        if start is None:
            for button in self.query(ActionButton):
                button.set_ordinal(None)
            return 1
        visible = self.buttons()
        for offset, button in enumerate(visible):
            place = start + offset
            button.set_ordinal(place if place <= ORDINAL_LIMIT else None)
        for button in self.query(ActionButton):
            if not button.display:
                button.set_ordinal(None)
        return start + len(visible)

    def _number_buttons(self) -> None:
        self.number_from(1)

    def set_visible(self, names: set[str] | None) -> None:
        """Show only the named actions (None: show everything).

        Keys are CONTEXTUALLY REUSED (Nick's pick, 2026-07-15 — the
        ctrl-letter pool ran out): one bar may hold two actions on the
        same chord as long as no context ever shows both. A chord only
        fires what its printed button says, so the visible set is the
        contract — enforced here, where every context change lands."""
        for button in self.query(ActionButton):
            button.display = names is None or button.spec.name in names
        keys = [b.spec.key for b in self.buttons() if b.spec.key]
        assert len(keys) == len(set(keys)), \
            f"{self.id}: chord collision among visible buttons ({keys})"
        self._number_buttons()      # positions moved with the visible set

    def action_for_key(self, key: str) -> Action | None:
        """The visible action bound to this key event name, if any —
        by its own letter chord, or by its printed position (^1…^9)."""
        for button in self.buttons():
            if button.spec.chord == key:
                return button.spec
        place = ordinal_for_key(key)
        if place is not None:
            for button in self.buttons():
                if button.ordinal == place:      # what it prints is what
                    return button.spec           # it answers to
        return None

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if isinstance(ev.button, ActionButton):
            ev.stop()
            self.post_message(self.Triggered(ev.button.spec))
