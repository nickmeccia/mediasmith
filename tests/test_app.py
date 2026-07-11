"""Interaction (Pilot) tests: keypresses in, observable state out."""

from pathlib import Path

from mediasmith import adapters
from mediasmith.app import MediasmithApp
from mediasmith.browser import LibraryTree, PathBar, parse_view
from mediasmith.details import ConfirmSave, DetailsPane, EditForm


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
        form = app.query_one("#form-audio", EditForm)
        assert form.values()["title"] == "Song One"


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


async def test_focus_locked_when_nothing_editable(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        assert tree.cursor_node.is_expanded          # the anchor folder
        for key in ("tab", "shift+tab", "enter"):
            await pilot.press(key)
            assert app.focused is tree
        assert tree.cursor_node.is_expanded          # enter didn't toggle it


async def test_details_escape_returns_to_browser(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        details = app.query_one(DetailsPane)
        details.focus()
        await pilot.pause()
        await pilot.press("tab")                     # no cycling out…
        assert app.focused is details
        await pilot.press("shift+tab")
        assert app.focused is details
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
    assert app.query_one(DetailsPane).kind == "audio"


async def test_tab_to_details_when_editable(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        tree = app.query_one(LibraryTree)
        await _goto_first_song(app, pilot)
        await pilot.press("tab")                     # descend: filename input
        assert app.focused.id == "fname"
        assert app.focused.value == "01 Song One.mp3"
        await pilot.press("escape")
        assert app.focused is tree


async def test_folder_panel_counts(media_tree):
    # counts view is for folders that don't bulk-qualify (subfolders inside);
    # Music has become a bulk form — see test_album_folder_shows_bulk_form
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # cursor on the anchor
        details = app.query_one(DetailsPane)
        assert details.kind == "folder"
        counts = app.query_one("#folder-counts")
        assert "5 folders" in str(counts.render())


async def test_pathbar_focus_puts_cursor_at_end(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+slash")
        bar = app.query_one(PathBar)
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
        await pilot.press("left")              # …jump to its parent (root)…
        assert tree.cursor_line == 0
        await pilot.press("left")              # …and climb
        await settle(pilot)
        assert str(tree.path) == str(media_tree.parent.parent)
        assert str(tree.cursor_node.label) == media_tree.parent.name


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


async def test_filesystem_root_labelled_slash():
    app = MediasmithApp(Path("/"))
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        assert str(tree.root.label) == "/"


async def test_cmd_up_down_jump_to_tree_ends(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("super+down")
        assert tree.cursor_line == tree.last_line
        assert app.focused is tree
        await pilot.press("super+up")
        assert tree.cursor_line == 1     # line 0 is the context row
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


async def test_blur_commits_filter_to_top_match(media_tree):
    # e.g. a mouse click elsewhere while a filter is typed
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathBar)
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
        bar = app.query_one(PathBar)
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
        media = tree.root.children[0]
        names = [c.data.path.name for c in media.children]
        assert names[0] == ".config"              # visible by default
        await pilot.press("ctrl+full_stop")
        await settle(pilot)
        media = tree.root.children[0]             # reload rebuilt the nodes
        names = [c.data.path.name for c in media.children]
        assert ".config" not in names


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
        bar = app.query_one(PathBar)
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
        bar = app.query_one(PathBar)
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


async def test_right_arrow_enters_details(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("right")                 # duplicates enter on a file
        assert app.focused.id == "fname"


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
        details = app.query_one(DetailsPane)
        assert not details.dirty                   # baseline moved with the save
        assert app.focused is not app.query_one(LibraryTree)   # ^s keeps focus


async def test_esc_clean_releases_focus(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "escape")
        assert app.focused is app.query_one(LibraryTree)


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
        details = app.query_one(DetailsPane)
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
        assert app.query_one(PathBar).value == str(new)
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
        details = app.query_one(DetailsPane)
        assert details.kind == "book"
        await pilot.press("enter", "down")           # title input
        form = app.query_one("#form-book", EditForm)
        assert app.focused is form.inputs()[0]
        app.focused.value = "Dune Messiah"
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        path = media_tree / "Books" / "Dune.epub"
        assert adapters.read_details(path).fields["title"] == "Dune Messiah"


async def test_contextual_strips_follow_focus(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        left = app.query_one("#strip-left")
        right = app.query_one("#strip-right")
        assert left.visible and not right.visible    # tree focused at launch
        await pilot.press("ctrl+slash")              # path bar
        assert left.visible and not right.visible
        await pilot.press("escape")
        await _goto_first_song(app, pilot)
        await pilot.press("enter")                   # details
        assert right.visible and not left.visible


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

        bar = app.query_one(PathBar)                 # same in the path bar
        bar.focus()
        await pilot.pause()
        await pilot.press("alt+shift+left")
        sel = bar.selection
        assert sel.start != sel.end


# -- album-art methods ----------------------------------------------------------


async def test_art_buttons_reachable_by_arrows(media_tree):
    from textual.widgets import Button
    from mediasmith.details import ArtField
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        for _ in range(20):                          # ↓ walks clean through:
            await pilot.press("down")                # fields → art → buttons
        assert app.focused.id == "art-btn-path"
        await pilot.press("down")                    # bottom row: clamp
        assert app.focused.id == "art-btn-path"
        await pilot.press("right")
        assert app.focused.id == "art-btn-fetch"
        await pilot.press("right")                   # rightmost: clamp
        assert app.focused.id == "art-btn-fetch"
        await pilot.press("left")
        assert app.focused.id == "art-btn-path"
        await pilot.press("up")                      # back to the art slot
        assert isinstance(app.focused, ArtField)
        await pilot.press("down", "left")            # ← at leftmost = esc
        assert app.focused is app.query_one(LibraryTree)


async def test_art_path_method(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "ctrl+o")         # path method, anywhere
        field = app.focused
        assert field.id == "art-path"
        assert app.query_one("#row-art-path").display
        field.value = str(media_tree / "Pics" / "photo.png")
        await pilot.press("enter")
        details = app.query_one(DetailsPane)
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
        await pilot.press("enter", "ctrl+o")
        app.focused.value = str(media_tree / "notes.txt")
        await pilot.press("enter")
        details = app.query_one(DetailsPane)
        assert not details.dirty                     # rejected, no pending art
        assert app.focused.id == "art-path"          # still correcting


async def test_art_path_esc_cancels_to_buttons(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter", "ctrl+o", "escape")
        assert app.focused.id == "art-btn-path"
        assert not app.query_one("#row-art-path").display
        assert not app.query_one(DetailsPane).dirty


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
        details = app.query_one(DetailsPane)
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
        details = app.query_one(DetailsPane)
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
        assert app.query_one(DetailsPane).paths is None


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
        details = app.query_one(DetailsPane)
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
        details = app.query_one(DetailsPane)
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
        assert not app.query_one(PathBar).display
        assert not app.query_one(DetailsPane).display


async def test_narrow_path_bar_summons_above_tree(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        bar = app.query_one(PathBar)
        tree = app.query_one(LibraryTree)
        await pilot.press("ctrl+slash")
        assert app.focused is bar
        assert bar.display and tree.display          # shared, not swapped
        await pilot.press("enter")
        await settle(pilot)
        assert app.focused is tree
        assert not bar.display                       # gone with its focus


async def test_narrow_read_only_views_without_focus(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down")                    # into the anchor folder
        await pilot.press("n")                       # notes.txt (kind: other)
        await settle(pilot)
        await pilot.press("enter")                   # view, not focus
        await pilot.pause()
        details = app.query_one(DetailsPane)
        assert details.display
        assert app.query_one("#left").region.width == 0   # width 0, not
        assert app.focused is tree                   # hidden: focus survives
        await pilot.press("escape")                  # swap back out
        await pilot.pause()
        assert not details.display
        assert app.query_one("#left").region.width > 0
        assert app.focused is tree


async def test_narrow_view_follows_cursor(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "n")               # notes.txt
        await settle(pilot)
        await pilot.press("enter")                   # view it
        details = app.query_one(DetailsPane)
        assert details.path == media_tree / "notes.txt"
        await pilot.press("down")                    # Pics, still viewing
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
        assert app.query_one(DetailsPane).display
        assert app.query_one("#left").region.width == 0
        await pilot.press("escape")                  # ascend: tree swaps back
        await pilot.pause()
        tree = app.query_one(LibraryTree)
        assert app.focused is tree
        assert not app.query_one(DetailsPane).display
        assert app.query_one("#left").region.width > 0


async def test_narrow_path_bar_summons_over_view(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(60, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "n")               # notes.txt
        await settle(pilot)
        await pilot.press("enter")                   # viewing details
        await pilot.press("ctrl+slash")              # summon the path bar
        await pilot.pause()
        bar = app.query_one(PathBar)
        assert app.focused is bar
        assert bar.display and app.query_one("#left").region.width > 0
        assert not app.query_one(DetailsPane).display


async def test_wide_carries_no_narrow_behavior(media_tree):
    # enter on a read-only kind stays a no-op on wide screens
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down", "n")               # notes.txt
        await settle(pilot)
        await pilot.press("enter")
        details = app.query_one(DetailsPane)
        assert app.focused is tree
        assert details.display                       # always shown on wide
        assert app.query_one("#left").display
        await pilot.press("escape")                  # and esc stays harmless
        assert details.display and app.query_one("#left").display


async def test_artist_folder_does_not_bulk(media_tree):
    # artist/album/track layout: an artist-level folder has subfolders
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # anchor folder has subdirs
        details = app.query_one(DetailsPane)
        assert details.paths is None
        assert details.kind == "folder"              # plain counts view
        assert app.query_one("#panel-folder").display
