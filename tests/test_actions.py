"""The app-wide button pattern: labels, wrapping, key dispatch."""

import pytest
from textual.app import App

from mediasmith.actions import Action, ActionBar, ActionButton, action_markup


# -- label markup ---------------------------------------------------------------


def test_key_first_char_splices_caret():
    assert action_markup("save", "s") == "[$text-accent]^s[/]ave"


def test_key_mid_word_splices_before_its_char():
    assert action_markup("fetch", "t") == "fe[$text-accent]^t[/]ch"


def test_key_absent_from_word_prefixes():
    assert action_markup("convert", "x") == "[$text-accent]^x[/] convert"


def test_key_match_is_case_insensitive():
    assert action_markup("Save", "s") == "[$text-accent]^S[/]ave"


def test_no_key_no_markup():
    assert action_markup("save", None) == "save"


def test_word_brackets_escaped():
    assert action_markup("a[b]", None) == r"a\[b]"


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
    CSS = "#host { width: 24; } ActionBar { width: 1fr; }"

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
        # 24 cells can't hold three ~9-cell buttons: at least one wraps,
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
