"""Left pane: pathsmith-style path bar + the library tree."""

from __future__ import annotations

import os
from pathlib import Path

from textual import events, work
from textual.binding import Binding
from textual.message import Message
from textual.suggester import Suggester
from textual.widgets import DirectoryTree, Input
from textual.worker import get_current_worker

from . import fs
from .details import DetailsPane

TYPE_SEARCH_SECONDS = 1.0   # Finder-style: pause this long and the buffer resets


def parse_view(value: str) -> tuple[Path, str | None]:
    """Split a path-input value into (directory shown, prefix filter).

    A value naming an existing directory — trailing slash or not — is that
    directory with no filter; anything else shows its parent filtered by
    the last segment.
    """
    p = Path(value.rstrip("/") or "/")
    if p.is_dir():
        return p, None
    return p.parent, p.name


class PathSuggester(Suggester):
    """Ghost text: the rest of the top match for the current value."""

    def __init__(self, bar: PathBar) -> None:
        # case_sensitive=True so we receive the raw value; matching is
        # case-insensitive inside _matches. No cache: listings change.
        super().__init__(use_cache=False, case_sensitive=True)
        self._bar = bar

    async def get_suggestion(self, value: str) -> str | None:
        matches = self._bar._matches(value)
        if not matches:
            return None
        first = matches[0]
        prefix_len = len(os.path.split(value)[1])
        return value + first.name[prefix_len:] + ("/" if first.is_dir() else "")


class PathBar(Input):
    """Full path of the selection; when focused, a live filter for the tree."""

    BINDINGS = [
        Binding("tab", "complete", "complete", priority=True),
        Binding("down", "to_tree", "tree", show=False),
    ]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("select_on_focus", False)
        super().__init__(*args, **kwargs)
        self.suggester = PathSuggester(self)

    def on_focus(self) -> None:
        # Editing the path means no tree node is selected: the tree becomes
        # a live preview and the details pane empties until focus returns.
        # (-editing hides the cursor and mutes highlight messages — the Tree
        # cursor itself can't be removed: cursor_line=-1 gets clamped to 0.)
        self.cursor_position = len(self.value)
        self.app.query_one(LibraryTree).add_class("-editing")
        self.app.query_one(DetailsPane).clear()

    def action_to_tree(self) -> None:
        """Mirror of the tree's up-from-top: down enters the tree."""
        tree = self.app.query_one(LibraryTree)
        tree.focus()
        if tree.view_filter is None:
            tree.cursor_line = 0
        # else: the blur commit puts the cursor on the top match.

    class Chosen(Message):
        """The user submitted a path that is an existing file."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def _matches(self, value: str | None = None) -> list[Path]:
        value = self.value if value is None else value
        base, prefix = os.path.split(value)
        base = Path(base or "/")
        try:
            entries = fs.list_dir(base)
        except OSError:
            return []
        show_hidden = getattr(self.app, "show_hidden", True)
        return [base / e.name for e in entries
                if (show_hidden or not e.name.startswith("."))
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
        # Only typing drives the tree; programmatic value sync (from tree
        # highlights) must not re-root it.
        if not self.has_focus:
            return
        directory, needle = parse_view(self.value)
        self.app.query_one(LibraryTree).show_filtered(directory, needle)

    async def on_blur(self) -> None:
        """Leaving the input commits: value completes to the top match,
        the filter clears, and the tree cursor lands on that match."""
        tree = self.app.query_one(LibraryTree)
        tree.remove_class("-editing")
        if tree.view_filter is not None:
            matches = self._matches()
            top = matches[0] if matches else None
            if top is not None:
                self.value = str(top) + ("/" if top.is_dir() else "")
            await tree.end_filter(select=top)
        elif (node := tree.cursor_node) is not None and node.data is not None:
            # Selection survives an edit-free visit; resync details/value.
            tree.post_message(tree.Focused(Path(node.data.path)))

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        tree = self.app.query_one(LibraryTree)
        if tree.view_filter is not None:
            matches = self._matches()
            if not matches:
                return
            target = matches[0]
        else:
            target = Path(self.value.rstrip("/") or "/")
        if target.is_dir():
            tree.show_filtered(target, None)   # enter it, filter cleared
            self.value = str(target) + "/"
            tree.focus()
        elif target.is_file():
            self.post_message(self.Chosen(target))


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

    view_filter: str | None = None
    """Prefix filter on the root directory's entries (path-bar filter view)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guide_depth = 3   # guides render one dash: "├─ ", not "├── "

    def show_filtered(self, directory: Path, needle: str | None) -> None:
        """Point the tree at ``directory``, filtered by ``needle`` (or not)."""
        self.view_filter = needle
        if str(directory) != str(self.path):
            self.path = directory   # reactive — reloads
        else:
            self.reload()

    async def end_filter(self, select: Path | None) -> None:
        """Leave filter view: full listing again, cursor on ``select``."""
        if self.view_filter is None:
            return
        self.view_filter = None
        await self.reload()
        if select is not None:
            for child in self.root.children:
                if child.data is not None and Path(child.data.path) == select:
                    self._move_cursor(child.line)
                    break

    class Focused(Message):
        """The cursor landed on a path (highlight, not selection)."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def _directory_content(self, location: Path, worker):
        # CachedPaths answer the tree's per-entry is_dir() calls (populate)
        # from the listing cache — no stat per entry, cheap revisits.
        needle = self.view_filter
        if needle is not None and Path(location) != Path(self.path).expanduser().resolve():
            needle = None   # the filter applies to the root directory only
        for child in fs.cached_children(location):
            if worker.is_cancelled:
                break
            if needle is None or child.name.lower().startswith(needle.lower()):
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
        if getattr(self.app, "show_hidden", True):
            return list(paths)
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
        # Muted while the path bar is editing: the tree is a preview then,
        # and internal reloads move the cursor without user intent.
        if ev.node.data is not None and not self.has_class("-editing"):
            self.post_message(self.Focused(Path(ev.node.data.path)))
