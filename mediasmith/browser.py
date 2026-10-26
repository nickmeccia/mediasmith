"""Tree View: the left pane — Path Input (a sub-view) above the library
tree. The views form a chain of command (see CLAUDE.md): the path input
is a subview OF the tree view, not a sibling zone, so the container owns
the pane border, the focus state, and (eventually) tree-level state."""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events, work
from textual._segment_tools import line_pad
from textual.binding import Binding
from textual.containers import Vertical
from textual.geometry import Region, Size
from textual.message import Message
from textual.strip import Strip
from textual.suggester import Suggester
from textual.widgets import DirectoryTree, Input
from textual.worker import get_current_worker

from . import fs
from .details import DEBOUNCE_SECONDS, WORD_BINDINGS, DetailsView

TYPE_SEARCH_SECONDS = 1.0   # Finder-style: pause this long and the buffer resets

READING = "reading\u2026"
"""Path Input border subtitle while a listing is in flight. The NAS can
take seconds to spin up; Finder makes that wait visible, so do we."""

LOAD_TIMEOUT = 30.0
"""Ceiling on the restore's wait for Textual's load queue (``_apply_restore``).

A re-root that arrives while the queue is draining can orphan the queue
this restore is joined to, and then the join never returns — which wedges
the tree's message pump for the rest of the session (Nick, 2026-08-22:
the only way out was to quit the app). Timing out abandons the cursor
placement, which is a repaint, not a dead app."""


def parse_view(value: str) -> tuple[Path, str | None]:
    """Split a path-input value into (directory shown, prefix filter).

    A value naming an existing directory — trailing slash or not — is that
    directory with no filter; anything else shows its parent filtered by
    the last segment.

    Touches the filesystem (``is_dir``), so it is a THREAD-ONLY call; the
    event loop reaches it through ``aparse_view``.
    """
    p = Path(value.rstrip("/") or "/")
    if p.is_dir():
        return p, None
    return p.parent, p.name


async def aparse_view(value: str) -> tuple[Path, str | None]:
    """``parse_view`` off the event loop."""
    return await asyncio.to_thread(parse_view, value)


async def _join(awaitable) -> None:
    """Wrap a bare awaitable so ``asyncio.wait_for`` will take it (Textual's
    AwaitComplete is awaitable but is neither a coroutine nor a Future)."""
    await awaitable


class PathSuggester(Suggester):
    """Ghost text: the rest of the top match for the current value."""

    def __init__(self, bar: PathInput) -> None:
        # case_sensitive=True so we receive the raw value; matching is
        # case-insensitive inside _matches. No cache: listings change.
        super().__init__(use_cache=False, case_sensitive=True)
        self._bar = bar

    async def get_suggestion(self, value: str) -> str | None:
        # Textual asks on EVERY value write (Input.watch_value), which
        # includes the tree's own path sync on each cursor move — and the
        # ghost only renders while the input has focus. Unfocused, the
        # listing would be pure NAS cost, once per arrow key.
        if not self._bar.has_focus:
            return None
        matches = await self._bar._matches(value)
        if not matches:
            return None
        first = matches[0]
        prefix_len = len(os.path.split(value)[1])
        return value + first.name[prefix_len:] + ("/" if first.is_dir() else "")


