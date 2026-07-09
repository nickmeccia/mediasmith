"""Interaction (Pilot) tests: keypresses in, observable state out."""

from pathlib import Path

from mediasmith.app import MediasmithApp
from mediasmith.browser import LibraryTree, PathBar, parse_view
from mediasmith.details import DetailsPane


async def settle(pilot, seconds=0.4):
    await pilot.pause(seconds)   # covers the details debounce


async def test_details_follow_highlight(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("down", "down", "down", "right")   # Books, Empty, Movies… expand
        await settle(pilot)
        details = app.query_one(DetailsPane)
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
        details = app.query_one(DetailsPane)
        assert details.kind == "audio"
        assert app.query_one("#panel-audio").display is True
        title_row = app.query_one("#audio-title")
        assert "Song One" in str(title_row.render())


async def test_pathbar_tab_completes(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        bar = app.query_one(PathBar)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await pilot.pause(0.1)
        await pilot.press("tab")
        assert bar.value == str(media_tree / "Music") + "/"


async def test_up_from_top_focuses_pathbar(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        tree.focus()
        tree.cursor_line = 0
        await pilot.press("up")
        assert app.focused is app.query_one(PathBar)


async def test_folder_panel_counts(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        while "Music" not in str(tree.cursor_node.label):
            await pilot.press("down")
        await settle(pilot)
        details = app.query_one(DetailsPane)
        assert details.kind == "folder"
        counts = app.query_one("#folder-counts")
        assert "2 audios" in str(counts.render())


async def test_pathbar_focus_puts_cursor_at_end(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        tree.focus()
        tree.cursor_line = 0
        await pilot.press("up")              # jump to the path bar
        bar = app.query_one(PathBar)
        assert app.focused is bar
        assert bar.cursor_position == len(bar.value)
        sel = bar.selection
        assert sel.start == sel.end          # nothing selected


async def test_tab_cycles_panes_only(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        details = app.query_one(DetailsPane)
        assert app.focused is tree
        await pilot.press("tab")
        assert app.focused is details
        await pilot.press("tab")
        assert app.focused is tree
        await pilot.press("shift+tab")
        assert app.focused is details
        await pilot.press("shift+tab")
        assert app.focused is tree


async def test_tree_interleaves_files_and_folders(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        names = [str(child.label) for child in tree.root.children]
        assert names == ["Books", "Empty", "Movies", "Music",
                         "notes.txt", "Pics"]


async def test_type_to_select_jumps_to_prefix(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("m")
        assert str(tree.cursor_node.label) == "Movies"
        await pilot.press("u")           # buffer is now "mu"
        assert str(tree.cursor_node.label) == "Music"


async def test_type_to_select_nearest_when_no_prefix(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("z")           # nothing starts with z
        assert str(tree.cursor_node.label) == "Pics"


async def test_type_to_select_buffer_resets(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("m", "u")
        assert str(tree.cursor_node.label) == "Music"
        await pilot.pause(1.2)           # past TYPE_SEARCH_SECONDS
        await pilot.press("b")
        assert str(tree.cursor_node.label) == "Books"


async def test_cmd_up_down_jump_to_tree_ends(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("super+down")
        assert tree.cursor_line == tree.last_line
        assert app.focused is tree
        await pilot.press("super+up")
        assert tree.cursor_line == 0
        assert app.focused is tree       # never the path bar


async def test_ctrl_slash_focuses_pathbar(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        bar = app.query_one(PathBar)
        await pilot.press("ctrl+slash")            # kitty-protocol name
        assert app.focused is bar
        app.query_one(DetailsPane).focus()
        await pilot.press("ctrl+underscore")       # legacy-terminal name
        assert app.focused is bar


async def test_opt_up_down_jump_to_sibling_ends(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
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
        bar = app.query_one(PathBar)
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
        bar = app.query_one(PathBar)
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


async def test_down_commits_filter_to_top_match(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathBar)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mo")
        await settle(pilot)
        await pilot.press("down")
        await settle(pilot)
        assert app.focused is tree
        assert str(tree.cursor_node.label) == "Movies"
        assert len(tree.root.children) == 6       # filter cleared
        assert bar.value == str(media_tree / "Movies")


async def test_enter_enters_top_match(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathBar)
        tree = app.query_one(LibraryTree)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert app.focused is tree
        assert str(tree.path) == str(media_tree / "Music")
        # watch_path re-cursors to the root row, whose highlight syncs value
        assert bar.value == str(media_tree / "Music")


async def test_no_matches_shows_empty_tree(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathBar)
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
        details = app.query_one(DetailsPane)
        assert details.path is not None
        await pilot.press("ctrl+slash")
        tree = app.query_one(LibraryTree)
        assert tree.has_class("-editing")
        assert details.path is None


async def test_ghost_suggestion_is_top_match(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathBar)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await settle(pilot)
        assert bar._suggestion == str(media_tree / "Music") + "/"


async def test_hidden_files_shown_and_toggleable(media_tree):
    (media_tree / ".config").write_text("x")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        names = [c.data.path.name for c in tree.root.children]
        assert names[0] == ".config"              # visible by default
        await pilot.press("ctrl+full_stop")
        await settle(pilot)
        names = [c.data.path.name for c in tree.root.children]
        assert ".config" not in names


async def test_down_from_pathbar_focuses_tree_top(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        bar = app.query_one(PathBar)
        bar.focus()
        await pilot.press("down")
        tree = app.query_one(LibraryTree)
        assert app.focused is tree
        assert tree.cursor_line == 0
