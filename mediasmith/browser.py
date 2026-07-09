"""Left pane: pathsmith-style path bar + the library tree."""

from __future__ import annotations

import os
from pathlib import Path

from textual import events, work
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DirectoryTree, Input
from textual.worker import get_current_worker

from . import fs

TYPE_SEARCH_SECONDS = 1.0   # Finder-style: pause this long and the buffer resets


class PathBar(Input):
    """Full path of the selection; type + tab for prefix completion."""

    BINDINGS = [
        Binding("tab", "complete", "complete", priority=True),
        Binding("down", "to_tree", "tree", show=False),
    ]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("select_on_focus", False)
        super().__init__(*args, **kwargs)

    def on_focus(self) -> None:
        self.cursor_position = len(self.value)

    def action_to_tree(self) -> None:
        """Mirror of the tree's up-from-top: down enters the tree at its top."""
        tree = self.app.query_one(LibraryTree)
        tree.focus()
        tree.cursor_line = 0

    class Chosen(Message):
        """The user submitted a path that is an existing file."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def _matches(self) -> list[Path]:
        base, prefix = os.path.split(self.value)
        base = Path(base or "/")
        try:
            entries = fs.list_dir(base)
        except OSError:
            return []
        return [base / e.name for e in entries
                if not e.name.startswith(".")
                and e.name.lower().startswith(prefix.lower())]

    def action_complete(self) -> None:
        matches = self._matches()
        if not matches:
            self.screen.focus_next()
            return
        first = matches[0]
        self.value = str(first) + ("/" if first.is_dir() else "")
        self.cursor_position = len(self.value)

    def on_input_changed(self, ev: Input.Changed) -> None:
        hints = self.app.query("#hint")
        if not hints:
            return
        matches = self._matches()
        hints.first().update("   ".join(m.name for m in matches[:6]))

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        p = Path(self.value.rstrip("/") or "/")
        if p.is_dir():
            tree = self.app.query_one(LibraryTree)
            tree.path = p
            tree.focus()
        elif p.is_file():
            self.post_message(self.Chosen(p))


class LibraryTree(DirectoryTree):
    """DirectoryTree with cached (NAS-friendly) listings and fold keys."""

    BINDINGS = [
        Binding("right", "fold_open", "expand", show=False),
        Binding("left", "fold_close", "collapse", show=False),
        # These outrank the Screen's tab/shift+tab (non-priority bindings
        # resolve focused-widget first), keeping the PathBar out of the cycle.
        Binding("tab", "app.focus_details", "details", show=False),
        Binding("shift+tab", "app.focus_details", "details", show=False),
        Binding("super+up", "cursor_first", "first", show=False),
        Binding("super+down", "cursor_last", "last", show=False),
        Binding("alt+up", "cursor_first_sibling", "folder top", show=False),
        Binding("alt+down", "cursor_last_sibling", "folder bottom", show=False),
    ]

    # Rounded, single-dash guides; all three styles the same so hover/cursor
    # recolor but never swap glyphs.
    LINES = {style: ("  ", "│ ", "╰─", "├─")
             for style in ("default", "bold", "double")}

    _search_buffer: str = ""
    _search_timer = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guide_depth = 3   # guides render one dash: "├─ ", not "├── "

    class Focused(Message):
        """The cursor landed on a path (highlight, not selection)."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def _directory_content(self, location: Path, worker):
        # CachedPaths answer the tree's per-entry is_dir() calls (populate)
        # from the listing cache — no stat per entry, cheap revisits.
        for child in fs.cached_children(location):
            if worker.is_cancelled:
                break
            yield child

    @work(thread=True, exit_on_error=False)
    def _load_directory(self, node):
        # Finder-style order — the base class sorts directories first.
        assert node.data is not None
        path = Path(node.data.path).expanduser().resolve()
        return sorted(
            self.filter_paths(self._directory_content(path, get_current_worker())),
            key=lambda p: fs.sort_key(p.name),
        )

    def filter_paths(self, paths):
        return [p for p in paths if not p.name.startswith(".")]

    def action_fold_open(self) -> None:
        node = self.cursor_node
        if node is not None and node.allow_expand:
            node.expand()

    def action_fold_close(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        elif node.parent is not None:
            self.cursor_line = node.parent.line

    def action_cursor_up(self) -> None:
        if self.cursor_line <= 0:
            self.screen.focus_previous()
        else:
            super().action_cursor_up()

    def action_cursor_first(self) -> None:
        self._move_cursor(0)

    def action_cursor_last(self) -> None:
        self._move_cursor(self.last_line)

    def action_cursor_first_sibling(self) -> None:
        node = self.cursor_node
        if node is not None and node.parent is not None and node.parent.children:
            self._move_cursor(node.parent.children[0].line)

    def action_cursor_last_sibling(self) -> None:
        node = self.cursor_node
        if node is not None and node.parent is not None and node.parent.children:
            self._move_cursor(node.parent.children[-1].line)

    def _move_cursor(self, line: int) -> None:
        self.cursor_line = line
        self.scroll_to_line(line, animate=False)

    # -- Finder-style type-to-select ------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Typed text jumps the cursor to the closest visible name."""
        if not event.is_printable or event.character is None:
            return
        if event.character == " " and not self._search_buffer:
            return   # a bare space stays a key; mid-search it is text
        event.stop()
        event.prevent_default()
        self._search_buffer += event.character
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(TYPE_SEARCH_SECONDS,
                                            self._reset_search)
        self._jump_to(self._search_buffer)

    def _reset_search(self) -> None:
        self._search_buffer = ""
        self._search_timer = None

    def _jump_to(self, text: str) -> None:
        text = text.lower()
        rows: list[tuple[int, str]] = []
        for line in range(self.last_line + 1):
            node = self.get_node_at_line(line)
            if node is None or node is self.root or node.data is None:
                continue
            rows.append((line, Path(node.data.path).name.lower()))
        for line, name in rows:
            if name.startswith(text):
                self._move_cursor(line)
                return
        # Finder's fallback: the last name sorting before the typed text.
        before = [(name, line) for line, name in rows if name < text]
        if before:
            self._move_cursor(max(before)[1])

    def on_tree_node_highlighted(self, ev) -> None:
        if ev.node.data is not None:
            self.post_message(self.Focused(Path(ev.node.data.path)))
