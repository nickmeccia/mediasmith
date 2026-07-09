"""mediasmith — the app shell."""

from __future__ import annotations

import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from .browser import LibraryTree, PathBar
from .details import DetailsPane


class MediasmithApp(App):

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
    #body { layout: horizontal; }
    #left { width: 38%; min-width: 30; border: round $surface-lighten-2; }
    #left:focus-within { border: round $accent; }
    PathBar { border: none; height: 1; background: $surface; }
    LibraryTree { height: 1fr; }
    /* While the path bar edits, no node is "selected": hide the cursor. */
    LibraryTree.-editing > .tree--cursor { background: transparent;
                                           text-style: none; }
    DetailsPane { width: 1fr; border: round $surface-lighten-2; padding: 0 1; }
    DetailsPane:focus-within { border: round $accent; }
    .panel { height: auto; }
    .dtitle { text-style: bold; padding: 1 0 0 0; }
    .frow { height: 1; }
    .fkey { color: $text-muted; }
    .fval { color: $text; }
    .cover { width: 32; height: 16; margin: 1 0 0 15; }
    #strip { dock: bottom; height: 1; background: $surface;
             color: $text-muted; padding-left: 1; }
    """

    def __init__(self, start_dir: Path, images: str = "auto"):
        super().__init__()
        self.start_dir = start_dir
        self.images = images
        self.show_hidden = True

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield PathBar(value=str(self.start_dir))
                yield LibraryTree(self.start_dir)
            yield DetailsPane(images=self.images)
        yield Static(
            " ⇥ pane · ^/ path · ↑↓ move · ←→ fold · type to jump"
            " · ^. hidden · ⏎ open · ^q quit",
            id="strip")

    def on_mount(self) -> None:
        self.query_one(LibraryTree).focus()

    def action_focus_path(self) -> None:
        self.query_one(PathBar).focus()

    def action_toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        self.query_one(LibraryTree).reload()

    def action_focus_tree(self) -> None:
        self.query_one(LibraryTree).focus()

    def action_focus_details(self) -> None:
        self.query_one(DetailsPane).focus()

    def on_library_tree_focused(self, ev: LibraryTree.Focused) -> None:
        self.query_one(PathBar).value = str(ev.path)
        self.query_one(DetailsPane).preview(ev.path)

    def on_path_bar_chosen(self, ev: PathBar.Chosen) -> None:
        self.query_one(DetailsPane).preview(ev.path, immediate=True)


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
