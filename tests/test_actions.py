"""The app-wide button pattern: labels, wrapping, key dispatch."""

import pytest
from textual.app import App

from mediasmith.actions import (ACTIONS, CHORD_PREFIX, CONTEXTUAL, FILE,
                                Action, ActionBar, ActionButton,
                                IDLE_KEY_STYLE, KEY_STYLE,
                                SELECTED_KEY_STYLE, action_markup,
                                chord_prefix, ordinal_for_key)


# -- label markup ---------------------------------------------------------------


def test_chord_prints_in_front_of_the_word():
    """One shape for every button, chord first (2026-10-26): the chord is
    no longer spliced into the word."""
    assert action_markup("Save", "^s") == f"[{KEY_STYLE}]^s[/] Save"


def test_key_style_override_recolors_the_chord():
    assert action_markup("Save", "^s", "#ffe6c2") == "[#ffe6c2]^s[/] Save"


def test_a_verbatim_chord_prints_as_given():
    """^DEL and ESC are chords no ctrl+<char> can express."""
    assert action_markup("Delete", "^DEL") == f"[{KEY_STYLE}]^DEL[/] Delete"
    assert action_markup("Cancel", "ESC") == f"[{KEY_STYLE}]ESC[/] Cancel"


def test_no_chord_no_markup():
    assert action_markup("Save", None) == "Save"


def test_word_brackets_escaped():
    assert action_markup("a[b]", None) == r"a\[b]"


def test_an_ordinal_replaces_the_letter():
    """A numbered bar prints no letters: the number is the address."""
    assert (action_markup("Save", "^s", KEY_STYLE, 1)
            == f"[{KEY_STYLE}]{CHORD_PREFIX}1[/] Save")


def test_ordinal_without_a_letter_chord():
    assert (action_markup("Save", None, KEY_STYLE, 3)
            == f"[{KEY_STYLE}]{CHORD_PREFIX}3[/] Save")


def test_the_printed_ordinal_follows_the_terminal():
    """^N cannot cross tmux, so under tmux the label says ⌥ and means it
    (Nick, 2026-10-26). Both forms are always accepted."""
    assert chord_prefix({"TMUX": "/tmp/tmux-501/default,1,0"}) == "\u2325"
    assert chord_prefix({}) == "^"


def test_printed_chord_comes_from_the_spec():
    assert Action("save", "Save", "s").printed_chord == "^s"
    assert Action("delete", "Delete", key_label="^DEL").printed_chord == "^DEL"
    assert Action("plan_cancel", "Cancel").printed_chord is None


def test_ordinal_for_key_reads_ctrl_digits():
    assert ordinal_for_key("ctrl+4") == 4
    assert ordinal_for_key("ctrl+0") is None      # ^0 would read as tenth
    assert ordinal_for_key("ctrl+s") is None
    assert ordinal_for_key("4") is None


def test_ordinal_for_key_reads_alt_digits():
    """⌥+digit is the spelling that survives tmux (ctrl+digit does not:
    of ^1…^9 only ^1 and ^9 cross intact)."""
    assert ordinal_for_key("alt+4") == 4
    assert ordinal_for_key("alt+0") is None


def test_ordinal_for_key_reads_the_option_glyphs():
    """What ⌥+digit actually arrives as — Ghostty types the glyph, and
    Textual decodes tmux's ESC+digit into the same one."""
    assert ordinal_for_key("inverted_exclamation_mark") == 1     # ⌥1 ¡
    assert ordinal_for_key("section_sign") == 6                  # ⌥6 §
    assert ordinal_for_key("ª") == 9                             # ⌥9 ª
    assert ordinal_for_key("pound_sign") == 3                    # ⌥3 £
    assert ordinal_for_key("dollar_sign") is None                # not one


# -- Action validation ------------------------------------------------------------


def test_reserved_key_rejected():
    with pytest.raises(AssertionError):
        Action("quit", "quit", "q")     # ctrl+q is the app's


class ReuseApp(App):
    # contextual reuse: two actions may share a chord as long as no
    # context ever shows both (set_visible enforces the contract)
    def compose(self):
        yield ActionBar(Action("a", "aaa", "a"), Action("b", "abba", "a"))


async def test_shared_key_ok_while_only_one_shows():
    app = ReuseApp()
    async with app.run_test(size=(80, 24)) as pilot:
        bar = app.query_one(ActionBar)
        bar.set_visible({"a"})
        await pilot.pause()
        assert bar.action_for_key("ctrl+a").name == "a"
        bar.set_visible({"b"})
        assert bar.action_for_key("ctrl+a").name == "b"


async def test_shared_key_both_visible_rejected():
    app = ReuseApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        bar = app.query_one(ActionBar)
        with pytest.raises(AssertionError):
            bar.set_visible({"a", "b"})


