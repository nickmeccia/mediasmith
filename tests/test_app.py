"""Interaction (Pilot) tests: keypresses in, observable state out."""

from pathlib import Path

from mediasmith import adapters
from mediasmith.app import LOGO, LOGO_MIN_WIDTH, MediasmithApp
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


async def test_album_art_shows_dimensions(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        details = app.query_one(DetailsPane)
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


async def test_book_cover_shows_dimensions(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        details = app.query_one(DetailsPane)
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
        bar = app.query_one(PathBar)
        bar.focus()
        await pilot.pause()          # let the Focus event land before typing
        bar.value = str(media_tree / "Mu")
        await pilot.pause(0.1)
        await pilot.press("tab")
        assert bar.value == str(media_tree / "Music") + "/"


async def test_other_file_is_editable(media_tree):
    # a plain file is renamable now (folder-style filename field); tab and
    # enter descend into its rename field, esc ascends back to the tree
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        tree = app.query_one(LibraryTree)
        await pilot.press("down", "n")               # notes.txt (kind: other)
        await settle(pilot)
        assert app.query_one(DetailsPane).can_edit()
        for key in ("tab", "enter"):
            await pilot.press(key)                   # descend into rename
            await pilot.pause()
            assert app.focused.id == "fname"
            await pilot.press("escape")              # ascend back to the tree
            await pilot.pause()
            assert app.focused is tree


async def test_details_escape_returns_to_browser(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        details = app.query_one(DetailsPane)
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
        await pilot.press("left")              # …and climb in one rung
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


async def _goto_dune(app, pilot):
    """Cursor onto Books/Dune.epub with the details settled."""
    await settle(pilot)
    await pilot.press("down", "right")           # Books, expanded
    await settle(pilot)
    await pilot.press("down")                    # Dune.epub
    await settle(pilot)
    assert app.query_one(DetailsPane).kind == "book"


async def test_book_offers_conversions_minus_own_format(media_tree):
    from mediasmith.actions import ActionBar
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        bar = app.query_one("#pane-bar", ActionBar)
        names = [b.spec.name for b in bar.buttons()]
        assert names == ["save", "convert_mobi", "convert_azw3",
                         "extract_cover", "book_cover", "create_opf",
                         "standardize", "sort", "move"]


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
        await pilot.press("ctrl+f")                # ^f cover
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
        assert app.query_one(DetailsPane).kind == "book"
        await pilot.press("ctrl+f")
        await pilot.pause(0.2)
        assert app.query_one("#book-cover-path").value == \
            str(media_tree / "Books" / "cover.jpg")


async def test_book_cover_prefill_falls_back_to_directory(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)               # Books/ has only Dune.epub
        await pilot.press("ctrl+f")
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
        await pilot.press("ctrl+f")
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
        await pilot.press("ctrl+f")
        await pilot.pause(0.2)
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not app.query_one("#book-cover-div").display


async def test_extract_cover_creates_sibling(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("ctrl+t")                  # ex^tract cover
        await pilot.pause(0.5)
        target = media_tree / "Books" / "cover.png"  # factory cover is png
        assert target.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(target) is not None


async def test_create_opf_creates_sidecar(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("ctrl+g")                  # create opf
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
        await pilot.press("ctrl+e")              # split omnibus
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
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
        await pilot.press("ctrl+e")
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
        await pilot.press("ctrl+e")
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
        await pilot.press("ctrl+e")
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
        assert details.plan_preview_open()
        await pilot.press("escape")              # from the focused form
        await settle(pilot)
        assert not details.plan_preview_open()
        assert not details._omnibus_editing
        assert app.focused is app.query_one(LibraryTree)   # ascended to tree
        assert not (media_tree / "Books"
                    / "Herbert, Frank - Omnibus - 01 - Book 1.epub").exists()


async def test_audio_offers_save_only(media_tree):
    from mediasmith.actions import ActionBar
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        bar = app.query_one("#pane-bar", ActionBar)
        assert [b.spec.name for b in bar.buttons()] == ["save", "move"]


async def test_convert_creates_sibling_and_tree_follows(media_tree, monkeypatch):
    from mediasmith import calibre

    def fake_convert(src, dst):
        dst.write_bytes(b"mobi bytes")

    monkeypatch.setattr(calibre, "convert", fake_convert)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)
        await pilot.press("ctrl+b")                  # convert to mo^bi
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
        await pilot.press("ctrl+b")
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
        await pilot.press("ctrl+b")                  # refuses, arms
        await pilot.pause(0.3)
        assert calls == [] and existing.read_bytes() == b"old"
        await pilot.press("ctrl+b")                  # same key again: overwrite
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
        await pilot.press("ctrl+b")                  # arms
        await pilot.pause(0.3)
        await pilot.press("up")                      # browse away disarms
        await settle(pilot)
        await pilot.press("down")                    # back to Dune.epub
        await settle(pilot)
        await pilot.press("ctrl+b")                  # first press again: refuses
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
        await pilot.press("ctrl+l")              # fo^lderize → plan preview
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
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
        await pilot.press("ctrl+l")
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
        assert details.plan_preview_open()
        await pilot.press("escape")              # tree keeps focus: esc = cancel
        await settle(pilot)
        assert not details.plan_preview_open()
        assert not app.query_one("#plan-preview").display
        assert (inbox / "strayA.mp3").exists()   # nothing moved
        assert "folderize" in _bar_names(app)    # back to the offer


async def test_folderize_offered_on_album_bulk_view(media_tree):
    # Music is an album-like leaf (bulk form), but its loose files are
    # unorganized — the folder action must still be reachable
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Music")
        await pilot.pause(0.4)                   # bulk read + probe
        names = _bar_names(app)
        assert "save" in names and "folderize" in names


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
    from mediasmith.details import ArtField
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("enter")
        for _ in range(30):                          # ↓ walks clean through:
            await pilot.press("down")                # fields → art → buttons
        assert app.focused.id == "act-move"          # …and clamps at the end
        await pilot.press("down")                    # bottom: clamp
        assert app.focused.id == "act-move"
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


async def test_action_key_fires_from_the_tree(media_tree):
    # the chord printed on a visible button works app-wide: no need to
    # descend into the details pane first
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        assert app.focused is app.query_one(LibraryTree)
        await pilot.press("ctrl+o")                  # art path, from the tree
        assert app.focused.id == "art-path"
        assert app.query_one("#row-art-path").display


async def test_action_key_inert_when_bar_hidden(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)                          # cursor on a folder
        assert app.query_one(DetailsPane).kind == "folder"
        await pilot.press("ctrl+o")                  # no audio bar on show
        assert app.focused is app.query_one(LibraryTree)
        assert not app.query_one("#row-art-path").display


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
        details = app.query_one(DetailsPane)
        assert details.display
        assert app.query_one("#left").region.width == 0   # narrow: swapped in
        assert app.focused.id == "fname"             # focus, not a bare view
        assert app.focused.value == "notes.txt"
        await pilot.press("escape")                  # ascend: tree swaps back
        await pilot.pause()
        assert not details.display
        assert app.query_one("#left").region.width > 0
        assert app.focused is tree


async def test_details_follow_cursor(media_tree):
    # the details pane tracks the tree highlight live (debounced), no
    # descend needed — browsing from a file to a folder swaps the panel
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("down", "n")               # notes.txt
        await settle(pilot)
        details = app.query_one(DetailsPane)
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
        details = app.query_one(DetailsPane)
        assert app.focused.id == "fname"             # descended into rename
        assert details.display
        assert app.query_one("#left").display        # wide: left column stays
        await pilot.press("escape")                  # ascend back to the tree
        await pilot.pause()
        assert app.focused is tree
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


# -- move (M1: ^n lifts, ^n places, esc cancels) ---------------------------------


async def _goto_notes(app, pilot):
    await settle(pilot)
    await pilot.press("down", "n")               # notes.txt
    await settle(pilot)
    assert app.query_one(DetailsPane).path == app.start_dir / "notes.txt"


async def test_move_lift_place_flow(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+n")              # lift
        await pilot.pause()
        assert app.lifted == [media_tree / "notes.txt"]
        strip = str(app.query_one("#strip-left").render())
        assert "moving 1 item" in strip
        await pilot.press("alt+up")              # Books (first sibling)
        await settle(pilot)
        await pilot.press("ctrl+n")              # place into Books
        await pilot.pause(0.8)
        assert (media_tree / "Books" / "notes.txt").exists()
        assert not (media_tree / "notes.txt").exists()
        assert app.lifted is None
        strip = str(app.query_one("#strip-left").render())
        assert "moving" not in strip             # strip restored


async def test_move_survives_pathbar_jump(media_tree):
    # Nick's long-distance flow: cut → ^/ → type destination → ⏎ → place
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.press("ctrl+slash")
        bar = app.query_one(PathBar)
        bar.value = str(media_tree / "Pics")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert app.lifted is not None            # the jump kept the lift
        await pilot.press("ctrl+n")              # place into Pics
        await pilot.pause(0.8)
        assert (media_tree / "Pics" / "notes.txt").exists()
        assert app.lifted is None


async def test_move_refuses_overwrite(media_tree):
    (media_tree / "Books" / "notes.txt").write_text("precious")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.press("alt+up")              # Books
        await settle(pilot)
        await pilot.press("ctrl+n")
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
        await pilot.press("ctrl+n")              # lift the folder
        await pilot.pause()
        await pilot.press("right")               # expand it
        await settle(pilot)
        await pilot.press("down")                # Alien (1979)
        await settle(pilot)
        await pilot.press("ctrl+n")              # into its own child: refused
        await pilot.pause(0.5)
        assert (media_tree / "Movies" / "Alien (1979)").exists()
        assert app.lifted is not None            # lift retained


async def test_move_same_folder_is_noop(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+n", "ctrl+n")    # lift, place in place
        await pilot.pause(0.5)
        assert (media_tree / "notes.txt").exists()
        assert app.lifted is not None            # kept for a real target


async def test_move_esc_cancels(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert app.lifted is not None
        await pilot.press("escape")
        await pilot.pause()
        assert app.lifted is None
        assert (media_tree / "notes.txt").exists()
        strip = str(app.query_one("#strip-left").render())
        assert "moving" not in strip


async def test_move_bulk_selection(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_first_song(app, pilot)
        await pilot.press("shift+down")          # both songs
        await _bulk_settle(pilot)
        await pilot.press("ctrl+n")              # lift the selection
        await pilot.pause()
        assert app.lifted is not None and len(app.lifted) == 2
        await pilot.press("left")                # up to Music
        await settle(pilot)
        await pilot.press("alt+up")              # Books
        await settle(pilot)
        await pilot.press("ctrl+n")
        await pilot.pause(0.8)
        assert (media_tree / "Books" / "01 Song One.mp3").exists()
        assert (media_tree / "Books" / "02 Song Two.mp3").exists()


async def test_move_button_label_flips(media_tree):
    from mediasmith.actions import ActionButton
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)
        button = app.query_one("#act-move", ActionButton)
        assert "move" in str(button.label)
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert "place" in str(button.label)
        await pilot.press("escape")              # cancel
        await pilot.pause()
        assert "place" not in str(button.label)


# -- fix multi-artist (folder action, folderize's pattern) ----------------------


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
        assert "fix_multi_artist" in _bar_names(app)
        await _goto_folder(app, pilot, "Music")  # untangled: no button
        assert "fix_multi_artist" not in _bar_names(app)


async def test_multiartist_preview_apply_rewrites_tags(media_tree):
    album = _make_tangled(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Tangle")
        await pilot.press("ctrl+x")              # fi^x multi-artist
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
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
        assert "fix_multi_artist" not in _bar_names(app)


async def test_multiartist_escape_cancels(media_tree):
    album = _make_tangled(media_tree)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Tangle")
        await pilot.press("ctrl+x")
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
        assert details.plan_preview_open()
        await pilot.press("escape")              # tree keeps focus: esc = cancel
        await settle(pilot)
        assert not details.plan_preview_open()
        d = adapters.read_details(album / "01 t.mp3")
        assert d.fields["artist"] == "Jax Jones/Rebecca Black"  # untouched


# -- subtitles (get / clean / shift / watch on video files) ---------------------


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
    assert app.query_one(DetailsPane).kind == "video"


async def test_video_offers_subtitle_actions(media_tree):
    (media_tree / "Movies" / "Alien (1979)" / "zz nosub.mkv").write_bytes(b"x")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        # video is renamable now, so "save" leads the bar (the rename write)
        assert _bar_names(app) == ["save", "get_subs", "clean_subs",
                                   "shift_subs", "watch", "download_posters",
                                   "gif", "move"]
        await pilot.press("z")                       # the srt-less video
        await settle(pilot)
        names = _bar_names(app)
        assert "get_subs" in names and "watch" in names
        assert "clean_subs" not in names             # nothing to clean/shift
        assert "shift_subs" not in names


async def test_clean_subs_strips_credits_and_markup(media_tree):
    srt_path = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.srt"
    srt_path.write_text(SRT_DIRTY)
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+u")                  # clean s^ubs, from the tree
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
        await pilot.press("ctrl+v")                  # open the shift div
        await pilot.pause(0.5)                       # load worker
        details = app.query_one(DetailsPane)
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
        await pilot.press("ctrl+v")
        await pilot.pause(0.5)
        details = app.query_one(DetailsPane)
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
        await pilot.press("ctrl+v")
        await pilot.pause(0.5)
        await pilot.press("right", "escape")         # pending: modal
        assert isinstance(app.screen, ConfirmSave)
        await pilot.press("d")                       # discard
        await pilot.pause()
        details = app.query_one(DetailsPane)
        assert not details._shift_open               # div closed
        assert srt_path.read_text() == original      # nothing written
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_esc_pending_save_writes(media_tree):
    srt_path = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.srt"
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+v")
        await pilot.pause(0.5)
        await pilot.press("right", "escape", "s")    # modal → save
        await pilot.pause(0.6)
        assert "00:00:01,100" in srt_path.read_text()
        details = app.query_one(DetailsPane)
        assert not details._shift_open               # released: closed out
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_toggle_pinned_while_pending(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+v")
        await pilot.pause(0.5)
        await pilot.press("right", "ctrl+v")         # toggle off refused
        details = app.query_one(DetailsPane)
        assert details._shift_open
        assert app.focused.id == "shift-control"
        await pilot.press("left", "ctrl+v")          # clean again: closes
        await pilot.pause()
        assert not details._shift_open
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_esc_clean_closes(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+v")
        await pilot.pause(0.5)
        await pilot.press("escape")
        await pilot.pause()
        details = app.query_one(DetailsPane)
        assert not details._shift_open
        assert not app.query_one("#shift-div").display
        assert app.focused is app.query_one(LibraryTree)


async def test_shift_down_reaches_bar_buttons(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+v")
        await pilot.pause(0.5)
        await pilot.press("down")                    # control → first button
        assert app.focused.id == "save-btn"
        await pilot.press("up")                      # and back
        assert app.focused.id == "shift-control"


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
        await pilot.press("ctrl+k")                  # get subs
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
        await pilot.press("ctrl+k")
        await pilot.pause(0.5)
        assert app.is_running


async def test_watch_launches_player(media_tree, monkeypatch):
    calls = []
    monkeypatch.setattr("mediasmith.details.launch",
                        lambda path: calls.append(path))
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+w")
        await pilot.pause()
        video = media_tree / "Movies" / "Alien (1979)" / "Alien.1979.mkv"
        assert calls == [video]


# -- video: container field + download posters ----------------------------------


async def test_video_panel_shows_container(media_tree):
    from textual.widgets import Static
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        row = app.query_one("#video-container", Static)
        assert str(row.render()) == "mkv"


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
        await pilot.press("ctrl+d")                  # ^download posters
        await pilot.pause(0.5)
        tree = app.query_one(LibraryTree)
        assert tree._node_for(folder) is not None    # re-listed in place


async def test_download_posters_honors_offline(media_tree, monkeypatch):
    calls = []
    monkeypatch.setattr("mediasmith.posters.run",
                        lambda *a, **kw: calls.append(a))
    monkeypatch.setenv("MEDIASMITH_OFFLINE", "1")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+d")
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
    assert app.query_one(DetailsPane).kind == "image"


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
        assert _bar_names(app) == ["save", "convert_jpg", "convert_webp",
                                   "convert_tiff", "resize", "rotate",
                                   "move"]                 # png: no png


async def test_image_convert_creates_sibling(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("ctrl+p")                  # convert to j^pg
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
        await pilot.press("ctrl+p")
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
        assert app.query_one(DetailsPane).kind == "image"
        await pilot.press("ctrl+p")                  # convert to jpg — refuses
        await pilot.pause(0.4)
        assert existing.read_bytes() == b"placeholder"
        await pilot.press("ctrl+p")                  # again: overwrites
        await pilot.pause(0.6)
        assert existing.read_bytes() != b"placeholder"
        assert Image.open(existing).format == "JPEG"   # a real conversion


async def test_resize_div_linked_fields(media_tree):
    from textual.widgets import Checkbox
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("ctrl+e")                  # r^esize
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
        await pilot.press("ctrl+e")
        await pilot.pause()
        from textual.widgets import Checkbox
        app.query_one("#resize-link", Checkbox).value = False
        app.query_one("#resize-w").value = "4"
        app.query_one("#resize-h").value = "2"
        await pilot.press("ctrl+a")                  # ^apply
        await pilot.pause(0.5)
        target = media_tree / "Pics" / "photo (4x2).png"
        assert target.exists()
        assert Image.open(target).size == (4, 2)
        details = app.query_one(DetailsPane)
        assert details._resize_open                  # div stays for more


async def test_resize_div_toggles_closed(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_photo(app, pilot)
        await pilot.press("ctrl+e")
        await pilot.pause()
        assert app.query_one("#resize-div").display is True
        await pilot.press("escape")                  # release to the tree
        assert app.focused is app.query_one(LibraryTree)
        assert app.query_one("#resize-div").display is True   # still open
        await pilot.press("ctrl+e")                  # react-style toggle
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
        await pilot.press("ctrl+o")                  # r^otate
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
        await pilot.press("ctrl+d")                  # stan^dardize
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
        await pilot.press("ctrl+d")
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
        await pilot.press("ctrl+d")
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
        await pilot.press("ctrl+o")                  # s^ort
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
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
        await pilot.press("ctrl+o")
        await pilot.pause(0.6)
        details = app.query_one(DetailsPane)
        assert details.plan_preview_open()
        await pilot.press("escape")
        await settle(pilot)
        assert not details.plan_preview_open()
        assert (media_tree / "Books" / "Dune.epub").exists()   # untouched


async def test_sort_single_ebook_wraps_renames_and_reselects(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_dune(app, pilot)                 # Books/Dune.epub, editable
        assert "sort" in _bar_names(app)             # probe filled in
        await pilot.press("ctrl+o")                  # s^ort — immediate, no preview
        await pilot.pause(0.8)
        wrapper = media_tree / "Books" / "Herbert, Frank - Dune"
        book = wrapper / "Herbert, Frank - Dune.epub"
        assert book.exists()                         # renamed + wrapped
        assert not (media_tree / "Books" / "Dune.epub").exists()
        details = app.query_one(DetailsPane)
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
        assert app.query_one(DetailsPane).kind == "book"
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
        details = app.query_one(DetailsPane)
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


async def test_folder_offers_new_and_trash_buttons(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        names = _bar_names(app)
        assert "new_folder" in names and "trash" in names
        await _goto_notes(app, pilot)                # kind: other — neither
        names = _bar_names(app)
        assert "new_folder" not in names and "trash" not in names


async def test_new_folder_creates_and_descends(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("ctrl+e")                   # n^ew folder
        await pilot.pause(0.8)
        target = media_tree / "Empty" / "untitled folder"
        assert target.is_dir()
        assert app.focused.id == "fname"             # straight into rename
        assert app.focused.value == "untitled folder"
        tree = app.query_one(LibraryTree)
        assert str(tree.cursor_node.label) == "untitled folder"


async def test_new_folder_on_file_targets_its_parent(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_notes(app, pilot)                # a file: its folder
        await pilot.press("ctrl+e")
        await pilot.pause(0.8)
        assert (media_tree / "untitled folder").is_dir()


async def test_new_folder_names_dont_collide(media_tree):
    (media_tree / "Empty" / "untitled folder").mkdir()
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_folder(app, pilot, "Empty")
        await pilot.press("ctrl+e")
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
        song = app.query_one(DetailsPane).path
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
        await pilot.press("ctrl+g")                  # make ^gif
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
        await pilot.press("ctrl+g")
        await pilot.pause()
        app.query_one("#gif-fps").value = "24"
        app.query_one("#gif-width").value = "320"
        await pilot.press("ctrl+a")                  # ^apply in the div
        await pilot.pause(0.6)
        target = (media_tree / "Movies" / "Alien (1979)"
                  / "Alien.1979.gif")
        assert target.exists()
        tree = app.query_one(LibraryTree)
        assert tree._node_for(target) is not None
        assert app.query_one(DetailsPane)._gif_open  # div stays for more


async def test_gif_honors_offline(media_tree, monkeypatch):
    from mediasmith import gif
    calls = []
    monkeypatch.setattr(gif, "make_gif", lambda *a, **kw: calls.append(a))
    monkeypatch.setenv("MEDIASMITH_OFFLINE", "1")
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("ctrl+a")
        await pilot.pause(0.3)
        assert calls == []


async def test_gif_down_walks_into_the_bars(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await _goto_alien(app, pilot)
        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("down")                    # fps → width
        assert app.focused.id == "gif-width"
        await pilot.press("down")                    # width → ^apply
        assert app.focused.id == "gif-apply-btn"
        await pilot.press("down")                    # → the pane bar (save leads)
        assert app.focused.id == "save-btn"
        await pilot.press("up", "up", "up")          # save → apply → width → fps
        assert app.focused.id == "gif-fps"


# -- global-strip logo ------------------------------------------------------


async def test_logo_shows_on_wide_viewport(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        logo = app.query_one("#strip-logo")
        assert logo.display is True
        assert str(logo.render()) == LOGO


async def test_logo_hides_when_it_would_collide(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(LOGO_MIN_WIDTH - 1, 40)) as pilot:
        await pilot.pause()
        assert app.query_one("#strip-logo").display is False


async def test_logo_follows_resize(media_tree):
    app = MediasmithApp(media_tree)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.resize_terminal(LOGO_MIN_WIDTH - 1, 40)
        await pilot.pause()
        assert app.query_one("#strip-logo").display is False
        await pilot.resize_terminal(LOGO_MIN_WIDTH, 40)
        await pilot.pause()
        assert app.query_one("#strip-logo").display is True


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
