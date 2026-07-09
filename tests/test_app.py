"""Interaction (Pilot) tests: keypresses in, observable state out."""

from mediasmith.app import MediasmithApp
from mediasmith.browser import LibraryTree, PathBar
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
