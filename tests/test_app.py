"""Interaction (Pilot) tests: keypresses in, observable state out."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from mediasmith import adapters
from mediasmith import details as details_mod
from mediasmith import fs
from mediasmith.app import LOGO, MediasmithApp, start_directory
from mediasmith.browser import LibraryTree, PathInput, TreeView, parse_view
from mediasmith.strip import CommandStrip
from mediasmith.details import ConfirmSave, DetailsView, EditForm
from textual.widgets import Input


async def settle(pilot, seconds=0.4):
    await pilot.pause(seconds)   # covers the details debounce


def test_start_directory_is_where_the_app_was_launched(tmp_path):
    """`mediasmith` with no argument opens the launch directory; a path
    that cannot be listed climbs to one that can."""
    (tmp_path / "song.mp3").write_bytes(b"")
    assert start_directory(tmp_path) == tmp_path.resolve()
    assert start_directory(tmp_path / "song.mp3") == tmp_path.resolve()
    assert start_directory(tmp_path / "gone" / "deeper") == tmp_path.resolve()
    assert start_directory(Path("/no-such-root-dir/nope")) == Path.home()


async def test_details_follow_highlight(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("down", "down", "down", "right")   # Books, Empty, Movies… expand
        await settle(pilot)
        details = app.query_one(DetailsView)
        assert details.path is not None


async def test_audio_panel_shows_tags(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        # walk to Music and expand, then to the first track
        while "Music" not in str(tree.cursor_node.label):
            await pilot.press("down")
        await pilot.press("right")
        await settle(pilot)
        await pilot.press("down")
        await settle(pilot)
        details = app.query_one(DetailsView)
        assert details.kind == "audio"
        assert app.query_one("#panel-audio").display is True
        form = app.query_one("#form-audio", EditForm)
        assert form.values()["title"] == "Song One"


async def test_album_art_shows_dimensions(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        details = app.query_one(DetailsView)
        # the first track carries an 8×8 cover; the second has none
        details.preview(media_tree / "Music" / "01 Song One.mp3",
                        immediate=True)
        await settle(pilot)
        dims = app.query_one("#cover-audio-dims")
        assert dims.display is True
        assert "8 × 8" in str(dims.render())
        details.preview(media_tree / "Music" / "02 Song Two.mp3",
                        immediate=True)
        await settle(pilot)
        assert app.query_one("#cover-audio-dims").display is False


async def test_damaged_album_art_shows_what_decoded(media_tree):
    """A cover whose JPEG scan ends early used to raise OSError inside the
    widget's render() — off the message pump, fatal (Nick, 2026-09-02)."""
    from tests.mediafactory import make_mp3, make_truncated_jpeg
    song = media_tree / "Music" / "03 Damaged Art.mp3"
    make_mp3(song, tags={"title": "Damaged Art"},
             cover=make_truncated_jpeg(size=(64, 64)))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        details = app.query_one(DetailsView)
        details.preview(song, immediate=True)
        await settle(pilot)
        dims = app.query_one("#cover-audio-dims")
        assert dims.display is True
        assert "64 × 64 · damaged" in str(dims.render())
        assert app.is_running                    # the render survived it


async def test_unreadable_album_art_hides_the_cover(media_tree):
    from tests.mediafactory import make_mp3, make_truncated_jpeg
    song = media_tree / "Music" / "04 No Art Left.mp3"
    make_mp3(song, tags={"title": "No Art Left"},
             cover=make_truncated_jpeg(size=(64, 64), cut=300))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.query_one(DetailsView).preview(song, immediate=True)
        await settle(pilot)
        assert app.query_one("#cover-audio").display is False
        assert app.query_one("#cover-audio-dims").display is False
        assert app.is_running


