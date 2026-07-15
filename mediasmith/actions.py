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


def action_markup(word: str, key: str | None) -> str:
    """The label markup: ``^`` + the key char in the accent color,
    spliced into the word when the char is part of it."""
    if key is None:
        return _escape(word)
    index = word.lower().find(key.lower())
    if index >= 0:
        return (f"{_escape(word[:index])}"
                f"[{KEY_STYLE}]^{word[index]}[/]"
                f"{_escape(word[index + 1:])}")
    return f"[{KEY_STYLE}]^{key}[/] {_escape(word)}"


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

    def __init__(self, spec: Action) -> None:
        super().__init__(Content.from_markup(action_markup(spec.word,
                                                           spec.key)),
                         id=spec.button_id or f"act-{spec.name}",
                         compact=True)
        self.spec = spec


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
        keys = [a.key for a in actions if a.key]
        assert len(keys) == len(set(keys)), f"{self.id}: duplicate keys"
        self.styles.layout = FlowLayout.name

    def compose(self):
        for spec in self._actions:
            yield ActionButton(spec)

    def buttons(self) -> list[ActionButton]:
        """The visible buttons, left to right."""
        return [b for b in self.query(ActionButton) if b.display]

    def set_visible(self, names: set[str] | None) -> None:
        """Show only the named actions (None: show everything)."""
        for button in self.query(ActionButton):
            button.display = names is None or button.spec.name in names

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
