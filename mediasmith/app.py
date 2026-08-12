"""mediasmith — the app shell."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.cells import cell_len
from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.scrollbar import ScrollBar, ScrollBarRender
from textual.widgets import Input, Static

from .browser import LibraryTree, PathInput, TreeView
from .details import DetailsView


class ThinScrollBarRender(ScrollBarRender):
    """Quarter-block thumb (▎ / ▂) instead of the default full-cell block."""

    # half, not one quarter: Textual's cell widths make the narrower left
    # blocks (U+258E, U+258D) render visibly thinner than the horizontal
    # U+2582, though they match on paper
    VERTICAL_GLYPH = "▌"    # U+258C LEFT HALF BLOCK
    HORIZONTAL_GLYPH = "▂"  # U+2582 LOWER ONE QUARTER BLOCK

    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: Color = Color.parse("#555555"),
        bar_color: Color = Color.parse("bright_magenta"),
    ) -> Segments:
        glyph = cls.VERTICAL_GLYPH if vertical else cls.HORIZONTAL_GLYPH
        width = thickness if vertical else 1
        blank = cls.BLANK_GLYPH * width
        segments = [Segment(blank, Style(bgcolor=back_color))] * int(size)
        if window_size and size and virtual_size and size != virtual_size:
            thumb = max(1, round(window_size * size / virtual_size))
            travel = max(1.0, virtual_size - window_size)
            start = round((size - thumb) * (position / travel))
            start = max(0, min(int(size) - thumb, start))
            upper = Segment(blank, Style(bgcolor=back_color,
                                         meta={"@mouse.down": "scroll_up"}))
            lower = Segment(blank, Style(bgcolor=back_color,
                                         meta={"@mouse.down": "scroll_down"}))
            grab = Segment(glyph * width,
                           Style(color=bar_color, bgcolor=back_color,
                                 meta={"@mouse.down": "grab"}))
            segments = ([upper] * start + [grab] * thumb
                        + [lower] * (int(size) - start - thumb))
        if vertical:
            return Segments(segments, new_lines=True)
        return Segments((segments + [Segment.line()]) * thickness,
                        new_lines=False)


ScrollBar.renderer = ThinScrollBarRender

NARROW_COLUMNS = 80
"""Below this many cells the columns swap instead of sharing the row."""

STRIP_GLOBAL = " ^/ path · ^. hidden · ^q quit"
STRIP_TREE = (" ↑↓ ←→ move · ⇧← collapse · type jump · ⏎ edit · "
              "^r refresh · ^e new · ^del trash")

LOGO = "𜵎𜵎▖𜷇🯦𜷇▌𜵅𜷃𜵈𜷓𜴀𜵎𜵎▖𜵅𜶍▐𜶓"
"""Octant-glyph wordmark (see notes/octant.py) — right edge of the
global strip. Every glyph is cell-width 1 under Rich (verified), so
the collision math below is exact."""

LOGO_MIN_WIDTH = 1 + cell_len(STRIP_GLOBAL) + 1 + cell_len(LOGO)
"""Viewport cells needed before the logo shows: the strip's 1-cell
left padding, the commands, one blank cell of separation, the logo."""
STRIP_PATH = " ⇥ complete · ⏎ go · esc cancel"
STRIP_DETAILS = " ↑↓ fields · ^s save · esc back"


class MediasmithApp(App):

    # Textual's command palette squats on ctrl+p (a system binding that
    # wins before App.on_key) — it silently ate the convert-to-epub and
    # convert-to-jpg chords, and none of this app's chrome comes from it
    ENABLE_COMMAND_PALETTE = False

    # sets -narrow / -wide on the screen as the terminal resizes; all
    # phone-layout rules hang off those classes
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (NARROW_COLUMNS, "-wide")]

    BINDINGS = [
        # ctrl+slash where the kitty keyboard protocol reports it; legacy
        # terminals send 0x1f for the same chord. Priority: works everywhere,
        # ahead of the tree's type-to-select.
        Binding("ctrl+slash", "focus_path", "path", show=False, priority=True),
        Binding("ctrl+underscore", "focus_path", "path", show=False,
                priority=True),
        Binding("ctrl+full_stop", "toggle_hidden", "hidden", show=False),
        # folder CRUD is app-dispatched in on_key: new directory on ^e (a pane
        # button chord reused across kinds), trash on ctrl+delete (its own
        # chord — see on_key). The old ⌘⇧N / ⌘⌫ Finder chords are gone (they
        # never reached Nick's terminal — macOS eats ⌘ before the TUI does).
    ]

    CSS = """
    #body { layout: horizontal; height: 1fr; }
    /* The Tree View is ONE bordered pane; Path Input is a sub-view boxed
       inside it (notes/mockups/path-input.txt). Focus on either child
       lights the pane. */
    TreeView { width: 38%; min-width: 30; border: round $surface-lighten-2; }
    TreeView:focus-within { border: round $accent; }
    PathInput { height: 3; margin: 0 1; background: $surface;
              border: round $surface-lighten-2; }
    PathInput:focus { border: round $accent; }
    /* one cell wide to match the thin thumb glyphs; track blends into
       each pane's own background */
    LibraryTree, DetailsView { scrollbar-size-vertical: 1; }
    LibraryTree { scrollbar-background: $surface;
                  scrollbar-background-hover: $surface;
                  scrollbar-background-active: $surface;
                  scrollbar-corner-color: $surface; }
    /* Tree's default :focus tints the pane 5% lighter, which the track
       can't follow (no scrollbar-background-tint exists); drop the tint
       so pane and track stay identical — focus still shows via the
       accent border. */
    LibraryTree:focus { background-tint: transparent; }
    DetailsView { scrollbar-background: $background;
                  scrollbar-background-hover: $background;
                  scrollbar-background-active: $background; }
    LibraryTree { height: 1fr; padding: 0 1; }
    /* While the path bar edits, no node is "selected": hide the cursor. */
    LibraryTree.-editing > .tree--cursor { background: transparent;
                                           text-style: none; }
    DetailsView { width: 1fr; border: round $surface-lighten-2; padding: 0 1; }
    DetailsView:focus, DetailsView:focus-within { border: round $accent; }
    .panel { height: auto; margin-top: 1; }
    .dtitle { text-style: bold; padding: 1 0 0 0; }
    #row-fname { height: 1; margin-top: 1; }
    #fname { width: 1fr; background: transparent; text-style: bold; }
    /* iTunes-style edited marker: a right-edge gutter column per field */
    .fmark { width: 2; color: $success; }
    EditForm { height: auto; }
    .frow { height: 1; }
    .fkey { color: $text-muted; }
    .fval { background: transparent; width: 1fr; }
    .fval-static { color: $text; }
    .cover { width: auto; height: 16; margin: 1 0 0 0; }
    /* pixel dimensions printed under a cover (album art, book cover) */
    .cover-dims { height: 1; color: $text-muted; }
    /* the audio art is a form field: image top-aligned with its label,
       left-aligned with the input column */
    #row-art { height: auto; }
    #art-none { color: $text-disabled; }
    /* 1fr, not auto: a width-auto image inside a width-auto container
       resolves to 0 (no reference width for the aspect computation) */
    ArtField { width: 1fr; height: auto; }
    ArtField:focus { outline: round $accent; }
    #cover-audio { margin: 0; }
    #row-art-buttons { height: auto; margin-top: 1; }
    #row-art-path { height: 1; margin-top: 1; }
    #art-path { background: transparent; }
    /* book cover: a path input toggled under the cover (art-path twin) */
    #book-cover-div { height: auto; margin-top: 1; }
    #book-cover-path { background: transparent; }
    #book-cover-hint { height: 1; color: $text-muted; }
    #pane-bar { margin-top: 1; }
    #shift-div { height: auto; margin-top: 1; }
    #shift-row { height: 1; }
    #shift-control { width: auto; }
    ShiftControl:focus { text-style: reverse; }
    #shift-hint { height: 1; color: $text-muted; }
    /* the resize wizard div — same block shape as #shift-div */
    #resize-div { height: auto; margin-top: 1; }
    #resize-row { height: 1; }
    .resize-num { width: 7; background: transparent; }
    #resize-x { width: 3; color: $text-muted; text-align: center; }
    #resize-link { margin-left: 2; }
    #resize-bar { margin-top: 1; }
    /* the gif wizard div — same block shape as resize */
    #gif-div { height: auto; margin-top: 1; }
    #gif-row { height: 1; }
    .wsep { width: auto; color: $text-muted; padding: 0 1; }
    #gif-bar { margin-top: 1; }
    #plan-preview { height: auto; margin-top: 1; }
    #plan-tree { height: auto; }
    /* the editable split-omnibus form (shares .frow/.fkey/.fval) */
    #panel-omnibus { height: auto; margin-top: 1; }
    .omni-source { color: $text-muted; height: auto; }
    .omni-book { height: auto; margin-top: 1; }
    .omni-head { text-style: bold; }
    #ctxrow { height: 1; background: $surface; color: $text-muted; }
    #strip-left { width: 38%; min-width: 30; padding-left: 1; }
    #strip-right { width: 1fr; padding-left: 1; }
    #strip { dock: bottom; height: 1; background: $surface;
             color: $text-muted; padding-left: 1; }
    #strip-global { width: 1fr; }
    #strip-logo { width: auto; }
    /* -- narrow (phone) breakpoint: one column at a time. Which column
       shows follows the pane hierarchy: -details-open swaps the details
       column in ("view" keeps the tree focused — no accent border;
       "focus" is the usual editable descend); -path-open summons the
       path bar above the tree rather than replacing it. */
    .-narrow TreeView { width: 1fr; min-width: 0; }
    .-narrow PathInput { display: none; }
    .-narrow.-path-open PathInput { display: block; }
    .-narrow DetailsView { display: none; }
    .-narrow.-details-open DetailsView { display: block; }
    /* width 0, not display none: in "view" the tree keeps focus while
       hidden, and hiding a focused widget makes Textual drop focus */
    /* width 0 AND border none: the pane's own border would otherwise
       hold 2 cells open even at width 0 */
    .-narrow.-details-open TreeView { width: 0; border: none; }
    .-narrow #strip-left { width: 1fr; min-width: 0; }
    ConfirmSave { align: center middle; }
    #confirm-box { width: auto; height: auto; padding: 1 2;
                   background: $surface; border: round $accent; }
    #confirm-msg { margin-bottom: 1; }
    #confirm-buttons { width: auto; height: auto; }
    #confirm-buttons Button { margin-right: 2; }
    """

    def __init__(self, start_dir: Path, images: str = "auto"):
        super().__init__()
        self.start_dir = start_dir
        self.images = images
        self.show_hidden = True
        self._details_viewing = False
        """Narrow "view": the details column is swapped in while the tree
        keeps focus — read-only kinds, which never take focus themselves."""
        self.lifted: list[Path] | None = None
        """A pending move (^n): app-level so it survives selection
        changes and path-bar jumps — the long-distance flow is
        cut → ^/ → destination → ⏎ → place."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            yield TreeView(self.start_dir)
            yield DetailsView(images=self.images)
        with Horizontal(id="ctxrow"):
            yield Static("", id="strip-left")
            yield Static("", id="strip-right")
        with Horizontal(id="strip"):
            yield Static(STRIP_GLOBAL, id="strip-global")
            yield Static(LOGO, id="strip-logo")

    async def on_mount(self) -> None:
        self.watch(self.screen, "focused", self._sync_strips)
        tree = self.query_one(LibraryTree)
        tree.focus()
        await tree.anchor(self.start_dir)   # launch dir in parent context

    def _sync_strips(self, focused) -> None:
        """Contextual strips: each pane's commands show only while it owns
        focus, on the line above the global strip, aligned to its column."""
        left = self.query_one("#strip-left", Static)
        right = self.query_one("#strip-right", Static)
        details = self.query_one(DetailsView)
        in_left = isinstance(focused, (PathInput, LibraryTree))
        in_details = focused is not None and (
            focused is details or details in focused.ancestors)
        left.visible = in_left
        if self.lifted is not None:             # a pending move owns the strip
            n = len(self.lifted)
            tree_strip = (f" moving {n} item{'s' if n != 1 else ''} · "
                          f"^n place here · esc cancel")
        else:
            tree_strip = STRIP_TREE
        left.update(STRIP_PATH if isinstance(focused, PathInput) else tree_strip)
        right.visible = in_details
        right.update(STRIP_DETAILS)
        # the logo yields before it collides with the global commands
        logo = self.query_one("#strip-logo", Static)
        logo.display = self.size.width >= LOGO_MIN_WIDTH
        # narrow: a hidden strip must release its width too (visible=False
        # keeps the space, which the wide layout wants for column alignment)
        narrow = self.screen.has_class("-narrow")
        left.display = in_left or not narrow
        right.display = in_details or not narrow
        # narrow columns follow focus; "view" holds -details-open while the
        # tree keeps focus (wide layouts carry the classes but ignore them)
        if in_details:
            self._details_viewing = False       # a real descend supersedes it
            self.screen.add_class("-details-open")
        elif in_left and not self._details_viewing:
            self.screen.remove_class("-details-open")
        self.screen.set_class(isinstance(focused, PathInput), "-path-open")

    def on_resize(self, event) -> None:
        # a breakpoint flip changes no focus: resync the classes/strips
        # (focused read inside the lambda — at startup the resize can be
        # scheduled before the initial focus lands)
        self.call_after_refresh(lambda: self._sync_strips(self.screen.focused))

    def reveal_details(self) -> None:
        """Display the details column ahead of a focus call — Textual
        refuses to focus a non-displayed widget, so order matters."""
        self.screen.add_class("-details-open")

    def view_details(self) -> None:
        """Narrow "view": the details column swaps in, the tree keeps focus
        (no accent border) — ↑↓ still browse live, esc swaps back."""
        if not self.screen.has_class("-narrow"):
            return
        self._details_viewing = True
        self.screen.add_class("-details-open")

    def close_details_view(self) -> None:
        """esc in the tree: swap the details column back out."""
        self._details_viewing = False
        self.screen.remove_class("-details-open")

    def action_focus_path(self) -> None:
        # narrow ordering: display the bar, move focus, and only then close
        # any open details column — Textual refuses to focus a non-displayed
        # widget and drops focus entirely when a focused one is hidden
        self.screen.add_class("-path-open")
        self.query_one(PathInput).focus()
        self._details_viewing = False
        self.screen.remove_class("-details-open")

    def action_toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        self.query_one(LibraryTree).reload()

    def action_focus_tree(self) -> None:
        self.query_one(LibraryTree).focus()

    # -- pending move (^n lift/place — DetailsView.action_move drives) ---------

    def begin_lift(self, paths: list[Path]) -> None:
        self.lifted = list(paths)
        n = len(paths)
        self.notify(f"{n} item{'s' if n != 1 else ''} lifted — browse to "
                    "the destination, ^n places, esc cancels", title="move")
        self._sync_strips(self.screen.focused)

    def end_lift(self) -> None:
        self.lifted = None
        self._sync_strips(self.screen.focused)

    def cancel_lift(self) -> None:
        self.notify("move cancelled", title="move")
        self.end_lift()
        self.query_one(DetailsView)._sync_pane_bar()

    def on_key(self, event: events.Key) -> None:
        # Any ^x chord printed on a visible action button fires it, no
        # matter where focus sits — read-only kinds (video, folder…) keep
        # the tree focused, yet their buttons still need their keys.
        if len(self.screen_stack) > 1:          # a modal owns the keys
            return
        details = self.query_one(DetailsView)
        # Trash: ctrl+delete on ANY selection (file or folder), app-dispatched
        # because no single-char chord can name it. Both the forward-delete and
        # the Mac backspace-labeled "delete" send it, depending on terminal;
        # accept both. Never while a text field is focused — that key is the
        # rename form's word-delete, which must survive; the button still trashes.
        if event.key in ("ctrl+delete", "ctrl+backspace"):
            if isinstance(self.focused, Input) or details.plan_preview_open():
                return
            event.stop()
            details.action_delete()
            return
        action = details.action_for_key(event.key)
        if action is not None:
            event.stop()
            details.trigger(action)
            return
        # New-folder fallback: ^e works on ANY selection, not just the folder
        # views where its button (and so the contextual dispatch above) lives —
        # ^e on a file makes a folder in its parent, matching the old ⌘⇧N. A
        # visible ^e button always wins first; a plan preview / split form owns
        # its own keys, so skip it there.
        if details.plan_preview_open():
            return
        if event.key == "ctrl+e":
            event.stop()
            details.action_new_directory()

    def on_library_tree_selected(self, ev: LibraryTree.Selected) -> None:
        self.query_one(PathInput).value = str(ev.path)
        self.query_one(DetailsView).preview(ev.path)

    def on_library_tree_bulk_selected(self, ev: LibraryTree.BulkSelected) -> None:
        self.query_one(PathInput).value = str(ev.paths[-1])
        self.query_one(DetailsView).preview_bulk(ev.paths)   # live, debounced

    async def on_details_view_saved(self, ev: DetailsView.Saved) -> None:
        self.query_one(PathInput).value = str(ev.new)
        if not ev.renamed:
            return
        tree = self.query_one(LibraryTree)
        if ev.old == Path(tree.path):           # renamed the context row
            await tree.anchor(ev.new)
            return
        # an expanded folder keeps its open subtree across the rename —
        # collect the old paths before the reload discards the nodes
        expanded = [Path(str(ev.new) + str(p)[len(str(ev.old)):])
                    for p in tree._expanded_paths()
                    if p == ev.old or ev.old in p.parents]
        parent = tree._node_for(ev.new.parent)
        if parent is None:
            return
        await tree.reload_node(parent)
        for path in expanded:                   # parents precede children
            node = tree._node_for(path)
            if node is not None and node.allow_expand:
                await tree._add_to_load_queue(node)
                node.expand()
        target = tree._node_for(ev.new)
        if target is not None:
            tree._move_cursor(target.line)

    async def on_details_view_file_created(self,
                                           ev: DetailsView.FileCreated) -> None:
        # a new sibling appeared (conversion, cover export…): re-list its
        # folder in place; cursor and expansion are untouched
        tree = self.query_one(LibraryTree)
        parent = tree._node_for(ev.path.parent)
        if parent is not None:
            await tree.reload_node(parent)

    async def on_details_view_folder_changed(
            self, ev: DetailsView.FolderChanged) -> None:
        tree = self.query_one(LibraryTree)
        node = tree._node_for(ev.path)
        if node is not None:
            await tree.reload_node(node)

    async def on_details_view_folder_created(
            self, ev: DetailsView.FolderCreated) -> None:
        # Finder's flow: show it, cursor on it, straight into the rename
        tree = self.query_one(LibraryTree)
        parent = tree._node_for(ev.path.parent)
        if parent is not None:
            await tree.reload_node(parent)
            if parent.allow_expand and not parent.is_expanded:
                await tree._add_to_load_queue(parent)
                parent.expand()
        target = tree._node_for(ev.path)
        if target is not None:
            tree._move_cursor(target.line)
        details = self.query_one(DetailsView)
        details.preview(ev.path, immediate=True)
        self.reveal_details()                   # narrow: display, then focus
        details.focus()

    async def on_details_view_book_sorted(
            self, ev: DetailsView.BookSorted) -> None:
        # the ebook moved into a brand-new wrapper folder beside where it
        # was: re-list that directory in place, expand the wrapper, cursor
        # on the book, then descend into its (editable) details — new-
        # folder's reveal, one level deeper (ev.path is the book itself)
        tree = self.query_one(LibraryTree)
        directory = tree._node_for(ev.path.parent.parent)   # the old dir
        if directory is not None:
            await tree.reload_node(directory)
        wrapper = tree._node_for(ev.path.parent)
        if (wrapper is not None and wrapper.allow_expand
                and not wrapper.is_expanded):
            await tree._add_to_load_queue(wrapper)
            wrapper.expand()
        target = tree._node_for(ev.path)
        if target is not None:
            tree._move_cursor(target.line)
        details = self.query_one(DetailsView)
        details.preview(ev.path, immediate=True)
        self.reveal_details()                   # narrow: display, then focus
        details.focus()

    async def on_details_view_deleted(self, ev: DetailsView.Deleted) -> None:
        tree = self.query_one(LibraryTree)
        if ev.path == Path(tree.path):          # trashed the context row:
            await tree.anchor(ev.path.parent)   # climb out of the dead root
            return
        parent = tree._node_for(ev.path.parent)
        if parent is not None:
            await tree.reload_node(parent)
            tree._move_cursor(parent.line)      # off the dead row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start_dir", nargs="?", default=".", type=Path)
    parser.add_argument("--images", default="auto",
                        choices=["auto", "halfcell", "unicode", "off"],
                        help="image renderer (auto = best protocol)")
    args = parser.parse_args()
    try:
        MediasmithApp(args.start_dir.resolve(), images=args.images).run()
    except Exception:
        import traceback
        log = Path(__file__).resolve().parent.parent / "crash.log"
        try:
            log.write_text(traceback.format_exc())
            print(f"crash written to {log}")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