# -- the bar: wrap, visibility, keys ----------------------------------------------


class BarApp(App):
    # 26 cells hold two of these buttons, not three: the labels wear a
    # positional chord now ("^1 a^lpha", 11 cells + 2 margin)
    CSS = "#host { width: 26; } ActionBar { width: 1fr; }"

    def compose(self):
        from textual.containers import Vertical
        with Vertical(id="host"):
            yield ActionBar(
                Action("one", "alpha", "l"),
                Action("two", "bravo", "b"),
                Action("three", "golf", "g"),
            )


async def test_buttons_wrap_like_flexbox():
    app = BarApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        buttons = app.query(ActionButton).nodes
        rows = [b.region.y for b in buttons]
        # 26 cells can't hold three ~11-cell buttons: at least one wraps,
        # and wrapped buttons restart at the left edge
        assert rows[0] == rows[1] != rows[2]
        assert buttons[2].region.x == buttons[0].region.x
        bar = app.query_one(ActionBar)
        assert bar.region.height == 2          # the bar grew to hold both rows


async def test_hidden_buttons_leave_the_flow():
    app = BarApp()
    async with app.run_test(size=(80, 24)) as pilot:
        bar = app.query_one(ActionBar)
        bar.set_visible({"one", "three"})
        await pilot.pause()
        assert [b.spec.name for b in bar.buttons()] == ["one", "three"]
        assert bar.action_for_key("ctrl+b") is None      # hidden: key inert
        assert bar.action_for_key("ctrl+g").name == "three"
        bar.set_visible(None)
        await pilot.pause()
        assert bar.action_for_key("ctrl+b").name == "two"


async def test_positions_follow_the_visible_set():
    app = BarApp()
    async with app.run_test(size=(80, 24)) as pilot:
        bar = app.query_one(ActionBar)
        await pilot.pause()
        assert [b.ordinal for b in bar.buttons()] == [1, 2, 3]
        bar.set_visible({"one", "three"})
        await pilot.pause()
        assert [b.ordinal for b in bar.buttons()] == [1, 2]
        # the number a button PRINTS is the one that fires it
        assert bar.action_for_key("ctrl+2").name == "three"
        assert bar.action_for_key("ctrl+3") is None


async def test_number_from_offsets_a_second_bar():
    app = BarApp()
    async with app.run_test(size=(80, 24)) as pilot:
        bar = app.query_one(ActionBar)
        await pilot.pause()
        assert bar.number_from(4) == 7          # next free number
        assert [b.ordinal for b in bar.buttons()] == [4, 5, 6]
        assert bar.action_for_key("ctrl+5").name == "two"
        assert bar.action_for_key("ctrl+1") is None
        bar.number_from(None)                   # a bar that isn't on show
        assert [b.ordinal for b in bar.buttons()] == [None, None, None]


async def test_focus_recolors_the_chord():
    """Two-way since 2026-10-26: the chord's color follows THIS button's
    focus and nothing else. It used to have a third state for "some other
    view has focus", which dimmed a button whose chord still worked.

    set_reactive-not-assignment matters here: Content.__eq__ compares
    plain text only, so a same-word recolor would otherwise be skipped.
    """
    app = BarApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        button = app.query(ActionButton).nodes[1]   # [0] is auto-focused
        assert KEY_STYLE in str(button.label.markup)
        app.set_focus(button)
        await pilot.pause()
        assert SELECTED_KEY_STYLE in str(button.label.markup)
        app.set_focus(None)
        await pilot.pause()
        assert KEY_STYLE in str(button.label.markup)
        # the retired mirror is a no-op, not a third look
        button.set_pane_focus(True)
        assert KEY_STYLE in str(button.label.markup)


async def test_focus_applies_its_css_at_once():
    # ActionButton overrides watch_has_focus, and Widget's version is
    # what applies the :focus rules. Without the super() call the
    # selected button's chrome stayed one event stale — the arrow moved,
    # the highlight didn't, so reversing direction looked like the arrow
    # kept going the old way (Nick, 2026-08-13).
    app = BarApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        first, second = app.query(ActionButton).nodes[:2]
        app.set_focus(second)
        await pilot.pause()
        # Button's own :focus rule tints the background; the tint is
        # there iff the focus styles have been applied to the node
        assert second.styles.background_tint.a > 0
        assert first.styles.background_tint.a == 0      # blurred: dropped


async def test_press_posts_triggered():
    triggered = []

    class CatchApp(BarApp):
        def on_action_bar_triggered(self, ev):
            triggered.append(ev.action.name)

    app = CatchApp()
    async with app.run_test(size=(80, 24)) as pilot:
        app.query(ActionButton).nodes[1].press()
        await pilot.pause()
        assert triggered == ["two"]
