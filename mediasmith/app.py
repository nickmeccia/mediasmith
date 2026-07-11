"""mediasmith — the app shell."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.scrollbar import ScrollBar, ScrollBarRender
from textual.widgets import Static

from .browser import LibraryTree, PathBar
from .details import DetailsPane


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
STRIP_TREE = " ↑↓ ←→ move · type jump · ⏎ edit · ^r refresh"
STRIP_PATH = " ⇥ complete · ⏎ go · esc cancel"
STRIP_DETAILS = " ↑↓ fields · ^s save · esc back"


class MediasmithApp(App):

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
        # ctrl+. plus the Finder chord cmd+shift+. — kitty protocol only.
        Binding("ctrl+full_stop", "toggle_hidden", "hidden", show=False),
        Binding("super+shift+full_stop", "toggle_hidden", "hidden",
                show=False),
    ]

    CSS = """
    #body { layout: horizontal; height: 1fr; }
    #left { width: 38%; min-width: 30; }
    PathBar { height: 3; background: $surface;
              border: round $surface-lighten-2; }
    PathBar:focus { border: round $accent; }
    /* one cell wide to match the thin thumb glyphs; track blends into
       each pane's own background */
    LibraryTree, DetailsPane { scrollbar-size-vertical: 1; }
    LibraryTree { scrollbar-background: $surface;
                  scrollbar-background-hover: $surface;
                  scrollbar-background-active: $surface;
                  scrollbar-corner-color: $surface; }
    /* Tree's default :focus tints the pane 5% lighter, which the track
       can't follow (no scrollbar-background-tint exists); drop the tint
       so pane and track stay identical — focus still shows via the
       accent border. */
    LibraryTree:focus { background-tint: transparent; }
    DetailsPane { scrollbar-background: $background;
                  scrollbar-background-hover: $background;
                  scrollbar-background-active: $background; }
    LibraryTree { height: 1fr; border: round $surface-lighten-2;
                  padding: 0 1; }
    LibraryTree:focus { border: round $accent; }
    /* While the path bar edits, no node is "selected": hide the cursor. */
    LibraryTree.-editing > .tree--cursor { background: transparent;
                                           text-style: none; }
    DetailsPane { width: 1fr; border: round $surface-lighten-2; padding: 0 1; }
    DetailsPane:focus, DetailsPane:focus-within { border: round $accent; }
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
    /* the audio art is a form field: image top-aligned with its label,
       left-aligned with the input column */
    #row-art { height: auto; }
    #art-none { color: $text-disabled; }
    /* 1fr, not auto: a width-auto image inside a width-auto container
       resolves to 0 (no reference width for the aspect computation) */
    ArtField { width: 1fr; height: auto; }
    ArtField:focus { outline: round $accent; }
    #cover-audio { margin: 0; }
    #row-art-buttons { height: 1; margin-top: 1; }
    #row-art-buttons Button { margin-right: 2; }
    #row-art-path { height: 1; margin-top: 1; }
    #art-path { background: transparent; }
    #save-btn { margin: 1 0 0 0; }
    #ctxrow { height: 1; background: $surface; color: $text-muted; }
    #strip-left { width: 38%; min-width: 30; padding-left: 1; }
    #strip-right { width: 1fr; padding-left: 1; }
    #strip { dock: bottom; height: 1; background: $surface;
             color: $text-muted; padding-left: 1; }
    /* -- narrow (phone) breakpoint: one column at a time. Which column
       shows follows the pane hierarchy: -details-open swaps the details
       column in ("view" keeps the tree focused — no accent border;
       "focus" is the usual editable descend); -path-open summons the
       path bar above the tree rather than replacing it. */
    .-narrow #left { width: 1fr; min-width: 0; }
    .-narrow PathBar { display: none; }
    .-narrow.-path-open PathBar { display: block; }
    .-narrow DetailsPane { display: none; }
    .-narrow.-details-open DetailsPane { display: block; }
    /* width 0, not display none: in "view" the tree keeps focus while
       hidden, and hiding a focused widget makes Textual drop focus */
    .-narrow.-details-open #left { width: 0; }
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

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield PathBar(value=str(self.start_dir))
                yield LibraryTree(self.start_dir)
            yield DetailsPane(images=self.images)
        with Horizontal(id="ctxrow"):
            yield Static("", id="strip-left")
            yield Static("", id="strip-right")
        yield Static(STRIP_GLOBAL, id="strip")

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
        details = self.query_one(DetailsPane)
        in_left = isinstance(focused, (PathBar, LibraryTree))
        in_details = focused is not None and (
            focused is details or details in focused.ancestors)
        left.visible = in_left
        left.update(STRIP_PATH if isinstance(focused, PathBar) else STRIP_TREE)
        right.visible = in_details
        right.update(STRIP_DETAILS)
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
        self.screen.set_class(isinstance(focused, PathBar), "-path-open")

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
        self.query_one(PathBar).focus()
        self._details_viewing = False
        self.screen.remove_class("-details-open")

    def action_toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        self.query_one(LibraryTree).reload()

    def action_focus_tree(self) -> None:
        self.query_one(LibraryTree).focus()

    def on_library_tree_focused(self, ev: LibraryTree.Focused) -> None:
        self.query_one(PathBar).value = str(ev.path)
        self.query_one(DetailsPane).preview(ev.path)

    def on_library_tree_selected(self, ev: LibraryTree.Selected) -> None:
        self.query_one(PathBar).value = str(ev.paths[-1])
        self.query_one(DetailsPane).preview_bulk(ev.paths)   # live, debounced

    async def on_details_pane_saved(self, ev: DetailsPane.Saved) -> None:
        self.query_one(PathBar).value = str(ev.new)
        if not ev.renamed:
            return
        tree = self.query_one(LibraryTree)
        parent = tree._node_for(ev.new.parent)
        if parent is None:
            return
        await tree.reload_node(parent)
        target = tree._node_for(ev.new)
        if target is not None:
            tree._move_cursor(target.line)


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