class PathInput(Input):
    """Full path of the selection; when focused, a live filter for the tree."""

    BINDINGS = [
        Binding("tab", "complete", "complete", priority=True),
        Binding("escape", "cancel", "cancel", show=False),
        # only enter/escape release focus; shadow the Screen's focus cycling
        Binding("shift+tab", "stay", show=False),
        *WORD_BINDINGS,
    ]

    def action_stay(self) -> None:
        pass

    _committing = False
    """Enter was just handled: ignore our own value writes until the (async,
    deferred) focus change lands — ``focus()`` doesn't blur immediately."""

    _nav_timer = None
    """Debounce between typing and re-rooting the tree (rule 4). Every
    keystroke used to queue a whole directory read; on the NAS those
    serialize, and the tree's message pump is stuck for all of them."""

    _reads = 0
    """Off-thread filesystem reads in flight; the subtitle shows while > 0."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("select_on_focus", False)
        super().__init__(*args, **kwargs)
        self.suggester = PathSuggester(self)

    def on_focus(self) -> None:
        self._committing = False
        # Editing the path means no tree node is selected: the tree becomes
        # a live preview and the details pane empties until focus returns.
        # (-editing hides the cursor and mutes highlight messages — the Tree
        # cursor itself can't be removed: cursor_line=-1 gets clamped to 0.)
        self.cursor_position = len(self.value)
        self.app.query_one(LibraryTree).add_class("-editing")
        # ...and the pane it sits in stops advertising focus: while the
        # path is being typed the only lit box is this one (Nick, todo-5)
        self.app.query_one(TreeView).add_class("-path-editing")
        self.app.query_one(DetailsView).clear()

    async def action_cancel(self) -> None:
        """Esc: delete the incomplete segment, hand focus to the browser."""
        self._cancel_nav()
        tree = self.app.query_one(LibraryTree)
        if tree.view_filter is not None:
            # the filter view IS rooted at that directory — read it off the
            # tree instead of re-stating the path (see aparse_view)
            directory = Path(tree.path)
            tree.view_filter = None
            self._committing = True
            self.value = str(directory).rstrip("/") + "/"
            tree.focus()
            await tree.anchor(directory)
        else:
            tree.focus()   # nothing partial: blur resyncs the selection

    @contextlib.contextmanager
    def _reading(self):
        """Mark the pane as waiting on the filesystem, for as long as it is."""
        self._reads += 1
        self.border_subtitle = READING
        try:
            yield
        finally:
            self._reads -= 1
            if not self._reads:
                self.border_subtitle = ""

    async def _matches(self, value: str | None = None) -> list[fs.CachedPath]:
        """Entries of the typed directory that the last segment prefixes.

        CachedPaths, so every ``is_dir()`` downstream is free — and read in
        a thread, because this runs from the suggester on each keystroke.
        """
        value = self.value if value is None else value
        base, prefix = os.path.split(value)
        with self._reading():
            children = await fs.acached_children(base or "/")
        show_hidden = getattr(self.app, "show_hidden", True)
        return [child for child in children
                if (show_hidden or not child.name.startswith("."))
                and child.name.lower().startswith(prefix.lower())]

    async def action_complete(self) -> None:
        matches = await self._matches()
        if not matches:
            return
        first = matches[0]
        self.value = str(first) + ("/" if first.is_dir() else "")
        self.cursor_position = len(self.value)

    def on_input_changed(self, ev: Input.Changed) -> None:
        # Only typing drives the tree; programmatic value sync (from tree
        # highlights, or our own Enter commit) must not re-root it.
        if not self.has_focus or self._committing:
            return
        # Debounced: a re-root reads a directory, and a directory read on
        # the NAS is measured in seconds. One per pause, not one per key.
        self._cancel_nav()
        self._nav_timer = self.set_timer(DEBOUNCE_SECONDS, self._navigate)

    def _cancel_nav(self) -> None:
        if self._nav_timer is not None:
            self._nav_timer.stop()
            self._nav_timer = None

    def _navigate(self) -> None:
        self._nav_timer = None
        self._show_typed(self.value)

    @work(exclusive=True, group="path-nav", exit_on_error=False)
    async def _show_typed(self, value: str) -> None:
        """Point the tree at what has been typed.

        The parse stats the path, so it happens in a thread: on the event
        loop a sleeping SMB share freezes the entire app, keys and all.
        """
        with self._reading():
            directory, needle = await aparse_view(value)
        if self.value != value or not self.has_focus:
            return          # typing moved on while we waited (rule 4)
        self.app.query_one(LibraryTree).show_filtered(directory, needle)

    async def on_blur(self) -> None:
        """Leaving the input commits: value completes to the top match,
        the filter clears, and the tree cursor lands on that match."""
        self._cancel_nav()
        tree = self.app.query_one(LibraryTree)
        tree.remove_class("-editing")
        self.app.query_one(TreeView).remove_class("-path-editing")
        if tree.view_filter is not None:
            matches = await self._matches()
            top = matches[0] if matches else None
            if top is not None:
                self.value = str(top) + ("/" if top.is_dir() else "")
            await tree.end_filter(select=top)
        elif (tree._pending_restore is None
              and (node := tree.cursor_node) is not None
              and node.data is not None):
            # Selection survives an edit-free visit; resync details/value.
            # (Skipped mid-anchor: the restore will place the cursor itself.)
            tree.post_message(tree.Selected(Path(node.data.path)))

    async def on_input_submitted(self, ev: Input.Submitted) -> None:
        """Enter: autocomplete an incomplete path, hand focus to the browser."""
        self._cancel_nav()
        tree = self.app.query_one(LibraryTree)
        if tree.view_filter is not None:
            tree.focus()   # the blur commit completes to the top match
            return
        target = Path(self.value.rstrip("/") or "/")
        self._committing = True                # our value writes ≠ typing
        with self._reading():                  # one off-thread stat, not two
            node_type = await fs.anode_type(target)
        if node_type == "dir":
            self.value = str(target).rstrip("/") + "/"
            tree.focus()
            await tree.anchor(target)          # enter it, in parent context
        elif node_type == "file":
            tree.focus()
            await tree.anchor(target.parent, cursor=target)
        else:
            tree.focus()


class LibraryTree(DirectoryTree):
    """DirectoryTree with cached (NAS-friendly) listings and fold keys."""

    BINDINGS = [
        Binding("right", "expand", "expand", show=False),
        Binding("left", "collapse", "collapse", show=False),
        # Pane hierarchy: the browser controls the details view. ⏎ hands
        # focus down — only when the selection is editable. (It also
        # shadows the Tree's enter=select.)
        Binding("enter", "edit", "details", show=False),
        # TAB folds instead of descending (Nick, todo-5): one key for
        # →/← on the directory under the cursor. It also shadows the
        # Screen's focus cycling, which is what kept the pane home base.
        Binding("tab", "toggle_fold", "expand/collapse", show=False),
        Binding("shift+tab", "stay", show=False),   # home base: no cycling out
        # narrow "view" (details shown, tree focused): esc swaps it back out
        Binding("escape", "close_view", show=False),
        Binding("ctrl+r", "refresh", "refresh", show=False),
        # shift+↑↓ grows a contiguous selection, confined to siblings;
        # any plain cursor move collapses it (Finder-style)
        Binding("shift+down", "extend_down", "extend", show=False),
        Binding("shift+up", "extend_up", "extend", show=False),
        Binding("ctrl+up", "cursor_first", "first", show=False),
        Binding("ctrl+down", "cursor_last", "last", show=False),
        Binding("alt+up", "cursor_first_sibling", "folder top", show=False),
        Binding("alt+down", "cursor_last_sibling", "folder bottom", show=False),
        # collapse the whole level flat — self, siblings, and their offspring.
        # ^← is the strip's chord (Nick, 2026-08-12); ⇧← stays as a hidden
        # alias for muscle memory.
        Binding("ctrl+left", "collapse_level", "collapse level", show=False),
        Binding("shift+left", "collapse_level", "collapse level", show=False),
        # the clipboard: cut/copy/paste/new-directory are TREE commands
        # (todo-4) — they exist only while the tree owns focus, per the
        # strip. ^y for copy: ^c is reserved (see notes/qa/todo-2.md).
        Binding("ctrl+x", "cut", "cut", show=False),
        Binding("ctrl+y", "copy", "copy", show=False),
        Binding("ctrl+v", "paste", "paste", show=False),
        Binding("ctrl+n", "new_directory", "new directory", show=False),
    ]

    # Rounded, single-dash guides; all three styles the same so hover/cursor
    # recolor but never swap glyphs.
    LINES = {style: ("  ", "│ ", "╰─", "├─")
             for style in ("default", "bold", "double")}

    _search_buffer: str = ""
    _search_timer = None
    _search_scope = None
    """The node whose children a running type-ahead searches — pinned when
    the buffer starts so later keystrokes keep hunting the same list."""

    view_filter: str | None = None
    """Prefix filter on the root directory's entries (path-bar filter view)."""

    _pending_restore: tuple[list[Path], Path] | None = None
    """(paths to re-expand, cursor path) applied after the next re-root."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guide_depth = 3   # guides render one dash: "├─ ", not "├── "

    def show_filtered(self, directory: Path, needle: str | None) -> None:
        """Point the tree at ``directory``, filtered by ``needle`` (or not)."""
        self._pending_restore = None   # a filter view replaces any ladder
        self.view_filter = needle
        if str(directory) != str(self.path):
            self.path = directory   # reactive — reloads
        else:
            self.reload()

    async def end_filter(self, select: Path | None) -> None:
        """Leave filter view: parent-context listing, cursor on ``select``."""
        if self.view_filter is None:
            return
        self.view_filter = None
        current = Path(self.path)
        await self.anchor(current, cursor=select or current)

    # -- parent-context ladder -------------------------------------------------

    async def watch_path(self) -> None:
        await super().watch_path()
        await self._apply_restore()

    async def anchor(self, directory: Path, cursor: Path | None = None) -> None:
        """Show ``directory`` in the context of its parent: the parent is
        the root row, ``directory`` is expanded, cursor on ``cursor``.

        A cursor that is itself a directory is expanded too (Nick,
        2026-08-22): arriving somewhere from the path input should show
        what is there, not a closed folder. Filtered navigation lands
        here through ``end_filter``."""
        parent = directory.parent
        expanded = [directory]                  # parents precede children
        if (cursor is not None and cursor != directory
                and await fs.ais_dir(cursor)):
            expanded.append(cursor)
        self._pending_restore = (expanded, cursor or directory)
        if parent != directory and str(parent) != str(self.path):
            self.path = parent          # watch_path chains the restore
        else:
            await self.reload()
            await self._apply_restore()

    async def reveal_parent(self) -> None:
        """Grow the ladder one rung: re-root a level up, keeping every
        expanded node and putting the cursor on the old root."""
        old_root = Path(self.path)
        if old_root.parent == old_root:
            return
        self._pending_restore = (self._expanded_paths(), old_root)
        self.path = old_root.parent

    async def _apply_restore(self) -> None:
        if self._pending_restore is None:
            return
        expanded, cursor_path = self._pending_restore
        self._pending_restore = None
        for path in expanded:           # parents always precede children
            node = self._node_for(path)
            if node is None or not node.allow_expand:
                continue
            # populate before expanding — under a timeout, because an
            # orphaned load queue never completes its join (LOAD_TIMEOUT)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(_join(self._add_to_load_queue(node)),
                                       LOAD_TIMEOUT)
            node.expand()
        node = self._node_for(cursor_path)
        if node is not None:
            self._move_cursor(node.line)

    def _expanded_paths(self) -> list[Path]:
        out: list[Path] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            if node.allow_expand and node.is_expanded and node.data is not None:
                out.append(Path(node.data.path))
                stack.extend(node.children)
        return out

    def reset_node(self, node, label, data=None):
        # the filesystem root has an empty .name; show it as "/"
        if node is self.root and not str(label):
            label = "/"
        return super().reset_node(node, label, data)

    def cursor_path(self) -> Path | None:
        """The highlighted row's path — the TRUTH for tree commands.

        Details view learns the highlight through a 150ms debounce, so a
        command that reads ``DetailsView.path`` acts on the previous row
        when it fires right after an arrow key.
        """
        node = self.cursor_node
        if node is None or node.data is None:
            return None
        return Path(node.data.path)

    def _node_for(self, path: Path):
        """The loaded node displaying ``path``, or None."""
        node = self.root
        if node.data is None:
            return None
        root_parts = Path(node.data.path).parts
        parts = path.parts
        if parts[:len(root_parts)] != root_parts:
            return None
        for part in parts[len(root_parts):]:
            for child in node.children:
                if child.data is not None and Path(child.data.path).name == part:
                    node = child
                    break
            else:
                return None
        return node

    class Selected(Message):
        """The cursor landed on a path (highlight, not selection)."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class BulkSelected(Message):
        """A multi-file selection changed (shift-extension)."""

        def __init__(self, paths: list[Path]) -> None:
            super().__init__()
            self.paths = paths

    # -- shift-selection ---------------------------------------------------------

    _sel_anchor = None      # TreeNode where the selection started
    _sel_keep = False       # the next highlight is our own shift-move
    _selected: frozenset[str] = frozenset()   # str paths, for render_label

    def action_extend_down(self) -> None:
        self._extend(+1)

    def action_extend_up(self) -> None:
        self._extend(-1)

    def _extend(self, delta: int) -> None:
        node = self.cursor_node
        if node is None or node.parent is None:
            return
        # membership, not just parent identity: a reload can rebuild the
        # children while keeping the parent node, stranding the anchor
        if (self._sel_anchor is None
                or self._sel_anchor.parent is not node.parent
                or self._sel_anchor not in node.parent.children):
            self._sel_anchor = node
        siblings = node.parent.children
        index = siblings.index(node) + delta
        if 0 <= index < len(siblings):      # confined to the folder
            self._sel_keep = True
            self._move_cursor(siblings[index].line)
        self._emit_selection()

    def _selection_paths(self) -> list[Path]:
        anchor = self._sel_anchor
        node = self.cursor_node
        if (anchor is None or node is None or anchor.parent is None
                or anchor.parent is not node.parent):
            return []
        siblings = anchor.parent.children
        try:
            first, last = sorted((siblings.index(anchor),
                                  siblings.index(node)))
        except ValueError:      # a reload rebuilt the rows under us:
            return []           # the anchored selection no longer exists
        return [Path(child.data.path) for child in siblings[first:last + 1]
                if child.data is not None and not child.allow_expand]

    def _emit_selection(self) -> None:
        paths = self._selection_paths()
        self._selected = frozenset(str(p) for p in paths)
        self.refresh()
        if len(paths) > 1:
            self.post_message(self.BulkSelected(paths))
        elif (node := self.cursor_node) is not None and node.data is not None:
            self.post_message(self.Selected(Path(node.data.path)))

    def _clear_selection(self) -> None:
        if self._sel_anchor is None:
            return
        self._sel_anchor = None
        self._selected = frozenset()
        self.refresh()

    def render_label(self, node, base_style, style):
        label = super().render_label(node, base_style, style)
        # Button-shaped padding (2026-08-23): the name wears one cell of
        # selection color on each side, like an ActionButton's label. The
        # left cell is the guide space in render_line — restyled, never
        # inserted — so nothing on the row moves; the right one is
        # appended past the name, where there was only row background.
        # The ICON is inside the run (2026-09-01): DirectoryTree styles
        # its prefix with base_style, which left the emoji cells on the
        # pane background mid-highlight; `style` from cell 0 makes the
        # block continuous from the box character to the trailing pad.
        icon = len(label.plain) - len(node.label.plain)
        if icon > 0:
            label.stylize(style, 0, icon)
        label.append(" ", style)
        if node.data is None:
            return label
        # the label's foreground is a token lookup, never a hex — colors
        # live in theme.py only. Which token: hidden (a dot-file) ×
        # selected (the tree cursor) × the view's idle/focus flip. The
        # cursor is not "selected" while the path bar edits (.-editing
        # hides it), so the row keeps its ordinary text color there.
        hidden = Path(node.data.path).name.startswith(".")
        selected = (node is self.cursor_node
                    and not self.has_class("-editing"))
        # dim: DirectoryTree's own `directory-tree--hidden` component
        # class fades hidden rows, which would blend a token toward the
        # row behind it (grey-10 on the cursor came out #684a20). The
        # non-hidden cursor isn't dimmed, so a SELECTED hidden row drops
        # dim to land on the token's true color.
        dim = None
        if hidden and selected:
            token = ("node-hidden-selected-fg-focus" if self.has_focus
                     else "node-hidden-selected-fg-idle")
            dim = False
        elif hidden:
            token = ("node-hidden-fg-focus" if self.has_focus
                     else "node-hidden-fg-idle")
        elif selected and not self.has_focus:
            token = "node-selected-fg-idle"     # focused: Textual's own
        else:                                   # cursor foreground
            token = None
        if token is not None:
            color = self.app.get_css_variables().get(token)
            if color:
                label.stylize(Style(color=color, dim=dim))
        if str(node.data.path) in self._selected:
            label.stylize("reverse")
        return label

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

    def action_expand(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand:
            node.expand()
        # → on a file: nothing. Nick retired the "→ edit" duplicate —
        # ⏎ is the one edit key (todo-4 strip refactor).

    async def action_collapse(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node is self.root:
            await self.reveal_parent()   # left on the context row: climb
        elif node.allow_expand and node.is_expanded:
            # collapse_all, not collapse: re-expanding a folder shows a plain
            # child list, never the shape it happened to have last time
            # (Nick, 2026-08-22) — ← then → is a reset, like Finder's ⌥←
            node.collapse_all()
        elif node.parent is self.root:
            # ascending to the context row only to press ← again is a wasted
            # rung: climb straight up, landing focus on that row as it goes
            await self.reveal_parent()
        elif node.parent is not None:
            self._move_cursor(node.parent.line)   # scroll so it re-centers

    def action_toggle_fold(self) -> None:
        """TAB: fold the directory under the cursor open or shut.

        The two halves of →/← in one key (Nick, todo-5) — so TAB no
        longer descends into the details view; ⏎ is the one edit key.
        A file has nothing to fold, exactly as → has nothing to expand.
        Collapsing goes through ``collapse_all`` like ←, so re-opening a
        folder always shows a plain child list rather than the shape it
        happened to have last time.
        """
        node = self.cursor_node
        if node is None or not node.allow_expand:
            return
        if node.is_expanded:
            node.collapse_all()
        else:
            node.expand()

    # -- the clipboard: cut / paste / new directory (tree commands) --------------
    # The heavy lifting (liftable/place targets, the move worker, pane-bar
    # sync) stays on DetailsView, which mirrors the selection; the tree
    # owns the KEYS, so the commands exist exactly where the strip says.

    def action_cut(self) -> None:
        if self.app.lifted is not None:     # one selection at a time —
            return                          # no second cut while carrying
        self.app.query_one(DetailsView).action_cut()

    def action_copy(self) -> None:
        if self.app.lifted is not None:     # ditto: the clipboard is full
            return
        self.app.query_one(DetailsView).action_copy()

    def action_paste(self) -> None:
        if self.app.lifted is None:
            return
        self.app.query_one(DetailsView).action_paste()

    def action_new_directory(self) -> None:
        self.app.query_one(DetailsView).action_new_directory()

    def action_edit(self) -> None:
        if self.app.lifted is not None:     # no editing while carrying —
            return                          # the clipboard state has no ⏎
        details = self.app.query_one(DetailsView)
        node = self.cursor_node
        selection = self._selection_paths()
        # skip the debounce: a keypress within 150ms of landing on the
        # row must not descend into a stale (or empty) details view
        if len(selection) > 1:
            details.preview_bulk(selection, immediate=True)
        elif node is not None and node.data is not None:
            details.preview(Path(node.data.path), immediate=True)
        if details.can_edit():
            self.app.reveal_details()       # narrow: display before focusing
            details.focus()
        elif details.loading_bulk:          # descend once the merge lands
            self.app.reveal_details()
            details.focus_when_loaded()
        elif node is not None and node.data is not None:
            # read-only kinds never take focus; on narrow the same key
            # "views" them — details swaps in, the tree keeps the keys
            self.app.view_details()

    def action_close_view(self) -> None:
        details = self.app.query_one(DetailsView)
        if details.plan_preview_open():         # esc backs out of a plan
            details.action_plan_cancel()
            return
        if self.app.lifted is not None:         # …or a pending move
            self.app.cancel_lift()
            return
        self.app.close_details_view()

    def action_stay(self) -> None:
        pass

    async def action_refresh(self) -> None:
        """Force a re-read: drop the listing cache (SMB can serve stale
        mtimes), reload, and keep expansion, cursor, and details."""
        fs.clear_cache()
        node = self.cursor_node
        cursor = (Path(node.data.path)
                  if node is not None and node.data is not None
                  else Path(self.path))
        self._pending_restore = (self._expanded_paths(), cursor)
        await self.reload()
        await self._apply_restore()
        node = self.cursor_node
        if node is not None and node.data is not None:
            self.post_message(self.Selected(Path(node.data.path)))

    def action_cursor_up(self) -> None:
        # Home base: the browser never gives up focus implicitly.
        if self.cursor_line > 0:
            super().action_cursor_up()

    def action_cursor_first(self) -> None:
        self._move_cursor(min(1, self.last_line))   # line 0 is the context row

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

    def action_collapse_level(self) -> None:
        """Flatten this folder level: collapse the cursor's node, every
        sibling beside it, and all their offspring — where ← collapses one
        node, this returns the whole level to a plain sibling list. The
        cursor stays put on its node (now collapsed)."""
        node = self.cursor_node
        if node is None:
            return
        # siblings share a parent; on the root context row there are none,
        # so fall back to collapsing everything below the row itself
        parent = node.parent if node.parent is not None else node
        targets = parent.children or (parent,)
        for target in targets:
            if target.allow_expand:
                target.collapse_all()
        self._tree_lines            # rebuild so node.line reflects the collapse
        self._move_cursor(node.line)

    def _move_cursor(self, line: int) -> None:
        self.cursor_line = line
        self.scroll_to_line(line, animate=False)

    def cursor_to_gap(self, parent, index: int | None) -> None:
        """Land the cursor where a row that is now GONE used to sit —
        Finder's rule (Nick, 2026-08-25): the sibling that slid up into
        its place, or the one above it when the dead row was last, or
        the parent when it was the only child.

        ``parent`` is the reloaded folder node; ``index`` is where the
        row sat among its siblings BEFORE the reload (the nodes are
        rebuilt, so the caller has to read it first).
        """
        children = parent.children
        if index is None or not children:
            self._move_cursor(parent.line)      # nothing left beside it
            return
        heir = children[index] if index < len(children) else children[-1]
        self._move_cursor(heir.line)

    # -- centered cursor scrolling ---------------------------------------------
    # When the rows overflow the pane the cursor rides the center line: the
    # list is padded top and bottom with blank space so focus stays put while
    # the rows scroll under it. `before` rows sit above the cursor — for an
    # even-height pane that leaves one extra row below — and scroll_y tracks
    # the cursor line one-for-one (line L centered ⇒ scroll_y == L).

    def _center_offset(self) -> int | None:
        """Rows to show above the centered cursor, or None when the list fits
        the pane — then plain top-aligned scrolling stands in."""
        height = self.scrollable_content_region.height
        if height <= 0 or len(self._tree_lines) <= height:
            return None
        return (height - 1) // 2

    @property
    def max_scroll_y(self) -> int:
        # Centering lets the last row reach the center line, so scroll_y runs
        # all the way to the last line index — not virtual_height − viewport.
        if self._center_offset() is None:
            return super().max_scroll_y
        return max(0, len(self._tree_lines) - 1)

    def scroll_to_line(self, line: int, animate: bool = True) -> None:
        if self._center_offset() is None:
            super().scroll_to_line(line, animate=animate)
        else:                       # scroll_y == cursor line ⇒ line centered
            self.scroll_to(y=line, animate=animate, force=True,
                           immediate=not animate)

    def _pad_virtual_size(self) -> None:
        """Grow the scrollable height by the blank top/bottom padding, so the
        scrollbar reflects the range the centered cursor travels through."""
        if self._center_offset() is None:
            return
        height = self.scrollable_content_region.height
        self.virtual_size = Size(self.virtual_size.width,
                                 len(self._tree_lines) + height - 1)

    def _build(self) -> None:
        super()._build()
        self._pad_virtual_size()

    def on_resize(self, event: events.Resize) -> None:
        self._pad_virtual_size()

    # Expanding/collapsing changes the row count — which can flip the pane
    # between "fits" and "overflows" and can land while the layout is
    # mid-reflow (region height transiently 0). Either way scroll_y can end
    # up out of step with the centered cursor (the classic symptom: after an
    # expand the view snaps to the top row instead of the cursor). Re-assert
    # scroll_y == cursor_line once the refresh has settled. call_after_refresh
    # runs after the rebuild+load-driven scroll, so it corrects a bad landing
    # rather than racing it.
    def on_tree_node_expanded(self, ev) -> None:
        self._recenter_cursor()

    def on_tree_node_collapsed(self, ev) -> None:
        self._recenter_cursor()

    def _recenter_cursor(self) -> None:
        def recenter() -> None:
            if self.cursor_line >= 0:
                self.scroll_to_line(self.cursor_line, animate=False)
        self.call_after_refresh(recenter)

    def render_line(self, y: int) -> Strip:
        # Shift the window down by `before`: content row (y + scroll_y) maps to
        # tree line (… − before), so line scroll_y lands on the center row.
        scroll_x, scroll_y = self.scroll_offset
        before = self._center_offset() or 0
        index = y + scroll_y - before
        if index < 0:               # blank padding above the first row
            return Strip.blank(self.size.width, self.rich_style)
        return self._render_line(index, scroll_x, scroll_x + self.size.width,
                                 self.rich_style)

    def _tint_level(self):
        """The child list whose guide column the cursor tints, or None.

        A guide column belongs to a node's parent, so the parent names the
        level. The cursor tints its OWN level — its siblings' spine — except
        over an expanded folder, which tints its CHILDREN's spine instead
        (Nick, 2026-09-03): the level type-ahead searches is the level that
        lights up, so the tint tracks where typing would land.

        It is part of the line cache key: every row under it renders
        differently depending on it, including rows whose path holds
        neither cursor node.
        """
        cursor = self.cursor_node if self.has_focus else None
        if cursor is None:
            return None
        return cursor if self._is_open_folder(cursor) else cursor.parent

    def watch_cursor_line(self, previous_line: int, line: int) -> None:
        super().watch_cursor_line(previous_line, line)
        # Upstream refreshes only the lines containing the old and new cursor
        # nodes. The tint spans a whole sibling level (2026-09-01), so a move
        # ACROSS levels also changes every row hanging off the level being
        # left and the one being entered — refresh both parents' subtrees.
        for at in (previous_line, line):
            node = self._get_node(at)
            if node is not None and node.parent is not None:
                self._refresh_node(node.parent)

    def _render_line(self, y: int, x1: int, x2: int, base_style: Style) -> Strip:
        # Reimplemented from Textual's Tree solely to un-stick the selected
        # guide style. Upstream OR-accumulates `selected` down the path, so the
        # cursor folder tints the guides of its ENTIRE subtree — every nested
        # ├─/╰─ turns blue. We tint exactly one column: the cursor's own
        # sibling level (see `_tint_level` and the loop below).
        tree_lines = self._tree_lines
        width = self.size.width

        if y >= len(tree_lines):
            return Strip.blank(width, base_style)

        line = tree_lines[y]

        is_hover = self.hover_line >= 0 and any(node._hover for node in line.path)

        cache_key = (
            y,
            is_hover,
            width,
            self._updates,
            self._pseudo_class_state,
            tuple(node._updates for node in line.path),
            self._tint_level(),
        )
        if cache_key in self._line_cache:
            strip = self._line_cache[cache_key]
        else:
            base_hidden = self.get_component_styles("tree--guides").color.a == 0
            hover_hidden = self.get_component_styles("tree--guides-hover").color.a == 0
            selected_hidden = (
                self.get_component_styles("tree--guides-selected").color.a == 0
            )

            base_guide_style = self.get_component_rich_style(
                "tree--guides", partial=True
            )
            guide_hover_style = base_guide_style + self.get_component_rich_style(
                "tree--guides-hover", partial=True
            )
            guide_selected_style = base_guide_style + self.get_component_rich_style(
                "tree--guides-selected", partial=True
            )

            hover = line.path[0]._hover
            # Which guide column the cursor lights up: the spine of the
            # level `_tint_level` names — its siblings', or its children's
            # when it is an expanded folder. A node's column belongs to its
            # parent's child list, so "parent is that level" is the whole
            # test, and the tint runs the full height of the level plus the
            # subtrees hanging off it.
            siblings = self._tint_level()

            def get_guides(style: Style, hidden: bool):
                if self.show_guides and not hidden:
                    lines = self.LINES["default"]
                    if style.bold:
                        lines = self.LINES["bold"]
                    elif style.underline2:
                        lines = self.LINES["double"]
                else:
                    lines = ("  ", "  ", "  ", "  ")

                guide_depth = max(0, self.guide_depth - 2)
                return tuple(
                    f"{characters[0]}{characters[1] * guide_depth} "
                    for characters in lines
                )

            if is_hover:
                line_style = self.get_component_rich_style("tree--highlight-line")
            else:
                line_style = base_style

            line_style += Style(meta={"line": y})

            guides = Text(style=line_style)
            guides_append = guides.append

            guide_style = base_guide_style

            hidden = True
            for node in line.path[1:]:
                # Reset both per iteration: upstream let `selected` stay sticky
                # so guide_style only ever escalated, but a column outside the
                # cursor's level must be able to fall back to the base style.
                guide_style = base_guide_style
                hidden = base_hidden
                if hover:
                    guide_style = guide_hover_style
                    hidden = hover_hidden
                if siblings is not None and node.parent is siblings:
                    guide_style = guide_selected_style
                    hidden = selected_hidden

                space, vertical, _, _ = get_guides(guide_style, hidden)
                guide = space if node.is_last else vertical
                if node != line.path[-1]:
                    guides_append(guide, style=guide_style)
                hover = hover or node._hover

            label_style = self.get_component_rich_style("tree--label", partial=True)
            if self.hover_line == y:
                label_style += self.get_component_rich_style(
                    "tree--highlight", partial=True
                )
            if self.cursor_line == y:
                label_style += self.get_component_rich_style(
                    "tree--cursor", partial=False
                )

            if len(line.path) > 1:
                _, _, terminator, cross = get_guides(guide_style, hidden)
                guide = terminator if line.last else cross
                # The last guide column ends in a space; that cell is the
                # one adjacent to the rightmost box character, so it wears
                # the LABEL style, not the guide's — the selection color
                # starts there (2026-08-23). Box characters keep their own.
                # A shift-marked row reverses its whole label, so the pad
                # reverses with it or the block starts a cell late.
                pad_style = label_style
                data = line.path[-1].data
                if data is not None and str(data.path) in self._selected:
                    pad_style += Style(reverse=True)
                guides.append(guide[:-1], style=guide_style)
                guides.append(guide[-1:], style=pad_style)

            label = self.render_label(line.path[-1], line_style, label_style).copy()
            label.stylize(Style(meta={"node": line.node._id}))
            guides.append(label)

            segments = list(guides.render(self.app.console))
            pad_width = max(self.virtual_size.width, width)
            segments = line_pad(segments, 0, pad_width - guides.cell_len, line_style)
            strip = self._line_cache[cache_key] = Strip(segments)

        strip = strip.crop(x1, x2)
        return strip

    def _refresh_line(self, line: int) -> None:
        # Tree-line index → its screen row, accounting for the center shift.
        before = self._center_offset() or 0
        region = Region(0, line - self.scroll_offset.y + before,
                        self.size.width, 1)
        self.refresh(region)

    # -- Finder-style type-to-select ------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Typed text jumps the cursor to the closest visible name."""
        if not event.is_printable or event.character is None:
            self._reset_search()   # navigation cancels the type-ahead
            return
        if event.character == " " and not self._search_buffer:
            return   # a bare space stays a key; mid-search it is text
        event.stop()
        event.prevent_default()
        if not self._search_buffer:
            self._search_scope = self._scope_node()
        self._search_buffer += event.character
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(TYPE_SEARCH_SECONDS,
                                            self._reset_search)
        self._jump_to(self._search_buffer)

    def _reset_search(self) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = None
        self._search_buffer = ""
        self._search_scope = None

    def _scope_node(self):
        """Which folder a type-ahead searches inside. An EXPANDED folder
        under the cursor searches its own children — typing descends the
        way ↓ then typing used to, and the folder itself is not a
        candidate (Nick, 2026-09-02). Anything else searches the folder
        holding the cursor: its siblings only, never rows above or below
        that belong to other folders. Pinned for the life of the buffer,
        so the second keystroke doesn't descend into whatever child the
        first one landed on."""
        node = self.cursor_node
        if node is None:
            return None
        if self._is_open_folder(node):
            return node                 # loading/empty folders fall through
        return node.parent if node.parent is not None else node

    @staticmethod
    def _is_open_folder(node) -> bool:
        """An expanded folder with children already loaded — the case where
        the cursor's level is its own child list rather than its siblings'.
        Shared by type-ahead scope and the guide tint so the two agree."""
        return bool(node.allow_expand and node.is_expanded
                    and any(child.data is not None for child in node.children))

    def _jump_to(self, text: str) -> None:
        text = text.lower()
        parent = self._search_scope
        if parent is None:
            return
        rows = [(child.line, Path(child.data.path).name.lower())
                for child in parent.children
                if child.data is not None and child.line >= 0]
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
        if self._sel_keep:                  # our own shift-move: selection
            self._sel_keep = False          # survives, Selected covers it
            return
        self._clear_selection()
        if ev.node.data is not None and not self.has_class("-editing"):
            self.post_message(self.Selected(Path(ev.node.data.path)))


class TreeView(Vertical):
    """The Tree View: Path Input above the library tree, one bordered
    pane. The border and focus state live HERE — the container is the
    view; the input and the tree are what it shows. (:focus-within
    lights the pane whichever of the two owns focus.)"""

    def __init__(self, start_dir: Path, **kw) -> None:
        super().__init__(**kw)
        self._start_dir = start_dir

    def compose(self):
        yield PathInput(value=str(self._start_dir))
        yield LibraryTree(self._start_dir)
