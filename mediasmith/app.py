"""mediasmith — the app shell."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.scrollbar import ScrollBar, ScrollBarRender
from textual.widgets import Input

from . import strip
from .browser import LibraryTree, PathInput, TreeView
from .details import DetailsView
from .strip import CommandStrip
from .theme import MEDIASMITH


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

LOGO = strip.LOGO  # re-exported: tests and notes/octant.py know it here


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
        # delete stays app-dispatched in on_key: ctrl+delete has no single-
        # char chord shape. Cut/paste/new-directory are LibraryTree bindings
        # (tree commands per todo-4). The old ⌘⇧N / ⌘⌫ Finder chords are
        # gone (macOS eats ⌘ before the TUI does).
    ]

    CSS = """
    #body { layout: horizontal; height: 1fr; }
    /* -- STATE: when each palette look applies (see theme.py — the
       PALETTE). A view is "focused" when it owns focus; details counts a
       focused child field (:focus-within). Rest = the dim idle look. */
    /* The Tree View is ONE bordered pane; Path Input is a sub-view boxed
       inside it (notes/mockups/path-input.txt). Focus on either child
       lights the pane. */
    /* the 1-cell inset lives on the PANE, not on its children: a child
       margin costs every sibling that width (vertical layout resolves
       1fr against the widest margin), which parked the tree's scrollbar
       3 cells off the border instead of 1 */
    TreeView { width: 38%; min-width: 30; border: round $border-fg-idle;
               padding: 0 1; }
    TreeView:focus-within { border: round $border-fg-focus; }
    /* ...except while the PATH is being typed: the input is its own box,
       and two nested lit borders read as two focused things (Nick,
       todo-5). PathInput toggles the class on focus/blur. */
    TreeView.-path-editing:focus-within { border: round $border-fg-idle; }
    PathInput { height: 3; background: $surface;
              border: round $border-fg-idle; color: $text-fg-idle; }
    PathInput:focus { border: round $border-fg-focus;
                      color: $text-fg-focus; }
    /* the "reading…" wait marker (browser.READING) rides the border, so a
       slow NAS read shows without displacing anything the user is typing */
    PathInput { border-subtitle-align: right;
                border-subtitle-color: $label-fg-idle; }
    PathInput:focus { border-subtitle-color: $label-fg-focus; }
    /* one cell wide to match the thin thumb glyphs */
    LibraryTree, DetailsView { scrollbar-size-vertical: 1; }
    /* text + scrollbar ride the same idle/focus flip */
    LibraryTree, DetailsView {
        color: $text-fg-idle;
        scrollbar-color: $scrollbar-color-idle;
        scrollbar-color-hover: $scrollbar-color-hover-idle;
        scrollbar-color-active: $scrollbar-color-active-idle;
        scrollbar-background: $scrollbar-track-idle;
        scrollbar-background-hover: $scrollbar-track-idle;
        scrollbar-background-active: $scrollbar-track-idle;
        /* the cell where the two scrollbars meet (Textual's
           ScrollBarCorner) — its own token, not the track's */
        scrollbar-corner-color: $scrollbar-corner-idle;
    }
    LibraryTree:focus, DetailsView:focus, DetailsView:focus-within {
        color: $text-fg-focus;
        scrollbar-color: $scrollbar-color-focus;
        scrollbar-color-hover: $scrollbar-color-hover-focus;
        scrollbar-color-active: $scrollbar-color-active-focus;
        scrollbar-background: $scrollbar-track-focus;
        scrollbar-background-hover: $scrollbar-track-focus;
        scrollbar-background-active: $scrollbar-track-focus;
        scrollbar-corner-color: $scrollbar-corner-focus;
    }
    /* Tree's default :focus tints the pane 5% lighter, which the track
       can't follow (no scrollbar-background-tint exists); drop the tint
       so pane and track stay identical — focus shows via the border. */
    LibraryTree { background: transparent; }
    LibraryTree:focus { background-tint: transparent; }
    LibraryTree { height: 1fr; }
    /* the selected node (tree cursor) swaps with the pane's focus */
    LibraryTree > .tree--cursor { background: $node-selected-bg-idle; }
    LibraryTree:focus > .tree--cursor {
        background: $node-selected-bg-focus; }
    /* While the path bar edits, no node is "selected": hide the cursor. */
    LibraryTree.-editing > .tree--cursor { background: transparent;
                                           text-style: none; }
    DetailsView { width: 1fr; border: round $border-fg-idle; padding: 0 1; }
    DetailsView:focus, DetailsView:focus-within {
        border: round $border-fg-focus; }
    /* buttons ride the pane's idle/focus flip; the arrow-key-selected
       button carries the selected pair */
    ActionButton { background: $button-bg-idle; color: $button-fg-idle; }
    DetailsView:focus-within ActionButton { background: $button-bg-focus;
                                            color: $button-fg-focus; }
    /* the selected pair needs the pane in its selector too: the rule
       above (two type names) outranks a bare ActionButton:focus, so the
       selected button was rendering in the plain focused-pane pair */
    ActionButton:focus,
    DetailsView:focus-within ActionButton:focus {
        background: $button-selected-bg-focus;
        color: $button-selected-fg-focus; }
    .panel { height: auto; margin-top: 1; }
    .dtitle { text-style: bold; padding: 1 0 0 0; }
    #row-fname { height: 1; margin-top: 1; }
    #fname { width: 1fr; background: transparent; text-style: bold; }
    /* iTunes-style edited marker: a right-edge gutter column per field */
    .fmark { width: 2; color: $success; }
    EditForm { height: auto; }
    .frow { height: 1; }
    /* field labels ride the pane's idle/focus flip */
    .fkey { color: $label-fg-idle; }
    DetailsView:focus-within .fkey { color: $label-fg-focus; }
    .fval { background: transparent; width: 1fr; }
    .fval-static { color: $text-fg-idle; }
    DetailsView:focus-within .fval-static { color: $text-fg-focus; }
    .cover { width: auto; height: 16; margin: 1 0 0 0; }
    /* pixel dimensions under a cover (album art, book cover, poster) */
    .cover-dims { height: 1; color: $label-fg-idle; }
    DetailsView:focus-within .cover-dims { color: $label-fg-focus; }
    /* the audio art is a form field: image top-aligned with its label,
       left-aligned with the input column */
    #row-art { height: auto; }
    #art-none { color: $label-fg-idle; }
    DetailsView:focus-within #art-none { color: $label-fg-focus; }
    /* 1fr, not auto: a width-auto image inside a width-auto container
       resolves to 0 (no reference width for the aspect computation) */
    ArtField { width: 1fr; height: auto; }
    ArtField:focus { outline: round $border-fg-focus; }
    #cover-audio { margin: 0; }
    #row-art-buttons { height: auto; margin-top: 1; }
    #row-art-path { height: 1; margin-top: 1; }
    #art-path { background: transparent; }
    /* book cover: a path input toggled under the cover (art-path twin) */
    #book-cover-div { height: auto; margin-top: 1; }
    #book-cover-path { background: transparent; }
    #book-cover-hint { height: 1; color: $label-fg-idle; }
    DetailsView:focus-within #book-cover-hint { color: $label-fg-focus; }
    #pane-bar { margin-top: 1; }
    #shift-div { height: auto; margin-top: 1; }
    #shift-row { height: 1; }
    #shift-control { width: auto; }
    ShiftControl:focus { text-style: reverse; }
    #shift-hint { height: 1; color: $label-fg-idle; }
    DetailsView:focus-within #shift-hint { color: $label-fg-focus; }
    /* the resize wizard div — same block shape as #shift-div */
    #resize-div { height: auto; margin-top: 1; }
    #resize-row { height: 1; }
    .resize-num { width: 7; background: transparent; }
    #resize-x { width: 3; color: $label-fg-idle; text-align: center; }
    DetailsView:focus-within #resize-x { color: $label-fg-focus; }
    #resize-link { margin-left: 2; }
    #resize-bar { margin-top: 1; }
    /* the gif wizard div — same block shape as resize */
    #gif-div { height: auto; margin-top: 1; }
    #gif-row { height: 1; }
    .wsep { width: auto; color: $label-fg-idle; padding: 0 1; }
    DetailsView:focus-within .wsep { color: $label-fg-focus; }
    #gif-bar { margin-top: 1; }
    /* Image Trace: the stepper rows, then the picture filling the rest
       (its cell size is set in code — DetailsView._trace_previewed) */
    #trace-div { height: auto; margin-top: 1; }
    .trace-row { height: 1; }
    TraceControl { width: auto; }
    TraceControl:focus { text-style: reverse; }
    #trace-hint { height: auto; color: $label-fg-idle; }
    DetailsView:focus-within #trace-hint { color: $label-fg-focus; }
    #trace-bar { margin-top: 1; }
    #plan-preview { height: auto; margin-top: 1; }
    #plan-tree { height: auto; }
    /* the editable split-omnibus form (shares .frow/.fkey/.fval) */
    #panel-omnibus { height: auto; margin-top: 1; }
    .omni-source { color: $label-fg-idle; height: auto; }
    DetailsView:focus-within .omni-source { color: $label-fg-focus; }
    .omni-book { height: auto; margin-top: 1; }
    .omni-head { text-style: bold; }
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
    /* width 0 AND border none AND padding 0: the pane's own gutter
       would otherwise hold 2 cells open even at width 0 */
    .-narrow.-details-open TreeView { width: 0; border: none;
                                      padding: 0; }
    ConfirmSave, ConfirmCaseRename { align: center middle; }
    #confirm-box { width: auto; height: auto; padding: 1 2;
                   background: $surface; border: round $border-fg-focus; }
    #confirm-msg { margin-bottom: 1; }
    #confirm-buttons { width: auto; height: auto; }
    #confirm-buttons Button { margin-right: 2; }
    """

    def __init__(self, start_dir: Path, images: str = "auto"):
        super().__init__()
        # registered before run so the CSS below parses with the theme's
        # variables in scope — every color in the app is a theme token
        self.register_theme(MEDIASMITH)
        self.theme = "mediasmith"
        self.start_dir = start_dir
        self.images = images
        self.show_hidden = True
        self._details_viewing = False
        """Narrow "view": the details column is swapped in while the tree
        keeps focus — read-only kinds, which never take focus themselves."""
        self.lifted: list[Path] | None = None
        """The clipboard (^x cut / ^y copy): app-level so it survives
        selection changes and path-bar jumps — the long-distance flow is
        cut → ^/ → destination → ⏎ → ^v paste. Holds ONE selection."""
        self.lift_copy = False
        """Whether the clipboard holds a copy (paste duplicates) rather
        than a cut (paste moves)."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            yield TreeView(self.start_dir)
            yield DetailsView(images=self.images)
        yield CommandStrip()

    async def on_mount(self) -> None:
        self.watch(self.screen, "focused", self._sync_strips)
        tree = self.query_one(LibraryTree)
        tree.focus()
        await tree.anchor(self.start_dir)   # launch dir in parent context

    def sync_strips(self) -> None:
        """Resync for the current focus — what the details bar calls when
        its buttons change (the tree's ^f rides the folderize button)."""
        self._sync_strips(self.screen.focused)

    def _sync_strips(self, focused) -> None:
        """ONE command strip, state-driven: what it shows is what works.
        States per todo-4 — path input / details / clipboard / tree."""
        details = self.query_one(DetailsView)
        in_left = isinstance(focused, (PathInput, LibraryTree))
        in_details = focused is not None and (
            focused is details or details in focused.ancestors)
        if isinstance(focused, PathInput):
            state = strip.STATE_PATH
        elif in_details:
            state = strip.STATE_DETAILS
        elif self.lifted is not None:       # clipboard active (tree focused)
            state = strip.STATE_CLIPBOARD
        else:
            # ^f folderize prints only when the selection has one to give
            state = strip.tree_state(details.folderize_action() is not None)
        self.query_one(CommandStrip).set_entries(state)
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
        # ^/ is a Tree-view command ONLY (todo-4: a keybinding not on the
        # strip must not work) — from details or the path input it idles
        if not isinstance(self.focused, LibraryTree):
            return
        # narrow ordering: display the bar, move focus, and only then close
        # any open details column — Textual refuses to focus a non-displayed
        # widget and drops focus entirely when a focused one is hidden
        self.screen.add_class("-path-open")
        self.query_one(PathInput).focus()
        self._details_viewing = False
        self.screen.remove_class("-details-open")

    def action_toggle_hidden(self) -> None:
        # a tree-state strip command: inert anywhere else (todo-4)
        if not isinstance(self.focused, LibraryTree):
            return
        self.show_hidden = not self.show_hidden
        self.query_one(LibraryTree).reload()

    def action_focus_tree(self) -> None:
        self.query_one(LibraryTree).focus()

    # -- the clipboard (^x cut / ^y copy / ^v paste — tree commands) ------------

    def begin_lift(self, paths: list[Path], copy: bool = False) -> None:
        self.lifted = list(paths)
        self.lift_copy = copy
        n = len(paths)
        verb = "copied" if copy else "cut"
        self.notify(f"{n} item{'s' if n != 1 else ''} {verb} — browse to "
                    "the destination, ^v pastes, esc cancels",
                    title="copy" if copy else "cut")
        self._sync_strips(self.screen.focused)

    def end_lift(self) -> None:
        self.lifted = None
        self.lift_copy = False
        self._sync_strips(self.screen.focused)

    def cancel_lift(self) -> None:
        self.notify(("copy" if self.lift_copy else "cut") + " cancelled",
                    title="clipboard")
        self.end_lift()
        self.query_one(DetailsView)._sync_pane_bar()

    def on_key(self, event: events.Key) -> None:
        # View-scoped dispatch (todo-4): a chord printed on a visible
        # action button fires ONLY while Details view holds focus — the
        # strip and the buttons are the contract for what a key does.
        if len(self.screen_stack) > 1:          # a modal owns the keys
            return
        details = self.query_one(DetailsView)
        focused = self.focused
        # Delete: a TREE command (^DEL on the strip), app-dispatched
        # because no single-char chord can name it. Both the forward-
        # delete and the Mac backspace-labeled "delete" send it,
        # depending on terminal; accept both.
        if event.key in ("ctrl+delete", "ctrl+backspace"):
            if (isinstance(focused, LibraryTree)
                    and not details.plan_preview_open()):
                event.stop()
                # the TREE's highlight is the target, not the pane's
                # debounced copy of it (a shift-range selection has no
                # single target, so it keeps its hands-off rule)
                cursor = (None if len(focused._selection_paths()) > 1
                          else focused.cursor_path())
                details.action_delete(cursor)
            return
        # Folderize is the one action reachable from BOTH views (Nick,
        # 2026-08-22): ^f in the tree fires whichever folderize the
        # selection is showing — video, single epub, or audio folder. It
        # is on the tree's strip only while one is on show, so this stays
        # inside the contract rather than beside it.
        if event.key == "ctrl+f" and isinstance(focused, LibraryTree):
            action = (None if details.plan_preview_open()
                      else details.folderize_action())
            if action is not None:
                event.stop()
                details.trigger(action)
            return
        in_details = focused is not None and (
            focused is details or details in focused.ancestors)
        if not in_details:
            return
        action = details.action_for_key(event.key)
        if action is not None:
            event.stop()
            details.trigger(action)

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

    async def on_details_view_wrapped(
            self, ev: DetailsView.Wrapped) -> None:
        # the file moved into a brand-new wrapper folder beside where it
        # was: re-list that directory in place, expand the wrapper, cursor
        # on the file, then descend into its (editable) details — new-
        # folder's reveal, one level deeper (ev.path is the file itself)
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
        if parent is None:
            return
        # read where the row sat BEFORE the reload rebuilds the children,
        # so the cursor can take its place (Nick, 2026-08-25) instead of
        # climbing to the folder — where a second ^DEL meant the folder
        node = tree._node_for(ev.path)
        index = (parent.children.index(node)
                 if node is not None and node in parent.children else None)
        await tree.reload_node(parent)
        tree.cursor_to_gap(parent, index)


def start_directory(given: Path) -> Path:
    """The directory the tree opens in: the launch directory (bin/mediasmith
    passes it explicitly) or the one named on the command line.

    A path that is not a directory — a file, or a cwd whose volume went
    away — climbs to the nearest directory above it rather than handing
    the tree a root it cannot list. A path with nothing above it either
    (a typo) lands at home rather than at the filesystem root."""
    try:
        path = given.expanduser().resolve()
    except OSError:                     # a cwd that no longer exists
        return Path.home()
    climbed = path
    while not climbed.is_dir() and climbed.parent != climbed:
        climbed = climbed.parent
    if not climbed.is_dir() or (climbed != path and climbed == Path(climbed.anchor)):
        return Path.home()
    return climbed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start_dir", nargs="?", default=".", type=Path)
    parser.add_argument("--images", default="auto",
                        choices=["auto", "halfcell", "unicode", "off"],
                        help="image renderer (auto = best protocol)")
    args = parser.parse_args()
    try:
        MediasmithApp(start_directory(args.start_dir), images=args.images).run()
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
