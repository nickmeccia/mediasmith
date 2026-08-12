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

from dataclasses import dataclass

from textual.content import Content
from textual.geometry import NULL_OFFSET, Region, Size
from textual.layout import ArrangeResult, Layout, WidgetPlacement
from textual.layouts.factory import LAYOUT_MAP
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button

KEY_STYLE = "$text-accent"
"""Markup style for the ``^x`` keybinding inside a button label."""

FOCUS_KEY_STYLE = "#ffe6c2"
"""The chord color while a button is focused (arrow-key selected): a light
orange that stays legible on the orange focus background (see ActionButton
CSS), where the accent color would vanish."""

# ctrl+<char> chords the terminal or the app already owns; binding an
# action to one of these would shadow typing or core chrome.
# Audited 2026-07-15 against Textual 8's real bindings (QA-TODO "key
# space", option 1): c/q are App-owned, h/i/j/m are terminal aliases
# for backspace/tab/newline/enter, z is shell suspend muscle memory.
# d and e turned out to be only Input editing chords (delete-right,
# end) — the same class as the already-assigned a/k/u/v/w/x, safe for
# actions whose context has no focusable Input.
RESERVED_KEYS = frozenset("chijmqz")


@dataclass(frozen=True)
class Action:
    """One contextual action: a button plus (optionally) a key chord."""

    name: str                   # dispatch name, unique within its bar
    word: str                   # the label text, e.g. "save"
    key: str | None = None      # single char, bound as ctrl+<key>
    button_id: str | None = None
    key_label: str | None = None
    """What the button prints when there is no single-char ``key`` — for a
    chord the ctrl+<char> shape can't express (trash → ``^del``). Display
    only; such chords are dispatched by the app, not ``action_for_key``."""

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


def action_markup(word: str, key: str | None,
                  key_style: str = KEY_STYLE) -> str:
    """The label markup: ``^`` + the key char in the accent color,
    spliced into the word when the char is part of it. ``key_style``
    swaps the chord color (focus recolors it — see FOCUS_KEY_STYLE)."""
    if key is None:
        return _escape(word)
    index = word.lower().find(key.lower())
    if index >= 0:
        return (f"{_escape(word[:index])}"
                f"[{key_style}]^{word[index]}[/]"
                f"{_escape(word[index + 1:])}")
    return f"[{key_style}]^{key}[/] {_escape(word)}"


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
    """A Button carrying its Action spec; label per the button pattern."""

    # arrow-key selection lands as focus: an orange highlight, with the
    # chord recolored so it stays legible where the accent would vanish
    DEFAULT_CSS = """
    ActionButton:focus {
        background: orange;
        color: black;
        text-style: bold;
    }
    """

    def __init__(self, spec: Action) -> None:
        self.spec = spec
        self._word = spec.word
        super().__init__(self._content(KEY_STYLE),
                         id=spec.button_id or f"act-{spec.name}",
                         compact=True)

    def _content(self, key_style: str) -> Content:
        return Content.from_markup(
            action_markup(self._word, self.spec.key or self.spec.key_label,
                          key_style))

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
        self._apply_label(FOCUS_KEY_STYLE if self.has_focus else KEY_STYLE)

    def watch_has_focus(self, value: bool) -> None:
        # arrow-key selection lands as focus; recolor the chord so it
        # reads on the orange highlight, restore the accent on blur
        self._apply_label(FOCUS_KEY_STYLE if value else KEY_STYLE)


class ActionBar(Widget):
    """One wrapping row of ActionButtons. Post a ``Triggered`` on press;
    the owner (DetailsPane) maps action names to handlers."""

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

    def buttons(self) -> list[ActionButton]:
        """The visible buttons, left to right."""
        return [b for b in self.query(ActionButton) if b.display]

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

    def action_for_key(self, key: str) -> Action | None:
        """The visible action bound to this key event name, if any."""
        for button in self.buttons():
            if button.spec.chord == key:
                return button.spec
        return None

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if isinstance(ev.button, ActionButton):
            ev.stop()
            self.post_message(self.Triggered(ev.button.spec))