async def test_book_cover_shows_dimensions(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        details = app.query_one(DetailsView)
        details.preview(media_tree / "Books" / "Dune.epub", immediate=True)
        await settle(pilot)
        assert details.kind == "book"
        dims = app.query_one("#cover-book-dims")
        assert dims.display is True
        assert "8 × 8" in str(dims.render())


async def test_pathbar_tab_completes(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        bar = app.query_one(PathInput)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await pilot.pause(0.1)
        await pilot.press("tab")
        assert bar.value == str(media_tree / "Music") + "/"


def _border_color(widget):
    return widget.styles.border_top[1].hex.lower()


async def test_path_focus_lights_only_the_input(media_tree):
    """Nick, todo-5: while the path is being typed, the Tree View's own
    border drops back to idle — one lit box, not two nested ones."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        view, bar = app.query_one(TreeView), app.query_one(PathInput)
        theme = app.get_css_variables()
        focus = theme["border-fg-focus"].lower()
        idle = theme["border-fg-idle"].lower()
        assert _border_color(view) == focus          # the tree has focus

        bar.focus()
        await pilot.pause()
        assert view.has_class("-path-editing")
        assert _border_color(view) == idle
        assert _border_color(bar) == focus           # …the input alone

        app.query_one(LibraryTree).focus()
        await pilot.pause()
        assert not view.has_class("-path-editing")
        assert _border_color(view) == focus
        assert _border_color(bar) == idle


async def test_pathbar_enter_expands_the_directory_it_lands_on(media_tree):
    # Nick, 2026-08-22: arriving somewhere from the path input should show
    # what is there — the landed-on folder is expanded, not just selected
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        bar.focus()
        await pilot.pause()
        bar.value = str(media_tree / "Mus")          # a filter view
        await pilot.pause(0.2)
        await pilot.press("enter")
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        node = tree._node_for(media_tree / "Music")
        assert node is not None
        assert node.is_expanded                      # its tracks are on show
        assert tree.cursor_node is node


async def test_other_file_is_editable(media_tree):
    # a plain file is renamable now (folder-style filename field); enter
    # descends into its rename field, esc ascends back to the tree
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down", "n")               # notes.txt (kind: other)
        await settle(pilot)
        assert app.query_one(DetailsView).can_edit()
        await pilot.press("enter")                   # descend into rename
        await pilot.pause()
        assert app.focused.id == "fname"
        await pilot.press("escape")                  # ascend back to the tree
        await pilot.pause()
        assert app.focused is tree


async def test_details_escape_returns_to_browser(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        details = app.query_one(DetailsView)
        details.focus()          # anchor folder: editable, lands on fname
        await pilot.pause()
        assert app.focused.id == "fname"
        await pilot.press("tab")                     # no cycling out…
        assert details in app.focused.ancestors
        await pilot.press("shift+tab")
        assert details in app.focused.ancestors
        await pilot.press("escape")                  # …only esc releases
        assert app.focused is app.query_one(LibraryTree)


async def _goto_first_song(app, pilot):
    """Cursor onto Music/01 Song One.mp3 with the details settled."""
    await settle(pilot)
    await pilot.press("down")
    await pilot.press("m", "u", "right")             # Music, expanded
    await settle(pilot)
    await pilot.press("down")                        # an audio file
    await settle(pilot)                              # details debounce
    assert app.query_one(DetailsView).kind == "audio"


async def test_enter_edit_when_editable(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        tree = app.query_one(LibraryTree)
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # descend: filename input
        assert app.focused.id == "fname"
        assert app.focused.value == "01 Song One.mp3"
        await pilot.press("escape")
        assert app.focused is tree


async def test_tab_folds_the_directory_under_the_cursor(media_tree):
    """TAB is →/← in one key (Nick, todo-5) — and no longer descends."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down", "m", "u")           # Music, collapsed
        await settle(pilot)
        node = tree.cursor_node
        assert node.data.path.name == "Music"
        assert not node.is_expanded

        await pilot.press("tab")                      # …expand
        await settle(pilot)
        assert node.is_expanded
        assert app.focused is tree                    # focus stays home

        await pilot.press("tab")                      # …and collapse again
        await settle(pilot)
        assert not node.is_expanded
        assert app.focused is tree


async def test_tab_on_a_file_does_nothing(media_tree):
    """A file has nothing to fold — as with →, the key is inert, and it
    must NOT fall through to Textual's focus cycling."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        tree = app.query_one(LibraryTree)
        await _goto_first_song(app, pilot)
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is tree


async def test_folder_panel_counts(media_tree):
    # counts view is for folders that don't bulk-qualify (subfolders inside);
    # Music has become a bulk form — see test_album_folder_shows_bulk_form
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # cursor on the anchor
        details = app.query_one(DetailsView)
        assert details.kind == "folder"
        counts = app.query_one("#folder-counts")
        assert "5 folders" in str(counts.render())


async def test_folder_panel_totals_fill_in_late(media_tree):
    """Nick, todo-5: a folder says how many files it holds and how much
    they weigh — recursively, so the walk runs in a worker and the rows
    start as "…"."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # cursor on the anchor
        assert app.query_one(DetailsView).kind == "folder"
        await pilot.pause(0.3)                       # the totals worker
        files = str(app.query_one("#folder-files").render())
        size = str(app.query_one("#folder-size").render())
        expected = [p for p in media_tree.rglob("*")
                    if p.is_file() and not p.name.startswith(".")]
        assert files == f"{len(expected):,}"
        assert size == details_mod.human_size(
            sum(p.stat().st_size for p in expected))


async def test_folder_totals_count_what_is_nested(media_tree):
    """The number is the whole subtree, not the top level: Movies holds
    one folder and no files of its own."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "m", "o")           # Movies/
        await settle(pilot)
        await pilot.pause(0.3)
        assert str(app.query_one("#folder-counts").render()) == "1 folder"
        assert str(app.query_one("#folder-files").render()) == "3"


async def test_pathbar_focus_puts_cursor_at_end(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+slash")
        bar = app.query_one(PathInput)
        assert app.focused is bar
        assert bar.cursor_position == len(bar.value)
        sel = bar.selection
        assert sel.start == sel.end          # nothing selected


async def test_tree_interleaves_files_and_folders(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        media = tree.root.children[0]          # root is the parent context
        names = [str(child.label) for child in media.children]
        assert names == ["Books", "Empty", "Movies", "Music",
                         "notes.txt", "Pics"]


async def test_launch_shows_parent_context(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        assert str(tree.path) == str(media_tree.parent)
        media = tree.root.children[0]
        assert str(media.label) == media_tree.name
        assert media.is_expanded
        assert tree.cursor_node is media


async def test_left_at_context_row_climbs(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        assert str(tree.cursor_node.label) == media_tree.name
        await pilot.press("up")                # onto the context row
        assert tree.cursor_line == 0
        await pilot.press("left")              # climb one rung
        await settle(pilot)
        assert str(tree.path) == str(media_tree.parent.parent)
        assert str(tree.cursor_node.label) == media_tree.parent.name
        # nothing below collapsed: media is still expanded with its children
        parent_node = tree.cursor_node
        media = next(c for c in parent_node.children
                     if str(c.label) == media_tree.name)
        assert media.is_expanded
        assert len(media.children) == 6


async def test_left_folds_then_climbs(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("left")              # collapse the anchor…
        assert str(tree.cursor_node.label) == media_tree.name
        assert not tree.cursor_node.is_expanded
        await pilot.press("left")              # …and climb in one rung
        await settle(pilot)
        assert str(tree.path) == str(media_tree.parent.parent)
        assert str(tree.cursor_node.label) == media_tree.parent.name


async def test_collapse_resets_child_expansion(media_tree):
    """← then → on the same folder returns a plain child list: the
    descendants' expanded state is reset, not remembered."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        anchor = tree.cursor_node                  # the media root, expanded
        while "Music" not in str(tree.cursor_node.label):
            await pilot.press("down")
        await pilot.press("right")                 # expand a child…
        await settle(pilot)
        music = tree.cursor_node
        assert music.is_expanded
        while tree.cursor_node is not anchor:
            await pilot.press("up")
        await pilot.press("left")                  # …collapse the parent…
        await settle(pilot)
        assert not anchor.is_expanded
        await pilot.press("right")                 # …and re-expand it
        await settle(pilot)
        assert anchor.is_expanded
        assert not music.is_expanded


async def test_up_at_top_no_longer_climbs(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("up")                # context row, no re-root
        assert str(tree.path) == str(media_tree.parent)
        assert tree.cursor_line == 0
        await pilot.press("up")                # home base: focus stays put
        assert app.focused is tree
        assert tree.cursor_line == 0


async def test_type_to_select_jumps_to_prefix(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")        # into the anchor folder first:
        await pilot.press("m")           # typing scopes to siblings
        assert str(tree.cursor_node.label) == "Movies"
        await pilot.press("u")           # buffer is now "mu"
        assert str(tree.cursor_node.label) == "Music"


async def test_type_to_select_nearest_when_no_prefix(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")        # into the anchor folder
        await pilot.press("z")           # nothing starts with z
        assert str(tree.cursor_node.label) == "Pics"


async def test_type_to_select_buffer_resets(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")        # into the anchor folder
        await pilot.press("m", "u")
        assert str(tree.cursor_node.label) == "Music"
        await pilot.pause(1.2)           # past TYPE_SEARCH_SECONDS
        await pilot.press("b")
        assert str(tree.cursor_node.label) == "Books"


async def test_type_to_select_scoped_to_folder(media_tree):
    # Nick's bug: 'b' while inside a subfolder jumped to a top-level
    # b-name instead of the sibling next to it.
    (media_tree / "Movies" / "Alien (1979)" / "behind.txt").write_text("x")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")              # into the anchor folder
        await pilot.press("m", "o")            # Movies
        await pilot.press("right")
        await settle(pilot)
        await pilot.press("down")              # Alien (1979)
        await pilot.press("right")
        await settle(pilot)
        await pilot.press("down")              # into the folder
        assert str(tree.cursor_node.label) == "Alien.1979.mkv"
        await pilot.press("b")                 # sibling, not top-level Books
        assert str(tree.cursor_node.label) == "behind.txt"
        await pilot.press("down")              # navigation resets the buffer
        await pilot.press("n")                 # no n-sibling: nearest-before
        assert str(tree.cursor_node.label) == "behind.txt"   # not notes.txt


async def test_type_to_select_descends_into_expanded_folder(media_tree):
    # Nick, 2026-09-02: typing on an EXPANDED folder searches its children,
    # so the hand never leaves the home row to press ↓ first.
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")              # into the anchor folder
        await pilot.press("m", "u")            # Music
        await pilot.press("right")             # expand; cursor stays on it
        await settle(pilot)
        assert str(tree.cursor_node.label) == "Music"
        await pilot.press("0")                 # a child, not a sibling
        assert str(tree.cursor_node.label) == "01 Song One.mp3"
        await pilot.press("2")                 # same scope, not the child's
        assert str(tree.cursor_node.label) == "02 Song Two.mp3"
        # the expanded folder is not its own candidate: 'm' finds no child,
        # so the nearest-before fallback answers from the children too
        await pilot.pause(1.2)                 # past TYPE_SEARCH_SECONDS
        await pilot.press("up", "up")          # back onto Music itself
        assert str(tree.cursor_node.label) == "Music"
        await pilot.press("m")
        assert str(tree.cursor_node.label) == "02 Song Two.mp3"


async def test_type_to_select_stays_on_siblings_when_collapsed(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")              # into the anchor folder
        await pilot.press("m", "u")            # Music, collapsed
        assert str(tree.cursor_node.label) == "Music"
        await pilot.pause(1.2)
        await pilot.press("p")                 # a sibling, not a child
        assert str(tree.cursor_node.label) == "Pics"


async def test_filesystem_root_labelled_slash():
    app = MediasmithApp(Path("/"))
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        assert str(tree.root.label) == "/"


async def test_ctrl_up_down_jump_to_tree_ends(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("ctrl+down")
        assert tree.cursor_line == tree.last_line
        assert app.focused is tree
        await pilot.press("ctrl+up")
        assert tree.cursor_line == 1     # line 0 is the context row
        assert app.focused is tree       # never the path bar


async def test_ctrl_slash_focuses_pathbar(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        bar = app.query_one(PathInput)
        await pilot.press("ctrl+slash")            # kitty-protocol name
        assert app.focused is bar
        await pilot.press("escape")                # back to the tree
        await pilot.press("ctrl+underscore")       # legacy-terminal name
        assert app.focused is bar
        # ^/ is a TREE command (todo-4): inert while details holds focus
        await pilot.press("escape")
        app.query_one(DetailsView).focus()
        await pilot.pause()
        await pilot.press("ctrl+slash")
        assert app.focused is not bar


async def test_opt_up_down_jump_to_sibling_ends(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")                  # into the anchor folder
        await pilot.press("m", "u")                # type-to-select Music
        await pilot.press("right")                 # expand it
        await settle(pilot)
        await pilot.press("down")                  # into the folder
        assert str(tree.cursor_node.label) == "01 Song One.mp3"
        await pilot.press("alt+down")
        assert str(tree.cursor_node.label) == "02 Song Two.mp3"
        await pilot.press("alt+up")
        assert str(tree.cursor_node.label) == "01 Song One.mp3"


async def test_opt_up_down_at_top_level(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")                  # into the anchor folder
        await pilot.press("m", "u")                # cursor on Music
        await pilot.press("alt+up")
        assert str(tree.cursor_node.label) == "Books"
        await pilot.press("alt+down")
        assert str(tree.cursor_node.label) == "Pics"


def test_parse_view(tmp_path):
    (tmp_path / "alpha").mkdir()
    d = str(tmp_path / "alpha")
    assert parse_view(d) == (tmp_path / "alpha", None)
    assert parse_view(d + "/") == (tmp_path / "alpha", None)   # slash: no-op
    assert parse_view(d + "/m") == (tmp_path / "alpha", "m")
    assert parse_view(str(tmp_path / "alp")) == (tmp_path, "alp")
    assert parse_view("/nope/zzz") == (Path("/nope"), "zzz")


async def test_typing_filters_tree(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "M")
        await settle(pilot)
        names = [c.data.path.name for c in tree.root.children]
        assert names == ["Movies", "Music"]
        assert tree.has_class("-editing")      # no selection while editing


async def test_slash_boundary_is_noop(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Music") + "/"
        await settle(pilot)
        songs = [c.data.path.name for c in tree.root.children]
        assert str(tree.path) == str(media_tree / "Music")
        assert songs == ["01 Song One.mp3", "02 Song Two.mp3"]
        bar.value = str(media_tree / "Music")     # slash deleted: same view
        await settle(pilot)
        assert str(tree.path) == str(media_tree / "Music")
        assert [c.data.path.name for c in tree.root.children] == songs
        bar.value = str(media_tree / "Musi")      # now a filter on the parent
        await settle(pilot)
        assert str(tree.path) == str(media_tree)
        assert [c.data.path.name for c in tree.root.children] == ["Music"]


async def test_blur_commits_filter_to_top_match(media_tree):
    # e.g. a mouse click elsewhere while a filter is typed
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mo")
        await settle(pilot)
        tree.focus()                 # any blur commits
        await settle(pilot)
        assert str(tree.cursor_node.label) == "Movies"
        media = tree.root.children[0]              # parent context is back
        assert len(media.children) == 6            # filter cleared
        assert bar.value == str(media_tree / "Movies")


async def test_enter_completes_to_top_match(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await settle(pilot)
        await pilot.press("enter")   # completes; does NOT enter the folder
        await settle(pilot)
        assert app.focused is tree
        assert str(tree.path) == str(media_tree.parent)
        assert str(tree.cursor_node.label) == "Music"
        assert bar.value == str(media_tree / "Music")


async def test_no_matches_shows_empty_tree(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "zzz")
        await settle(pilot)
        assert len(tree.root.children) == 0


async def test_input_focus_clears_selection(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down")
        await settle(pilot)
        details = app.query_one(DetailsView)
        assert details.path is not None
        await pilot.press("ctrl+slash")
        tree = app.query_one(LibraryTree)
        assert tree.has_class("-editing")
        assert details.path is None


async def test_ghost_suggestion_is_top_match(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await settle(pilot)
        assert bar._suggestion == str(media_tree / "Music") + "/"


async def test_typing_re_roots_the_tree_once_per_pause(media_tree, monkeypatch):
    """A burst of keystrokes is ONE re-root, not one per character.

    Every re-root reads a directory, and on the NAS a directory read costs
    seconds; un-debounced, typing a path queued dozens of them back to back
    and the tree's message pump was stuck for all of them (Nick, 2026-08-22).
    """
    re_roots = []
    original = LibraryTree.show_filtered

    def counted(self, directory, needle):
        re_roots.append((directory, needle))
        return original(self, directory, needle)

    monkeypatch.setattr(LibraryTree, "show_filtered", counted)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree) + "/"
        bar.cursor_position = len(bar.value)
        for char in "Mus":           # a burst, faster than the debounce
            await pilot.press(char)
        await settle(pilot)
        assert re_roots == [(media_tree, "Mus")]
        tree = app.query_one(LibraryTree)
        assert [c.data.path.name for c in tree.root.children] == ["Music"]


async def test_slow_directory_read_keeps_the_app_alive(media_tree, monkeypatch):
    """The NAS freeze (Nick, 2026-08-22): the path input stat'd and listed
    on the event loop, so a spun-down SMB disk stopped the WHOLE app — no
    redraw, no keys, quit-and-restart the only way out.

    A ticker measures the thing that actually broke: whether the loop keeps
    turning while a listing is in flight.
    """
    real_list_dir = fs.list_dir

    def slow_list_dir(path):
        if Path(path) == media_tree:      # the NAS, spinning up
            time.sleep(0.4)
        return real_list_dir(path)

    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing

        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        monkeypatch.setattr(fs, "list_dir", slow_list_dir)
        beat = asyncio.create_task(ticker())
        try:
            bar.value = str(media_tree / "Mu")
            await settle(pilot, 1.5)
        finally:
            beat.cancel()
        assert ticks > 20            # blocked, this was single digits
        tree = app.query_one(LibraryTree)
        assert [c.data.path.name for c in tree.root.children] == ["Music"]
        monkeypatch.setattr(fs, "list_dir", real_list_dir)   # disks awake
        await settle(pilot)          # let the reads drain before teardown


async def test_a_slow_read_shows_the_waiting_marker(media_tree,
                                                    monkeypatch):
    """The wait is honest: the path input says it is reading while it is
    (browser.READING), and stops saying so when it stops."""
    from mediasmith.browser import READING
    real_list_dir = fs.list_dir

    def slow_list_dir(path):
        if Path(path) == media_tree:
            time.sleep(0.3)
        return real_list_dir(path)

    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        assert bar.border_subtitle in ("", None)
        monkeypatch.setattr(fs, "list_dir", slow_list_dir)
        bar.value = str(media_tree / "Mu")
        await pilot.pause(0.25)      # mid-read
        assert bar.border_subtitle == READING
        monkeypatch.setattr(fs, "list_dir", real_list_dir)
        await settle(pilot, 1.0)
        assert bar.border_subtitle == ""


async def test_matches_are_cached_paths(media_tree):
    """``is_dir()`` on a match must not go back to the filesystem: the
    suggester calls it on every keystroke."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        matches = await bar._matches(str(media_tree / "Mu"))
        assert [m.name for m in matches] == ["Music"]
        assert all(isinstance(m, fs.CachedPath) for m in matches)


async def test_hidden_files_shown_and_toggleable(media_tree):
    (media_tree / ".config").write_text("x")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        media = tree.root.children[0]
        names = [c.data.path.name for c in media.children]
        assert names[0] == ".config"              # visible by default
        await pilot.press("ctrl+full_stop")
        await settle(pilot)
        media = tree.root.children[0]             # reload rebuilt the nodes
        names = [c.data.path.name for c in media.children]
        assert ".config" not in names
        # ^. is a tree-state strip command: inert while details is focused
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        await pilot.press("ctrl+full_stop")
        await pilot.pause()
        assert app.show_hidden is False           # unchanged from details


async def test_tree_is_inset_one_cell_on_both_sides(media_tree):
    # the pane's padding is the only inset: a child margin would cost
    # every sibling that width and push the tree's scrollbar (its
    # rightmost content column) 3 cells off the border instead of 1
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        pane = app.query_one(TreeView)
        tree = app.query_one(LibraryTree)
        path_input = app.query_one(PathInput)
        left_border, right_border = pane.region.x, pane.region.right - 1
        scrollbar = tree.region.right - 1   # the tree's last content column
        assert tree.region.x - left_border - 1 == 1     # one cell, left
        assert right_border - scrollbar - 1 == 1        # one cell, right
        assert path_input.region.x == tree.region.x     # boxes line up
        assert path_input.region.right == tree.region.right


def _label_color(tree, line):
    """The rendered foreground of a tree row's name, as a hex string."""
    segments = [s for s in tree.render_line(line)._segments if s.text.strip()]
    return segments[-1].style.color.triplet.hex


async def test_selected_node_colors_come_from_the_theme(media_tree):
    # every color is a theme token (theme.py); the tree cursor picks the
    # hidden × selected × idle/focus one. A hidden row is dimmed by
    # DirectoryTree's own component class, so the selected pair drops
    # dim to land on the token itself.
    (media_tree / ".config").write_text("x")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        theme = app.get_css_variables()
        await pilot.press("down", "right")        # into media/, .config first
        await settle(pilot)
        line = tree.cursor_line
        assert str(tree.cursor_node.label) == ".config"
        assert _label_color(tree, line) == theme["node-hidden-selected-fg-focus"]
        app.query_one(DetailsView).focus()
        await pilot.pause()
        assert _label_color(tree, line) == theme["node-hidden-selected-fg-idle"]
        tree.focus()
        await pilot.press("down")                 # off the hidden row
        await settle(pilot)
        line = tree.cursor_line
        assert _label_color(tree, line) != theme["node-hidden-fg-focus"]
        app.query_one(DetailsView).focus()
        await pilot.pause()
        assert _label_color(tree, line) == theme["node-selected-fg-idle"]


def _row_cells(tree, line):
    """A tree row as (text, background-hex-or-None) per rendered segment."""
    return [(s.text,
             s.style.bgcolor.triplet.hex if s.style.bgcolor else None)
            for s in tree.render_line(line)._segments]


async def test_selected_row_wears_a_pad_cell_on_each_side(media_tree):
    # the selection color runs from the cell after the box character to
    # one cell past the name, icon included — a button's label, padded.
    # Both pads are cells the row already had; only their color changes.
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down", "right")     # into media/, first child
        await settle(pilot)
        selected = app.get_css_variables()["node-selected-bg-focus"]
        cells = _row_cells(tree, tree.cursor_line)
        name = str(tree.cursor_node.label)
        at = [text for text, _ in cells].index(name)
        assert cells[at][1] == selected                     # the name
        assert cells[at + 1] == (" ", selected)             # right pad
        assert cells[at - 1][1] == selected                 # the icon, in
        assert cells[at - 1][0].strip()                     # the run
        assert cells[at - 2] == (" ", selected)             # left pad
        assert cells[at - 3][0].endswith("─")               # the box char
        assert cells[at - 3][1] != selected                 # stays a guide
        # nothing moved: the same row, once the cursor leaves it, keeps
        # the name in the same column — the pads only change color
        line = tree.cursor_line
        here = "".join(text for text, _ in cells).index(name)
        await pilot.press("down")
        await settle(pilot)
        cells = _row_cells(tree, line)
        assert "".join(text for text, _ in cells).index(name) == here
        assert selected not in [bg for _, bg in cells]


def _guide_colors(tree, line):
    """Foreground of each guide column of a row, outermost first."""
    return [s.style.color.triplet.hex
            for s in tree.render_line(line)._segments
            if any(char in "│├╰─" for char in s.text)]


async def test_guides_tint_the_level_type_ahead_searches(media_tree):
    # the tint marks the level type-ahead would search: the cursor's own
    # sibling group, except over an EXPANDED folder, which marks its
    # children's column instead (Nick, 2026-09-03).
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        tint = tree.get_component_rich_style(
            "tree--guides-selected", partial=True).color.triplet.hex
        plain = tree.get_component_rich_style(
            "tree--guides", partial=True).color.triplet.hex
        assert tint != plain
        await pilot.press("down", "right")     # Books/, expanded
        await settle(pilot)
        assert str(tree.cursor_node.label) == "Books"
        cursor, child, sibling = (tree.cursor_line,
                                  tree.cursor_line + 1,      # Dune.epub
                                  tree.cursor_line + 2)      # Empty/
        # expanded: the tint drops a level, onto the children it searches
        assert _guide_colors(tree, child) == [plain, tint]
        assert _guide_colors(tree, cursor) == [plain]
        assert _guide_colors(tree, sibling) == [plain]
        await pilot.press("down")              # into the epub — same level
        await settle(pilot)
        assert tree.cursor_line == child
        assert _guide_colors(tree, child) == [plain, tint]
        await pilot.press("down")              # Empty/, collapsed: siblings
        await settle(pilot)
        assert tree.cursor_line == sibling
        assert _guide_colors(tree, sibling) == [tint]
        assert _guide_colors(tree, cursor) == [tint]
        assert _guide_colors(tree, child) == [tint, plain]   # repaints too
        app.query_one(DetailsView).focus()     # no tint on an idle tree
        await pilot.pause()
        idle = tree.get_component_rich_style(
            "tree--guides", partial=True).color.triplet.hex
        assert _guide_colors(tree, child) == [idle, idle]


async def test_enter_without_edit_returns_to_browser(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("ctrl+slash")
        await pilot.press("enter")
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        assert app.focused is tree
        assert str(tree.cursor_node.label) == media_tree.name


async def test_enter_on_complete_dir_anchors_into_it(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Music")     # a complete path: no filter
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert app.focused is tree
        assert str(tree.path) == str(media_tree)  # Music in parent context
        assert str(tree.cursor_node.label) == "Music"
        assert tree.cursor_node.is_expanded
        assert bar.value == str(media_tree / "Music")


async def test_escape_deletes_partial_segment(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await settle(pilot)
        await pilot.press("escape")
        await settle(pilot)
        assert app.focused is tree
        assert tree.view_filter is None
        assert str(tree.cursor_node.label) == media_tree.name
        assert bar.value == str(media_tree)       # partial "Mu" deleted
        media = tree.root.children[0]
        assert len(media.children) == 6           # full listing restored


# -- details editing ----------------------------------------------------------


async def test_right_arrow_does_not_edit_files(media_tree):
    # Nick retired the "→ edit" duplicate (todo-4): ⏎ is the one edit key
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("right")                 # → on a file: nothing
        assert app.focused is app.query_one(LibraryTree)


async def test_right_arrow_still_expands_folders(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")
        await pilot.press("m", "u")                # Music, collapsed
        await pilot.press("right")
        await settle(pilot)
        assert tree.cursor_node.is_expanded
        assert app.focused is tree


async def test_up_down_move_between_fields(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        assert app.focused.id == "fname"           # filename selected first
        await pilot.press("down")                  # first tag input
        form = app.query_one("#form-audio", EditForm)
        assert app.focused is form.inputs()[0]
        assert app.focused.value == "Song One"
        await pilot.press("up")
        assert app.focused.id == "fname"
        await pilot.press("up")                    # clamped at the top
        assert app.focused.id == "fname"


async def test_ctrl_s_saves_tags(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "down")         # title input
        app.focused.value = "Song Won"
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)                     # save runs in a thread
        path = media_tree / "Music" / "01 Song One.mp3"
        assert adapters.read_details(path).fields["title"] == "Song Won"
        details = app.query_one(DetailsView)
        assert not details.dirty                   # baseline moved with the save
        assert app.focused is not app.query_one(LibraryTree)   # ^s keeps focus


async def test_ctrl_s_acknowledges_the_save(media_tree):
    """Nick, 2026-08-25: a single-file save used to land in silence."""
    from textual.widgets._toast import Toast
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40), notifications=True) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "down")
        app.focused.value = "Song Won"
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        shown = [t._notification.message for t in app.query(Toast)]
        assert any("saved" in message for message in shown), shown


# -- positional chords: ^1…^9 beside the letter chords (Nick's A/B) -------------


async def test_buttons_print_their_position(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        from mediasmith.actions import ActionBar
        labels = [b.label.plain
                  for b in app.query_one("#pane-bar", ActionBar).buttons()]
        assert labels[0].startswith("^1 ")
        assert labels[1].startswith("^2 ")
        assert "^s" in labels[0]                 # the letter chord stayed


async def test_positional_chord_fires_the_second_button(media_tree,
                                                        monkeypatch):
    """^2 fires whatever is printed second — here "open" (audio's ^o)."""
    calls = []
    monkeypatch.setattr(details_mod, "launch", lambda p: calls.append(p))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        from mediasmith.actions import ActionBar
        bar = app.query_one("#pane-bar", ActionBar)
        assert bar.buttons()[1].spec.name == "open"
        await pilot.press("enter")               # details holds focus
        await pilot.press("ctrl+2")
        await pilot.pause(0.3)
        assert calls == [media_tree / "Music" / "01 Song One.mp3"]


async def test_option_digit_fires_the_same_button(media_tree, monkeypatch):
    """⌥2 is the number chord's tmux-proof spelling: it arrives as the
    macOS Option GLYPH (Ghostty types it; Textual decodes tmux's
    ESC+digit into the same one), not as "alt+2"."""
    calls = []
    monkeypatch.setattr(details_mod, "launch", lambda p: calls.append(p))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # details holds focus
        await pilot.press("trade_mark_sign")         # ⌥2 → "open"
        await pilot.pause(0.3)
        assert calls == [media_tree / "Music" / "01 Song One.mp3"]


async def test_option_digit_does_not_type_into_a_field(media_tree,
                                                       monkeypatch):
    """The glyph is printable, so a field would happily type "™"."""
    monkeypatch.setattr(details_mod, "launch", lambda p: None)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # #fname focused
        assert app.focused.id == "fname"
        before = app.focused.value
        await pilot.press("trade_mark_sign")
        await pilot.pause(0.2)
        assert app.query_one("#fname", Input).value == before


async def test_positions_renumber_with_the_visible_set(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        from mediasmith.actions import ActionBar
        bar = app.query_one("#pane-bar", ActionBar)
        await _goto_folder(app, pilot, "Empty")   # a folder: save only
        assert [b.label.plain for b in bar.buttons()][0].startswith("^1 ")
        assert len(bar.buttons()) == 1
        await _goto_first_song(app, pilot)        # audio: the full palette
        numbers = [b.label.plain.split()[0] for b in bar.buttons()]
        assert numbers == [f"^{i}" for i in range(1, len(numbers) + 1)]


async def test_esc_clean_releases_focus(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "escape")
        assert app.focused is app.query_one(LibraryTree)


async def test_confirm_save_survives_double_dismiss(media_tree):
    # two modal keys inside one frame (esc esc) once dismissed twice;
    # the second pop emptied the screen stack = app death (fuzz seed 10)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        app.focused.value = "junk.mp3"               # dirty
        await pilot.press("escape")                  # modal up
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ConfirmSave)
        modal.action_choose("cancel")                # both keys land…
        modal.action_choose("cancel")                # …before the pop
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmSave)
        assert app.is_running


async def test_esc_dirty_confirm_discard(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "down")
        app.focused.value = "Edited"
        await pilot.press("escape")
        assert isinstance(app.screen, ConfirmSave)   # pending edits: modal
        await pilot.press("d")                       # discard
        await pilot.pause()
        assert app.focused is app.query_one(LibraryTree)
        form = app.query_one("#form-audio", EditForm)
        assert form.values()["title"] == "Song One"  # restored
        path = media_tree / "Music" / "01 Song One.mp3"
        assert adapters.read_details(path).fields["title"] == "Song One"


async def test_esc_dirty_confirm_keep_editing(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "down")
        app.focused.value = "Edited"
        await pilot.press("escape", "escape")        # modal, then cancel
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmSave)
        form = app.query_one("#form-audio", EditForm)
        assert form.values()["title"] == "Edited"    # edit kept, still editing
        details = app.query_one(DetailsView)
        assert details.dirty


async def test_esc_dirty_confirm_save(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "down")
        app.focused.value = "Song Won"
        await pilot.press("escape", "s")             # modal → save
        await pilot.pause(0.5)
        assert app.focused is app.query_one(LibraryTree)
        path = media_tree / "Music" / "01 Song One.mp3"
        assert adapters.read_details(path).fields["title"] == "Song Won"


async def test_rename_via_details(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # fname focused
        app.focused.value = "01 First Song.mp3"
        await pilot.press("ctrl+s")
        await pilot.pause(0.6)
        old = media_tree / "Music" / "01 Song One.mp3"
        new = media_tree / "Music" / "01 First Song.mp3"
        assert new.exists() and not old.exists()
        assert app.query_one(PathInput).value == str(new)
        tree = app.query_one(LibraryTree)
        assert str(tree.cursor_node.label) == "01 First Song.mp3"


async def test_book_panel_is_editable(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "right")           # Books, expanded
        await settle(pilot)
        await pilot.press("down")                    # Dune.epub
        await settle(pilot)
        details = app.query_one(DetailsView)
        assert details.kind == "book"
        await pilot.press("enter", "down")           # title input
        form = app.query_one("#form-book", EditForm)
        assert app.focused is form.inputs()[0]
        app.focused.value = "Dune Messiah"
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        path = media_tree / "Books" / "Dune.epub"
        assert adapters.read_details(path).fields["title"] == "Dune Messiah"


async def _goto_dune(app, pilot):
    """Cursor onto Books/Dune.epub with the details settled."""
    await settle(pilot)
    await pilot.press("down", "right")           # Books, expanded
    await settle(pilot)
    await pilot.press("down")                    # Dune.epub
    await settle(pilot)
    assert app.query_one(DetailsView).kind == "book"


async def test_book_offers_conversions_minus_own_format(media_tree):
    from mediasmith.actions import ActionBar
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        bar = app.query_one("#pane-bar", ActionBar)
        names = [b.spec.name for b in bar.buttons()]
        assert names == ["save", "open", "convert_mobi", "convert_azw3",
                         "create_opf", "standardize", "book_cover",
                         "extract_cover", "sort_book"]


async def test_plain_book_hides_extract_cover(media_tree):
    from mediasmith.actions import ActionBar
    from tests.mediafactory import make_epub
    make_epub(media_tree / "Books" / "Plain.epub", cover=None)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("down")                    # Plain.epub (D < P)
        await settle(pilot)
        bar = app.query_one("#pane-bar", ActionBar)
        names = [b.spec.name for b in bar.buttons()]
        assert "extract_cover" not in names          # nothing to extract
        assert "create_opf" in names


async def test_book_cover_button_opens_prefilled_path(media_tree):
    from tests.mediafactory import make_png
    make_png(media_tree / "Books" / "Dune.png")   # sibling sharing the stem
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        assert "book_cover" in _bar_names(app)     # offered on every epub
        await pilot.press("enter", "ctrl+u")       # ^upload cover
        await pilot.pause(0.2)
        field = app.query_one("#book-cover-path")
        assert app.focused is field
        assert field.value == str(media_tree / "Books" / "Dune.png")


async def test_book_cover_prefill_falls_back_to_cover_image(media_tree):
    from tests.mediafactory import make_png
    make_png(media_tree / "Books" / "cover.jpg")   # no same-stem sibling
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "right")         # Books expanded
        await settle(pilot)
        await pilot.press("down", "down")          # past cover.jpg → Dune.epub
        await settle(pilot)
        assert app.query_one(DetailsView).kind == "book"
        await pilot.press("enter", "ctrl+u")
        await pilot.pause(0.2)
        assert app.query_one("#book-cover-path").value == \
            str(media_tree / "Books" / "cover.jpg")


async def test_book_cover_prefill_falls_back_to_directory(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)               # Books/ has only Dune.epub
        await pilot.press("enter", "ctrl+u")
        await pilot.pause(0.2)
        assert app.query_one("#book-cover-path").value == \
            str(media_tree / "Books") + "/"


async def test_book_cover_apply_writes_into_epub(media_tree):
    import io

    from PIL import Image

    from mediasmith import epub as epublib
    from tests.mediafactory import make_png
    make_png(media_tree / "Books" / "Dune.png", size=(44, 66))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+u")
        await pilot.pause(0.2)
        await pilot.press("enter")                 # ⏎ apply
        await pilot.pause(0.8)
        out = epublib.extract_cover_bytes(media_tree / "Books" / "Dune.epub")
        assert out is not None
        assert Image.open(io.BytesIO(out)).size == (44, 66)   # new cover won
        assert not app.query_one("#book-cover-div").display   # input closed


async def test_book_cover_escape_cancels(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+u")
        await pilot.pause(0.2)
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not app.query_one("#book-cover-div").display


async def test_extract_cover_creates_sibling(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+e")         # ^extract cover
        await pilot.pause(0.5)
        target = media_tree / "Books" / "cover.png"  # factory cover is png
        assert target.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(target) is not None


async def test_create_opf_creates_sidecar(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+w")         # ^write opf
        await pilot.pause(0.5)
        target = media_tree / "Books" / "metadata.opf"
        assert target.exists()
        assert "<dc:title>Dune</dc:title>" in target.read_text()


async def _goto_omni(app, pilot, media_tree):
    """An omnibus in Books/, cursor on it, probe settled."""
    from tests.mediafactory import make_omnibus
    make_omnibus(media_tree / "Books" / "Omni.epub")
    await _goto_dune(app, pilot)
    await pilot.press("down")                    # Omni.epub (D < O)
    await settle(pilot)
    await pilot.pause(0.3)                       # the zip-read probe


async def test_split_omnibus_button_is_probe_gated(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_omni(app, pilot, media_tree)
        assert "split_omnibus" in _bar_names(app)
        await pilot.press("up")                  # back to Dune (one book)
        await settle(pilot)
        await pilot.pause(0.3)
        assert "split_omnibus" not in _bar_names(app)


async def test_split_omnibus_opens_editable_form_focused(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_omni(app, pilot, media_tree)
        await pilot.press("enter", "ctrl+b")     # split omni^bus
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details._omnibus_editing
        # the pane holds focus, on the first (author) field, pre-filled
        assert app.focused is app.query_one("#omni-author")
        assert app.query_one("#omni-author").value == "Frank Herbert"
        assert app.query_one("#omni-series").value == "Omnibus"
        assert app.query_one("#omni-title-0").value == "Book 1"
        assert set(_bar_names(app)) == {"plan_apply", "plan_cancel"}


async def test_split_omnibus_apply_defaults(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_omni(app, pilot, media_tree)
        await pilot.press("enter", "ctrl+b")
        await pilot.pause(0.6)
        await pilot.press("ctrl+a")              # ^apply, from within a field
        await pilot.pause(0.8)
        one = media_tree / "Books" / "Herbert, Frank - Omnibus - 01 - Book 1.epub"
        two = media_tree / "Books" / "Herbert, Frank - Omnibus - 02 - Book 2.epub"
        assert one.exists() and two.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(one) is not None   # tree re-listed in place
        assert app.focused is tree               # ascended after apply


async def test_split_omnibus_edits_feed_output(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_omni(app, pilot, media_tree)
        await pilot.press("enter", "ctrl+b")
        await pilot.pause(0.6)
        # correct the mangled title and the cruft-laden series name
        app.query_one("#omni-series").value = "Dune Chronicles"
        app.query_one("#omni-title-0").value = "Dune"
        await pilot.press("ctrl+a")
        await pilot.pause(0.8)
        out = (media_tree / "Books"
               / "Herbert, Frank - Dune Chronicles - 01 - Dune.epub")
        assert out.exists()                      # edited metadata → filename
        assert not (media_tree / "Books"
                    / "Herbert, Frank - Omnibus - 01 - Book 1.epub").exists()


async def test_split_omnibus_escape_cancels(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_omni(app, pilot, media_tree)
        await pilot.press("enter", "ctrl+b")
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details.plan_preview_open()
        await pilot.press("escape")              # from the focused form
        await settle(pilot)
        assert not details.plan_preview_open()
        assert not details._omnibus_editing
        assert app.focused is app.query_one(LibraryTree)   # ascended to tree
        assert not (media_tree / "Books"
                    / "Herbert, Frank - Omnibus - 01 - Book 1.epub").exists()


async def test_audio_offers_save_and_open(media_tree):
    from mediasmith.actions import ActionBar
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        bar = app.query_one("#pane-bar", ActionBar)
        assert [b.spec.name for b in bar.buttons()] == ["save", "open"]


async def test_convert_creates_sibling_and_tree_follows(media_tree, monkeypatch):
    from mediasmith import calibre

    def fake_convert(src, dst):
        dst.write_bytes(b"mobi bytes")

    monkeypatch.setattr(calibre, "convert", fake_convert)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+t")         # conver^t to mobi
        await pilot.pause(0.5)
        target = media_tree / "Books" / "Dune.mobi"
        assert target.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(target) is not None    # tree picked it up


async def test_convert_never_overwrites(media_tree, monkeypatch):
    from mediasmith import calibre
    existing = media_tree / "Books" / "Dune.mobi"
    existing.write_bytes(b"precious")

    def fake_convert(src, dst):                      # must not be reached
        raise AssertionError("convert ran over an existing file")

    monkeypatch.setattr(calibre, "convert", fake_convert)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+t")
        await pilot.pause(0.5)
        assert existing.read_bytes() == b"precious"


async def test_convert_overwrites_on_second_press(media_tree, monkeypatch):
    from mediasmith import calibre
    existing = media_tree / "Books" / "Dune.mobi"
    existing.write_bytes(b"old")
    calls = []

    def fake_convert(src, dst):
        calls.append(dst)
        dst.write_bytes(b"new")

    monkeypatch.setattr(calibre, "convert", fake_convert)
    monkeypatch.setattr(calibre, "find_ebook_convert", lambda: object())
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+t")         # refuses, arms
        await pilot.pause(0.3)
        assert calls == [] and existing.read_bytes() == b"old"
        await pilot.press("ctrl+t")                  # same key again: overwrite
        await pilot.pause(0.5)
        assert calls and existing.read_bytes() == b"new"


async def test_convert_arm_resets_when_selection_moves(media_tree, monkeypatch):
    from mediasmith import calibre
    (media_tree / "Books" / "Dune.mobi").write_bytes(b"old")
    calls = []
    monkeypatch.setattr(calibre, "convert", lambda s, d: calls.append(d))
    monkeypatch.setattr(calibre, "find_ebook_convert", lambda: object())
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+t")         # arms
        await pilot.pause(0.3)
        await pilot.press("escape")                  # back to the tree
        await pilot.press("up")                      # browse away disarms
        await settle(pilot)
        await pilot.press("down")                    # back to Dune.epub
        await settle(pilot)
        await pilot.press("enter", "ctrl+t")         # first press again: refuses
        await pilot.pause(0.4)
        assert calls == []                           # not overwritten


# -- folderize --------------------------------------------------------------------


def _make_inbox(media_tree):
    """A messy dumping-ground folder: two tagged strays, one untagged."""
    from tests.mediafactory import make_mp3
    inbox = media_tree / "Inbox"
    inbox.mkdir()
    make_mp3(inbox / "strayA.mp3",
             tags={"title": "A", "artist": "The Band", "album": "Alpha"})
    make_mp3(inbox / "strayB.mp3",
             tags={"title": "B", "artist": "The Band", "album": "Alpha"})
    make_mp3(inbox / "mystery.mp3", tags={"title": "?"})
    return inbox


async def _goto_folder(app, pilot, name):
    await settle(pilot)
    await pilot.press("down")                    # into the anchor's children
    await pilot.press(*name.lower()[:3])         # type-to-select
    await settle(pilot)
    await pilot.pause(0.6)                       # probe worker fills in late
    node = app.query_one(LibraryTree).cursor_node
    assert name in str(node.label)


def _bar_names(app):
    from mediasmith.actions import ActionBar
    return [b.spec.name for b in app.query_one("#pane-bar", ActionBar).buttons()]


async def test_folderize_appears_only_where_useful(media_tree):
    _make_inbox(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Inbox")
        assert "folderize" in _bar_names(app)
        await _goto_folder(app, pilot, "Books")  # no audio below
        assert "folderize" not in _bar_names(app)


async def test_folderize_preview_apply_flow(media_tree):
    inbox = _make_inbox(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Inbox")
        await pilot.press("enter", "ctrl+l")     # fo^lderize → plan preview
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details.plan_preview_open()
        assert app.query_one("#plan-preview").display
        assert set(_bar_names(app)) == {"plan_apply", "plan_cancel"}
        await pilot.press("ctrl+a")              # apply
        await pilot.pause(0.8)
        assert (inbox / "The Band" / "Alpha" / "strayA.mp3").exists()
        assert (inbox / "* Skipped" / "mystery.mp3").exists()
        assert not details.plan_preview_open()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(inbox / "The Band") is not None
        await pilot.pause(0.6)                   # re-probe: nothing left
        assert "folderize" not in _bar_names(app)


async def test_folderize_escape_cancels_preview(media_tree):
    inbox = _make_inbox(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Inbox")
        await pilot.press("enter", "ctrl+l")
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details.plan_preview_open()
        await pilot.press("escape")              # tree keeps focus: esc = cancel
        await settle(pilot)
        assert not details.plan_preview_open()
        assert not app.query_one("#plan-preview").display
        assert (inbox / "strayA.mp3").exists()   # nothing moved
        assert "folderize" in _bar_names(app)    # back to the offer


async def test_folderize_asks_before_respelling_an_artist_folder(media_tree):
    """The plan-shaped folderize meets the same case clash: "the band/"
    already exists where the tags say "The Band/" goes."""
    from mediasmith.details import ConfirmCaseRename
    inbox = _make_inbox(media_tree)
    if not _case_blind(inbox):
        pytest.skip("case-sensitive filesystem: no collision to resolve")
    (inbox / "the band").mkdir()
    fs.clear_cache()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Inbox")
        await pilot.press("enter", "ctrl+l")     # fo^lderize → plan preview
        await pilot.pause(0.6)
        await pilot.press("ctrl+a")              # apply
        await pilot.pause(0.6)
        assert isinstance(app.screen, ConfirmCaseRename)
        await pilot.press("k")                   # rename, keep contents
        await pilot.pause(1.2)
        assert (inbox / "The Band" / "Alpha" / "strayA.mp3").is_file()
        assert "The Band" in os.listdir(inbox)   # the tags' casing won


async def test_folderize_offered_on_album_bulk_view(media_tree):
    # Music is an album-like leaf (bulk form), but its loose files are
    # unorganized — the folder action must still be reachable
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Music")
        await pilot.pause(0.4)                   # bulk read + probe
        names = _bar_names(app)
        assert "save" in names and "folderize" in names


def _strip_text(app) -> str:
    return app.query_one(CommandStrip).render().plain


async def test_command_strip_follows_state(media_tree):
    # ONE strip; its contents are the state contract (todo-4)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(160, 40)) as pilot:
        await settle(pilot)
        text = _strip_text(app)                      # tree focused at launch
        assert "cut" in text and "new directory" in text and "edit" in text
        assert "→ TAB expand" in text                # TAB folds (todo-5)
        assert "← TAB collapse" in text
        assert "complete" not in text and "close" not in text
        await pilot.press("ctrl+slash")              # path input focused
        await pilot.pause()
        text = _strip_text(app)
        assert "complete" in text and "go" in text and "cancel" in text
        assert "cut" not in text and "refresh" not in text
        await pilot.press("escape")
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # details focused
        await pilot.pause()
        text = _strip_text(app)
        assert "navigate" in text and "close" in text
        assert "save" not in text                    # the button carries ^s
        assert "refresh" not in text


async def test_left_mid_text_moves_cursor_not_focus(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # fname, cursor at end
        assert app.focused.id == "fname"
        await pilot.press("left")
        assert app.focused.id == "fname"             # still editing


async def test_left_at_text_start_releases(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "home", "left")   # ← at position 0 = esc
        assert app.focused is app.query_one(LibraryTree)


async def test_left_at_text_start_respects_dirty(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "down")
        app.focused.value = "Edited"
        await pilot.press("home", "left")
        assert isinstance(app.screen, ConfirmSave)   # same guard as esc
        await pilot.press("escape")                  # keep editing


async def test_field_focus_places_cursor_at_end(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        bar = app.focused                            # fname
        assert bar.cursor_position == len(bar.value)
        sel = bar.selection
        assert sel.start == sel.end                  # nothing selected
        await pilot.press("down")                    # title input: same rule
        assert app.focused.cursor_position == len(app.focused.value)
        assert app.focused.selection.start == app.focused.selection.end


async def test_art_field_after_last_input(media_tree):
    from mediasmith.details import ArtField, EditForm
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        form = app.query_one("#form-audio", EditForm)
        for _ in range(1 + len(form.inputs())):      # fname + every tag
            await pilot.press("down")
        assert isinstance(app.focused, ArtField)     # art follows the inputs
        await pilot.press("up")
        assert app.focused.id != "fname"             # back into the tags
        await pilot.press("escape")
        assert app.focused is app.query_one(LibraryTree)


async def test_audio_info_parked_below_save(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        info = app.query_one("#row-audio-info")
        assert info.display                          # shown for audio…
        assert info.region.y > app.query_one("#save-btn").region.y
        tree = app.query_one(LibraryTree)
        await pilot.press("down", "down")            # notes.txt (other kind)
        await settle(pilot)
        assert not info.display                      # …hidden elsewhere


async def test_ctrl_r_refreshes_tree(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        (media_tree / "zzz new.txt").write_text("x")   # external change
        await pilot.press("ctrl+r")
        await settle(pilot)
        media = tree.root.children[0]
        names = [c.data.path.name for c in media.children]
        assert "zzz new.txt" in names
        assert str(tree.cursor_node.label) == media_tree.name   # cursor kept
        assert media.is_expanded                                # ladder kept


async def test_opt_shift_arrows_select_words(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # fname, cursor at end
        field = app.focused
        await pilot.press("alt+shift+left")          # select back one word
        sel = field.selection
        assert sel.start != sel.end
        assert field.value[min(sel):max(sel)] == "mp3"
        await pilot.press("alt+shift+right")         # and shrink it again
        sel = field.selection
        assert sel.start == sel.end

        bar = app.query_one(PathInput)                 # same in the path bar
        bar.focus()
        await pilot.pause()
        await pilot.press("alt+shift+left")
        sel = bar.selection
        assert sel.start != sel.end


# -- album-art methods ----------------------------------------------------------


async def test_art_buttons_reachable_by_arrows(media_tree):
    from mediasmith.details import ArtField
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        for _ in range(30):                          # ↓ walks clean through:
            await pilot.press("down")                # fields → art → buttons
        assert app.focused.id == "act-open"          # …and clamps at the end
        await pilot.press("down")                    # bottom: clamp
        assert app.focused.id == "act-open"
        await pilot.press("up", "up", "up")          # ↑ = left through buttons
        assert app.focused.id == "art-btn-path"
        await pilot.press("right")
        assert app.focused.id == "art-btn-fetch"
        await pilot.press("right")                   # rightmost of its bar: clamp
        assert app.focused.id == "art-btn-fetch"
        await pilot.press("left")
        assert app.focused.id == "art-btn-path"
        await pilot.press("up")                      # back to the art slot
        assert isinstance(app.focused, ArtField)
        await pilot.press("down", "left")            # ← at leftmost = esc
        assert app.focused is app.query_one(LibraryTree)


async def test_action_key_inert_from_the_tree(media_tree):
    # chords are VIEW-SCOPED (todo-4): a Details-view button's chord does
    # nothing while the tree owns focus — the strip is the contract
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        assert app.focused is app.query_one(LibraryTree)
        await pilot.press("ctrl+p")                  # im^port — from the tree
        assert app.focused is app.query_one(LibraryTree)   # inert
        assert not app.query_one("#row-art-path").display


async def test_action_key_inert_when_bar_hidden(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # cursor on a folder
        assert app.query_one(DetailsView).kind == "folder"
        await pilot.press("ctrl+p")                  # no audio bar on show
        assert app.focused is app.query_one(LibraryTree)
        assert not app.query_one("#row-art-path").display


async def test_art_path_method(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "ctrl+p")         # im^port method
        field = app.focused
        assert field.id == "art-path"
        assert app.query_one("#row-art-path").display
        field.value = str(media_tree / "Pics" / "photo.png")
        await pilot.press("enter")
        details = app.query_one(DetailsView)
        assert details.dirty                         # pending art
        assert not app.query_one("#row-art-path").display
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        path = media_tree / "Music" / "01 Song One.mp3"
        assert (adapters.cover_bytes(path)
                == (media_tree / "Pics" / "photo.png").read_bytes())
        assert not details.dirty


async def test_art_path_rejects_non_image(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "ctrl+p")
        app.focused.value = str(media_tree / "notes.txt")
        await pilot.press("enter")
        details = app.query_one(DetailsView)
        assert not details.dirty                     # rejected, no pending art
        assert app.focused.id == "art-path"          # still correcting


async def test_art_path_esc_cancels_to_buttons(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "ctrl+p", "escape")
        assert app.focused.id == "art-btn-path"
        assert not app.query_one("#row-art-path").display
        assert not app.query_one(DetailsView).dirty


async def test_art_fetch_method(media_tree, monkeypatch):
    from mediasmith import artfetch
    from tests.mediafactory import make_png
    art_a = make_png(color=(9, 9, 9))
    art_b = make_png(color=(200, 200, 9))
    candidates = [artfetch.CoverCandidate(url="a", label="The Band — First"),
                  artfetch.CoverCandidate(url="b", label="The Band — Live")]
    monkeypatch.setattr(artfetch, "search_covers",
                        lambda artist, album, limit=5: candidates)
    monkeypatch.setattr(artfetch, "fetch_bytes",
                        lambda url: art_a if url == "a" else art_b)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "ctrl+f")
        await pilot.pause(0.5)                       # worker round trip
        details = app.query_one(DetailsView)
        assert details._pending_art == art_a
        await pilot.press("ctrl+f")                  # repeat: next candidate
        await pilot.pause(0.5)
        assert details._pending_art == art_b
        await pilot.press("escape")                  # dirty: modal
        assert isinstance(app.screen, ConfirmSave)
        await pilot.press("d")                       # discard restores baseline
        await pilot.pause()
        assert details._pending_art is None
        assert not details.dirty
        path = media_tree / "Music" / "01 Song One.mp3"
        assert adapters.cover_bytes(path) != art_b   # nothing written


async def test_edited_fields_show_check_marks(media_tree):
    from textual.widgets import Static
    from mediasmith.details import EditForm
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "down")           # title input
        form = app.query_one("#form-audio", EditForm)
        title_row = form.children[0]

        def mark(row):
            return str(row.query_one(".fmark", Static).render())

        assert mark(title_row) == ""                 # pristine
        await pilot.press("x")                       # type into title
        await pilot.pause()
        assert mark(title_row) == "✓"                # edited
        assert mark(form.children[1]) == ""          # neighbours untouched
        await pilot.press("backspace")               # back to original value
        await pilot.pause()
        assert mark(title_row) == ""                 # value == baseline again

        await pilot.press("x")                       # dirty once more…
        await pilot.pause()
        await pilot.press("ctrl+s")                  # …and save
        await pilot.pause(0.5)
        assert mark(title_row) == ""                 # saved: clean marks

        fname_mark = app.query_one("#fname-mark", Static)
        await pilot.press("up", "x")                 # edit the filename
        await pilot.pause()
        assert str(fname_mark.render()) == "✓"
        await pilot.press("escape", "d")             # discard via the modal
        await pilot.pause()
        assert str(fname_mark.render()) == ""


# -- bulk editing -----------------------------------------------------------------


async def _bulk_settle(pilot):
    await pilot.pause(0.6)                           # debounce + read worker


async def test_shift_down_selects_and_shows_bulk_form(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)           # cursor on song one
        await pilot.press("shift+down")              # extend to song two
        await _bulk_settle(pilot)
        details = app.query_one(DetailsView)
        assert details.paths is not None and len(details.paths) == 2
        form = app.query_one("#form-audio", EditForm)
        assert form.values()["artist"] == "The Band"     # unanimous
        assert form.values()["title"] == ""              # mixed
        title_input = form.inputs()[0]
        assert title_input.placeholder == "(mixed)"
        title_label = str(app.query_one("#dtitle").render())
        assert "2 audio files selected" in title_label


async def test_plain_move_collapses_selection(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")
        await _bulk_settle(pilot)
        tree = app.query_one(LibraryTree)
        assert len(tree._selection_paths()) == 2
        await pilot.press("up")                      # plain move: collapse
        await settle(pilot)
        assert tree._selection_paths() == []
        assert app.query_one(DetailsView).paths is None


async def test_selection_confined_to_siblings(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down", "shift+down", "shift+down",
                          "shift+down")              # way past the last track
        await _bulk_settle(pilot)
        tree = app.query_one(LibraryTree)
        names = [p.name for p in tree._selection_paths()]
        assert names == ["01 Song One.mp3", "02 Song Two.mp3"]


async def test_bulk_edit_applies_to_all(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")
        await _bulk_settle(pilot)
        await pilot.press("enter")                   # descend into the form
        form = app.query_one("#form-audio", EditForm)
        assert app.focused is form.inputs()[0]       # no fname stop in bulk
        details = app.query_one(DetailsView)
        # edit a unanimous field and a mixed one
        album_input = form.inputs()[3]               # title,artist,albumartist,album
        album_input.focus()
        album_input.value = "Bulk Album"
        title_input = form.inputs()[0]
        title_input.focus()
        title_input.value = "Same Name"
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause(0.8)
        music = media_tree / "Music"
        for name in ("01 Song One.mp3", "02 Song Two.mp3"):
            d = adapters.read_details(music / name)
            assert d.fields["album"] == "Bulk Album"
            assert d.fields["title"] == "Same Name"
        assert not details.dirty                     # fresh baseline post-save


async def test_bulk_save_keeps_focus(media_tree):
    # todo-5 bug: after a bulk ^s the re-read (_begin_bulk) hid the form
    # under the focused field and NOTHING held focus — no keypress could
    # bring it back. Saving while editing must land focus back in the form.
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")
        await _bulk_settle(pilot)
        await pilot.press("enter")                   # descend into the form
        form = app.query_one("#form-audio", EditForm)
        form.inputs()[3].focus()                     # album (unanimous)
        form.inputs()[3].value = "Bulk Album"
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause(0.8)                       # save + re-read settle
        assert app.focused is not None               # focus never dropped
        details = app.query_one(DetailsView)
        assert details in app.focused.ancestors      # …and stayed in the pane


async def test_bulk_untouched_mixed_field_not_written(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")
        await _bulk_settle(pilot)
        await pilot.press("enter")
        form = app.query_one("#form-audio", EditForm)
        form.inputs()[3].focus()                     # album (unanimous, empty)
        form.inputs()[3].value = "Bulk Album"
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause(0.8)
        music = media_tree / "Music"
        one = adapters.read_details(music / "01 Song One.mp3")
        two = adapters.read_details(music / "02 Song Two.mp3")
        assert one.fields["title"] == "Song One"     # mixed field untouched
        assert two.fields["title"] == "Song Two"
        assert one.fields["album"] == "Bulk Album"


async def test_album_folder_shows_bulk_form(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")
        await pilot.press("m", "u")                  # cursor on Music (album-like)
        await _bulk_settle(pilot)
        details = app.query_one(DetailsView)
        assert details.paths is not None and len(details.paths) == 2
        assert details.kind == "audio"
        assert details.can_edit()
        await pilot.press("enter")                   # enter → details view
        await pilot.pause(0.3)
        form = app.query_one("#form-audio", EditForm)
        assert app.focused is form.inputs()[0]
        await pilot.press("escape")
        assert app.focused is tree


async def test_stale_selection_anchor_survives_reload(media_tree):
    # fuzz-caught crash: a reload can rebuild a node's children in place,
    # leaving _sel_anchor pointing at a node no longer in the tree; the
    # next shift-move then died on siblings.index(anchor) (ValueError)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")              # anchor on song one
        await _bulk_settle(pilot)
        tree = app.query_one(LibraryTree)
        stale = tree._sel_anchor
        assert stale is not None
        music = tree._node_for(media_tree / "Music")
        await tree.reload_node(music)                # children rebuilt
        await settle(pilot)
        cursor = tree.cursor_node
        if cursor is None or cursor.parent is not music:
            tree._move_cursor(music.children[-1].line)
        tree._sel_anchor = stale                     # the stranded anchor
        assert stale.parent is music                 # identity guard passes…
        assert stale not in music.children           # …membership is gone
        assert tree._selection_paths() == []         # detached: no selection
        await pilot.press("shift+up")                # must re-anchor, not die
        await settle(pilot)
        assert tree._sel_anchor is not stale
        assert app.is_running


# -- narrow (phone) breakpoint ------------------------------------------------


async def test_narrow_starts_tree_only(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        assert app.screen.has_class("-narrow")
        assert app.query_one(LibraryTree).display
        assert not app.query_one(PathInput).display
        assert not app.query_one(DetailsView).display


async def test_narrow_path_bar_summons_above_tree(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathInput)
        tree = app.query_one(LibraryTree)
        await pilot.press("ctrl+slash")
        assert app.focused is bar
        assert bar.display and tree.display          # shared, not swapped
        await pilot.press("enter")
        await settle(pilot)
        assert app.focused is tree
        assert not bar.display                       # gone with its focus


async def test_narrow_other_descends_editable(media_tree):
    # every kind is renamable now (the folder-style filename field), so a
    # plain file descends into its rename field WITH focus, like audio —
    # there is no longer a read-only "view without focus" kind
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")                    # into the anchor folder
        await pilot.press("n")                       # notes.txt (kind: other)
        await settle(pilot)
        await pilot.press("enter")                   # descend into rename
        await pilot.pause()
        details = app.query_one(DetailsView)
        assert details.display
        assert app.query_one(TreeView).region.width == 0   # narrow: swapped in
        assert app.focused.id == "fname"             # focus, not a bare view
        assert app.focused.value == "notes.txt"
        await pilot.press("escape")                  # ascend: tree swaps back
        await pilot.pause()
        assert not details.display
        assert app.query_one(TreeView).region.width > 0
        assert app.focused is tree


async def test_details_follow_cursor(media_tree):
    # the details pane tracks the tree highlight live (debounced), no
    # descend needed — browsing from a file to a folder swaps the panel
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "n")               # notes.txt
        await settle(pilot)
        details = app.query_one(DetailsView)
        assert details.path == media_tree / "notes.txt"
        await pilot.press("down")                    # Pics — cursor still in tree
        await settle(pilot)
        assert details.display
        assert details.path == media_tree / "Pics"


async def test_narrow_editable_descends_with_focus(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # focus, orange border
        await pilot.pause()
        assert app.focused.id == "fname"
        assert app.query_one(DetailsView).display
        assert app.query_one(TreeView).region.width == 0
        await pilot.press("escape")                  # ascend: tree swaps back
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        assert app.focused is tree
        assert not app.query_one(DetailsView).display
        assert app.query_one(TreeView).region.width > 0


async def test_narrow_path_bar_summons_over_view(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "n")               # notes.txt
        await settle(pilot)
        await pilot.press("enter")                   # editing details
        await pilot.press("ctrl+slash")              # ^/ is tree-only now
        await pilot.pause()
        assert app.focused.id == "fname"             # no-op from details
        await pilot.press("escape")                  # ascend to the tree
        await pilot.press("ctrl+slash")              # now it summons
        await pilot.pause()
        bar = app.query_one(PathInput)
        assert app.focused is bar
        assert bar.display and app.query_one(TreeView).region.width > 0
        assert not app.query_one(DetailsView).display


async def test_wide_enter_focuses_any_kind(media_tree):
    # every kind is editable now: enter on a plain file descends into its
    # rename field, on wide as on narrow (the old read-only no-op is gone)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down", "n")               # notes.txt
        await settle(pilot)
        await pilot.press("enter")
        await pilot.pause()
        details = app.query_one(DetailsView)
        assert app.focused.id == "fname"             # descended into rename
        assert details.display
        assert app.query_one(TreeView).display        # wide: left column stays
        await pilot.press("escape")                  # ascend back to the tree
        await pilot.pause()
        assert app.focused is tree
        assert details.display and app.query_one(TreeView).display


async def test_artist_folder_does_not_bulk(media_tree):
    # artist/album/track layout: an artist-level folder has subfolders
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # anchor folder has subdirs
        details = app.query_one(DetailsView)
        assert details.paths is None
        assert details.kind == "folder"              # plain counts view
        assert app.query_one("#panel-folder").display


# -- cut/paste (^x cuts to the clipboard, ^v pastes, esc cancels) -----------------


async def _goto_notes(app, pilot):
    await settle(pilot)
    await pilot.press("down", "n")               # notes.txt
    await settle(pilot)
    assert app.query_one(DetailsView).path == app.start_dir / "notes.txt"


async def test_cut_paste_flow(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(160, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+x")              # cut
        await pilot.pause()
        assert app.lifted == [media_tree / "notes.txt"]
        assert "paste" in _strip_text(app)       # clipboard state strip
        await pilot.press("alt+up")              # Books (first sibling)
        await settle(pilot)
        await pilot.press("ctrl+v")              # paste into Books
        await pilot.pause(0.8)
        assert (media_tree / "Books" / "notes.txt").exists()
        assert not (media_tree / "notes.txt").exists()
        assert app.lifted is None
        assert "paste" not in _strip_text(app)   # strip restored


async def test_move_survives_pathbar_jump(media_tree):
    # Nick's long-distance flow: cut → ^/ → type destination → ⏎ → place
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+x")
        await pilot.pause()
        await pilot.press("ctrl+slash")
        bar = app.query_one(PathInput)
        bar.value = str(media_tree / "Pics")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert app.lifted is not None            # the jump kept the cut
        await pilot.press("ctrl+v")              # paste into Pics
        await pilot.pause(0.8)
        assert (media_tree / "Pics" / "notes.txt").exists()
        assert app.lifted is None


async def test_move_refuses_overwrite(media_tree):
    (media_tree / "Books" / "notes.txt").write_text("precious")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+x")
        await pilot.pause()
        await pilot.press("alt+up")              # Books
        await settle(pilot)
        await pilot.press("ctrl+v")
        await pilot.pause(0.8)
        assert (media_tree / "notes.txt").exists()               # unmoved
        assert (media_tree / "Books" / "notes.txt").read_text() == "precious"


async def test_move_into_own_subtree_refused(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down")
        await pilot.press("m", "o")              # Movies
        await settle(pilot)
        await pilot.press("ctrl+x")              # cut the folder
        await pilot.pause()
        await pilot.press("right")               # expand it
        await settle(pilot)
        await pilot.press("down")                # Alien (1979)
        await settle(pilot)
        await pilot.press("ctrl+v")              # into its own child: refused
        await pilot.pause(0.5)
        assert (media_tree / "Movies" / "Alien (1979)").exists()
        assert app.lifted is not None            # cut retained


async def test_move_same_folder_is_noop(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+x", "ctrl+v")    # cut, paste in place
        await pilot.pause(0.5)
        assert (media_tree / "notes.txt").exists()
        assert app.lifted is not None            # kept for a real target


async def test_cut_esc_cancels(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(160, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+x")
        await pilot.pause()
        assert app.lifted is not None
        await pilot.press("escape")
        await pilot.pause()
        assert app.lifted is None
        assert (media_tree / "notes.txt").exists()
        assert "paste" not in _strip_text(app)


async def test_move_bulk_selection(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")          # both songs
        await _bulk_settle(pilot)
        await pilot.press("ctrl+x")              # cut the selection
        await pilot.pause()
        assert app.lifted is not None and len(app.lifted) == 2
        await pilot.press("left")                # up to Music
        await settle(pilot)
        await pilot.press("alt+up")              # Books
        await settle(pilot)
        await pilot.press("ctrl+v")
        await pilot.pause(0.8)
        assert (media_tree / "Books" / "01 Song One.mp3").exists()
        assert (media_tree / "Books" / "02 Song Two.mp3").exists()


async def test_copy_paste_duplicates_file(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(160, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+y")              # copy
        await pilot.pause()
        assert app.lifted == [media_tree / "notes.txt"]
        assert app.lift_copy
        assert "paste" in _strip_text(app)       # same clipboard state
        await pilot.press("alt+up")              # Books
        await settle(pilot)
        await pilot.press("ctrl+v")              # paste a duplicate
        await pilot.pause(0.8)
        assert (media_tree / "Books" / "notes.txt").exists()
        assert (media_tree / "notes.txt").exists()   # source untouched
        assert app.lifted is None


async def test_copy_paste_duplicates_folder(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(160, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down")
        await pilot.press("m", "u")              # Music
        await _bulk_settle(pilot)
        await pilot.press("ctrl+y")              # copy the folder
        await pilot.pause()
        await pilot.press("alt+up")              # Books
        await settle(pilot)
        await pilot.press("ctrl+v")
        await pilot.pause(0.8)
        assert (media_tree / "Books" / "Music" / "01 Song One.mp3").exists()
        assert (media_tree / "Music" / "01 Song One.mp3").exists()


async def test_clipboard_locks_out_edit_and_second_cut(media_tree):
    # the clipboard holds ONE selection; carrying forbids ⏎ edit (todo-4)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(160, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+x")
        await pilot.pause()
        first = app.lifted
        await pilot.press("down")
        await settle(pilot)
        await pilot.press("ctrl+x")              # second cut: refused
        await pilot.pause()
        assert app.lifted == first
        await pilot.press("enter")               # edit while carrying: refused
        await pilot.pause()
        assert app.focused is app.query_one(LibraryTree)
        text = _strip_text(app)
        assert "edit" not in text and "cut" not in text


# -- strip multi-artist (folder action, folderize's pattern) ----------------------


def _make_tangled(media_tree):
    """An artist/album layout where deemix-style slash tags crept in."""
    from tests.mediafactory import make_mp3
    album = media_tree / "Tangle" / "Jax Jones" / "Split EP"
    album.mkdir(parents=True)
    make_mp3(album / "01 t.mp3",
             tags={"title": "t", "artist": "Jax Jones/Rebecca Black",
                   "albumartist": "Jax Jones", "album": "Split EP"})
    make_mp3(album / "02 u.mp3",
             tags={"title": "u", "artist": "Jax Jones",
                   "albumartist": "Jax Jones", "album": "Split EP"})
    return album


async def test_multiartist_button_only_where_tangled(media_tree):
    _make_tangled(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Tangle")
        assert "strip_multi_artist" in _bar_names(app)
        await _goto_folder(app, pilot, "Music")  # untangled: no button
        assert "strip_multi_artist" not in _bar_names(app)


async def test_multiartist_preview_apply_rewrites_tags(media_tree):
    album = _make_tangled(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Tangle")
        await pilot.press("enter", "ctrl+x")     # strip multi-artist
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details.plan_preview_open()
        assert set(_bar_names(app)) == {"plan_apply", "plan_cancel"}
        preview = str(app.query_one("#plan-tree").render())
        assert "Split EP" in preview and "Jax Jones" in preview
        await pilot.press("ctrl+a")              # apply
        await pilot.pause(0.8)
        d = adapters.read_details(album / "01 t.mp3")
        assert d.fields["artist"] == "Jax Jones"
        assert d.fields["albumartist"] == "Jax Jones"
        assert not details.plan_preview_open()
        await pilot.pause(0.6)                   # re-probe: nothing left
        assert "strip_multi_artist" not in _bar_names(app)


async def test_multiartist_escape_cancels(media_tree):
    album = _make_tangled(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Tangle")
        await pilot.press("enter", "ctrl+x")
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details.plan_preview_open()
        await pilot.press("escape")              # tree keeps focus: esc = cancel
        await settle(pilot)
        assert not details.plan_preview_open()
        d = adapters.read_details(album / "01 t.mp3")
        assert d.fields["artist"] == "Jax Jones/Rebecca Black"  # untouched


# -- subtitles (get / clean / shift on video files) -----------------------------


SRT_DIRTY = (
    "1\n00:00:01,000 --> 00:00:02,000\nSubs by CoolGuy - www.example.com\n\n"
    '2\n00:00:05,000 --> 00:00:06,000\n<font color="#fff">hello</font>\n\n'
    "3\n00:00:08,000 --> 00:00:09,000\nplain line\n"
)


async def _goto_alien(app, pilot):
    """Cursor onto Movies/Alien (1979)/Alien.1979.mkv, details settled."""
    await settle(pilot)
    await pilot.press("down")
    await pilot.press("m", "o", "right")             # Movies, expanded
    await settle(pilot)
    await pilot.press("down", "right")               # Alien (1979), expanded
    await settle(pilot)
    await pilot.press("down")                        # Alien.1979.mkv
    await settle(pilot)
    assert app.query_one(DetailsView).kind == "video"


async def test_video_offers_subtitle_actions(media_tree):
    (media_tree / "Movies" / "Alien (1979)" / "zz nosub.mkv").write_bytes(b"x")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        # video is renamable now, so "save" leads the bar (the rename
        # write); "open" is always second (2026-08-22)
        assert _bar_names(app) == ["save", "open", "get_subs", "clean_subs",
                                   "shift_subs", "download_posters", "gif",
                                   "folderize_video"]
        await pilot.press("z")                       # the srt-less video
        await settle(pilot)
        names = _bar_names(app)
        assert "get_subs" in names and "open" in names
        assert "clean_subs" not in names             # nothing to clean/shift
        assert "shift_subs" not in names


async def test_clean_subs_strips_credits_and_markup(media_tree):
    srt_path = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.srt"
    srt_path.write_text(SRT_DIRTY)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+l")         # c^lean subs
        await pilot.pause(0.5)
        text = srt_path.read_text()
        assert "www.example.com" not in text         # credit cue dropped
        assert "<font" not in text                   # markup stripped
        assert "hello" in text and "plain line" in text


async def test_shift_div_nudge_and_save(media_tree):
    srt_path = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.srt"
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")         # open the shift div
        await pilot.pause(0.5)                       # load worker
        details = app.query_one(DetailsView)
        assert details._shift_open
        assert app.query_one("#shift-div").display
        assert app.focused.id == "shift-control"
        assert "save" in _bar_names(app)             # ^s joins the bar
        await pilot.press("right", "right", "right")
        assert details._shift_target_ms == 300
        assert details._shift_pending                # ✓ shown
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        assert "00:00:01,300" in srt_path.read_text()
        assert not details._shift_pending            # applied == target
        assert details._shift_open                   # ^s keeps the div open
        # nudging back recomputes from the ORIGINAL parse, not the file
        await pilot.press("left", "left", "left")
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        assert "00:00:01,000" in srt_path.read_text()


async def test_shift_arrow_steps(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")
        await pilot.pause(0.5)
        details = app.query_one(DetailsView)
        await pilot.press("shift+right")             # ±1s
        assert details._shift_target_ms == 1000
        await pilot.press("pageup")                  # ±10s
        assert details._shift_target_ms == 11000
        await pilot.press("pagedown", "shift+left", "left")
        assert details._shift_target_ms == -100      # display clamps on write


async def test_shift_esc_pending_confirms(media_tree):
    srt_path = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.srt"
    original = srt_path.read_text()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")
        await pilot.pause(0.5)
        await pilot.press("right", "escape")         # pending: modal
        assert isinstance(app.screen, ConfirmSave)
        await pilot.press("d")                       # discard
        await pilot.pause()
        details = app.query_one(DetailsView)
        assert not details._shift_open               # div closed
        assert srt_path.read_text() == original      # nothing written
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_esc_pending_save_writes(media_tree):
    srt_path = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.srt"
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")
        await pilot.pause(0.5)
        await pilot.press("right", "escape", "s")    # modal → save
        await pilot.pause(0.6)
        assert "00:00:01,100" in srt_path.read_text()
        details = app.query_one(DetailsView)
        assert not details._shift_open               # released: closed out
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_toggle_pinned_while_pending(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")
        await pilot.pause(0.5)
        await pilot.press("right", "ctrl+t")         # toggle off refused
        details = app.query_one(DetailsView)
        assert details._shift_open
        assert app.focused.id == "shift-control"
        await pilot.press("left", "ctrl+t")          # clean again: closes
        await pilot.pause()
        assert not details._shift_open
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_esc_clean_closes(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")
        await pilot.pause(0.5)
        await pilot.press("escape")
        await pilot.pause()
        details = app.query_one(DetailsView)
        assert not details._shift_open
        assert not app.query_one("#shift-div").display
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_down_reaches_bar_buttons(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")
        await pilot.pause(0.5)
        await pilot.press("down")                    # control → first button
        assert app.focused.id == "save-btn"
        await pilot.press("up")                      # and back
        assert app.focused.id == "shift-control"


async def test_focus_lockdown_shift_blocks_other_chords(media_tree, monkeypatch):
    # todo-4 "Focus": a focused sub-form owns the user — while the shift
    # control has focus, the pane's OTHER commands must not fire
    calls = []
    monkeypatch.setattr("mediasmith.details.launch",
                        lambda path: calls.append(path))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+t")         # open + focus the shift div
        await pilot.pause(0.5)
        assert app.focused.id == "shift-control"
        await pilot.press("ctrl+o")                  # open: locked out
        await pilot.pause(0.2)
        assert calls == []
        await pilot.press("right", "ctrl+s")         # its own save still works
        await pilot.pause(0.5)
        details = app.query_one(DetailsView)
        assert not details._shift_pending            # the shift was written


async def test_focus_lockdown_confines_arrow_walk(media_tree):
    # inside a wizard, ↑↓ must not escape to the pane's fields/buttons
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo_lockdown(app, pilot)
        await pilot.press("enter", "ctrl+e")         # resize wizard, w focused
        await pilot.pause()
        assert app.focused.id == "resize-w"
        await pilot.press("up")                      # top of the sub-form: stay
        assert app.focused.id == "resize-w"
        for _ in range(6):
            await pilot.press("down")                # h → link → save, clamp
        assert app.focused.id == "resize-apply-btn"


async def _goto_photo_lockdown(app, pilot):
    await settle(pilot)
    await pilot.press("down")
    await pilot.press(*"pic", "right")
    await settle(pilot)
    await pilot.press("down")
    await settle(pilot)
    assert app.query_one(DetailsView).kind == "image"


async def test_focus_lockdown_art_path_blocks_fetch(media_tree, monkeypatch):
    from mediasmith import artfetch
    monkeypatch.setattr(artfetch, "search_covers",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            AssertionError("fetch ran under lockdown")))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "ctrl+p")         # Import Album Art input
        assert app.focused.id == "art-path"
        await pilot.press("ctrl+f")                  # fetch: locked out
        await pilot.pause(0.3)
        assert app.focused.id == "art-path"          # still in the sub-form


async def test_get_subs_installs_and_tree_follows(media_tree, monkeypatch):
    from mediasmith import subsync
    movie = media_tree / "Movies" / "Alien (1979)"
    (movie / "Alien.1979.srt").unlink()              # start subless

    def fake_run(targets, force=False, safe=False):
        target = Path(targets[0])
        dest = target.with_suffix(".srt")
        dest.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n")
        result = subsync.FileResult(target, Path(target.name), "ok",
                                    "synced (+56ms)", dest.name)
        yield subsync.FileDone(result)
        yield subsync.RunDone(subsync.Counts(installed=1),
                              ((target.parent, (result,)),))

    monkeypatch.setattr(subsync, "check_requirements", lambda: [])
    monkeypatch.setattr(subsync, "run", fake_run)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        assert "clean_subs" not in _bar_names(app)   # no srt yet
        await pilot.press("enter", "ctrl+u")         # fetch s^ubtitles
        await pilot.pause(0.8)
        dest = movie / "Alien.1979.srt"
        assert dest.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(dest) is not None      # tree picked it up
        assert "clean_subs" in _bar_names(app)       # details refreshed


async def test_get_subs_honors_offline(media_tree, monkeypatch):
    from mediasmith import subsync

    def must_not_run(*a, **kw):                      # pragma: no cover
        raise AssertionError("engine ran while offline")

    monkeypatch.setattr(subsync, "run", must_not_run)
    monkeypatch.setenv("MEDIASMITH_OFFLINE", "1")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+u")         # fetch s^ubtitles
        await pilot.pause(0.5)
        assert app.is_running


# -- details.launch: the one shell-out with no library behind it ---------------


def test_launch_uses_the_platform_opener(tmp_path, monkeypatch):
    """macOS gets `open`, everything else `xdg-open`. Before 2026-08-22 this
    hardcoded `open`, which silently did the wrong thing off macOS."""
    target = tmp_path / "clip.mkv"
    target.write_bytes(b"x")
    seen = []
    monkeypatch.setattr(details_mod.subprocess, "Popen",
                        lambda argv, **kw: seen.append(argv))

    monkeypatch.setattr(details_mod.sys, "platform", "darwin")
    details_mod.launch(target)
    assert seen[-1] == ["open", str(target)]

    monkeypatch.setattr(details_mod.sys, "platform", "linux")
    details_mod.launch(target)
    assert seen[-1] == ["xdg-open", str(target)]


def test_launch_uses_startfile_on_windows(tmp_path, monkeypatch):
    """os.startfile exists only on Windows, so it is reached through the
    platform branch and never through Popen."""
    target = tmp_path / "clip.mkv"
    target.write_bytes(b"x")
    started = []

    def no_popen(*args, **kwargs):
        raise AssertionError("Windows must not reach Popen")

    monkeypatch.setattr(details_mod.sys, "platform", "win32")
    monkeypatch.setattr(details_mod.os, "startfile", started.append,
                        raising=False)
    monkeypatch.setattr(details_mod.subprocess, "Popen", no_popen)
    details_mod.launch(target)
    assert started == [target]


async def test_open_launches_default_app(media_tree, monkeypatch):
    calls = []
    monkeypatch.setattr("mediasmith.details.launch",
                        lambda path: calls.append(path))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+o")
        await pilot.pause()
        video = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.mkv"
        assert calls == [video]


async def test_open_offered_on_every_file_kind(media_tree, monkeypatch):
    # "open" is the universal second button (Nick, 2026-08-22)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                      # the tree's own first select
        details = app.query_one(DetailsView)
        for path in (media_tree / "Music" / "01 Song One.mp3",
                     media_tree / "Books" / "Dune.epub",
                     media_tree / "Pics" / "photo.png",
                     media_tree / "notes.txt"):
            details.preview(path, immediate=True)
            await settle(pilot)
            names = _bar_names(app)
            assert names[:2] == ["save", "open"], f"{path.name}: {names}"
        details.preview(media_tree / "Music", immediate=True)   # a folder
        await settle(pilot)
        assert "open" not in _bar_names(app)     # its ^o is the sort button


async def test_open_launches_the_selected_file(media_tree, monkeypatch):
    calls = []
    monkeypatch.setattr("mediasmith.details.launch",
                        lambda path: calls.append(path))
    song = media_tree / "Music" / "01 Song One.mp3"
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down")                    # into the anchor
        await pilot.press("m", "u", "right")         # Music, expanded
        await settle(pilot)
        await pilot.press("down")                    # 01 Song One.mp3
        await settle(pilot)
        assert app.query_one(DetailsView).path == song
        await pilot.press("enter", "ctrl+o")
        await pilot.pause()
        assert calls == [song]


# -- video: folderize (wrap the video into a folder named after it) -------------


async def test_video_folderize_wraps_the_video_and_its_subtitle(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        assert "folderize_video" in _bar_names(app)
        await pilot.press("enter", "ctrl+f")         # ^folderize
        await pilot.pause(0.8)
        wrapper = media_tree / "Movies" / "Alien (1979)" / "Alien.1979"
        video = wrapper / "Alien.1979.mkv"
        assert video.exists()
        assert (wrapper / "Alien.1979.srt").exists()     # the sidecar came
        assert (wrapper / "poster.jpg").exists()         # sole video: art too
        details = app.query_one(DetailsView)
        assert details.path == video                 # same video still shown
        assert details.kind == "video"
        assert "folderize_video" not in _bar_names(app)   # now in place
        tree = app.query_one(LibraryTree)
        assert tree._node_for(video) is not None      # revealed in the tree


async def test_folderize_also_works_from_the_tree(media_tree):
    """Nick, 2026-08-22: folderize is reachable from BOTH views. ^f in
    the tree fires whichever folderize the selection is showing."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)                # tree keeps focus
        assert isinstance(app.focused, LibraryTree)
        await pilot.press("ctrl+f")                  # ^folderize, no ⏎ first
        await pilot.pause(0.8)
        wrapper = media_tree / "Movies" / "Alien (1979)" / "Alien.1979"
        assert (wrapper / "Alien.1979.mkv").exists()


async def test_the_tree_strip_prints_folderize_where_it_works(media_tree):
    """The strip is the contract: ^f shows where it fires."""
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)                # a video: offered
        await pilot.pause(0.6)
        assert "^f" in [e.key for e in app.query_one(CommandStrip)._entries]


async def test_the_tree_strip_omits_folderize_where_it_does_not(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")      # nothing to folderize
        assert "^f" not in [e.key for e in
                            app.query_one(CommandStrip)._entries]


async def test_tree_folderize_is_inert_without_one_to_run(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        before = sorted(p.name for p in media_tree.iterdir())
        await pilot.press("ctrl+f")
        await pilot.pause(0.5)
        assert app.is_running
        assert sorted(p.name for p in media_tree.iterdir()) == before


async def test_video_folderize_hidden_when_already_wrapped(media_tree):
    from mediasmith import fs
    movies = media_tree / "Movies" / "Alien (1979)"
    (movies / "Alien (1979).mkv").write_bytes(b"x")   # named for its folder
    fs.clear_cache()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        app.query_one(DetailsView).preview(movies / "Alien (1979).mkv",
                                           immediate=True)
        await settle(pilot)
        assert "folderize_video" not in _bar_names(app)


# -- folderize onto a case-only clash (Nick, 2026-08-25) ------------------------


def _case_blind(path):
    """Whether this filesystem folds case — the whole point of the modal."""
    probe = path / "CaseProbe"
    probe.mkdir()
    folded = (path / "caseprobe").exists()
    probe.rmdir()
    return folded


async def _goto_alien_past_the_clash(app, pilot):
    """_goto_alien, but the clashing folder sorts above the video: walk
    down to the .mkv row by name instead of counting rows."""
    await settle(pilot)
    await pilot.press("down")
    await pilot.press("m", "o", "right")             # Movies, expanded
    await settle(pilot)
    await pilot.press("down", "right")               # Alien (1979), expanded
    await settle(pilot)
    tree = app.query_one(LibraryTree)
    for _ in range(8):
        await pilot.press("down")
        if "Alien.1979.mkv" in str(tree.cursor_node.label):
            break
    await settle(pilot)
    assert app.query_one(DetailsView).kind == "video"


async def test_case_clash_asks_before_renaming(media_tree, monkeypatch):
    """A folder spelled differently already sits where folderize wants to
    write, and this volume can't hold both: ask, don't guess."""
    from mediasmith.details import ConfirmCaseRename
    movie = media_tree / "Movies" / "Alien (1979)"
    if not _case_blind(movie):
        pytest.skip("case-sensitive filesystem: no collision to resolve")
    (movie / "alien.1979").mkdir()               # the other spelling
    (movie / "alien.1979" / "keep.txt").write_text("mine")
    fs.clear_cache()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien_past_the_clash(app, pilot)
        await pilot.press("ctrl+f")              # ^folderize, from the tree
        await pilot.pause(0.6)
        assert isinstance(app.screen, ConfirmCaseRename)
        await pilot.press("k")                   # rename, keep contents
        await pilot.pause(1.0)
        wrapper = movie / "Alien.1979"
        assert wrapper.name in os.listdir(movie)         # Nick's casing won
        assert (wrapper / "Alien.1979.mkv").is_file()    # the video landed
        assert (wrapper / "keep.txt").is_file()          # contents preserved


async def test_case_clash_can_trash_the_contents(media_tree, monkeypatch):
    from mediasmith.details import ConfirmCaseRename
    movie = media_tree / "Movies" / "Alien (1979)"
    if not _case_blind(movie):
        pytest.skip("case-sensitive filesystem: no collision to resolve")
    trashed = []
    monkeypatch.setattr(adapters, "trash",
                        lambda p: (trashed.append(Path(p)),
                                   Path(p).unlink())[0])
    monkeypatch.delenv("MEDIASMITH_OFFLINE", raising=False)
    (movie / "alien.1979").mkdir()
    (movie / "alien.1979" / "old.txt").write_text("bye")
    fs.clear_cache()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien_past_the_clash(app, pilot)
        await pilot.press("ctrl+f")
        await pilot.pause(0.6)
        assert isinstance(app.screen, ConfirmCaseRename)
        await pilot.press("d")                   # rename, delete contents
        await pilot.pause(1.0)
        wrapper = movie / "Alien.1979"
        assert [p.name for p in trashed] == ["old.txt"]
        assert (wrapper / "Alien.1979.mkv").is_file()
        assert not (wrapper / "old.txt").exists()


async def test_case_clash_cancel_writes_nothing(media_tree):
    from mediasmith.details import ConfirmCaseRename
    movie = media_tree / "Movies" / "Alien (1979)"
    if not _case_blind(movie):
        pytest.skip("case-sensitive filesystem: no collision to resolve")
    (movie / "alien.1979").mkdir()
    fs.clear_cache()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien_past_the_clash(app, pilot)
        await pilot.press("ctrl+f")
        await pilot.pause(0.6)
        assert isinstance(app.screen, ConfirmCaseRename)
        await pilot.press("escape")
        await pilot.pause(0.6)
        assert (movie / "Alien.1979.mkv").is_file()      # never moved
        assert "Alien.1979" not in os.listdir(movie)     # never respelled


# -- video: the poster (album art's twin) ---------------------------------------


async def test_video_panel_shows_the_poster_with_dimensions(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        dims = app.query_one("#cover-video-dims")
        assert dims.display is True
        assert "8 × 8" in str(dims.render())          # the fixture's poster.jpg


async def test_video_poster_found_inside_the_poster_folder(media_tree):
    from mediasmith import fs
    from textual.widgets import Static
    from tests.mediafactory import make_png
    movie = media_tree / "Movies" / "Alien (1979)"
    (movie / "poster.jpg").unlink()                   # only the folder is left
    (movie / "Alien (1979)").mkdir()
    make_png(movie / "Alien (1979)" / "a.png", size=(12, 20))
    fs.clear_cache()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # the poster folder now
        details = app.query_one(DetailsView)         # sorts above the video
        details.preview(movie / "Alien.1979.mkv", immediate=True)
        await settle(pilot)
        row = app.query_one("#video-posters", Static)
        assert str(row.render()) == "Alien (1979)/a.png"
        assert "12 × 20" in str(app.query_one("#cover-video-dims").render())


# -- video: container field + download posters ----------------------------------


async def test_video_panel_shows_container(media_tree):
    from textual.widgets import Static
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        row = app.query_one("#video-container", Static)
        assert str(row.render()) == "mkv"


async def test_video_panel_shows_codec(media_tree, monkeypatch):
    """Nick, todo-5: the codec rides beside the container — a header read,
    so the same worker as the embedded title fills it in late."""
    from textual.widgets import Static
    monkeypatch.setattr("mediasmith.adapters.probe_video_codec",
                        lambda path: "H.265")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.pause(0.3)                       # the probe worker
        assert str(app.query_one("#video-codec", Static).render()) == "H.265"


async def test_video_codec_unreadable_prints_a_dash(media_tree):
    """The fixture .mkv is 16 bytes of junk — an unparsable header is a
    dash, never a stuck "…" and never a traceback."""
    from textual.widgets import Static
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.pause(0.3)
        assert str(app.query_one("#video-codec", Static).render()) == "—"


async def test_download_posters_lands_files_and_tree_follows(
        media_tree, monkeypatch):
    from mediasmith import posters
    video = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.mkv"
    folder = video.parent / "Alien (1979)"

    def fake_run(target, **kwargs):
        assert target == video
        folder.mkdir()
        (folder / "a.png").write_bytes(b"poster")
        yield posters.Identified("Alien (1979)")
        yield posters.Done(folder=folder, saved=1, duplicates=2, existing=0)

    monkeypatch.setattr("mediasmith.posters.run", fake_run)
    monkeypatch.setattr("mediasmith.adapters.probe_video_title",
                        lambda path: None)
    monkeypatch.delenv("MEDIASMITH_OFFLINE", raising=False)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+p")         # download ^posters
        await pilot.pause(0.5)
        tree = app.query_one(LibraryTree)
        assert tree._node_for(folder) is not None    # re-listed in place


async def test_a_running_job_keeps_one_toast_through_its_messages(
        media_tree, monkeypatch):
    """Nick, 2026-08-22: each message used to raise its own toast, and
    each faded before the next arrived — so a five-second fetch looked
    like a dead keypress. One job, one toast, held until it finishes."""
    from textual.widgets._toast import Toast

    from mediasmith import posters
    video = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.mkv"
    folder = video.parent / "Alien (1979)"

    def fake_run(target, **kwargs):
        yield posters.Identified("Alien (1979)")
        yield posters.PhaseStarted("fingerprinting 12 posters…")
        folder.mkdir()
        yield posters.Done(folder=folder, saved=3, duplicates=2, existing=0)

    monkeypatch.setattr("mediasmith.posters.run", fake_run)
    monkeypatch.setattr("mediasmith.adapters.probe_video_title",
                        lambda path: None)
    monkeypatch.delenv("MEDIASMITH_OFFLINE", raising=False)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40), notifications=True) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+p")         # download ^posters
        await pilot.pause(0.5)
        shown = [t._notification.message for t in app.query(Toast)]
        assert len(shown) == 1                       # not four
        assert "3 posters" in shown[0]               # the last word wins


async def test_download_posters_honors_offline(media_tree, monkeypatch):
    calls = []
    monkeypatch.setattr("mediasmith.posters.run",
                        lambda *a, **kw: calls.append(a))
    monkeypatch.setenv("MEDIASMITH_OFFLINE", "1")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+p")
        await pilot.pause(0.3)
        assert calls == []


# -- images: rename / convert / resize / rotate ------------------------------


async def _goto_photo(app, pilot):
    """Cursor onto Pics/photo.png with the details settled."""
    await settle(pilot)
    await pilot.press("down")
    await pilot.press(*"pic", "right")           # Pics, expanded
    await settle(pilot)
    await pilot.press("down")                    # photo.png
    await settle(pilot)
    assert app.query_one(DetailsView).kind == "image"


async def test_image_is_renameable(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("enter")                   # fname focused
        assert app.focused.id == "fname"
        assert app.focused.value == "photo.png"
        app.focused.value = "vacation.png"
        await pilot.press("ctrl+s")
        await pilot.pause(0.6)
        old = media_tree / "Pics" / "photo.png"
        new = media_tree / "Pics" / "vacation.png"
        assert new.exists() and not old.exists()
        tree = app.query_one(LibraryTree)
        assert str(tree.cursor_node.label) == "vacation.png"


async def test_image_offers_converts_minus_own_format(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        assert _bar_names(app) == ["save", "open", "rotate", "resize",
                                   "trace", "convert_jpg", "convert_tiff",
                                   "convert_webp"]         # png: no png


async def test_image_convert_creates_sibling(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("enter", "ctrl+g")         # convert to jp^g
        await pilot.pause(0.5)
        target = media_tree / "Pics" / "photo.jpg"
        assert target.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(target) is not None    # tree picked it up


async def test_image_convert_never_overwrites(media_tree):
    existing = media_tree / "Pics" / "photo.jpg"
    existing.write_bytes(b"precious")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("enter", "ctrl+g")
        await pilot.pause(0.5)
        assert existing.read_bytes() == b"precious"


async def test_image_convert_overwrites_on_second_press(media_tree):
    from PIL import Image
    existing = media_tree / "Pics" / "photo.jpg"
    existing.write_bytes(b"placeholder")             # exists, blocks convert
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down")
        await pilot.press(*"pic", "right")           # Pics expanded
        await settle(pilot)
        await pilot.press("down", "down")            # past photo.jpg → photo.png
        await settle(pilot)
        assert app.query_one(DetailsView).kind == "image"
        await pilot.press("enter", "ctrl+g")         # convert to jpg — refuses
        await pilot.pause(0.4)
        assert existing.read_bytes() == b"placeholder"
        await pilot.press("ctrl+g")                  # again: overwrites
        await pilot.pause(0.6)
        assert existing.read_bytes() != b"placeholder"
        assert Image.open(existing).format == "JPEG"   # a real conversion


async def test_resize_div_linked_fields(media_tree):
    from textual.widgets import Checkbox
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("enter", "ctrl+e")         # r^esize
        await pilot.pause()
        assert app.focused.id == "resize-w"
        assert app.focused.value == "8"              # prefilled: true dims
        height = app.query_one("#resize-h")
        assert height.value == "8"
        app.focused.value = "4"                      # linked: height follows
        await pilot.pause()
        assert height.value == "4"
        app.query_one("#resize-link", Checkbox).value = False
        app.focused.value = "2"                      # unlinked: it doesn't
        await pilot.pause()
        assert height.value == "4"


async def test_resize_apply_creates_file(media_tree):
    from PIL import Image
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("enter", "ctrl+e")
        await pilot.pause()
        from textual.widgets import Checkbox
        app.query_one("#resize-link", Checkbox).value = False
        app.query_one("#resize-w").value = "4"
        app.query_one("#resize-h").value = "2"
        await pilot.press("ctrl+s")                  # ^save (the wizard's)
        await pilot.pause(0.5)
        target = media_tree / "Pics" / "photo (4x2).png"
        assert target.exists()
        assert Image.open(target).size == (4, 2)
        details = app.query_one(DetailsView)
        assert details._resize_open                  # div stays for more


async def test_resize_div_toggles_closed(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("enter", "ctrl+e")
        await pilot.pause()
        assert app.query_one("#resize-div").display is True
        await pilot.press("escape")                  # release to the tree
        assert app.focused is app.query_one(LibraryTree)
        assert app.query_one("#resize-div").display is True   # still open
        await pilot.press("enter", "ctrl+e")         # react-style toggle
        await pilot.pause()
        assert app.query_one("#resize-div").display is False


async def test_rotate_rotates_in_place(media_tree):
    from PIL import Image
    from tests.mediafactory import make_png
    make_png(media_tree / "Pics" / "wide.png", size=(8, 4))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("down")                    # wide.png (p < w)
        await settle(pilot)
        await pilot.press("enter", "ctrl+r")         # ^rotate
        await pilot.pause(0.5)
        assert Image.open(media_tree / "Pics" / "wide.png").size == (4, 8)
        assert sorted(p.name for p in (media_tree / "Pics").iterdir()) \
            == ["photo.png", "wide.png"]             # in place: no siblings


# -- standardize formatting -----------------------------------------------------


async def test_standardize_creates_clean_sibling(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        assert "standardize" in _bar_names(app)
        await pilot.press("enter", "ctrl+n")         # clea^n
        await pilot.pause(0.6)
        target = media_tree / "Books" / "Dune (clean).epub"
        assert target.exists()
        assert adapters.read_details(target).fields["title"] == "Dune"
        tree = app.query_one(LibraryTree)
        assert tree._node_for(target) is not None    # tree picked it up


async def test_standardize_folder_batch(media_tree):
    from tests.mediafactory import make_epub
    make_epub(media_tree / "Books" / "Second.epub", title="Second")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Books")
        assert "standardize" in _bar_names(app)      # probe filled in
        await pilot.press("enter", "ctrl+n")
        await pilot.pause(1.0)
        assert (media_tree / "Books" / "Dune (clean).epub").exists()
        assert (media_tree / "Books" / "Second (clean).epub").exists()


async def test_standardize_probe_hides_when_done(media_tree):
    from mediasmith import standardize
    dune = media_tree / "Books" / "Dune.epub"
    standardize.standardize(dune, standardize.clean_target(dune))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Books")      # everything clean
        assert "standardize" not in _bar_names(app)


async def test_standardize_never_overwrites(media_tree):
    existing = media_tree / "Books" / "Dune (clean).epub"
    existing.write_bytes(b"precious")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("enter", "ctrl+n")
        await pilot.pause(0.6)
        assert existing.read_bytes() == b"precious"


# -- sort: wrap book files into "Author Sort - Title/" ---------------------------


async def test_sort_button_is_probe_gated(media_tree):
    from tests.mediafactory import make_epub
    wrapper = media_tree / "Books" / "Herbert, Frank - Solo"
    wrapper.mkdir()
    make_epub(wrapper / "Solo.epub", title="Solo", author="Frank Herbert")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Books")      # loose Dune.epub
        assert "sort" in _bar_names(app)
        await pilot.press("down")                    # the wrapper folder
        await settle(pilot)
        await pilot.pause(0.3)
        assert "sort" not in _bar_names(app)         # already in place


async def test_sort_preview_and_apply(media_tree):
    (media_tree / "Books" / "Dune.mobi").write_bytes(b"mobi")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Books")
        await pilot.press("enter", "ctrl+o")         # s^ort
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details.plan_preview_open()
        assert set(_bar_names(app)) == {"plan_apply", "plan_cancel"}
        await pilot.press("ctrl+a")                  # apply
        await pilot.pause(0.8)
        wrapper = media_tree / "Books" / "Herbert, Frank - Dune"
        assert (wrapper / "Herbert, Frank - Dune.epub").exists()  # renamed
        assert (wrapper / "Herbert, Frank - Dune.mobi").exists()  # every format
        assert not (media_tree / "Books" / "Dune.epub").exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(wrapper) is not None


async def test_sort_escape_cancels(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Books")
        await pilot.press("enter", "ctrl+o")
        await pilot.pause(0.6)
        details = app.query_one(DetailsView)
        assert details.plan_preview_open()
        await pilot.press("escape")
        await settle(pilot)
        assert not details.plan_preview_open()
        assert (media_tree / "Books" / "Dune.epub").exists()   # untouched


async def test_sort_single_ebook_wraps_renames_and_reselects(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)                 # Books/Dune.epub, editable
        assert "sort_book" in _bar_names(app)        # probe filled in
        await pilot.press("enter", "ctrl+f")         # ^folderize — no preview
        await pilot.pause(0.8)
        wrapper = media_tree / "Books" / "Herbert, Frank - Dune"
        book = wrapper / "Herbert, Frank - Dune.epub"
        assert book.exists()                         # renamed + wrapped
        assert not (media_tree / "Books" / "Dune.epub").exists()
        details = app.query_one(DetailsView)
        assert details.path == book                  # same book still shown
        assert details.kind == "book"
        assert app.focused is app.query_one("#fname")  # editable, filename focused
        assert app.query_one("#fname").value == book.name
        assert "sort" not in _bar_names(app)         # now already in place
        tree = app.query_one(LibraryTree)
        assert tree._node_for(book) is not None      # revealed in the tree


async def test_sort_single_ebook_refuses_overwrite(media_tree):
    wrapper = media_tree / "Books" / "Herbert, Frank - Dune"
    wrapper.mkdir()
    (wrapper / "Herbert, Frank - Dune.epub").write_bytes(b"precious")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "right")           # Books, expanded
        await settle(pilot)
        await pilot.press("down", "down")            # past the wrapper → Dune.epub
        await settle(pilot)
        assert app.query_one(DetailsView).kind == "book"
        await pilot.press("ctrl+o")
        await pilot.pause(0.8)
        assert (wrapper / "Herbert, Frank - Dune.epub").read_bytes() \
            == b"precious"                           # not clobbered
        assert (media_tree / "Books" / "Dune.epub").exists()   # source untouched


# -- folders: rename / new / trash --------------------------------------------


async def test_folder_is_renameable(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("enter")                   # fname focused
        assert app.focused.id == "fname"
        assert app.focused.value == "Empty"
        app.focused.value = "Emptier"
        await pilot.press("ctrl+s")
        await pilot.pause(0.6)
        assert (media_tree / "Emptier").is_dir()
        assert not (media_tree / "Empty").exists()
        tree = app.query_one(LibraryTree)
        assert str(tree.cursor_node.label) == "Emptier"


async def test_folder_rename_keeps_expansion(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Movies")
        await pilot.press("right")                   # expand Movies
        await settle(pilot)
        await pilot.press("down", "right")           # expand Alien (1979)
        await settle(pilot)
        await pilot.press("up")                      # back onto Movies
        await settle(pilot)
        await pilot.press("enter")
        assert app.focused.value == "Movies"
        app.focused.value = "Films"
        await pilot.press("ctrl+s")
        await pilot.pause(0.8)
        assert (media_tree / "Films" / "Alien (1979)").is_dir()
        tree = app.query_one(LibraryTree)
        child = tree._node_for(media_tree / "Films" / "Alien (1979)")
        assert child is not None and child.is_expanded   # subtree survived
        assert str(tree.cursor_node.label) == "Films"


async def test_rename_context_row_reanchors(media_tree):
    # the tree's own root line is a folder like any other: renaming it
    # must re-anchor instead of leaving every loaded path dangling
    # (the fuzz walk hit exactly this on the scratch dir)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("up")                      # the context row
        await settle(pilot)
        details = app.query_one(DetailsView)
        assert details.path == media_tree.parent
        await pilot.press("enter")                   # descend into rename
        assert app.focused.id == "fname"
        app.focused.value = media_tree.parent.name + " renamed"
        await pilot.press("ctrl+s")
        await pilot.pause(1.0)
        new_parent = media_tree.parent.with_name(
            media_tree.parent.name + " renamed")
        assert new_parent.is_dir()
        tree = app.query_one(LibraryTree)
        assert Path(tree.path) == new_parent.parent  # re-anchored cleanly
        assert tree._node_for(new_parent) is not None


async def test_folder_offers_save_only(media_tree):
    # new-directory/delete are TREE commands now (^n / ^DEL on the strip);
    # their buttons are gone from Details view (todo-4 Button Refactor)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        names = _bar_names(app)
        assert names == ["save"]                     # a folder has no "open"
        await _goto_notes(app, pilot)                # kind: other — a FILE,
        names = _bar_names(app)                      # so it opens
        assert names == ["save", "open"]


async def test_new_directory_creates_and_descends(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("ctrl+n")                   # ^n new directory
        await pilot.pause(0.8)
        target = media_tree / "Empty" / "untitled folder"
        assert target.is_dir()
        assert app.focused.id == "fname"             # straight into rename
        assert app.focused.value == "untitled folder"
        tree = app.query_one(LibraryTree)
        assert str(tree.cursor_node.label) == "untitled folder"


async def test_new_directory_on_file_targets_its_parent(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)                # a file: its folder
        await pilot.press("ctrl+n")
        await pilot.pause(0.8)
        assert (media_tree / "untitled folder").is_dir()


async def test_new_directory_names_dont_collide(media_tree):
    (media_tree / "Empty" / "untitled folder").mkdir()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("ctrl+n")
        await pilot.pause(0.8)
        assert (media_tree / "Empty" / "untitled folder 2").is_dir()


async def test_trash_sends_to_trash_and_tree_follows(media_tree, monkeypatch):
    import shutil
    trashed = []

    def fake_trash(path):
        trashed.append(path)
        shutil.rmtree(path)

    monkeypatch.setattr(adapters, "trash", fake_trash)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("ctrl+delete")             # ^del trash
        await pilot.pause(0.8)
        assert trashed == [media_tree / "Empty"]
        tree = app.query_one(LibraryTree)
        assert tree._node_for(media_tree / "Empty") is None


async def test_trash_works_on_a_file(media_tree, monkeypatch):
    """The reported bug: trash used to no-op on files (folder-only target)."""
    import shutil
    trashed = []

    def fake_trash(path):
        trashed.append(path)
        (shutil.rmtree if path.is_dir() else __import__("os").remove)(path)

    monkeypatch.setattr(adapters, "trash", fake_trash)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)           # an audio FILE
        song = app.query_one(DetailsView).path
        assert song is not None and song.is_file()
        await pilot.press("ctrl+delete")
        await pilot.pause(0.8)
        assert trashed == [song]


async def test_trash_backspace_variant_also_fires(media_tree, monkeypatch):
    """Mac's delete-labeled key sends backspace; accept that too."""
    calls = []
    monkeypatch.setattr(adapters, "trash", lambda p: calls.append(p))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("ctrl+backspace")
        await pilot.pause(0.6)
        assert calls == [media_tree / "Empty"]


async def test_trash_takes_the_row_the_tree_highlights(media_tree,
                                                       monkeypatch):
    """Nick's "^DEL sometimes doesn't delete" (2026-08-25): the pane
    learns the highlight through a 150ms debounce, so a ^DEL pressed
    right after an arrow key used to trash the PREVIOUS row — or, once
    that row was gone, nothing at all."""
    trashed = []
    monkeypatch.setattr(adapters, "trash", lambda p: trashed.append(p))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)           # 01 Song One.mp3
        await pilot.press("down")                    # → 02 Song Two.mp3
        await pilot.press("ctrl+delete")             # before the debounce
        await pilot.pause(0.8)
        assert trashed == [media_tree / "Music" / "02 Song Two.mp3"]


def _fake_trash(calls):
    import shutil

    def trash(path):
        calls.append(path)
        (shutil.rmtree if path.is_dir() else os.remove)(path)
    return trash


async def test_after_delete_the_cursor_takes_the_dead_row_s_place(
        media_tree, monkeypatch):
    """Nick, 2026-08-25: Finder's rule — the row below slides up under
    the cursor, so a second ^DEL is the next file, never the folder."""
    monkeypatch.setattr(adapters, "trash", _fake_trash([]))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)           # 01 Song One.mp3
        await pilot.press("ctrl+delete")
        await pilot.pause(0.8)
        tree = app.query_one(LibraryTree)
        assert tree.cursor_path() == media_tree / "Music" / "02 Song Two.mp3"


async def test_deleting_the_last_row_falls_back_to_the_one_above(
        media_tree, monkeypatch):
    monkeypatch.setattr(adapters, "trash", _fake_trash([]))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("down")                    # 02 Song Two.mp3 (last)
        await settle(pilot)
        await pilot.press("ctrl+delete")
        await pilot.pause(0.8)
        tree = app.query_one(LibraryTree)
        assert tree.cursor_path() == media_tree / "Music" / "01 Song One.mp3"


async def test_deleting_an_only_child_falls_back_to_the_parent(
        media_tree, monkeypatch):
    monkeypatch.setattr(adapters, "trash", _fake_trash([]))
    lonely = media_tree / "Empty" / "only.txt"
    lonely.write_text("x")
    fs.clear_cache()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("right")                   # expand it
        await settle(pilot)
        await pilot.press("down")                    # only.txt
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        assert tree.cursor_path() == lonely
        await pilot.press("ctrl+delete")
        await pilot.pause(0.8)
        assert tree.cursor_path() == media_tree / "Empty"


async def test_trash_says_so_when_there_is_no_single_target(media_tree,
                                                            monkeypatch):
    """A shift-range selection has no single target — ^DEL leaves it
    alone, but says so instead of swallowing the key."""
    from textual.widgets._toast import Toast
    trashed = []
    monkeypatch.setattr(adapters, "trash", lambda p: trashed.append(p))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40), notifications=True) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")              # two files marked
        await settle(pilot)
        await pilot.press("ctrl+delete")
        await pilot.pause(0.5)
        assert trashed == []
        shown = [t._notification.message for t in app.query(Toast)]
        assert any("nothing to delete" in message for message in shown), shown


async def test_trash_honors_offline(media_tree, monkeypatch):
    calls = []
    monkeypatch.setattr(adapters, "trash", lambda p: calls.append(p))
    monkeypatch.setenv("MEDIASMITH_OFFLINE", "1")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("ctrl+delete")
        await pilot.pause(0.3)
        assert calls == []
        assert (media_tree / "Empty").is_dir()


# -- video → gif (the third wizard div) -------------------------------------


async def test_gif_div_toggles_with_tasty_defaults(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+g")         # make ^gif
        await pilot.pause()
        assert app.query_one("#gif-div").display is True
        assert app.focused.id == "gif-fps"
        assert app.focused.value == "12"
        assert app.query_one("#gif-width").value == "480"
        await pilot.press("ctrl+g")                  # react-style toggle
        await pilot.pause()
        assert app.query_one("#gif-div").display is False
        assert app.focused is app.query_one(LibraryTree)


async def test_gif_apply_creates_sibling(media_tree, monkeypatch):
    from mediasmith import gif

    def fake_make(video, fps, width, overwrite=False):
        assert (fps, width) == (24, 320)
        target = gif.gif_target(video)
        target.write_bytes(b"gif")
        return target

    monkeypatch.setattr(gif, "make_gif", fake_make)
    monkeypatch.setattr(gif, "check_requirements", lambda: [])
    monkeypatch.delenv("MEDIASMITH_OFFLINE", raising=False)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+g")
        await pilot.pause()
        app.query_one("#gif-fps").value = "24"
        app.query_one("#gif-width").value = "320"
        await pilot.press("ctrl+s")                  # ^save in the div
        await pilot.pause(0.6)
        target = (media_tree / "Movies" / "Alien (1979)"
                  / "Alien.1979.gif")
        assert target.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(target) is not None
        assert app.query_one(DetailsView)._gif_open  # div stays for more


async def test_gif_honors_offline(media_tree, monkeypatch):
    from mediasmith import gif
    calls = []
    monkeypatch.setattr(gif, "make_gif", lambda *a, **kw: calls.append(a))
    monkeypatch.setenv("MEDIASMITH_OFFLINE", "1")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+g")
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause(0.3)
        assert calls == []


async def test_gif_down_walks_into_the_bars(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("enter", "ctrl+g")
        await pilot.pause()
        await pilot.press("down")                    # fps → width
        assert app.focused.id == "gif-width"
        await pilot.press("down")                    # width → the wizard's ^save
        assert app.focused.id == "gif-apply-btn"
        await pilot.press("down")                    # lockdown: clamp inside
        assert app.focused.id == "gif-apply-btn"
        await pilot.press("up", "up")                # save → width → fps
        assert app.focused.id == "gif-fps"


# -- command strip: responsive wrapping + the logo ---------------------------


async def test_strip_wide_is_one_line_logo_right(media_tree):
    # 240, not 220: TAB joined the two fold entries (todo-5), and the tree
    # state with ^f folderize on show now wants 222 columns for one line
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(240, 40)) as pilot:
        await pilot.pause()
        lines = _strip_text(app).split("\n")
        assert len(lines) == 1                       # wide: everything fits
        assert lines[0].rstrip().endswith(LOGO)      # space-between


async def test_strip_wraps_on_narrow_viewport(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await pilot.pause()
        lines = _strip_text(app).split("\n")
        assert len(lines) > 1                        # narrow: wrapped
        assert lines[-1].rstrip().endswith(LOGO)     # logo rides the last line
        strip = app.query_one(CommandStrip)
        assert strip.region.height == len(lines)     # height follows the wrap


async def test_strip_rewraps_on_resize(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(240, 40)) as pilot:
        await pilot.pause()
        assert len(_strip_text(app).split("\n")) == 1
        await pilot.resize_terminal(60, 40)
        await pilot.pause()
        assert len(_strip_text(app).split("\n")) > 1
        await pilot.resize_terminal(240, 40)
        await pilot.pause()
        assert len(_strip_text(app).split("\n")) == 1


# -- centered cursor scrolling ----------------------------------------------


def _flat_tree(tmp_path, n):
    root = tmp_path / "big"
    root.mkdir()
    for i in range(n):
        (root / f"f{i:02d}").write_text("x")
    return root


def _cursor_screen_row(tree):
    """Which pane row the cursor line renders on, given the center shift."""
    before = tree._center_offset() or 0
    return tree.cursor_line - tree.scroll_offset.y + before


async def test_cursor_rides_center_line(tmp_path):
    app = MediasmithApp(_flat_tree(tmp_path, 20))
    async with app.run_test(size=(40, 12)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        height = tree.scrollable_content_region.height
        assert len(tree._tree_lines) > height          # the rows overflow
        before = tree._center_offset()
        assert before == (height - 1) // 2             # one extra row below
        # top row, an interior row, and the very last row all stay centered
        for line in (0, before + 2, len(tree._tree_lines) - 1):
            tree._move_cursor(line)
            await pilot.pause()
            assert _cursor_screen_row(tree) == before


async def test_no_centering_when_list_fits(tmp_path):
    app = MediasmithApp(_flat_tree(tmp_path, 3))
    async with app.run_test(size=(40, 30)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        assert len(tree._tree_lines) <= tree.scrollable_content_region.height
        assert tree._center_offset() is None           # no overflow, no shift
        tree._move_cursor(len(tree._tree_lines) - 1)
        await pilot.pause()
        assert tree.scroll_offset.y == 0               # plain top-aligned view


async def test_left_to_parent_recenters(tmp_path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    for i in range(20):
        (root / "sub" / f"f{i:02d}").write_text("x")
    app = MediasmithApp(root)
    async with app.run_test(size=(40, 12)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        while "sub" not in str(tree.cursor_node.label):
            await pilot.press("down")
        await pilot.press("right")                     # expand sub
        await pilot.pause()
        sub_line = tree.cursor_node.line
        for _ in range(12):                            # dive deep past its row
            await pilot.press("down")
        await pilot.pause()
        assert tree.cursor_line > sub_line
        await pilot.press("left")                      # jump back to the parent
        await pilot.pause()
        assert tree.cursor_node.line == sub_line
        # the parent must re-center, not sit off-screen where its row was
        assert _cursor_screen_row(tree) == tree._center_offset()


# -- image trace ---------------------------------------------------------------

from mediasmith import trace as trace_mod  # noqa: E402

needs_potrace = pytest.mark.skipif(trace_mod.find_potrace() is None,
                                   reason="potrace not installed")


async def _open_trace(app, pilot):
    await _goto_photo(app, pilot)
    await pilot.press("enter", "ctrl+a")         # tr^ace
    await pilot.pause(0.5)
    details = app.query_one(DetailsView)
    assert details._trace_open
    return details


@needs_potrace
async def test_trace_takes_over_the_image_panel(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_trace(app, pilot)
        assert app.focused.id == "trace-threshold"
        assert app.query_one("#trace-div").display is True
        for hidden in ("#pane-bar", "#row-image-size", "#row-image-dims",
                       "#row-fname"):
            assert app.query_one(hidden).display is False, hidden
        assert app.query_one("#dtitle").display is True


@needs_potrace
async def test_trace_steppers_nudge_flip_and_cycle(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        details = await _open_trace(app, pilot)
        details._trace_settings = trace_mod.TraceSettings()    # session-wide
        await pilot.press("right", "shift+right")
        assert details._trace_settings.threshold == 139
        assert "139" in str(app.focused.render())
        await pilot.press("down", "down", "down", "down")    # invert
        assert app.focused.id == "trace-invert"
        await pilot.press("left")
        assert details._trace_settings.invert is True
        await pilot.press("down", "down", "right")         # format
        assert details._trace_settings.format == "eps"
        await pilot.press("down")                          # onto the bar
        assert app.focused.id == "trace-save-btn"


@needs_potrace
async def test_trace_preview_fills_the_details_view(media_tree):
    from mediasmith.images import IMAGES_OK
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        details = await _open_trace(app, pilot)
        await pilot.pause(1.0)
        cover = app.query_one("#cover-image")
        if not IMAGES_OK or not hasattr(cover, "image"):
            pytest.skip("images unavailable in this environment")
        area = details.scrollable_content_region
        # square source: the height is the limit, and the picture runs to
        # the pane's floor without spilling past it
        assert cover.region.height > 16                  # the normal cover
        assert cover.region.bottom <= area.bottom
        assert area.bottom - cover.region.bottom <= 1
        assert cover.region.right <= area.right


@needs_potrace
async def test_trace_save_writes_the_picked_format(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        details = await _open_trace(app, pilot)
        details._trace_settings = trace_mod.TraceSettings()
        await pilot.press("ctrl+s")
        await pilot.pause(0.8)
        svg = media_tree / "Pics" / "photo.svg"
        assert svg.read_bytes().startswith(b"<?xml")
        assert details._trace_open                       # stays for more
        assert app.query_one("#pane-bar").display is False
        details._trace_settings = details._trace_settings.nudged("format", 1)
        await pilot.press("ctrl+s")
        await pilot.pause(0.8)
        eps = media_tree / "Pics" / "photo.eps"
        assert eps.read_bytes().startswith(b"%!PS-Adobe")


@needs_potrace
async def test_trace_save_refuses_overwrite_until_pressed_again(media_tree):
    existing = media_tree / "Pics" / "photo.svg"
    existing.write_text("precious")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        details = app.query_one(DetailsView)
        details._trace_settings = trace_mod.TraceSettings()
        await pilot.press("enter", "ctrl+a")
        await pilot.pause(0.5)
        await pilot.press("ctrl+s")
        await pilot.pause(0.6)
        assert existing.read_text() == "precious"
        await pilot.press("ctrl+s")
        await pilot.pause(0.8)
        assert existing.read_bytes().startswith(b"<?xml")


@needs_potrace
async def test_trace_view_toggles_source_and_tracing(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        details = await _open_trace(app, pilot)
        button = app.query_one("#trace-view-btn")
        assert "source" in str(button.label)
        await pilot.press("ctrl+v")
        assert details._trace_view == "source"
        assert "tracing" in str(button.label)
        await pilot.press("right")                       # a change shows
        assert details._trace_view == "trace"            # its result


@needs_potrace
async def test_trace_esc_closes_and_restores_the_panel(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        details = await _open_trace(app, pilot)
        await pilot.press("escape")
        assert not details._trace_open
        assert app.focused is app.query_one(LibraryTree)
        for shown in ("#pane-bar", "#row-image-size", "#row-image-dims",
                      "#row-fname"):
            assert app.query_one(shown).display is True, shown
        assert app.query_one("#trace-div").display is False


@needs_potrace
async def test_trace_closes_when_browsing_away(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        details = await _open_trace(app, pilot)
        await pilot.press("escape")
        await pilot.press("enter", "ctrl+a")
        await pilot.pause(0.5)
        assert details._trace_open
        app.query_one(LibraryTree).focus()
        await pilot.press("up")                          # off the image
        await settle(pilot)
        assert not details._trace_open
        assert app.query_one("#pane-bar").display is True
