"""mediasmith — the app shell."""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.scrollbar import ScrollBar, ScrollBarRender
from textual.widgets import Input

from . import actions, prefs, strip, update
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
       PALETTE). Since 2026-10-26 a focusable ELEMENT carries its own
       look: $focusable-* when it could take focus, $focused-* when it
       IS the focused element, $traversed-* for the elements and path
       characters the user came through to reach it, and $triggerable-fg
       for a keybinding that works right now. Nothing flips with a
       VIEW's focus (todo-6 ¹). */
    /* NO PANE BORDERS (always-available-actions-3, 2026-10-26). A border
       said "this view has focus", which is the question the path model
       stopped asking: focus is one ELEMENT, and the element says so with
       its own background. The Path Input keeps a box because it is a box
       — a text field you type into, not a pane. */
    /* the 1-cell inset lives on the PANE, not on its children: a child
       margin costs every sibling that width (vertical layout resolves
       1fr against the widest margin), which parked the tree's scrollbar
       3 cells off the border instead of 1 */
    /* no right padding: the tree's own right edge has to touch the
       details pane, or the run cannot reach the Spine (todo-6) */
    TreeView { width: 38%; min-width: 30; padding: 0 0 0 1; }
    /* the Path Input and its chip share ONE box: the chip prints the key
       that gets you in or out, inside the border, on the path's own line */
    PathRow { height: 3; background: $chrome-bg; padding: 0 1;
              border: round $focusable-bg; }
    PathRow:focus-within { border: round $focused-bg; }
    PathChip { width: 5; height: 1; }
    PathInput { height: 1; width: 1fr; background: $chrome-bg;
                border: none; padding: 0; color: $focusable-fg; }
    /* the "reading…" wait marker (browser.READING) rides the border, so a
       slow NAS read shows without displacing anything the user is typing */
    PathRow { border-subtitle-align: right;
              border-subtitle-color: $muted; }
    /* one cell wide to match the thin thumb glyphs */
    LibraryTree, DetailsView { scrollbar-size-vertical: 1; }
    /* ONE look each: a view's text and scrollbar do not change because
       focus moved somewhere else (todo-6) */
    LibraryTree, DetailsView {
        color: $text-fg;
        scrollbar-color: $scrollbar-color;
        scrollbar-color-hover: $scrollbar-color;
        scrollbar-color-active: $traversed-path-fg;
        scrollbar-background: $scrollbar-track;
        scrollbar-background-hover: $scrollbar-track;
        scrollbar-background-active: $scrollbar-track;
        /* the cell where the two scrollbars meet (Textual's
           ScrollBarCorner) — its own token, not the track's */
        scrollbar-corner-color: $scrollbar-corner;
    }
    /* Tree's default :focus tints the pane 5% lighter, which the track
       can't follow (no scrollbar-background-tint exists); drop the tint
       so pane and track stay identical — focus shows via the border. */
    LibraryTree { background: transparent; }
    LibraryTree:focus { background-tint: transparent; }
    LibraryTree { height: 1fr; }
    /* every row is a focusable element: it wears the grey chip, and the
       CURSOR wears PRIMARY — whether or not the tree has focus, because
       nothing dims for being un-focused now. (The mockup greys the
       cursor too and lets the connector carry the selection; the
       connector is the next slice, so until then the accent stays
       rather than leaving no selection cue at all.) */
    LibraryTree > .tree--node-chip { background: $focusable-bg; }
    /* the run: ordinary text until focus travels down it (todo-6 ¹) */
    /* A path cell paints the CANVAS behind it. Colour alone leaves
       `bgcolor=None`, which is not the app's background but the
       TERMINAL's — the one place on screen that leaked it, and it read
       as a block in a different shade under Ghostty (Nick, todo-6 ¹). */
    /* the tree's structure lines, dimmer than the path that crosses them */
    LibraryTree > .tree--guides { color: $guide-fg; }
    LibraryTree > .tree--guides-hover,
    LibraryTree > .tree--guides-selected { color: $guide-level-fg; }
    LibraryTree > .tree--run {
        color: $path-fg;
        background: $background;
    }
    LibraryTree > .tree--run-traversed {
        color: $traversed-path-fg;
        background: $background;
    }
    /* no vertical scrollbar BETWEEN the panes: it would sit in the
       connector's way, and its track cells are spaces with a background,
       so they erase whatever passes under them. The mockup puts this bar
       at the viewport's edge, which is the full-width-tree architecture
       (its "Scrollbars" consequence) — until that lands, the tree keeps
       the cursor visible by centring it and shows no vertical bar. */
    LibraryTree { scrollbar-size-vertical: 0; }
    /* the selected row: FOCUSED while the tree has the cursor, and
       FOCUS-PATH while focus has moved down the path into the pane —
       it is then a thing the path runs through, not the thing with
       focus (Nick's example, todo-6) */
    LibraryTree > .tree--cursor { background: $traversed-element-bg;
                                  color: $traversed-element-fg; }
    LibraryTree:focus > .tree--cursor { background: $focused-bg;
                                        color: $focused-fg; }
    /* While the path bar edits, no node is "selected": hide the cursor. */
    LibraryTree.-editing > .tree--cursor { background: transparent;
                                           text-style: none; }
    DetailsView { width: 1fr; padding: 0 0 0 0; }
    /* the connector's own column, down the pane's left edge. Docked, so
       the line stays put while the content scrolls past it; the stub
       cells are what used to be the pane's left padding. */
    /* width comes from Spine.WIDTH (set in Python) */
    Spine { dock: left; height: 100%; color: $path-fg; }
    /* the stretch of line the path runs along, from the selected tree row
       to the field with focus */
    Spine > .spine--path {
        color: $traversed-path-fg;
        background: $background;     /* same canvas rule as .tree--run */
    }
    /* every button is a focusable ELEMENT: grey always, PRIMARY when it
       is the one thing with focus. No view-focus flip — a button does not
       dim because the cursor is in the tree; it is still available. */
    ActionButton { background: $focusable-bg; color: $focusable-fg; }
    /* background-tint: Textual lightens a focused Button by 5%, which
       would put a color on screen that is not in theme.py (rule 5) */
    ActionButton:focus { background: $focused-bg; color: $focused-fg;
                         background-tint: transparent; }
    ActionButton.-traversed { background: $traversed-element-bg;
                              color: $traversed-element-fg; }
    /* the links between buttons: ordinary text, or traversed where the
       path to the focused button ran through them (todo-6 ⁵) */
    BarLink { color: $path-fg; }
    BarLink.-traversed { color: $traversed-path-fg; }
    .panel { height: auto; margin-top: 1; }
    .dtitle { text-style: bold; padding: 1 0 0 0; }
    #row-fname { height: 1; margin-top: 1; }
    #fname { width: 1fr; background: transparent; text-style: bold; }
    /* iTunes-style edited marker: a right-edge gutter column per field */
    .fmark { width: 2; color: $success; }
    EditForm { height: auto; }
    .frow { height: 1; }
    /* a field's LABEL is its chip (FieldLabel paints it; the block hugs
       the word plus one cell so the VALUES still line up) */
    .fkey { color: $focusable-fg; }
    .fval { background: transparent; width: 1fr; }
    .fval-static { color: $focusable-fg; }
    .cover { width: auto; height: 16; margin: 1 0 0 0; }
    /* pixel dimensions under a cover (album art, book cover, poster) */
    .cover-dims { height: 1; color: $muted; }
    /* the audio art is a form field: image top-aligned with its label,
       left-aligned with the input column */
    #row-art, #row-poster, #row-cover { height: auto; }
    #row-art { width: 1fr; }
    /* the blank line that separates the artwork from the metadata */
    .fgap { height: 1; }
    /* ² : the info line is its own group, below the buttons. A hidden row
       contributes no margin, so this leaves no stray blank line on the
       kinds that have no info row. */
    #row-audio-info { margin-top: 1; }
    /* the spinner standing in for a button group still probing (todo-6 ⁸) */
    /* one cell between the line and the marker: a spinner is not a
       button, so it does not touch the stub (Nick, todo-6) */
    #actions-loading { height: 1; color: $muted; padding-left: 1; }
    #art-none, #poster-none, #cover-none { color: $muted; }
    /* an empty field prints "-" (or "(mixed)") as Input's PLACEHOLDER,
       which Textual greys with its own derived $text-disabled — a colour
       that is not in theme.py (rule 5). It is in-pane secondary text
       like any other, so it takes $muted. */
    FieldInput > .input--placeholder { color: $muted; }
    /* 1fr, not auto: a width-auto image inside a width-auto container
       resolves to 0 (no reference width for the aspect computation) */
    ArtField { width: 1fr; height: auto; }
    #cover-audio { margin: 0; }
    /* the artwork block: label · the path's branch · the stack it leads
       to (todo-6 ⁴). The stack holds the picture, the method buttons and
       the import input, so nothing needs a pad to line up any more. */
    #art-block { height: auto; }
    #art-stack { width: 1fr; height: auto; }
    #art-bar { margin-top: 1; }
    #row-art-path { height: 1; margin-top: 1; }
    #art-path { background: transparent; }
    /* book cover: a path input toggled under the cover (art-path twin) */
    #book-cover-div { height: auto; margin-top: 1; }
    #book-cover-path { background: transparent; }
    #book-cover-hint { height: 1; color: $muted; }
    /* the three bars: Contextual, File, Actions (always-available-actions-3).
       A blank line above the stack AND between the groups — they are three
       answers to three different questions, not one list (Nick, todo-6). */
    #bars { height: auto; margin-top: 1; }
    #bars ActionBar { height: auto; }
    /* the blank line BETWEEN the groups, by id: `:last-of-type` matched
       all three, so none of them kept a margin and a group that appeared
       after its probe landed flush against the one above (Nick's bug
       report, todo-6) */
    #contextual-bar, #file-bar { margin-bottom: 1; }
    #shift-div { height: auto; margin-top: 1; }
    #shift-row { height: 1; }
    #shift-control { width: auto; }
    ShiftControl:focus { text-style: reverse; }
    #shift-hint { height: 1; color: $muted; }
    /* the resize wizard div — same block shape as #shift-div */
    #resize-div { height: auto; margin-top: 1; }
    #resize-row { height: 1; }
    .resize-num { width: 7; background: transparent; }
    #resize-x { width: 3; color: $muted; text-align: center; }
    #resize-link { margin-left: 2; }
    #resize-bar { margin-top: 1; }
    /* the gif wizard div — same block shape as resize */
    #gif-div { height: auto; margin-top: 1; }
    #gif-row { height: 1; }
    .wsep { width: auto; color: $muted; padding: 0 1; }
    #gif-bar { margin-top: 1; }
    /* Image Trace: the stepper rows, then the picture filling the rest
       (its cell size is set in code — DetailsView._trace_previewed) */
    #trace-div { height: auto; margin-top: 1; }
    .trace-row { height: 1; }
    TraceControl { width: auto; }
    TraceControl:focus { text-style: reverse; }
    #trace-hint { height: auto; color: $muted; }
    #trace-bar { margin-top: 1; }
    #plan-preview { height: auto; margin-top: 1; }
    #plan-tree { height: auto; }
    /* the editable split-omnibus form (shares .frow/.fkey/.fval) */
    #panel-omnibus { height: auto; margin-top: 1; }
    .omni-source { color: $muted; height: auto; }
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
    /* the two confirm MODALS are gone (2026-10-26): a question is a state
       of the Contextual bar now, so it needs no chrome of its own */
    """

    def __init__(self, start_dir: Path, images: str = "auto"):
        super().__init__()
        # registered before run so the CSS below parses with the theme's
        # variables in scope — every color in the app is a theme token
        self.register_theme(MEDIASMITH)
        self.theme = "mediasmith"
        self.start_dir = start_dir
        self.images = images
        # read once, before the app starts: a saved switch is part of
        # how it opens, and this is a local file, not the library
        self.show_hidden = bool(prefs.load()["show_hidden"])
        self._details_viewing = False
        """Narrow "view": the details column is swapped in while the tree
        keeps focus — read-only kinds, which never take focus themselves."""
        self._chord_queue: list[tuple[str, Path | list[Path]]] = []
        """Chords pressed while the pane was still building its bar, with
        the row each was pressed ON (see the dispatch section below)."""
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
        self._check_for_an_update()

    @work(thread=True, group="update", exclusive=True)
    def _check_for_an_update(self) -> None:
        """Bring a `uv tool install`ed copy up to date (todo-6).

        In a thread and after the tree is up, because it talks to the
        network: nobody waits on it, and a copy that is not uv's own —
        Nick's checkout, for one — is left alone (update.managed_install).
        """
        version = update.check()
        if version:
            self.call_from_thread(
                self.notify,
                f"updated to {version} — it runs on the next launch",
                title="mediasmith", timeout=10.0)

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
            state = strip.tree_state()
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
        """^/ : jump to the Path Input from ANYWHERE that has nothing
        pending (Nick, todo-6). It used to be a tree-only command, from
        the days when a chord belonged to one view — but the path input is
        a step on the path from anywhere, and the only reason to refuse is
        unsaved work, which esc already asks about."""
        details = self.query_one(DetailsView)
        if isinstance(self.focused, PathInput):
            return                              # already there
        if details.question_open:
            return                              # a question owns the keys
        if details.dirty:
            self.notify("unsaved edits — ^s saves, esc asks",
                        title="path", severity="warning")
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
        # the choice outlives the session (Nick, todo-6). In a thread
        # because it writes a file, even a small local one.
        self.run_worker(partial(prefs.save, show_hidden=self.show_hidden),
                        thread=True, group="prefs", exclusive=True)

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

    # -- chord dispatch: the actions are ALWAYS available ----------------------
    # Nick, 2026-10-26 (always-available-actions-3): the old rule was that a
    # button's chord fired only while Details view held focus, which cost two
    # keystrokes and a read per action and did not match what he was doing —
    # "I visualize them almost as keys modifying the action I intend". Now a
    # printed chord fires from the tree as well.
    #
    # Two things make that safe, and they are his answers #1 and #4:
    #
    #   · the TARGET is the tree's cursor, captured when the key is pressed —
    #     never the pane's 150ms-debounced copy of it. That bug cost a ^DEL
    #     the wrong row in session 9; always-available actions would have
    #     handed the same bug to every one of them, most of which WRITE.
    #   · a chord that arrives while the pane is still building its bar is
    #     BUFFERED, not guessed at. It fires once the pane has settled on the
    #     row it was pressed on — so ^3 means what the label said at the
    #     moment of the keypress, and a probe landing late cannot move it.

    CHORD_QUEUE_LIMIT = 4
    """How many buffered chords are kept. A mashed key should not queue up a
    minute of writes; past this the extras are dropped."""

    def on_key(self, event: events.Key) -> None:
        if len(self.screen_stack) > 1:          # a modal owns the keys
            return
        details = self.query_one(DetailsView)
        focused = self.focused
        if isinstance(focused, PathInput):
            # a focused sub-view owns its keys (the pane's wizards do the
            # same through _focus_scope): the path input is for typing
            return
        in_details = focused is not None and (
            focused is details or details in focused.ancestors)
        in_tree = isinstance(focused, LibraryTree)
        if not (in_details or in_tree):
            return
        # Delete: app-dispatched because no single-char chord can name it.
        # Both the forward-delete and the Mac backspace-labeled "delete"
        # send it, depending on terminal; accept both.
        if event.key in ("ctrl+delete", "ctrl+backspace"):
            if not details.plan_preview_open():
                event.stop()
                self._chord(event.key, details, in_tree)
            return
        if not (actions.ordinal_for_key(event.key) is not None
                or event.key in details.all_chords()):
            return          # not a chord any button prints: leave it alone
        event.stop()
        self._chord(event.key, details, in_tree)

    def _chord_target(self, in_tree: bool) -> Path | list[Path] | None:
        """What a chord acts on, decided at the keypress."""
        details = self.query_one(DetailsView)
        if not in_tree:
            return details.paths or details.path
        tree = self.query_one(LibraryTree)
        selection = tree._selection_paths()
        return selection if len(selection) > 1 else tree.cursor_path()

    def _chord(self, key: str, details: DetailsView, in_tree: bool) -> None:
        """Fire now if the pane is settled on the captured row; otherwise
        buffer and bring that row in (FIFO by target, Nick's answer #4)."""
        target = self._chord_target(in_tree)
        if target is None:
            return
        if details.busy or not details.showing(target):
            if len(self._chord_queue) < self.CHORD_QUEUE_LIMIT:
                self._chord_queue.append((key, target))
            self._pull_in(target)
            return
        self._fire_chord(key, target)

    def _pull_in(self, target: Path | list[Path]) -> None:
        """Ask the pane for the row a buffered chord was pressed on."""
        details = self.query_one(DetailsView)
        if details.busy or details.showing(target):
            return                              # already coming, or here
        if isinstance(target, list):
            details.preview_bulk(target, immediate=True)
        else:
            details.preview(target, immediate=True)

    def _fire_chord(self, key: str, target: Path | list[Path]) -> None:
        details = self.query_one(DetailsView)
        if key in ("ctrl+delete", "ctrl+backspace"):
            # a shift-range selection has no single target, so delete keeps
            # its hands-off rule
            details.action_delete(None if isinstance(target, list) else target)
            return
        action = details.action_for_key(key)
        if action is not None:
            details.trigger(action)
            return
        # a chord nothing on show answers: say so once, rather than leave a
        # keypress looking dead (the ^s rule, 2026-08-25)
        name = target[-1].name if isinstance(target, list) else target.name
        self.notify(f"{name} has no action on that key",
                    title="no action", severity="warning")

    def on_details_view_settled(self, ev: DetailsView.Settled) -> None:
        self._drain_chords()

    def _drain_chords(self) -> None:
        """Resolve buffered chords in order, each against the bar of the row
        it was pressed on. A chord whose row offers nothing says so once."""
        details = self.query_one(DetailsView)
        while self._chord_queue and not details.busy:
            key, target = self._chord_queue[0]
            if not details.showing(target):
                if isinstance(target, list) or target.exists():
                    self._pull_in(target)
                    return                      # resolve on its Settled
                self._chord_queue.pop(0)        # the row is gone
                continue
            self._chord_queue.pop(0)
            self._fire_chord(key, target)

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
        details.preview(ev.path, immediate=True, force=True)
        self.reveal_details()                   # narrow: display, then focus
        details.focus_when_loaded()             # the read is in a worker now

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
        details.preview(ev.path, immediate=True, force=True)
        self.reveal_details()                   # narrow: display, then focus
        details.focus_when_loaded()             # the read is in a worker now

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
