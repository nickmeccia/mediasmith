"""Right pane: details of the highlighted path; an editable form for
audio and epub selections.

Composed ONCE — one hidden panel per file kind, plus a fixed pool of
label+input rows per editable kind; a selection change only swaps values
and visibility. Never rebuild this pane with ``remove_children()`` per
selection: a cancelled removal can leak CancelledError into the app's
message pump, which Textual treats as a silent quit (reproduced crash in
the v1 prototype).

Editing model: filename first, then one input per metadata field. up/down
(and tab/shift+tab) move between inputs; nothing is written until ^s (or
the save button). esc releases focus back to the browser — through a
confirm modal when edits are pending.
"""

from __future__ import annotations

import io
import os
import subprocess
from pathlib import Path

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from . import (adapters, artfetch, booksort, calibre, epub, folderize, fs,
               gif, imageops, kinds, multiartist, omnibus, posters, srt,
               standardize, subsync, videofolder)
from .actions import Action, ActionBar, ActionButton
from .images import image_widget

PANELS = [kinds.AUDIO, kinds.VIDEO, kinds.BOOK, kinds.IMAGE,
          kinds.FOLDER, kinds.OTHER]


def _image_size(data: bytes | None) -> tuple[int, int] | None:
    """Pixel dimensions of encoded image bytes, or None if undecodable.
    PIL reads the header lazily — no full decode for the size."""
    if not data:
        return None
    try:
        from PIL import Image as PILImage
        return PILImage.open(io.BytesIO(data)).size
    except Exception:
        return None


PANE_ACTIONS = [
    # the one bar at the pane's foot, composed once with the full palette;
    # selection changes only show/hide buttons (_sync_pane_bar). Words,
    # keys, and order per todo-4 "Button Refactor"; where Nick's chord was
    # reserved (see actions.RESERVED_KEYS) the nearest safe letter stands
    # in — every substitution is logged in notes/qa/todo-2.md. Chords are
    # view-scoped now: they fire only while Details view holds focus
    # (App.on_key), with FieldInput forwarding the Input-eaten ones.
    Action("save", "save", "s", button_id="save-btn"),
    # every file kind can be handed to the OS (Nick, 2026-08-22): "open"
    # is ALWAYS the second button, so it lives second in this list — the
    # bar composes in list order and context only shows/hides. It
    # replaces video's old "watch"; ^o cost "write opf" its chord (→ ^w)
    Action("open", "open", "o"),
    # -- book (epub) — spec order: split omnibus rides right after save
    Action("split_omnibus", "split omnibus", "b"),
    # ^m is reserved (enter alias): ^t stands in — "conver^t to mobi"
    Action("convert_mobi", "convert to mobi", "t"),
    Action("convert_azw3", "convert to azw3", "a"),
    # ^o is "open" everywhere now: ^w stands in — "^write opf"
    Action("create_opf", "write opf", "w"),
    # ^c is reserved (interrupt): ^n stands in — "clea^n". The tree's ^n
    # (new directory) lives in a different state, so no collision.
    Action("standardize", "clean", "n"),
    Action("book_cover", "upload cover", "u"),
    Action("extract_cover", "extract cover", "e"),
    # a single epub's sort is "folderize" now (spec); the FOLDER context
    # keeps the old word via its own button below — same handlers
    Action("sort_book", "folderize", "f"),
    # -- mobi/azw3
    Action("convert_epub", "convert to epub", "e"),
    # -- image — rotate/resize precede the converts (spec order)
    Action("rotate", "rotate", "r"),
    # ^z is reserved (suspend): ^e stands in — "r^esize" (the old chord)
    Action("resize", "resize", "e"),
    # ^j is reserved (newline alias): ^g stands in — "convert to jp^g"
    Action("convert_jpg", "convert to jpg", "g"),
    Action("convert_png", "convert to png", "p"),
    Action("convert_tiff", "convert to tiff", "t"),
    Action("convert_webp", "convert to webp", "w"),
    # -- video: the subtitle suite, then posters/gif (spec order, minus
    # "watch" — it is the universal "open" button above now)
    Action("get_subs", "fetch subtitles", "f"),
    # ^c reserved: ^l stands in — "c^lean subs"
    Action("clean_subs", "clean subs", "l"),
    # ^h is reserved (backspace alias): ^t stands in — "shif^t subs"
    Action("shift_subs", "shift subs", "t"),
    Action("download_posters", "download posters", "p"),
    Action("gif", "make gif", "g"),
    # the ebook gesture on a video (2026-08-22); ^f/^l/^t are the
    # subtitle suite and ^o is "open", so "fol^derize" takes ^d (an Input
    # editing chord, which FieldInput forwards to a visible button)
    Action("folderize_video", "folderize", "d"),
    # -- folder probes (todo-4 lists no renames for these): sort keeps
    # its folder word so a folder never shows two "folderize" buttons
    Action("sort", "sort", "o"),
    Action("folderize", "folderize", "l"),
    Action("strip_multi_artist", "strip multi-artist", "x"),
    # while any plan preview is up, these two own the bar
    Action("plan_apply", "apply", "a"),
    Action("plan_cancel", "cancel"),            # esc cancels too
    # new-directory/delete BUTTONS are gone (tree commands now: ^n, ^DEL);
    # their action_* handlers below remain — the tree bindings call them.
]

EDITABLE_KINDS: frozenset[str] = frozenset(PANELS)
"""Every kind whose details can take focus for editing — which is all of
them: every selection can at least be renamed. Audio and book carry a
metadata form; image, plain folder, video, and other edit as a
filename-only form (no fields) — rename is the edit, modeled on the
folder panel. Album-like folders never reach here: they descend into the
bulk form of their contents before the folder panel is consulted."""

DEBOUNCE_SECONDS = 0.15

LABEL_GUTTER = 2   # spaces between a field label and its input


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n:.0f} B"
        n /= 1024


def _mk(text: str) -> str:
    """Escape a filename for Textual content markup."""
    return text.replace("[", r"\[")


PLAN_PREVIEW_LINES = 40


def render_plan(plan) -> str:
    """The folderize preview: the structure the apply button will build."""
    n = len(plan.moves)
    lines = [f"{n} file{'s' if n != 1 else ''} to organize:", ""]
    structure = plan.structure()
    for artist in sorted(structure, key=str.lower):
        albums = structure[artist]
        lines.append(f"  [bold]{_mk(artist)}/[/]")
        for album in sorted(albums, key=str.lower):
            count = albums[album]
            lines.append(f"    {_mk(album)}/  [dim]({count} "
                         f"file{'s' if count != 1 else ''})[/]")
    if plan.skips:
        lines.append("")
        lines.append(f"  [bold]{_mk(folderize.SKIPPED_DIR_NAME)}/[/]  "
                     f"[dim]({len(plan.skips)} missing tags)[/]")
        for skip in plan.skips[:8]:
            lines.append(f"    {_mk(skip.source.name)}  [dim]{skip.reason}[/]")
        if len(plan.skips) > 8:
            lines.append(f"    [dim]…and {len(plan.skips) - 8} more[/]")
    if len(lines) > PLAN_PREVIEW_LINES:
        hidden = len(lines) - PLAN_PREVIEW_LINES
        lines = lines[:PLAN_PREVIEW_LINES] + [f"[dim]…and {hidden} more lines[/]"]
    return "\n".join(lines)


GROUP_PREVIEW_FILES = 6


def render_multiartist_plan(plan: multiartist.MultiArtistPlan) -> str:
    """The fix-multi-artist preview: per album, the main artist every
    track will be set to, then each file's tangled values."""
    n, g = plan.file_count, len(plan.groups)
    lines = [f"{n} file{'s' if n != 1 else ''} across "
             f"{g} album{'s' if g != 1 else ''}:", ""]
    for group in plan.groups:
        lines.append(f"  [bold]{_mk(group.album or group.folder.name)}[/]"
                     f" → {_mk(group.main)}")
        for change in group.changes[:GROUP_PREVIEW_FILES]:
            old = " / ".join(change.artists or change.album_artists)
            lines.append(f"    {_mk(change.path.name)}  [dim]{_mk(old)}[/]")
        if len(group.changes) > GROUP_PREVIEW_FILES:
            more = len(group.changes) - GROUP_PREVIEW_FILES
            lines.append(f"    [dim]…and {more} more[/]")
    if len(lines) > PLAN_PREVIEW_LINES:
        hidden = len(lines) - PLAN_PREVIEW_LINES
        lines = lines[:PLAN_PREVIEW_LINES] + [f"[dim]…and {hidden} more lines[/]"]
    return "\n".join(lines)


def render_sort_plan(plan: booksort.SortPlan) -> str:
    """The sort preview: each wrapper folder and the files moving in."""
    n, g = plan.file_count, len(plan.groups)
    lines = [f"{n} file{'s' if n != 1 else ''} into "
             f"{g} book folder{'s' if g != 1 else ''}:", ""]
    for group in plan.groups:
        lines.append(f"  [bold]{_mk(group.folder_name)}/[/]")
        for file in group.files:
            lines.append(f"    {_mk(file.name)}")
    if plan.skips:
        lines.append("")
        for skip in plan.skips[:8]:
            lines.append(f"  {_mk(skip.source.name)}  [dim]{skip.reason}[/]")
        if len(plan.skips) > 8:
            lines.append(f"  [dim]…and {len(plan.skips) - 8} more[/]")
    if len(lines) > PLAN_PREVIEW_LINES:
        hidden = len(lines) - PLAN_PREVIEW_LINES
        lines = lines[:PLAN_PREVIEW_LINES] + [f"[dim]…and {hidden} more lines[/]"]
    return "\n".join(lines)


def render_omnibus_plan(plan: omnibus.OmnibusPlan) -> str:
    """The split-omnibus preview: each detected book and the epub the
    apply button will write beside the source."""
    n = len(plan.books)
    lines = [f'{n} books found in "{_mk(plan.title)}":', ""]
    for i, book in enumerate(plan.books, 1):
        lines.append(f"  {i}. [bold]{_mk(book.label)}[/]  "
                     f"[dim]({book.chapters} chapter"
                     f"{'s' if book.chapters != 1 else ''})[/]")
        lines.append(f"     → {_mk(book.filename)}")
    if len(lines) > PLAN_PREVIEW_LINES:
        hidden = len(lines) - PLAN_PREVIEW_LINES
        lines = lines[:PLAN_PREVIEW_LINES] + [f"[dim]…and {hidden} more lines[/]"]
    return "\n".join(lines)


WORD_BINDINGS = [
    # Input only binds ctrl+arrow word combos; macOS option arrives as alt
    # under the kitty protocol, so bind those names too (opt+shift = select
    # by word, matching native macOS text fields).
    Binding("alt+left", "cursor_left_word", show=False),
    Binding("alt+right", "cursor_right_word", show=False),
    Binding("alt+shift+left", "cursor_left_word(True)", show=False),
    Binding("alt+shift+right", "cursor_right_word(True)", show=False),
]


class FieldInput(Input):
    """An Input whose ← ascends the pane hierarchy when it can't move the
    text cursor: at the start of the text it acts like esc (release back
    to the browser, confirm modal when dirty); anywhere else it is normal
    cursor movement. The symmetric partner of the browser's → descend.

    Focus never selects the text — the cursor just lands after the final
    character."""

    BINDINGS = [Binding("left", "left_or_release", show=False),
                *WORD_BINDINGS]

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("select_on_focus", False)
        super().__init__(*args, **kwargs)

    def on_focus(self) -> None:
        self.cursor_position = len(self.value)

    def on_key(self, event) -> None:
        # A chord printed on a visible button outranks Input's editing
        # chords (^a home, ^e end, ^u clear, …): Nick's button letters
        # include Input-eaten ones (todo-4 Button Refactor), and the
        # printed button is the contract. Unclaimed chords still edit.
        if not event.key.startswith("ctrl+"):
            return
        pane = self.screen.query_one(DetailsView)
        action = pane.action_for_key(event.key)
        if action is not None:
            event.stop()
            event.prevent_default()
            pane.trigger(action)

    def action_left_or_release(self) -> None:
        if self.cursor_position == 0:
            self.screen.query_one(DetailsView).action_release()
        else:
            self.action_cursor_left()


class ArtField(Vertical, can_focus=True):
    """The album-art slot: a labeled, focusable field like any other, so
    it sits in the ↑↓ cycle. New art arrives via the method buttons
    beneath it (path entry, online fetch); ↓ reaches them."""


class ArtPathInput(FieldInput):
    """Art method 1: type a path to an image, tab-completing against the
    filesystem (directories and image files only). Enter commits the file
    as pending art; esc (or ← at the start) cancels back to the buttons."""

    BINDINGS = [
        Binding("tab", "complete", show=False, priority=True),
        Binding("escape", "cancel", show=False),
    ]

    def _matches(self) -> list[fs.CachedPath]:
        base, prefix = os.path.split(self.value)
        prefix = prefix.lower()
        return [child for child in fs.cached_children(base or "/")
                if child.name.lower().startswith(prefix)
                and (child.is_dir()
                     or kinds.kind_of(child, is_dir=False) == kinds.IMAGE)]

    def action_complete(self) -> None:
        matches = self._matches()
        if not matches:
            return
        first = matches[0]
        self.value = str(first) + ("/" if first.is_dir() else "")
        self.cursor_position = len(self.value)

    def action_cancel(self) -> None:
        pane = self.screen.query_one(DetailsView)
        pane._hide_art_path()
        pane._art_buttons()[0].focus()

    def action_left_or_release(self) -> None:
        if self.cursor_position == 0:
            self.action_cancel()
        else:
            self.action_cursor_left()

    def on_blur(self) -> None:
        # focus moved on (any reason): the method is no longer active
        if self.parent is not None:
            self.parent.display = False


class CoverPathInput(FieldInput):
    """Book cover method: type a path to an image to write into the epub,
    tab-completing against the filesystem (directories and image files).
    Enter applies (writes the cover); esc (or ← at the start) cancels.
    Mirrors ArtPathInput; the book cover has no online-fetch method yet."""

    BINDINGS = [
        Binding("tab", "complete", show=False, priority=True),
        Binding("escape", "cancel", show=False),
    ]

    def _matches(self) -> list[fs.CachedPath]:
        base, prefix = os.path.split(self.value)
        prefix = prefix.lower()
        return [child for child in fs.cached_children(base or "/")
                if child.name.lower().startswith(prefix)
                and (child.is_dir()
                     or kinds.kind_of(child, is_dir=False) == kinds.IMAGE)]

    def action_complete(self) -> None:
        matches = self._matches()
        if not matches:
            return
        first = matches[0]
        self.value = str(first) + ("/" if first.is_dir() else "")
        self.cursor_position = len(self.value)

    def action_cancel(self) -> None:
        self.screen.query_one(DetailsView)._hide_book_cover_path()

    def action_left_or_release(self) -> None:
        if self.cursor_position == 0:
            self.action_cancel()
        else:
            self.action_cursor_left()

    def on_blur(self) -> None:
        if self.parent is not None:
            self.parent.display = False


SHIFT_HINT = "←→ 0.1s · ⇧←→ 1s · ⇞⇟ 10s · ^s write · esc close"


def launch(path: Path) -> None:
    """Open a file in its default app (the watch action's seam —
    monkeypatch this in tests, subprocess.run shares Popen)."""
    subprocess.Popen(["open", str(path)])


class ShiftControl(Static, can_focus=True):
    """The shift-subs wizard: a focusable readout of the pending total
    shift. Arrow keys nudge; every write recomputes from the ORIGINAL
    parse (v1's nudge model) so back-and-forth never loses cues. The
    inline-div wizard pattern (art path is the other exemplar): toggled
    under the fields, never a modal."""

    BINDINGS = [
        Binding("left", "nudge(-100)", show=False),
        Binding("right", "nudge(100)", show=False),
        Binding("shift+left", "nudge(-1000)", show=False),
        Binding("shift+right", "nudge(1000)", show=False),
        Binding("pageup", "nudge(10000)", show=False),
        Binding("pagedown", "nudge(-10000)", show=False),
        Binding("escape", "close", show=False),
    ]

    def action_nudge(self, delta_ms: int) -> None:
        self.screen.query_one(DetailsView)._shift_nudge(delta_ms)

    def action_close(self) -> None:
        self.screen.query_one(DetailsView)._shift_close()


class EditForm(Vertical):
    """A column of label+input rows drawing on a fixed pool (composed once,
    see the module docstring): ``set_fields`` re-labels, re-fills, and
    shows/hides rows — it never adds or removes widgets."""

    def __init__(self, pool: int, **kw) -> None:
        super().__init__(**kw)
        self._pool = pool
        self._names: list[str] = []
        self._mixed: frozenset[str] = frozenset()

    def compose(self):
        for _ in range(self._pool):
            with Horizontal(classes="frow"):
                yield Label("", classes="fkey")
                yield FieldInput(placeholder="-", compact=True, classes="fval")
                yield Static("", classes="fmark")

    def on_mount(self) -> None:
        for row in self.query(".frow"):
            row.display = False

    def _rows(self):
        return list(self.children)

    label_width: int = 0
    """The padded label column width of the current field set."""

    def set_fields(self, fields: dict[str, str],
                   mixed: frozenset[str] = frozenset()) -> None:
        """``mixed`` names (bulk view: values diverge across the files)
        show empty with a "(mixed)" placeholder; typing into one means
        "apply this to every file"."""
        self._names = list(fields)[:self._pool]
        self._mixed = mixed
        labels = adapters.FIELD_LABELS
        width = max((len(labels.get(n, n)) for n in self._names),
                    default=0) + LABEL_GUTTER
        self.label_width = width
        for i, row in enumerate(self._rows()):
            if i < len(self._names):
                name = self._names[i]
                row.query_one(Label).update(f"{labels.get(name, name):<{width}}")
                field = row.query_one(Input)
                field.value = fields[name]
                field.placeholder = "(mixed)" if name in mixed else "-"
                row.query_one(".fmark", Static).update("")
                row.display = True
            else:
                row.display = False

    def _edited(self, name: str, value: str, baseline: dict[str, str]) -> bool:
        """Whether a field counts as edited (and so will be written).
        A mixed field is edited only once it holds text — emptying it back
        out returns it to "leave every file alone"; deleting a mixed tag
        everywhere is deliberately unsupported."""
        if name in self._mixed:
            return value != ""
        return value != baseline.get(name, "")

    def changed_fields(self, baseline: dict[str, str]) -> dict[str, str]:
        """The fields a save must write: exactly the ✓-marked ones."""
        rows = self._rows()
        return {name: value for i, name in enumerate(self._names)
                if self._edited(
                    name, value := rows[i].query_one(Input).value, baseline)}

    def refresh_marks(self, baseline: dict[str, str]) -> None:
        """iTunes-style ✓ after each field whose value differs from
        ``baseline`` — the visible record of what a save will write."""
        rows = self._rows()
        for i, name in enumerate(self._names):
            edited = self._edited(name, rows[i].query_one(Input).value,
                                  baseline)
            rows[i].query_one(".fmark", Static).update("✓" if edited else "")

    def set_values(self, fields: dict[str, str]) -> None:
        """Refill values only (same field names) — the discard path."""
        rows = self._rows()
        for i, name in enumerate(self._names):
            rows[i].query_one(Input).value = fields.get(name, "")

    def values(self) -> dict[str, str]:
        rows = self._rows()
        return {name: rows[i].query_one(Input).value
                for i, name in enumerate(self._names)}

    def inputs(self) -> list[Input]:
        rows = self._rows()
        return [rows[i].query_one(Input) for i in range(len(self._names))]


class OmniInput(FieldInput):
    """A split-form field that forwards ^a to the ^apply chord. A plain
    Input binds ctrl+a to cursor-home and eats it, so the printed ^apply
    wouldn't fire while a field is focused — unlike ^s (save), whose letter
    Input doesn't grab. Home key still homes the cursor."""

    BINDINGS = [Binding("ctrl+a", "omni_apply", show=False)]

    def action_omni_apply(self) -> None:
        self.screen.query_one(DetailsView).action_plan_apply()


class OmnibusForm(Vertical):
    """The editable split-omnibus plan: three shared fields — author,
    author sort, series — then one (title, series no.) block per
    constituent book, so the user corrects the NCX's guesses (which mangle
    titles like "Book01 The Fifth Season") BEFORE a single file is written.

    Composed ONCE with a fixed pool of book blocks (the compose-once rule);
    ``set_plan`` only swaps values and shows/hides blocks — never rebuilt."""

    POOL = 20   # constituent books per omnibus; more falls back to preview

    GLOBAL = [("author", "omni-author"),
              ("author sort", "omni-author-sort"),
              ("series", "omni-series")]

    def compose(self):
        width = len("series no.") + LABEL_GUTTER
        yield Static("", id="omni-source", classes="omni-source")
        for label, wid in self.GLOBAL:
            with Horizontal(classes="frow"):
                yield Label(f"{label:<{width}}", classes="fkey")
                yield OmniInput(id=wid, compact=True, classes="fval")
        for i in range(self.POOL):
            with Vertical(classes="omni-book", id=f"omni-book-{i}"):
                yield Label("", id=f"omni-head-{i}", classes="omni-head")
                with Horizontal(classes="frow"):
                    yield Label(f"{'title':<{width}}", classes="fkey")
                    yield OmniInput(id=f"omni-title-{i}", compact=True,
                                    classes="fval")
                with Horizontal(classes="frow"):
                    yield Label(f"{'series no.':<{width}}", classes="fkey")
                    yield OmniInput(id=f"omni-no-{i}", compact=True,
                                    type="integer", classes="fval")

    def on_mount(self) -> None:
        for block in self.query(".omni-book"):
            block.display = False

    def set_plan(self, plan) -> None:
        self.query_one("#omni-source", Static).update(plan.source.name)
        self.query_one("#omni-author", Input).value = plan.author
        self.query_one("#omni-author-sort", Input).value = plan.author_sort
        self.query_one("#omni-series", Input).value = plan.title
        for i in range(self.POOL):
            block = self.query_one(f"#omni-book-{i}")
            if i < len(plan.books):
                book = plan.books[i]
                self.query_one(f"#omni-head-{i}", Label).update(f"Book {i + 1}")
                self.query_one(f"#omni-title-{i}", Input).value = book.label
                self.query_one(f"#omni-no-{i}", Input).value = str(
                    book.series_index)
                block.display = True
            else:
                block.display = False

    def inputs(self, count: int) -> list[Input]:
        """Every focusable field top-to-bottom: the three shared fields,
        then each shown book's title and series-no — the ↑↓/⇥ walk order."""
        items = [self.query_one(f"#{wid}", Input) for _, wid in self.GLOBAL]
        for i in range(count):
            items.append(self.query_one(f"#omni-title-{i}", Input))
            items.append(self.query_one(f"#omni-no-{i}", Input))
        return items

    def edits(self, count: int) -> tuple[str, str, str, list[tuple[str, str]]]:
        """What ``apply`` reads: (author, author sort, series, [(title,
        series-no) per book]) — raw strings, parsed by omnibus.with_edits."""
        g = {wid: self.query_one(f"#{wid}", Input).value.strip()
             for _, wid in self.GLOBAL}
        books = [(self.query_one(f"#omni-title-{i}", Input).value.strip(),
                  self.query_one(f"#omni-no-{i}", Input).value.strip())
                 for i in range(count)]
        return (g["omni-author"], g["omni-author-sort"], g["omni-series"],
                books)


class ConfirmSave(ModalScreen[str]):
    """esc with pending edits: save them, discard them, or keep editing."""

    BINDINGS = [
        Binding("s", "choose('save')", "save"),
        Binding("d", "choose('discard')", "discard"),
        Binding("escape", "choose('cancel')", "keep editing"),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._filename = name
        self._decided = False

    def _decide(self, choice: str) -> None:
        # two keys inside one frame (esc esc, enter+esc…) would dismiss
        # twice — the second pop has no screen left and ScreenStackError
        # is app death (fuzz seed 10, 2026-07-16). First answer wins.
        if self._decided:
            return
        self._decided = True
        self.dismiss(choice)

    def compose(self):
        with Vertical(id="confirm-box"):
            yield Label(f"Save changes to {self._filename}?", id="confirm-msg")
            with Horizontal(id="confirm-buttons"):
                yield Button("Save", id="save", variant="primary")
                yield Button("Discard", id="discard")
                yield Button("Keep editing", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#save", Button).focus()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self._decide(ev.button.id or "cancel")

    def action_choose(self, choice: str) -> None:
        self._decide(choice)


class DetailsView(VerticalScroll, can_focus=True):

    BINDINGS = [
        Binding("escape", "release", "back", show=False),
        # ←/→ : between the buttons of an action bar when one is focused;
        # otherwise ← duplicates esc (inside a field, FieldInput owns ←)
        Binding("left", "pane_left", "back", show=False),
        Binding("right", "pane_right", show=False),
        # action keys (^s, ^o, …) are not bound here: the app dispatches
        # any ctrl chord printed on a visible action button, so they work
        # from the tree too (read-only kinds never focus this pane)
        Binding("up", "field_prev", show=False),
        Binding("down", "field_next", show=False),
        # form-style cycling; also shadows the Screen's focus cycling so
        # focus never escapes the pane except through esc
        Binding("tab", "field_next", show=False),
        Binding("shift+tab", "field_prev", show=False),
    ]

    class Saved(Message):
        """A save finished; ``renamed`` when the filename changed."""

        def __init__(self, old: Path, new: Path) -> None:
            super().__init__()
            self.old = old
            self.new = new
            self.renamed = old != new

    class FileCreated(Message):
        """An action produced a new file (conversion, cover export, …);
        the tree should pick it up without losing its place."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class FolderChanged(Message):
        """An action rearranged a folder's subtree (folderize, …); the
        tree should re-list that node."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class FolderCreated(Message):
        """New-folder made ``path``; the tree should show it, put the
        cursor on it, and descend into the rename field (Finder's flow)."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class Deleted(Message):
        """``path`` went to the Trash; the tree should re-list its parent
        and move the cursor off the dead row."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class Wrapped(Message):
        """A single file was wrapped into its own new directory beside
        where it was (an ebook into ``Author Sort - Title/``, a video into
        a folder named after it); ``path`` is where it landed. The tree
        should re-list, expand the wrapper, and drop the cursor on the
        file — editable, like new-folder's flow one level deeper."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def can_edit(self) -> bool:
        """Focus may enter this pane only when the shown kind is editable."""
        return self.kind in EDITABLE_KINDS and self._readable

    def _open_target(self) -> Path | None:
        """The single file "open" hands to the OS, or None. Any one file
        qualifies — a folder does not (its ^o is the sort button), and
        neither does a bulk selection (one gesture, one file)."""
        if (self.paths is not None or self.path is None
                or self.kind in (None, kinds.FOLDER)):
            return None
        return self.path        # the kind already says it is a file

    def __init__(self, *, images: str = "auto", **kw) -> None:
        super().__init__(**kw)
        self.images = images
        self.path: Path | None = None
        self.paths: list[Path] | None = None    # bulk selection, when set
        self.kind: str | None = None
        self._readable = False
        self._focus_after_load = False
        self._baseline: tuple[str, dict[str, str]] | None = None
        self._pending: Path | None = None
        self._debounce = None
        self._pending_art: bytes | None = None   # unsaved replacement art
        self._baseline_art: bytes | None = None  # what discard restores
        self._art_candidates: list[artfetch.CoverCandidate] = []
        self._art_index = 0
        self._book_cover = False    # shown book has an extractable cover
        self._omnibus_ready = False     # probe: this epub holds ≥2 books
        self._omnibus_plan: omnibus.OmnibusPlan | None = None
        self._omnibus_editing = False   # the editable split form is on show
        self._folderize_ready = False   # probe: this folder has work to do
        self._folderize_plan: folderize.FolderizePlan | None = None
        self._standardize_ready = False     # probe: uncleaned epubs below
        self._sort_ready = False            # probe: unwrapped books below
        self._sort_plan: booksort.SortPlan | None = None
        self._multiartist_ready = False
        self._multiartist_plan: multiartist.MultiArtistPlan | None = None
        self._video_srt: Path | None = None     # cleanable/shiftable sibling
        self._gif_open = False
        self._resize_open = False
        self._resize_base: tuple[int, int] | None = None    # true dimensions
        self._resize_syncing = False    # guards the linked-field recompute
        self._shift_open = False
        self._shift_entries: list[srt.Entry] | None = None  # ORIGINAL parse
        self._shift_target_ms = 0   # pending total shift (the display)
        self._shift_applied_ms = 0  # total already written this session
        # refuse-overwrite escape hatch: (action title, source) armed by a
        # refusal; the next same-action press on the same file overwrites
        self._overwrite_arm: tuple[str, Path] | None = None

    # -- static layout ---------------------------------------------------------

    def _row(self, key: str, id: str, width: int,
             row_id: str | None = None) -> Horizontal:
        return Horizontal(Label(f"{key:<{width}}", classes="fkey"),
                          Static("", id=id, classes="fval-static"),
                          classes="frow", id=row_id)

    def compose(self):
        yield Label("", id="dtitle", classes="dtitle")
        with Horizontal(id="row-fname"):
            yield FieldInput(id="fname", compact=True)
            yield Static("", id="fname-mark", classes="fmark")

        with Vertical(id="panel-audio", classes="panel"):
            yield EditForm(24, id="form-audio")
            # album art is the last field: label column matches the form,
            # image top-aligned with the label, left-aligned with inputs
            with Horizontal(id="row-art"):
                yield Label("", id="art-label", classes="fkey")
                yield Static("-", id="art-none", classes="fval-static")
                with ArtField(id="art-field"):
                    yield image_widget(self.images, id="cover-audio")
                    yield Label("", id="cover-audio-dims", classes="cover-dims")
                yield Static("", id="art-mark", classes="fmark")
            with Horizontal(id="row-art-buttons"):
                yield Label("", id="art-buttons-pad", classes="fkey")
                # "im^port": ^i is reserved (tab alias), ^p stands in —
                # logged in notes/qa/todo-2.md
                yield ActionBar(
                    Action("art_path", "import", "p",
                           button_id="art-btn-path"),
                    Action("art_fetch", "fetch", "f",
                           button_id="art-btn-fetch"),
                    id="art-bar")
            with Horizontal(id="row-art-path"):
                yield Label("", id="art-path-pad", classes="fkey")
                yield ArtPathInput(id="art-path", compact=True)

        with Vertical(id="panel-video", classes="panel"):
            width = len("embedded title") + LABEL_GUTTER
            yield self._row("embedded title", "video-title", width)
            yield self._row("container", "video-container", width)
            yield self._row("size", "video-size", width)
            yield self._row("subtitles", "video-subs", width)
            yield self._row("posters", "video-posters", width)
            with Vertical(id="shift-div"):
                with Horizontal(id="shift-row"):
                    yield Label(f"{'shift':<{width}}", classes="fkey")
                    yield ShiftControl(" 0:00.0", id="shift-control")
                    yield Static("", id="shift-mark", classes="fmark")
                yield Static(SHIFT_HINT, id="shift-hint")
            with Vertical(id="gif-div"):    # the third wizard div
                with Horizontal(id="gif-row"):
                    yield Label(f"{'gif':<{width}}", classes="fkey")
                    yield FieldInput(id="gif-fps", compact=True,
                                     type="integer", classes="resize-num")
                    yield Label("fps", classes="wsep")
                    yield FieldInput(id="gif-width", compact=True,
                                     type="integer", classes="resize-num")
                    yield Label("px wide", classes="wsep")
                # "^save" per spec (was "apply ^a") — the wizard's write
                yield ActionBar(
                    Action("gif_make", "save", "s",
                           button_id="gif-apply-btn"),
                    id="gif-bar")
            # the poster, with its pixel dimensions under it — album art
            # and the book cover's twin (Nick, 2026-08-22)
            yield image_widget(self.images, id="cover-video")
            yield Label("", id="cover-video-dims", classes="cover-dims")

        with Vertical(id="panel-book", classes="panel"):
            yield EditForm(12, id="form-book")
            yield image_widget(self.images, id="cover-book")
            yield Label("", id="cover-book-dims", classes="cover-dims")
            # cover method: a path input toggled by the ^f cover button
            # (mirrors audio art-path). Enter applies, esc cancels.
            with Vertical(id="book-cover-div"):
                yield CoverPathInput(id="book-cover-path", compact=True)
                yield Static("⏎ apply · esc cancel", id="book-cover-hint")

        with Vertical(id="panel-image", classes="panel"):
            width = len("dimensions") + LABEL_GUTTER
            yield self._row("size", "image-size", width)
            yield self._row("dimensions", "image-dims", width)
            with Vertical(id="resize-div"):     # the wizard div, shift-style
                with Horizontal(id="resize-row"):
                    yield Label(f"{'resize':<{width}}", classes="fkey")
                    yield FieldInput(id="resize-w", compact=True,
                                     type="integer", classes="resize-num")
                    yield Label("×", id="resize-x")
                    yield FieldInput(id="resize-h", compact=True,
                                     type="integer", classes="resize-num")
                    yield Checkbox("link", value=True, id="resize-link",
                                   compact=True)
                # "^save" per spec (was "apply ^a") — the wizard's write
                yield ActionBar(
                    Action("resize_apply", "save", "s",
                           button_id="resize-apply-btn"),
                    id="resize-bar")
            yield image_widget(self.images, id="cover-image")

        with Vertical(id="panel-folder", classes="panel"):
            yield self._row("contains", "folder-counts", 8 + LABEL_GUTTER)
            with Vertical(id="plan-preview"):   # folderize, multi-artist, …
                yield Static("", id="plan-tree")

        with Vertical(id="panel-other", classes="panel"):
            width = 4 + LABEL_GUTTER
            yield self._row("size", "other-size", width)
            yield self._row("type", "other-type", width)

        # not a kind panel: a transient editable form shown while a split
        # is being set up (books ≤ pool); the pane holds focus so metadata
        # is corrected before the write
        with Vertical(id="panel-omnibus"):
            yield OmnibusForm(id="omnibus-form")

        yield ActionBar(*PANE_ACTIONS, id="pane-bar")
        # parked below save while its final home is decided (audio only);
        # width matches the widest standard audio label (albumartist, 11)
        yield self._row("info", "audio-info", 11 + LABEL_GUTTER,
                        row_id="row-audio-info")

    def on_mount(self) -> None:
        # chord colors inside button labels are markup, not CSS: mirror
        # the pane's focus-within flip onto them by hand (theme.py)
        self.watch(self.screen, "focused", self._sync_button_chrome)
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False
        self.query_one("#row-fname").display = False
        self.query_one("#row-audio-info").display = False
        self.query_one("#row-art-path").display = False
        self.query_one("#plan-preview").display = False
        self.query_one("#panel-omnibus").display = False
        self.query_one("#book-cover-div").display = False
        self.query_one("#shift-div").display = False
        self.query_one("#gif-div").display = False
        self.query_one("#resize-div").display = False
        self._sync_pane_bar()

    def _sync_button_chrome(self, focused) -> None:
        """Focus crossed the pane's edge (or moved inside it): recolor
        every button's printed chord to the matching idle/focus token."""
        inside = focused is not None and (focused is self
                                          or self in focused.ancestors)
        for button in self.query(ActionButton):
            button.set_pane_focus(inside)

    # -- value plumbing ----------------------------------------------------------

    def _set(self, id: str, value: str) -> None:
        self.query_one(f"#{id}", Static).update(value)

    def _set_cover(self, id: str, data: bytes | None) -> None:
        widget = self.query_one(f"#{id}")
        size: tuple[int, int] | None = None
        if isinstance(widget, Static):     # images off / unavailable
            size = _image_size(data)       # dims still show where a label exists
        else:
            try:
                if data:
                    from PIL import Image as PILImage
                    image = PILImage.open(io.BytesIO(data))
                    widget.image = image
                    widget.display = True
                    size = image.size
                else:
                    widget.display = False
            except Exception:
                widget.display = False
        self._set_cover_dims(f"{id}-dims", size)

    def _set_cover_dims(self, id: str, size: tuple[int, int] | None) -> None:
        """Print the cover's pixel dimensions ('600 × 600') beneath it, for
        the kinds that carry a dims label (album art, book cover, video
        poster)."""
        labels = self.query(f"#{id}")
        if not labels:
            return
        label = labels.first(Label)
        if size:
            label.update(f"{size[0]} × {size[1]}")
        label.display = size is not None

    # -- selection → panels --------------------------------------------------------

    def clear(self) -> None:
        """No selection: empty title, every panel hidden."""
        self._pending = None
        if self._debounce is not None:
            self._debounce.stop()
            self._debounce = None
        self.path = None
        self.paths = None
        self.kind = None
        self._readable = False
        self._baseline = None
        self.query_one("#dtitle", Label).update("")
        self.query_one("#dtitle").display = True
        self.query_one("#row-fname").display = False
        self.query_one("#row-audio-info").display = False
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False
        self._sync_pane_bar()

    def preview(self, path: Path, immediate: bool = False) -> None:
        """Debounced: browsing quickly must not read every file passed over."""
        self._queue_preview(path, immediate)

    def preview_bulk(self, paths: list[Path], immediate: bool = False) -> None:
        """Multi-file selection preview: same debounce, merged details."""
        self._queue_preview(list(paths), immediate)

    def _queue_preview(self, target: Path | list[Path],
                       immediate: bool) -> None:
        self._pending = target
        if self._debounce is not None:
            self._debounce.stop()
            self._debounce = None
        if immediate:
            self._apply_pending()
        else:
            self._debounce = self.set_timer(DEBOUNCE_SECONDS, self._apply_pending)

    def _reset_state(self) -> None:
        self._readable = False
        self._baseline = None
        self._pending_art = None
        self._baseline_art = None
        self._art_mixed = False
        self._art_candidates = []
        self._art_index = 0
        self._book_cover = False
        self._omnibus_ready = False
        self._omnibus_plan = None
        self._omnibus_editing = False
        self.query_one("#panel-omnibus").display = False
        self._folderize_ready = False
        self._folderize_plan = None
        self._standardize_ready = False
        self._sort_ready = False
        self._sort_plan = None
        self._multiartist_ready = False
        self._multiartist_plan = None
        self.query_one("#plan-preview").display = False
        self._hide_art_path()
        self.query_one("#book-cover-div").display = False
        self._overwrite_arm = None      # browsing away disarms any refusal
        self._video_srt = None
        self._resize_base = None
        self._resize_hide()     # browsing away closes the divs (no pending
        self._gif_hide()        # state to lose — both write siblings)
        self._shift_hide()      # browsing away drops a pending shift

    def _apply_pending(self) -> None:
        if self._pending is None:
            return
        target = self._pending
        if isinstance(target, list):
            self._begin_bulk(target, origin=None)
            return
        # re-previewing the SAME file (a resize/gif just landed and the
        # tree re-listed, or a rotate refreshed the pane) must not slam
        # an open wizard div shut under the user
        keep_resize = self._resize_open and target == self.path
        keep_gif = self._gif_open and target == self.path
        self.path = target
        self.paths = None
        self.kind = kinds.kind_of(target)
        self._reset_state()
        if self.kind == kinds.FOLDER:
            bulk = adapters.bulk_paths_for_folder(target)
            if bulk:      # an album-like folder edits as its contents
                self._begin_bulk(bulk, origin=target)
                return
        title = self.query_one("#dtitle", Label)
        title.update(self.path.name)
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = (panel == self.kind)
        self.query_one("#row-audio-info").display = False   # _fill_audio shows it
        try:
            details = adapters.read_details(self.path)
        except Exception as error:
            title.update(f"{self.path.name} — unreadable ({error})")
            self._show_editable(False)
            return
        self._readable = True
        self._show_editable(self.can_edit())
        getattr(self, f"_fill_{self.kind}")(self.path, details)
        self._baseline = self._current_state()
        self._refresh_marks()
        if keep_resize and self.kind == kinds.IMAGE:
            # reopen without re-prefilling: the user's numbers stand
            self._resize_open = True
            self.query_one("#resize-div").display = True
        if keep_gif and self.kind == kinds.VIDEO:
            self._gif_open = True
            self.query_one("#gif-div").display = True

    # -- bulk view: one form applied to many files -----------------------------------

    @property
    def loading_bulk(self) -> bool:
        return self.paths is not None and not self._readable

    def focus_when_loaded(self) -> None:
        """Descend (enter on a folder/selection) once the bulk read lands."""
        self._focus_after_load = True

    def _count_label(self) -> str:
        n = len(self.paths or [])
        noun = {kinds.AUDIO: "audio file", kinds.BOOK: "book",
                kinds.IMAGE: "image"}.get(self.kind, "file")
        return f"{n} {noun}{'s' if n != 1 else ''}"

    def _begin_bulk(self, paths: list[Path], origin: Path | None) -> None:
        self.path = origin                  # the folder, for folder-origin bulk
        self.paths = paths
        self.kind = kinds.kind_of(paths[0])
        self._reset_state()
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False
        self.query_one("#dtitle", Label).update(
            f"reading {self._count_label()}…")
        self.query_one("#dtitle").display = True
        self.query_one("#row-fname").display = False
        self.query_one("#row-audio-info").display = False
        self._sync_pane_bar()
        self._bulk_read_worker(list(paths))

    @work(thread=True, exclusive=True, group="bulkread")
    def _bulk_read_worker(self, paths: list[Path]) -> None:
        # N tag reads is slower than one: NAS rule, off the UI thread.
        try:
            bulk = adapters.read_bulk(paths)
        except Exception as error:
            self.app.call_from_thread(self._bulk_read_failed, paths, error)
            return
        self.app.call_from_thread(self._fill_bulk, paths, bulk)

    def _dom_intact(self) -> bool:
        """False when a worker callback lands after the pane's children
        were torn down (app/test shutdown): compose-once means #dtitle is
        always present on a live pane, so its absence is the teardown tell.
        Guards the same race _sync_pane_bar's NoMatches catch does."""
        try:
            self.query_one("#dtitle")
        except NoMatches:
            return False
        return True

    def _bulk_read_failed(self, paths: list[Path], error: Exception) -> None:
        if self.paths == paths and self._dom_intact():
            self.query_one("#dtitle", Label).update(
                f"{self._count_label()} — unreadable ({error})")

    def _fill_bulk(self, paths: list[Path], bulk: adapters.BulkDetails) -> None:
        if self.paths != paths or not self._dom_intact():
            return                          # moved on, or torn down under us
        self.kind = bulk.kind
        self._readable = True
        self.query_one(f"#panel-{bulk.kind}").display = True
        self.query_one("#dtitle", Label).update(
            f"{self._count_label()} selected")
        self._sync_pane_bar()
        form = self._active_form()
        assert form is not None
        form.set_fields(bulk.fields, bulk.mixed)
        if bulk.kind == kinds.AUDIO:
            gutter = " " * form.label_width
            self.query_one("#art-label", Label).update(
                f"{'album art':<{form.label_width}}")
            self.query_one("#art-buttons-pad", Label).update(gutter)
            self.query_one("#art-path-pad", Label).update(gutter)
            self._set("audio-info",
                      f"{bulk.length_seconds:.0f}s · {human_size(bulk.size)}")
            self.query_one("#row-audio-info").display = True
            self._baseline_art = bulk.cover
            self._art_mixed = bulk.cover_mixed
            self._show_art(bulk.cover, mixed=bulk.cover_mixed)
        else:
            self._set_cover("cover-book", bulk.cover)
        self._baseline = self._current_state()
        self._refresh_marks()
        if self.path is not None:               # album-folder origin: the
            self._probe_folderize(self.path)    # folder actions still apply
            self._probe_multiartist(self.path)
            self._probe_standardize(self.path)
            self._probe_sort(self.path)
        if self._focus_after_load:
            self._focus_after_load = False
            self.focus()

    def _show_editable(self, editable: bool) -> None:
        """Editable selections show the filename input; others the title."""
        self.query_one("#dtitle").display = not editable
        self.query_one("#row-fname").display = editable
        self._sync_pane_bar()
        if editable and self.path is not None:
            self.query_one("#fname", Input).value = self.path.name

    def _fill_audio(self, path: Path, d: adapters.AudioDetails) -> None:
        form = self.query_one("#form-audio", EditForm)
        form.set_fields(d.fields)
        gutter = " " * form.label_width
        self.query_one("#art-label", Label).update(
            f"{'album art':<{form.label_width}}")
        self.query_one("#art-buttons-pad", Label).update(gutter)
        self.query_one("#art-path-pad", Label).update(gutter)
        self._set("audio-info",
                  f"{d.length_seconds:.0f}s · {human_size(d.size)}")
        self.query_one("#row-audio-info").display = True
        self._baseline_art = d.cover
        self._show_art(d.cover)

    def _show_art(self, data: bytes | None, mixed: bool = False) -> None:
        self._set_cover("cover-audio", None if mixed else data)
        cover = self.query_one("#cover-audio")
        has_art = not isinstance(cover, Static) and cover.display
        none_label = self.query_one("#art-none", Static)
        none_label.update("(mixed)" if mixed else "-")
        none_label.display = not has_art

    def _fill_video(self, path: Path, d: adapters.VideoDetails) -> None:
        self._set("video-size", human_size(d.size))
        self._set("video-container", d.container or "—")
        self._set("video-title", "…")
        self._set("video-subs", d.subtitle_name or "none")
        self._set("video-posters", d.poster_name or "none")
        self._set_cover("cover-video", d.poster_bytes)
        # clean/shift work on SRT only (the engine's format); .ass/.vtt
        # siblings still show in the row but get no buttons
        self._video_srt = (path.parent / d.subtitle_name
                           if d.subtitle_name
                           and d.subtitle_name.endswith(".srt") else None)
        self._sync_pane_bar()       # subtitle buttons appear with the file
        self._probe_title(path)

    @work(thread=True, exclusive=True, group="probe")
    def _probe_title(self, path: Path) -> None:
        title = adapters.probe_video_title(path) or "—"
        if self.path == path:
            self.app.call_from_thread(self._set, "video-title", title)

    def _fill_book(self, path: Path, d: adapters.BookDetails) -> None:
        self.query_one("#form-book", EditForm).set_fields(d.fields)
        self._set_cover("cover-book", d.cover)
        self._book_cover = d.cover is not None
        self._sync_pane_bar()       # extract-cover appears with the cover
        if path.suffix.lower() == ".epub":
            self._probe_omnibus(path)   # split button fills in late
            self._probe_sort_book(path)  # sort button fills in late too

    def _fill_image(self, path: Path, d: adapters.ImageDetails) -> None:
        self._set("image-size", human_size(d.size))
        has_dims = bool(d.width and d.height)
        self._set("image-dims",
                  f"{d.width} × {d.height}" if has_dims else "—")
        self._resize_base = (d.width, d.height) if has_dims else None
        self._set_cover("cover-image", d.data)
        self._sync_pane_bar()       # convert/resize/rotate ride the kind

    def _fill_folder(self, path: Path, d: adapters.FolderDetails) -> None:
        summary = " · ".join(
            f"{d.counts[k]} {k}{'s' if d.counts[k] != 1 else ''}"
            for k in (kinds.FOLDER, kinds.VIDEO, kinds.AUDIO,
                      kinds.BOOK, kinds.IMAGE, kinds.OTHER)
            if d.counts.get(k)) or "empty"
        self._set("folder-counts", summary)
        self._probe_folderize(path)
        self._probe_multiartist(path)
        self._probe_standardize(path)
        self._probe_sort(path)

    def _fill_other(self, path: Path, d: adapters.OtherDetails) -> None:
        self._set("other-size", human_size(d.size))
        self._set("other-type", d.suffix or "—")

    # -- editing -------------------------------------------------------------------

    def _active_form(self) -> EditForm | None:
        if self.kind == kinds.AUDIO:
            return self.query_one("#form-audio", EditForm)
        if self.kind == kinds.BOOK:
            return self.query_one("#form-book", EditForm)
        return None

    def _field_inputs(self) -> list:
        """Every focusable field, top to bottom: filename first (single
        file only — bulk has no filename), the album-art slot last."""
        if self._omnibus_editing and self._omnibus_plan is not None:
            # the split form owns the pane's fields while it's up
            return self.query_one(OmnibusForm).inputs(
                len(self._omnibus_plan.books))
        if not self.can_edit():
            return []
        fields = ([] if self.paths is not None
                  else [self.query_one("#fname", Input)])
        form = self._active_form()
        if form is not None:
            fields.extend(form.inputs())
        if self.kind == kinds.AUDIO:
            fields.append(self.query_one("#art-field", ArtField))
        if self._resize_open:       # the div's controls join the ↑↓ walk
            fields.extend([self.query_one("#resize-w", FieldInput),
                           self.query_one("#resize-h", FieldInput),
                           self.query_one("#resize-link", Checkbox)])
        return fields

    def _current_state(self) -> tuple[str, dict[str, str]] | None:
        if not self.can_edit():
            return None
        form = self._active_form()
        fname = ("" if self.paths is not None
                 else self.query_one("#fname", Input).value)
        return (fname, form.values() if form is not None else {})

    @property
    def dirty(self) -> bool:
        if self._omnibus_editing:
            # split-form edits are ephemeral plan tweaks, not file edits:
            # esc cancels the whole split, never a save-confirm
            return False
        if self._pending_art is not None:
            return True
        if self._shift_pending:
            return True
        return (self._baseline is not None
                and self._current_state() != self._baseline)

    def _refresh_marks(self) -> None:
        """iTunes-style ✓ after every field whose value differs from the
        baseline — the visible record of exactly what a save will write."""
        baseline = self._baseline
        if baseline is None or not self.can_edit():
            self.query_one("#fname-mark", Static).update("")
            self.query_one("#art-mark", Static).update("")
            return
        name, fields = baseline
        edited = (self.paths is None
                  and self.query_one("#fname", Input).value != name)
        self.query_one("#fname-mark", Static).update("✓" if edited else "")
        form = self._active_form()
        if form is not None:
            form.refresh_marks(fields)
        self.query_one("#art-mark", Static).update(
            "✓" if self._pending_art is not None else "")

    def on_input_changed(self, ev: Input.Changed) -> None:
        if ev.input.id in ("resize-w", "resize-h"):     # not fields either
            self._resize_link_sync(ev.input.id)
            return
        if ev.input.id and ev.input.id.startswith("omni-"):
            return                          # split-form fields: no ✓ marks
        if ev.input.id != "art-path":       # method input: not a field
            self._refresh_marks()

    def focus(self, scroll_visible: bool = True):
        """Focusing the pane means editing: land on the filename input."""
        inputs = self._field_inputs()
        if inputs:
            inputs[0].focus(scroll_visible)
            return self
        return super().focus(scroll_visible)

    # -- action bars: contextual buttons below the fields. ↑↓ walk straight
    # through them (inline buttons: ↓ moves right), ←→ move within one bar,
    # and any printed ^x chord fires app-wide while its bar is on show ----------

    def _active_bars(self) -> list[ActionBar]:
        """Bars on show: every ancestor up to the pane is displayed."""
        bars = []
        for bar in self.query(ActionBar):
            node = bar
            while node is not None and node is not self:
                if not node.display:
                    break
                node = node.parent
            else:
                bars.append(bar)
        return bars

    def _art_buttons(self) -> list[ActionButton]:
        if self.kind != kinds.AUDIO or not self.can_edit():
            return []
        return self.query_one("#art-bar", ActionBar).buttons()

    def _sync_pane_bar(self) -> None:
        """Show the pane-bar buttons the current selection has earned."""
        names: set[str] = set()
        if self.plan_preview_open():            # a preview owns the bar
            names = {"plan_apply", "plan_cancel"}
        else:
            if self.can_edit():
                names.add("save")
                # "open" rides the same gate as save, not because it
                # writes anything but because a pane that can't take
                # focus has no reachable buttons
                if self._open_target() is not None:
                    names.add("open")           # every single file, 2nd
                if (self.kind == kinds.BOOK and self.paths is None
                        and self.path is not None):
                    suffix = self.path.suffix.lower()
                    names |= {f"convert_{fmt}"
                              for fmt in calibre.EBOOK_FORMATS
                              if fmt != suffix.lstrip(".")}
                    if suffix == ".epub":       # the only kind we can read
                        names.add("create_opf")
                        names.add("standardize")
                        names.add("book_cover")     # add or replace the cover
                        if self._book_cover:    # only when there is one
                            names.add("extract_cover")
                        if self._omnibus_ready:  # probe: ≥2 books inside
                            names.add("split_omnibus")
                if (self.kind == kinds.IMAGE and self.paths is None
                        and self.path is not None):
                    own = imageops.normalize_format(self.path.suffix)
                    names |= {f"convert_{fmt}"
                              for fmt in imageops.CONVERT_FORMATS
                              if fmt != own}
                    names |= {"resize", "rotate"}
            if self._folderize_ready:           # probe: work to do below
                names.add("folderize")
            if self._standardize_ready:         # probe: uncleaned epubs
                names.add("standardize")
            if self._sort_ready:                # probe: unwrapped books —
                # a single epub's button says "folderize" (spec), the
                # folder's says "sort"; same engine either way
                names.add("sort_book"
                          if self.kind == kinds.BOOK and self.paths is None
                          else "sort")
            if self._multiartist_ready:
                names.add("strip_multi_artist")
            if (video := self._video_target()) is not None:
                names |= {"get_subs", "download_posters", "gif"}
                if videofolder.probe(video):    # free: a name comparison
                    names.add("folderize_video")
                if self._video_srt is not None:
                    names |= {"clean_subs", "shift_subs"}
                if self._shift_open:            # the write manifest: ^s
                    names.add("save")           # writes the pending shift
        try:
            bar = self.query_one("#pane-bar", ActionBar)
        except NoMatches:
            # a probe worker's call_from_thread can land mid-teardown,
            # after the pane's children are gone — a late result is
            # meaningless then, not an error (flaked the suite twice)
            return
        bar.set_visible(names)

    # -- focus lockdown (todo-4 "Focus"): a focused sub-view owns the user.
    # While an inline wizard / import input / plan form holds focus, only
    # ITS commands are transmittable — nothing reaches the rest of the
    # pane until it is saved or cancelled (terms-of-art: sub-form states).

    def _within(self, selector: str) -> bool:
        focused = self.app.focused
        if focused is None:
            return False
        try:
            div = self.query_one(selector)
        except NoMatches:
            return False
        return div.display and (focused is div or div in focused.ancestors)

    def _focus_scope(self) -> set[str] | None:
        """Action names reachable from the focused sub-view — None when
        no sub-view owns focus (everything visible is reachable)."""
        if self._within("#row-art-path"):       # Import Album Art
            return set()                        # ⏎ applies, esc cancels
        if self._within("#book-cover-div"):     # Import Cover
            return set()
        # each wizard's scope: its write, plus its own toggle chord (the
        # toggle is the sub-form's command — pinned-while-pending included)
        if self._within("#shift-div"):          # Shift Subtitles
            return {"save", "shift_subs"}       # ^s writes the shift
        if self._within("#resize-div"):         # Resize Image
            return {"resize_apply", "resize"}
        if self._within("#gif-div"):            # Make GIF
            return {"gif_make", "gif"}
        if self._within("#panel-omnibus"):      # Split Omnibus
            return {"plan_apply", "plan_cancel"}
        return None

    def action_for_key(self, key: str) -> Action | None:
        """The action a key chord should fire: its button is on show,
        and the focused sub-view (if any) claims it."""
        scope = self._focus_scope()
        for bar in self._active_bars():
            action = bar.action_for_key(key)
            if action is None:
                continue
            if scope is None or action.name in scope:
                return action
            # else: this bar's match is locked out — a later bar may
            # still hold the scoped action on the same chord
        return None

    def trigger(self, action: Action) -> None:
        handler = getattr(self, f"action_{action.name}", None)
        if handler is not None:
            handler()

    def on_action_bar_triggered(self, ev: ActionBar.Triggered) -> None:
        ev.stop()
        self.trigger(ev.action)

    def _nav_items(self) -> list:
        """Everything ↑↓ walks, top to bottom: the fields, then any open
        wizard's controls, then every visible action button in reading
        order. A FOCUSED sub-view confines the walk to its own controls
        (focus lockdown, todo-4): save or cancel to leave."""
        if self._within("#shift-div"):          # its save is the pane ^s
            items: list = [self.query_one("#shift-control", ShiftControl)]
            save = self.query_one("#save-btn", ActionButton)
            if save.display:
                items.append(save)
            return items
        if self._within("#resize-div"):
            return [self.query_one("#resize-w", FieldInput),
                    self.query_one("#resize-h", FieldInput),
                    self.query_one("#resize-link", Checkbox),
                    *self.query_one("#resize-bar", ActionBar).buttons()]
        if self._within("#gif-div"):
            return [self.query_one("#gif-fps", FieldInput),
                    self.query_one("#gif-width", FieldInput),
                    *self.query_one("#gif-bar", ActionBar).buttons()]
        if self._within("#row-art-path"):       # single-input sub-forms:
            return [self.query_one("#art-path", ArtPathInput)]
        if self._within("#book-cover-div"):     # ↑↓ stay put
            return [self.query_one("#book-cover-path", CoverPathInput)]
        items = self._field_inputs()            # the pane's normal walk
        if self._shift_open:
            items.append(self.query_one("#shift-control", ShiftControl))
        if self._gif_open:
            items.extend([self.query_one("#gif-fps", FieldInput),
                          self.query_one("#gif-width", FieldInput)])
        if items:
            for bar in self._active_bars():
                items.extend(bar.buttons())
        return items

    def _move_nav(self, delta: int) -> None:
        items = self._nav_items()
        if not items:
            return
        focused = self.app.focused
        if focused in items:
            index = max(0, min(len(items) - 1, items.index(focused) + delta))
        else:
            index = 0
        items[index].focus()

    def action_field_next(self) -> None:
        self._move_nav(+1)

    def action_field_prev(self) -> None:
        self._move_nav(-1)

    def action_pane_left(self) -> None:
        focused = self.app.focused
        if (isinstance(focused, ActionButton)
                and isinstance(focused.parent, ActionBar)
                and focused in (row := focused.parent.buttons())):
            # focused not in row: a context change (probe fill-in, a
            # debounced re-preview) hid this button out from under the
            # cursor — fall through and ascend rather than index a list
            # it's no longer in (fuzz seed 12, 2026-08-07)
            index = row.index(focused)
            if index > 0:
                row[index - 1].focus()
                return                          # leftmost falls through: release
        self.action_release()

    def action_pane_right(self) -> None:
        focused = self.app.focused
        if (isinstance(focused, ActionButton)
                and isinstance(focused.parent, ActionBar)
                and focused in (row := focused.parent.buttons())):
            index = row.index(focused)          # focused-not-in-row: no-op
            if index < len(row) - 1:
                row[index + 1].focus()

    def action_release(self) -> None:
        if self.plan_preview_open():        # esc backs out of a plan/split
            self.action_plan_cancel()       # (which returns focus to the tree)
            return
        if not self.dirty:
            self.app.action_focus_tree()
            return

        def decided(choice: str | None) -> None:
            if choice == "save":
                self._start_save(release=True)
            elif choice == "discard":
                self._restore_baseline()
                self.app.action_focus_tree()
            # cancel: keep editing

        subject = (self._video_srt.name if self._shift_pending
                   and self._video_srt is not None
                   else self._count_label() if self.paths is not None
                   else self.path.name if self.path is not None else "?")
        self.app.push_screen(ConfirmSave(subject), decided)

    def _restore_baseline(self) -> None:
        if self._shift_pending:         # discard a pending shift: close the div
            self._shift_hide()
        if self._baseline is None:
            return
        name, fields = self._baseline
        self.query_one("#fname", Input).value = name
        form = self._active_form()
        if form is not None:
            form.set_values(fields)
        if self._pending_art is not None:
            self._pending_art = None
            self._show_art(self._baseline_art, mixed=self._art_mixed)
        self._refresh_marks()

    # -- art method 1: path entry ---------------------------------------------------

    def _hide_art_path(self) -> None:
        self.query_one("#row-art-path").display = False

    def action_art_path(self) -> None:
        if not self._art_buttons():
            return
        self.query_one("#row-art-path").display = True
        art_path = self.query_one("#art-path", ArtPathInput)
        assert self.path is not None
        art_path.value = str(self.path.parent) + "/"
        art_path.focus()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        if ev.input.id in ("resize-w", "resize-h"):     # ⏎ applies
            ev.stop()
            self.action_resize_apply()
            return
        if ev.input.id in ("gif-fps", "gif-width"):     # ⏎ applies
            ev.stop()
            self.action_gif_make()
            return
        if ev.input.id == "book-cover-path":            # ⏎ applies (writes)
            ev.stop()
            self._apply_book_cover(ev.value)
            return
        if ev.input.id != "art-path":
            return
        ev.stop()
        target = Path(ev.value)
        if kinds.kind_of(target) != kinds.IMAGE:
            self.notify(f"{target.name or ev.value}: not an image file",
                        severity="warning", title="album art")
            return
        try:
            data = target.read_bytes()
        except OSError as error:
            self.notify(str(error), severity="error", title="album art")
            return
        self._set_pending_art(data)
        self._hide_art_path()
        self.query_one("#art-field", ArtField).focus()

    # -- book cover: type a path, apply writes it into the epub -----------------------

    def _hide_book_cover_path(self) -> None:
        self.query_one("#book-cover-div").display = False
        if self.can_edit():             # return focus to the metadata fields
            self.focus()

    def _cover_prefill(self, book: Path) -> str:
        """The path to seed the input with, by priority: a sibling image
        sharing the book's stem, then a cover.* image, then the book's own
        directory (so the user browses from there)."""
        parent = book.parent
        children = fs.cached_children(str(parent))

        def image(child) -> bool:
            return (not child.is_dir()
                    and kinds.kind_of(child, is_dir=False) == kinds.IMAGE)

        for child in children:          # 1. same name as the book file
            if image(child) and os.path.splitext(child.name)[0] == book.stem:
                return str(child)
        for child in children:          # 2. a cover.* image
            if image(child) and os.path.splitext(child.name)[0].lower() \
                    == "cover":
                return str(child)
        return str(parent) + "/"        # 3. the book's directory

    def action_book_cover(self) -> None:
        if (self.kind != kinds.BOOK or self.paths is not None
                or self.path is None
                or self.path.suffix.lower() != ".epub"):
            return
        self.query_one("#book-cover-div").display = True
        field = self.query_one("#book-cover-path", CoverPathInput)
        field.value = self._cover_prefill(self.path)
        field.focus()

    def _apply_book_cover(self, value: str) -> None:
        target = Path(value)
        if kinds.kind_of(target) != kinds.IMAGE:
            self.notify(f"{target.name or value}: not an image file",
                        severity="warning", title="cover")
            return
        if self.path is None:
            return
        book = self.path
        self._hide_book_cover_path()
        self.notify("writing cover…", title="cover")
        self._book_cover_worker(book, target)

    @work(thread=True, exclusive=True, group="book-cover")
    def _book_cover_worker(self, book: Path, image: Path) -> None:
        try:
            epub.set_cover(book, image.read_bytes())
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="cover", severity="error")
            return
        self.app.call_from_thread(self._book_cover_done, book)

    def _book_cover_done(self, book: Path) -> None:
        self.notify("cover updated", title="cover")
        if self.path == book:
            self.preview(book, immediate=True)      # refresh the cover preview

    def _set_pending_art(self, data: bytes) -> None:
        self._pending_art = data
        self._show_art(data)
        self._refresh_marks()

    # -- art method 8: online lookup ------------------------------------------------

    def action_art_fetch(self) -> None:
        if not self._art_buttons():
            return
        if self._art_candidates:                # repeat press: next candidate
            self._art_index = (self._art_index + 1) % len(self._art_candidates)
            self._art_fetch_worker(self.path, None, self._art_index)
            return
        form = self._active_form()
        values = form.values() if form is not None else {}
        artist = values.get("artist") or values.get("albumartist") or ""
        album = values.get("album") or ""
        if not (artist or album):
            self.notify("need an artist or album tag to search",
                        severity="warning", title="album art")
            return
        self._art_fetch_worker(self.path, (artist, album), 0)

    @work(thread=True, exclusive=True, group="artfetch")
    def _art_fetch_worker(self, path: Path | None,
                          query: tuple[str, str] | None, index: int) -> None:
        try:
            candidates = (self._art_candidates if query is None
                          else artfetch.search_covers(*query))
            if not candidates:
                self.app.call_from_thread(
                    self.notify, "no covers found", title="album art",
                    severity="warning")
                return
            candidate = candidates[index % len(candidates)]
            data = artfetch.fetch_bytes(candidate.url)
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="album art fetch failed",
                severity="error")
            return
        self.app.call_from_thread(
            self._art_fetched, path, candidates, index, candidate, data)

    def _art_fetched(self, path: Path | None,
                     candidates: list[artfetch.CoverCandidate], index: int,
                     candidate: artfetch.CoverCandidate, data: bytes) -> None:
        if self.path != path:                   # selection moved on: drop it
            return
        self._art_candidates = candidates
        self._art_index = index
        self._set_pending_art(data)
        self.notify(
            f"{candidate.label}  ({index + 1}/{len(candidates)} — ^f next)",
            title="album art")

    def action_save(self) -> None:
        self._start_save(release=False)

    def _start_save(self, release: bool) -> None:
        if self._shift_pending:         # video: ^s writes the pending shift
            assert (self.path is not None and self._video_srt is not None
                    and self._shift_entries is not None)
            self._shift_save_worker(self.path, self._video_srt,
                                    list(self._shift_entries),
                                    self._shift_target_ms, release)
            return
        state = self._current_state()
        if state is None:
            return
        if self.paths is not None:
            form = self._active_form()
            baseline_fields = self._baseline[1] if self._baseline else {}
            changed = (form.changed_fields(baseline_fields)
                       if form is not None else {})
            if not changed and self._pending_art is None:
                if release:
                    self.app.action_focus_tree()
                return
            self._bulk_save_worker(list(self.paths), changed,
                                   self._pending_art, release)
            return
        if self.path is None:
            return
        new_name, fields = state
        self._save_worker(self.path, new_name, fields, self._pending_art,
                          release)

    @work(thread=True, exclusive=True, group="save")
    def _bulk_save_worker(self, paths: list[Path], fields: dict[str, str],
                          art: bytes | None, release: bool) -> None:
        errors = adapters.save_bulk(paths, fields, art=art)
        self.app.call_from_thread(self._bulk_save_done, paths, errors, release)

    def _bulk_save_done(self, paths: list[Path],
                        errors: list[tuple[Path, Exception]],
                        release: bool) -> None:
        saved = len(paths) - len(errors)
        if errors:
            path, error = errors[0]
            self.notify(f"{saved} saved · {len(errors)} failed: "
                        f"{path.name} ({error})",
                        title="bulk save", severity="warning", timeout=10)
        else:
            self.notify(f"{saved} saved", title="bulk save")
        if self.paths == paths:
            self._pending_art = None
            # _begin_bulk hides the form under the focused field, which
            # drops focus on the floor (todo-5 bug): note where focus sat
            # first, and re-descend once the re-read lands
            focused = self.app.focused
            editing = focused is not None and self in focused.ancestors
            self._begin_bulk(paths, origin=self.path)   # re-read: new baseline
            if editing and not release:
                self.focus_when_loaded()
        if release:
            self.app.action_focus_tree()

    @work(thread=True, exclusive=True, group="save")
    def _save_worker(self, path: Path, new_name: str, fields: dict[str, str],
                     art: bytes | None, release: bool) -> None:
        # NAS rule: a save is at least a tag write, possibly a whole-epub
        # rewrite — never block the UI on it.
        try:
            new_path = adapters.save_details(path, new_name, fields, art=art)
        except Exception as error:
            self.app.call_from_thread(self._save_failed, error)
            return
        self.app.call_from_thread(self._save_done, path, new_path, release)

    def _save_failed(self, error: Exception) -> None:
        self.notify(str(error), title="save failed", severity="error")

    def _save_done(self, old: Path, new: Path, release: bool) -> None:
        if self.path == old:
            self.path = new
        if self._pending_art is not None:       # the saved art is the new base
            self._baseline_art = self._pending_art
            self._pending_art = None
        self._baseline = self._current_state()
        self._refresh_marks()                   # saved: everything clean again
        self.post_message(self.Saved(old, new))
        if release:
            self.app.action_focus_tree()

    # -- book conversion --------------------------------------------------------

    def action_convert_epub(self) -> None:
        self._convert("epub")

    def action_convert_mobi(self) -> None:
        self._convert("mobi")

    def action_convert_azw3(self) -> None:
        self._convert("azw3")

    def _convert(self, fmt: str) -> None:
        if self.kind != kinds.BOOK or self.path is None or self.paths is not None:
            return
        if os.environ.get(artfetch.OFFLINE_ENV):
            # the fuzz gate presses every chord; real ebook-convert spawns
            # are minutes each — too heavy for it (this guard is what let
            # ^p/^b/^y join tests/fuzz.py KEYS)
            self.notify("convert disabled (MEDIASMITH_OFFLINE set)",
                        title="convert", severity="warning")
            return
        source = self.path
        target = source.with_suffix("." + fmt)
        title = f"convert to {fmt}"
        if target.exists() and not self._take_overwrite(title, source):
            self._arm_overwrite(title, source, f"{target.name} already exists")
            return
        if calibre.find_ebook_convert() is None:
            self.notify("Calibre not found — install it from "
                        "https://calibre-ebook.com",
                        severity="error", title="convert")
            return
        self.notify(f"{source.name} → .{fmt}…", title="converting")
        self._convert_worker(source, target)

    @work(thread=True, group="convert", exclusive=False)
    def _convert_worker(self, source: Path, target: Path) -> None:
        # conversions take seconds to minutes: never block the UI, and
        # let several queue up side by side
        try:
            calibre.convert(source, target)
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="convert failed",
                severity="error")
            return
        self.app.call_from_thread(self._convert_done, target)

    def _convert_done(self, target: Path) -> None:
        self.notify(f"{target.name} created", title="convert")
        self.post_message(self.FileCreated(target))

    # -- produce-a-sibling actions (cover export, metadata.opf) -------------------

    # -- refuse-overwrite, with a second-press escape hatch -------------------------
    # A produce action that would clobber an existing file refuses, but arms
    # a one-shot: pressing the SAME action on the SAME file again overwrites.
    # Uniform across the produce-a-sibling actions (extract cover, create
    # opf, image convert/resize, gif) and the book converts.

    def _take_overwrite(self, title: str, source: Path) -> bool:
        """Consume a pending overwrite confirmation for (title, source):
        True when the user just re-pressed the same action on the same file
        to confirm. One-shot."""
        if self._overwrite_arm == (title, source):
            self._overwrite_arm = None
            return True
        return False

    def _arm_overwrite(self, title: str, source: Path, label: str) -> None:
        """Refuse this overwrite but leave the door open: arm the one-shot
        and tell the user how to force it."""
        self._overwrite_arm = (title, source)
        self.notify(f"{label} — press again to overwrite",
                    severity="warning", title=title)

    def action_extract_cover(self) -> None:
        self._produce("extract cover",
                      lambda p, ow: adapters.extract_cover(p, overwrite=ow))

    def action_create_opf(self) -> None:
        self._produce("create opf",
                      lambda p, ow: adapters.create_opf(p, overwrite=ow))

    def _produce(self, title: str, producer) -> None:
        if (self.kind != kinds.BOOK or self.path is None
                or self.paths is not None):
            return
        self._run_producer(title, producer, self.path)

    def _run_producer(self, title: str, producer, source: Path) -> None:
        """Run a produce-a-sibling action, honoring an armed overwrite."""
        overwrite = self._take_overwrite(title, source)
        self._produce_worker(title, producer, source, overwrite)

    @work(thread=True, group="produce", exclusive=False)
    def _produce_worker(self, title: str, producer, path: Path,
                        overwrite: bool) -> None:
        # a zip read + a write: quick, but not NAS-quick — off the UI thread
        try:
            target = producer(path, overwrite)
        except FileExistsError as error:       # arm the second-press hatch
            self.app.call_from_thread(self._arm_overwrite, title, path,
                                      str(error))
            return
        except Exception as error:
            self.app.call_from_thread(self.notify, str(error), title=title,
                                      severity="warning")
            return
        self.app.call_from_thread(self._produced, title, target)

    def _produced(self, title: str, target: Path) -> None:
        self.notify(f"{target.name} created", title=title)
        self.post_message(self.FileCreated(target))

    # -- image actions: convert / resize / rotate (imageops.py) --------------------
    # Convert and resize are produce-a-sibling actions (refuse-overwrite
    # lives in the engine); rotate is the one in-place pixel edit. The
    # resize div is the second wizard div (shift-subs is the exemplar):
    # ^e toggles it, ⏎ or ^a applies, esc closes — resize never pends,
    # so there is no ConfirmSave leg.

    def _image_target(self) -> Path | None:
        """The single image file the actions apply to, or None."""
        if (self.kind == kinds.IMAGE and self.paths is None
                and self.path is not None and self._readable):
            return self.path
        return None

    def action_convert_jpg(self) -> None:
        self._image_convert("jpg")

    def action_convert_png(self) -> None:
        self._image_convert("png")

    def action_convert_webp(self) -> None:
        self._image_convert("webp")

    def action_convert_tiff(self) -> None:
        self._image_convert("tiff")

    def _image_convert(self, fmt: str) -> None:
        image = self._image_target()
        if image is None:
            return
        self._run_producer(
            f"convert to {fmt}",
            lambda path, ow, f=fmt: imageops.convert(path, f, overwrite=ow),
            image)

    def action_resize(self) -> None:
        image = self._image_target()
        if image is None:
            return
        if self._resize_open:           # react-style toggle; nothing pends
            div = self.query_one("#resize-div")
            inside = (self.app.focused is not None
                      and div in self.app.focused.ancestors)
            self._resize_hide()
            if inside:                  # don't strand a dropped focus
                self.app.action_focus_tree()
            return
        if self._resize_base is None:
            self.notify("can't read the image's dimensions",
                        title="resize", severity="warning")
            return
        width, height = self._resize_base
        self._resize_syncing = True     # prefill is not an edit
        self.query_one("#resize-w", FieldInput).value = str(width)
        self.query_one("#resize-h", FieldInput).value = str(height)
        self._resize_syncing = False
        self.query_one("#resize-link", Checkbox).value = True
        self._resize_open = True
        self.query_one("#resize-div").display = True
        self.app.reveal_details()       # narrow: display, then focus
        self.query_one("#resize-w", FieldInput).focus()

    def _resize_hide(self) -> None:
        self._resize_open = False
        self.query_one("#resize-div").display = False

    def _resize_link_sync(self, changed_id: str) -> None:
        """The link checkbox: editing one dimension recomputes the other
        from the image's true aspect (Photoshop's chain icon). Unlinked,
        each field stands alone and the resize distorts."""
        if (self._resize_syncing or not self._resize_open
                or self._resize_base is None
                or not self.query_one("#resize-link", Checkbox).value):
            return
        try:
            value = int(self.query_one(f"#{changed_id}", FieldInput).value)
        except ValueError:
            return
        if value < 1:
            return
        width, height = self._resize_base
        if changed_id == "resize-w":
            _, other = imageops.fit_dimensions(
                width, height, new_width=value, new_height=None)
            target = self.query_one("#resize-h", FieldInput)
        else:
            other, _ = imageops.fit_dimensions(
                width, height, new_width=None, new_height=value)
            target = self.query_one("#resize-w", FieldInput)
        self._resize_syncing = True
        target.value = str(other)
        self._resize_syncing = False

    def on_checkbox_changed(self, ev: Checkbox.Changed) -> None:
        if ev.checkbox.id == "resize-link" and ev.value:
            self._resize_link_sync("resize-w")      # re-link: width wins

    def action_resize_apply(self) -> None:
        image = self._image_target()
        if image is None or not self._resize_open:
            return
        try:
            width = int(self.query_one("#resize-w", FieldInput).value)
            height = int(self.query_one("#resize-h", FieldInput).value)
        except ValueError:
            width = height = 0
        if width < 1 or height < 1:
            self.notify("both dimensions need a positive number",
                        title="resize", severity="warning")
            return
        # the div stays open — a second size costs nothing extra
        self._run_producer(
            "resize",
            lambda path, ow, w=width, h=height: imageops.resize(
                path, w, h, overwrite=ow),
            image)

    def action_rotate(self) -> None:
        image = self._image_target()
        if image is None:
            return
        self._rotate_worker(image)

    @work(thread=True, exclusive=True, group="rotate")
    def _rotate_worker(self, path: Path) -> None:
        # in place and read-modify-write: exclusive, so rapid presses
        # queue instead of racing the same file
        try:
            _, lossy = imageops.rotate(path, 1)
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="rotate", severity="error")
            return
        self.app.call_from_thread(self._rotated, path, lossy)

    def _rotated(self, path: Path, lossy: bool) -> None:
        note = " (JPEG re-encoded)" if lossy else ""
        self.notify(f"{path.name}: rotated 90° clockwise{note}",
                    title="rotate")
        if self.path == path:
            self.preview(path, immediate=True)  # fresh image + dimensions

    # -- folder plans: probe → button → preview → apply/cancel ---------------------
    # Folderize and fix-multi-artist share the mechanism: probes fill in
    # late (NAS rule); a button appears only when the subtree has work to
    # do; pressing it plans in a worker and swaps the folder panel to a
    # preview; ONE apply/cancel pair owns the bar until resolved —
    # whichever plan is open receives them.

    def plan_preview_open(self) -> bool:
        return (self._folderize_plan is not None
                or self._multiartist_plan is not None
                or self._omnibus_plan is not None
                or self._sort_plan is not None)

    def _show_plan_preview(self, title: str, text: str) -> None:
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = (panel == kinds.FOLDER)
        self.query_one("#dtitle", Label).update(title)
        self.query_one("#dtitle").display = True
        self.query_one("#row-fname").display = False
        self.query_one("#row-audio-info").display = False
        self.query_one("#plan-tree", Static).update(text)
        self.query_one("#plan-preview").display = True
        self._sync_pane_bar()
        # the preview owns the pane: chords are view-scoped now, and
        # opening it hid the fields under any focused one — land focus on
        # apply so ^a / esc / ←→ work immediately
        self.app.reveal_details()               # narrow: display, then focus
        self.query_one("#act-plan_apply", ActionButton).focus()

    def _plan_root(self) -> Path | None:
        """The folder a plan action applies to: a folder selection, or
        the origin folder of an album-like bulk view."""
        if self.path is None:
            return None
        if self.kind == kinds.FOLDER or self.paths is not None:
            return self.path if self.path.is_dir() else None
        return None

    def action_plan_apply(self) -> None:
        if not self.plan_preview_open():    # a stray ^a must not yank focus
            return
        if self._folderize_plan is not None:
            plan = self._folderize_plan
            self._folderize_plan = None
            self.notify("organizing…", title="folderize")
            self._folderize_exec_worker(plan)
        elif self._multiartist_plan is not None:
            plan = self._multiartist_plan
            self._multiartist_plan = None
            self.notify("stripping…", title="strip multi-artist")
            self._multiartist_exec_worker(plan)
        elif self._omnibus_plan is not None:
            plan = self._omnibus_plan
            editing = self._omnibus_editing
            if editing:                     # fold the form's corrections in
                plan = omnibus.with_edits(
                    plan, *self.query_one(OmnibusForm).edits(len(plan.books)))
            self._omnibus_plan = None
            self._omnibus_editing = False
            self.notify("splitting…", title="split omnibus")
            self._omnibus_exec_worker(plan)
        elif self._sort_plan is not None:
            plan = self._sort_plan
            self._sort_plan = None
            self.notify("wrapping…", title="sort")
            self._sort_exec_worker(plan)
        # the preview (or split form) held focus; the exec hid it — ascend
        self.app.action_focus_tree()

    def action_plan_cancel(self) -> None:
        if not self.plan_preview_open():
            return
        self._folderize_plan = None
        self._multiartist_plan = None
        self._omnibus_plan = None
        self._omnibus_editing = False
        self._sort_plan = None
        if self.path is not None:               # restore the normal view
            self.preview(self.path, immediate=True)
        self.app.action_focus_tree()            # ascend out of the pane

    # -- folderize --------------------------------------------------------------

    @work(thread=True, exclusive=True, group="folderize-probe")
    def _probe_folderize(self, root: Path) -> None:
        ready = folderize.probe(root)
        if ready:
            self.app.call_from_thread(self._folderize_probed, root)

    def _folderize_probed(self, root: Path) -> None:
        if self.path == root and not self.plan_preview_open():
            self._folderize_ready = True
            self._sync_pane_bar()

    def action_folderize(self) -> None:
        root = self._plan_root()
        if root is None or not self._folderize_ready:
            return
        self.notify("scanning…", title="folderize")
        self._folderize_plan_worker(root)

    @work(thread=True, exclusive=True, group="folderize-plan")
    def _folderize_plan_worker(self, root: Path) -> None:
        plan = folderize.build_plan(root)
        self.app.call_from_thread(self._folderize_planned, root, plan)

    def _folderize_planned(self, root: Path,
                           plan: folderize.FolderizePlan) -> None:
        if self.path != root:                   # selection moved on
            return
        if plan.empty:
            self.notify("already organized", title="folderize")
            self._folderize_ready = False
            self._sync_pane_bar()
            return
        self._folderize_plan = plan
        self._show_plan_preview(f"folderize {root.name}/", render_plan(plan))

    @work(thread=True, exclusive=True, group="folderize-exec")
    def _folderize_exec_worker(self, plan: folderize.FolderizePlan) -> None:
        moved, skipped, errors = folderize.execute(plan)
        self.app.call_from_thread(
            self._folderize_done, plan.root, moved, skipped, errors)

    def _folderize_done(self, root: Path, moved: int, skipped: int,
                        errors: list[tuple[Path, str]]) -> None:
        parts = [f"{moved} moved"]
        if skipped:
            parts.append(f"{skipped} skipped (missing tags)")
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} failed — {path.name}: {reason}")
        self.notify(" · ".join(parts), title="folderize", timeout=8,
                    severity="warning" if errors else "information")
        fs.clear_cache()                        # the subtree just changed
        self.post_message(self.FolderChanged(root))
        if self.path == root:
            self.preview(root, immediate=True)  # fresh counts, fresh probe

    # -- strip multi-artist ---------------------------------------------------------

    @work(thread=True, exclusive=True, group="multiartist-probe")
    def _probe_multiartist(self, root: Path) -> None:
        ready = multiartist.probe(root)
        if ready:
            self.app.call_from_thread(self._multiartist_probed, root)

    def _multiartist_probed(self, root: Path) -> None:
        if self.path == root and not self.plan_preview_open():
            self._multiartist_ready = True
            self._sync_pane_bar()

    def action_strip_multi_artist(self) -> None:
        root = self._plan_root()
        if root is None or not self._multiartist_ready:
            return
        self.notify("scanning…", title="strip multi-artist")
        self._multiartist_plan_worker(root)

    @work(thread=True, exclusive=True, group="multiartist-plan")
    def _multiartist_plan_worker(self, root: Path) -> None:
        plan = multiartist.build_plan(root)
        self.app.call_from_thread(self._multiartist_planned, root, plan)

    def _multiartist_planned(self, root: Path,
                             plan: multiartist.MultiArtistPlan) -> None:
        if self.path != root:                   # selection moved on
            return
        if plan.empty:
            self.notify("no tangled artists", title="strip multi-artist")
            self._multiartist_ready = False
            self._sync_pane_bar()
            return
        self._multiartist_plan = plan
        self._show_plan_preview(f"strip multi-artist in {root.name}/",
                                render_multiartist_plan(plan))

    @work(thread=True, exclusive=True, group="multiartist-exec")
    def _multiartist_exec_worker(self,
                                 plan: multiartist.MultiArtistPlan) -> None:
        fixed, errors = multiartist.execute(plan)
        self.app.call_from_thread(
            self._multiartist_done, plan.root, fixed, errors)

    def _multiartist_done(self, root: Path, fixed: int,
                          errors: list[tuple[Path, str]]) -> None:
        parts = [f"{fixed} fixed"]
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} failed — {path.name}: {reason}")
        self.notify(" · ".join(parts), title="strip multi-artist", timeout=8,
                    severity="warning" if errors else "information")
        # tags changed in place — no tree structure change, just re-read
        if self.path == root:
            self.preview(root, immediate=True)  # fresh view, fresh probes

    # -- split omnibus: the third plan-shaped action (epub, not folder) ------------

    @work(thread=True, exclusive=True, group="omnibus-probe")
    def _probe_omnibus(self, path: Path) -> None:
        ready = omnibus.probe(path)             # one zip read
        if ready:
            self.app.call_from_thread(self._omnibus_probed, path)

    def _omnibus_probed(self, path: Path) -> None:
        if self.path == path and not self.plan_preview_open():
            self._omnibus_ready = True
            self._sync_pane_bar()

    def action_split_omnibus(self) -> None:
        path = self.path
        if (path is None or not self._omnibus_ready
                or self.paths is not None):
            return
        self.notify("reading…", title="split omnibus")
        self._omnibus_plan_worker(path)

    @work(thread=True, exclusive=True, group="omnibus-plan")
    def _omnibus_plan_worker(self, path: Path) -> None:
        try:
            plan = omnibus.build_plan(path)
        except (ValueError, OSError) as error:
            self.app.call_from_thread(
                self.notify, str(error), title="split omnibus",
                severity="error")
            return
        self.app.call_from_thread(self._omnibus_planned, path, plan)

    def _omnibus_planned(self, path: Path, plan: omnibus.OmnibusPlan) -> None:
        if self.path != path:                   # selection moved on
            return
        if plan.empty:
            self.notify("not an omnibus after all", title="split omnibus")
            self._omnibus_ready = False
            self._sync_pane_bar()
            return
        self._omnibus_plan = plan
        if len(plan.books) <= OmnibusForm.POOL:
            # the editable form: correct the NCX's guesses before writing,
            # with the pane focused (the user's feedback, 2026-08-07)
            self._omnibus_editing = True
            self._show_omnibus_form(plan)
            self.app.reveal_details()           # narrow: display, then focus
            self.focus()                        # lands on the author field
        else:                                   # too many to edit inline:
            self._show_plan_preview(f"split {path.name}",   # read-only preview
                                    render_omnibus_plan(plan))

    def _show_omnibus_form(self, plan: omnibus.OmnibusPlan) -> None:
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False
        self.query_one("#plan-preview").display = False
        self.query_one("#dtitle", Label).update("Split Omnibus")
        self.query_one("#dtitle").display = True
        self.query_one("#row-fname").display = False
        self.query_one("#row-audio-info").display = False
        self.query_one(OmnibusForm).set_plan(plan)
        self.query_one("#panel-omnibus").display = True
        self._sync_pane_bar()

    @work(thread=True, exclusive=True, group="omnibus-exec")
    def _omnibus_exec_worker(self, plan: omnibus.OmnibusPlan) -> None:
        written, errors = omnibus.execute(plan)
        self.app.call_from_thread(self._omnibus_done, plan.source,
                                  written, errors)

    def _omnibus_done(self, source: Path, written: list[Path],
                      errors: list[tuple[str, str]]) -> None:
        parts = [f"{len(written)} book{'s' if len(written) != 1 else ''} "
                 "written"]
        if errors:
            name, reason = errors[0]
            parts.append(f"{len(errors)} failed — {name}: {reason}")
        self.notify(" · ".join(parts), title="split omnibus", timeout=8,
                    severity="warning" if errors else "information")
        for path in written:
            self.post_message(self.FileCreated(path))
        if self.path == source:
            self.preview(source, immediate=True)    # restore the book view

    # -- sort: wrap each book's files into "Author Sort - Title/" ------------------
    # The fourth plan-shaped action (booksort.py) — folderize's exact
    # shape on the shared plan_apply/plan_cancel pair. On a single epub the
    # same engine runs one-file and immediately (no preview): rename + wrap,
    # then reveal the book in its new directory, still editable (Wrapped).
    # One _sort_ready flag serves both contexts — they never coexist.

    @work(thread=True, exclusive=True, group="sort-probe")
    def _probe_sort(self, root: Path) -> None:
        ready = booksort.probe(root)
        if ready:
            self.app.call_from_thread(self._sort_probed, root)

    def _sort_probed(self, root: Path) -> None:
        if self.path == root and not self.plan_preview_open():
            self._sort_ready = True
            self._sync_pane_bar()

    @work(thread=True, exclusive=True, group="sort-book-probe")
    def _probe_sort_book(self, book: Path) -> None:
        if booksort.probe_book(book):
            self.app.call_from_thread(self._sort_book_probed, book)

    def _sort_book_probed(self, book: Path) -> None:
        if self.path == book and not self.plan_preview_open():
            self._sort_ready = True
            self._sync_pane_bar()

    def action_sort_book(self) -> None:
        # the single-epub button ("folderize", spec rename) — same engine
        self.action_sort()

    def action_sort(self) -> None:
        if not self._sort_ready:
            return
        if (self.kind == kinds.BOOK and self.paths is None
                and self.path is not None):
            self.notify("reading…", title="sort")     # single ebook: no preview
            self._sort_book_worker(self.path)
            return
        root = self._plan_root()
        if root is None:
            return
        self.notify("reading…", title="sort")
        self._sort_plan_worker(root)

    @work(thread=True, exclusive=True, group="sort-book-exec")
    def _sort_book_worker(self, book: Path) -> None:
        plan = booksort.plan_for_book(book)
        if plan is None:
            self.app.call_from_thread(
                self.notify, f"{book.name}: no readable metadata",
                title="sort", severity="warning")
            return
        new_path = booksort.sorted_path(book, plan.groups[0].folder_name)
        moved, errors = booksort.execute(plan)
        self.app.call_from_thread(self._sort_book_done, book, new_path,
                                  moved, errors)

    def _sort_book_done(self, book: Path, new_path: Path, moved: int,
                        errors: list[tuple[Path, str]]) -> None:
        if errors:
            _, reason = errors[0]
            self.notify(f"{book.name}: {reason}", title="sort",
                        severity="error", timeout=8)
            return
        self.notify(f"wrapped into {new_path.parent.name}/", title="sort")
        fs.clear_cache()                        # the subtree just changed
        self.post_message(self.Wrapped(new_path))

    @work(thread=True, exclusive=True, group="sort-plan")
    def _sort_plan_worker(self, root: Path) -> None:
        plan = booksort.build_plan(root)
        self.app.call_from_thread(self._sort_planned, root, plan)

    def _sort_planned(self, root: Path, plan: booksort.SortPlan) -> None:
        if self.path != root:                   # selection moved on
            return
        if plan.empty:
            self.notify("every book here is already wrapped", title="sort")
            self._sort_ready = False
            self._sync_pane_bar()
            return
        self._sort_plan = plan
        self._show_plan_preview(f"sort {root.name}/", render_sort_plan(plan))

    @work(thread=True, exclusive=True, group="sort-exec")
    def _sort_exec_worker(self, plan: booksort.SortPlan) -> None:
        moved, errors = booksort.execute(plan)
        self.app.call_from_thread(self._sort_done, plan.root, moved, errors)

    def _sort_done(self, root: Path, moved: int,
                   errors: list[tuple[Path, str]]) -> None:
        parts = [f"{moved} file{'s' if moved != 1 else ''} wrapped"]
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} failed — {path.name}: {reason}")
        self.notify(" · ".join(parts), title="sort", timeout=8,
                    severity="warning" if errors else "information")
        fs.clear_cache()                        # the subtree just changed
        self.post_message(self.FolderChanged(root))
        if self.path == root:
            self.preview(root, immediate=True)  # fresh counts, fresh probes

    # -- standardize formatting: strip source cruft, rebuild clean -----------------
    # One engine, two contexts: a single epub, or every direct-child
    # epub of a folder (batch = v1's multi-file mode). Outputs are
    # "(clean)" siblings, so no plan preview — nothing moves.

    @work(thread=True, exclusive=True, group="standardize-probe")
    def _probe_standardize(self, root: Path) -> None:
        ready = standardize.probe_folder(root)
        if ready:
            self.app.call_from_thread(self._standardize_probed, root)

    def _standardize_probed(self, root: Path) -> None:
        if self.path == root and not self.plan_preview_open():
            self._standardize_ready = True
            self._sync_pane_bar()

    def action_standardize(self) -> None:
        if (self.kind == kinds.BOOK and self.paths is None
                and self.path is not None
                and self.path.suffix.lower() == ".epub"):
            books = [self.path]
        else:
            root = self._plan_root()
            if root is None or not self._standardize_ready:
                return
            books = standardize.folder_books(root)
            books = [b for b in books
                     if not standardize.clean_target(b).exists()]
            if not books:
                self.notify("everything here is already standardized",
                            title="standardize")
                self._standardize_ready = False
                self._sync_pane_bar()
                return
        n = len(books)
        self.notify(f"standardizing {n} book{'s' if n != 1 else ''}…",
                    title="standardize")
        self._standardize_worker(books)

    @work(thread=True, exclusive=False, group="standardize")
    def _standardize_worker(self, books: list[Path]) -> None:
        # a whole-book rewrite per file — the heaviest batch yet; stream
        # results as they land
        done: list[standardize.BookDone] = []
        failed: list[standardize.BookFailed] = []
        for event in standardize.run(books):
            if isinstance(event, standardize.BookDone):
                done.append(event)
                self.app.call_from_thread(self._standardized, event)
            else:
                failed.append(event)
                self.app.call_from_thread(
                    self.notify, f"{event.source.name}: {event.reason}",
                    title="standardize", severity="warning", timeout=8)
        if len(books) > 1:
            summary = [f"{len(done)} standardized"]
            if failed:
                summary.append(f"{len(failed)} failed")
            self.app.call_from_thread(
                self.notify, " · ".join(summary), title="standardize",
                timeout=8,
                severity="warning" if failed else "information")

    def _standardized(self, event: standardize.BookDone) -> None:
        self.notify(f"{event.target.name} · {event.style} · "
                    f"{event.chapters} chapter"
                    f"{'s' if event.chapters != 1 else ''}",
                    title="standardize")
        self.post_message(self.FileCreated(event.target))

    # -- cut/paste: lift the selection to the clipboard, browse, paste -------------
    # Tree commands (^x/^v bind on LibraryTree — todo-4); the logic lives
    # here because the pane mirrors the selection. State lives on the App
    # so a cut survives selection changes and path-bar jumps — cut → ^/ →
    # type destination → ⏎ → paste is the intended long-distance flow.
    # The strip carries the clipboard state; esc in the tree cancels.

    def _liftable_paths(self) -> list[Path]:
        """What ^x would pick up: the highlighted folder (even when it
        opens as an album-like bulk form), the shift-selection, or the
        single highlighted path (any kind — a cut is a filesystem op).
        No stats here: ``path`` beside ``paths`` is always a folder."""
        if self.paths:
            if self.path is not None:       # folder-origin bulk: the folder
                return [self.path]
            return list(self.paths)         # shift-range: the files
        if self.path is not None:
            return [self.path]
        return []

    def _place_target(self) -> Path | None:
        """Where ^v would drop: the highlighted folder (album-like bulk
        views count — their ``kind`` reads as the children's), or the
        highlighted file's folder."""
        if self.path is not None:
            if self.kind == kinds.FOLDER or self.paths:
                return self.path
            return self.path.parent
        if self.paths:
            return self.paths[0].parent
        return None

    def action_cut(self) -> None:
        if self.app.lifted is not None:         # the clipboard holds ONE
            return
        paths = self._liftable_paths()
        if paths:
            self.app.begin_lift(paths)
            self._sync_pane_bar()

    def action_copy(self) -> None:
        """Copy follows cut's exact pattern; paste duplicates instead of
        moving (todo-4 "New Feature: Copy")."""
        if self.app.lifted is not None:
            return
        paths = self._liftable_paths()
        if paths:
            self.app.begin_lift(paths, copy=True)
            self._sync_pane_bar()

    def action_paste(self) -> None:
        lifted = self.app.lifted
        if lifted is None:
            return
        copy = self.app.lift_copy
        target = self._place_target()
        if target is None:
            return
        movable = [p for p in lifted if p.parent != target]
        if not movable:
            self.notify("already here — pick another folder (esc cancels)",
                        title="paste")
            return
        for source in movable:                  # a folder can't enter itself
            if source == target or source in target.parents:
                self.notify(f"can't move {source.name} into itself",
                            title="paste", severity="warning")
                return
        self.notify(f"{'copying' if copy else 'moving'} {len(movable)}…",
                    title="paste")
        self._move_worker(movable, target, copy)

    @work(thread=True, exclusive=True, group="move")
    def _move_worker(self, sources: list[Path], target: Path,
                     copy: bool) -> None:
        # cross-volume (NAS↔local) is copy+delete under the hood — never
        # block the UI on it
        import shutil
        moved: list[Path] = []
        errors: list[tuple[Path, str]] = []
        for source in sources:
            dest = target / source.name
            if dest.exists():                   # refuse-overwrite, per file
                errors.append((source, f"{dest.name} already exists"))
                continue
            try:
                if copy and source.is_dir():
                    shutil.copytree(str(source), str(dest), symlinks=True)
                elif copy:
                    shutil.copy2(str(source), str(dest))
                else:
                    shutil.move(str(source), str(dest))
                moved.append(source)
            except OSError as error:
                errors.append((source, str(error)))
        self.app.call_from_thread(self._move_done, moved, errors, target,
                                  copy)

    def _move_done(self, moved: list[Path],
                   errors: list[tuple[Path, str]], target: Path,
                   copy: bool) -> None:
        parts = [f"{len(moved)} {'copied' if copy else 'moved'} "
                 f"to {target.name or target}/"]
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} failed — {path.name}: {reason}")
        self.notify(" · ".join(parts), title="paste", timeout=8,
                    severity="warning" if errors else "information")
        self.app.end_lift()
        fs.clear_cache()
        self.post_message(self.FolderChanged(target))
        if not copy:                            # a copy leaves sources alone
            for parent in {p.parent for p in moved}:
                self.post_message(self.FolderChanged(parent))
        self._sync_pane_bar()

    # -- folder CRUD: new directory / trash (rename rides the editable form) ----------
    # Chords are the buttons' own ^e / ^t, dispatched app-wide while the
    # buttons show (folder views). The chord works with ANY selection — a
    # highlighted folder is the target, a highlighted file means its folder.

    def action_new_directory(self) -> None:
        target = self._place_target()
        if target is None:
            return
        self._new_directory_worker(target)

    @work(thread=True, exclusive=True, group="new-folder")
    def _new_directory_worker(self, parent: Path) -> None:
        # one mkdir — but NAS rule: no filesystem op on the UI thread
        try:
            folder = adapters.create_folder(parent)
        except OSError as error:
            self.app.call_from_thread(
                self.notify, str(error), title="new directory", severity="error")
            return
        self.app.call_from_thread(self._new_directory_done, folder)

    def _new_directory_done(self, folder: Path) -> None:
        fs.clear_cache()
        self.post_message(self.FolderCreated(folder))

    def _delete_target(self) -> Path | None:
        """What ^del removes: the highlighted item itself — file OR folder
        (or an album-like folder shown as its contents). A shift-range bulk
        selection has no single target, so it is left alone."""
        if self.path is not None and self.path.exists():
            return self.path
        return None

    def action_delete(self) -> None:
        root = self._delete_target()
        if root is None:
            return
        if os.environ.get(artfetch.OFFLINE_ENV):
            # the fuzz gate presses everything — it must not fill the
            # REAL Trash with scratch folders
            self.notify("delete disabled (MEDIASMITH_OFFLINE set)",
                        title="delete", severity="warning")
            return
        self._delete_worker(root)

    @work(thread=True, exclusive=True, group="delete")
    def _delete_worker(self, path: Path) -> None:
        try:
            adapters.trash(path)
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="delete", severity="error")
            return
        self.app.call_from_thread(self._deleted, path)

    def _deleted(self, path: Path) -> None:
        self.notify(f"{path.name} moved to Trash", title="delete")
        fs.clear_cache()
        self.post_message(self.Deleted(path))

    # -- subtitles: get / clean / shift / watch on a video file --------------------
    # The engine work lives in subsync.py (dl+sync, the tuned v1 policy)
    # and srt.py (clean/shift). Chords fire from the tree — video never
    # takes focus — except the shift div, the one focusable thing in a
    # non-editable pane (modeled on ArtPathInput, not EDITABLE_KINDS).

    def _video_target(self) -> Path | None:
        """The single video file the subtitle actions apply to, or None."""
        if (self.kind == kinds.VIDEO and self.paths is None
                and self.path is not None and self._readable):
            return self.path
        return None

    def action_get_subs(self) -> None:
        video = self._video_target()
        if video is None:
            return
        if os.environ.get(artfetch.OFFLINE_ENV):
            self.notify("offline (MEDIASMITH_OFFLINE set)",
                        title="get subs", severity="warning")
            return
        self.notify(f"{video.name}: fetching subtitles…", title="get subs")
        self._get_subs_worker(video)

    @work(thread=True, group="get-subs", exclusive=False)
    def _get_subs_worker(self, video: Path) -> None:
        # like conversions: several fetches may run side by side, and a
        # clean on another file must not cancel one
        problems = subsync.check_requirements()
        if problems:
            self.app.call_from_thread(
                self.notify, "\n".join(problems), title="get subs",
                severity="error", timeout=10)
            return
        # an explicit press on a file that already has a sub means
        # "re-fetch" — the one deliberate exception to refuse-overwrite
        force = subsync.find_subtitle(video) is not None
        try:
            for event in subsync.run([video], force=force):
                if isinstance(event, subsync.PhaseStarted):
                    self.app.call_from_thread(
                        self.notify, event.label, title="get subs", timeout=3)
                elif isinstance(event, subsync.Note):
                    self.app.call_from_thread(
                        self.notify, event.text, title="get subs", timeout=5)
                elif isinstance(event, subsync.FileDone):
                    self.app.call_from_thread(self._got_subs, video,
                                              event.result)
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="get subs", severity="error")

    def _got_subs(self, video: Path, result: subsync.FileResult) -> None:
        self.notify(result.status, title=f"subtitles — {video.name}",
                    severity=("information" if result.category == "ok"
                              else "warning"), timeout=8)
        if result.installed:
            self.post_message(self.FileCreated(video.parent / result.installed))
            if self.path == video:
                self.preview(video, immediate=True)  # fresh subtitles row

    def action_clean_subs(self) -> None:
        video = self._video_target()
        if video is None or self._video_srt is None:
            return
        if self._shift_pending:     # clean rewrites the file under the shift
            self.notify("save or discard the pending shift first",
                        title="clean subs", severity="warning")
            return
        if self._shift_open:        # shift's ORIGINAL parse would go stale
            self._shift_hide()
        self._clean_subs_worker(video, self._video_srt)

    @work(thread=True, group="clean-subs", exclusive=False)
    def _clean_subs_worker(self, video: Path, srt_path: Path) -> None:
        # read + rewrite: NAS rule, off the UI thread
        try:
            result = srt.clean(srt.read(srt_path))
            if not result.unchanged:
                srt.write(result.kept, srt_path)
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="clean subs", severity="error")
            return
        self.app.call_from_thread(self._cleaned_subs, srt_path, result)

    def _cleaned_subs(self, srt_path: Path, result: srt.CleanResult) -> None:
        if result.unchanged:
            self.notify(f"{srt_path.name}: already clean", title="clean subs")
            return
        parts = []
        if result.removed:
            n = len(result.removed)
            parts.append(f"{n} credit cue{'s' if n != 1 else ''} removed")
        if result.color_stripped:
            n = result.color_stripped
            parts.append(f"markup stripped from {n} cue{'s' if n != 1 else ''}")
        self.notify(" · ".join(parts), title=f"clean subs — {srt_path.name}")

    def action_open(self) -> None:
        """Hand the file to the OS — the video pane's old "watch" button,
        now every file kind's (Nick, 2026-08-22). On a video this is still
        the player (subs auto-load when named like the video, which
        get-subs guarantees); on an mp3 it is the music app, on an epub
        the reader."""
        path = self._open_target()
        if path is None:
            return
        if os.environ.get(artfetch.OFFLINE_ENV):
            # the fuzz gate presses everything; don't open 100 players
            self.notify("open disabled (MEDIASMITH_OFFLINE set)",
                        title="open")
            return
        try:
            launch(path)
        except OSError as error:
            self.notify(str(error), title="open", severity="error")

    # -- download posters: TMDB fetch into a curation folder (posters.py) ---------

    def action_download_posters(self) -> None:
        video = self._video_target()
        if video is None:
            return
        if os.environ.get(artfetch.OFFLINE_ENV):
            self.notify("offline (MEDIASMITH_OFFLINE set)",
                        title="download posters", severity="warning")
            return
        self.notify(f"{video.name}: identifying film…",
                    title="download posters")
        self._posters_worker(video)

    @work(thread=True, group="posters", exclusive=False)
    def _posters_worker(self, video: Path) -> None:
        # the longest worker yet (N image downloads) — progress via
        # notify, throttled so a 40-poster film doesn't post 40 toasts
        notify = lambda *a, **kw: self.app.call_from_thread(  # noqa: E731
            self.notify, *a, title="download posters", **kw)
        try:
            title = adapters.probe_video_title(video)
            for event in posters.run(video, container_title=title):
                if isinstance(event, posters.Failed):
                    notify(event.reason, severity="warning", timeout=10)
                elif isinstance(event, posters.Identified):
                    notify(event.label, timeout=3)
                elif isinstance(event, posters.PhaseStarted):
                    notify(event.label, timeout=3)
                elif isinstance(event, posters.Progress):
                    if event.phase == "downloading" and event.done % 5 == 0:
                        notify(f"{event.done}/{event.total} downloaded…",
                               timeout=2)
                elif isinstance(event, posters.Done):
                    self.app.call_from_thread(self._posters_done, event)
        except Exception as error:
            notify(str(error), severity="error")

    def _posters_done(self, done: posters.Done) -> None:
        parts = [f"{done.saved} poster{'s' if done.saved != 1 else ''} "
                 f"→ {done.folder}"]
        if done.duplicates:
            parts.append(f"{done.duplicates} near-duplicates skipped")
        if done.existing:
            parts.append(f"{done.existing} already there (kept)")
        self.notify(" · ".join(parts), title="download posters", timeout=10)
        self.post_message(self.FolderChanged(done.folder.parent))

    # -- video → gif: the third wizard div (gif.py) ---------------------------------
    # React-style toggle like resize: no pending state (output is a
    # sibling), so esc just releases and the div stays until toggled.

    def action_gif(self) -> None:
        video = self._video_target()
        if video is None:
            return
        if self._gif_open:
            div = self.query_one("#gif-div")
            inside = (self.app.focused is not None
                      and div in self.app.focused.ancestors)
            self._gif_hide()
            if inside:                  # don't strand a dropped focus
                self.app.action_focus_tree()
            return
        self.query_one("#gif-fps", FieldInput).value = str(gif.DEFAULT_FPS)
        self.query_one("#gif-width", FieldInput).value = str(
            gif.DEFAULT_WIDTH)
        self._gif_open = True
        self.query_one("#gif-div").display = True
        self.app.reveal_details()       # narrow: display, then focus
        self.query_one("#gif-fps", FieldInput).focus()

    def _gif_hide(self) -> None:
        self._gif_open = False
        self.query_one("#gif-div").display = False

    def action_gif_make(self) -> None:
        video = self._video_target()
        if video is None or not self._gif_open:
            return
        try:
            fps = int(self.query_one("#gif-fps", FieldInput).value)
            width = int(self.query_one("#gif-width", FieldInput).value)
        except ValueError:
            fps = width = 0
        if fps < 1 or width < 1:
            self.notify("fps and width need positive numbers",
                        title="make gif", severity="warning")
            return
        if os.environ.get(artfetch.OFFLINE_ENV):
            # ffmpeg spawns are too heavy for the fuzz gate (the div
            # itself still gets fuzzed)
            self.notify("make gif disabled (MEDIASMITH_OFFLINE set)",
                        title="make gif", severity="warning")
            return
        problems = gif.check_requirements()
        if problems:
            self.notify("\n".join(problems), title="make gif",
                        severity="error", timeout=10)
            return
        target = gif.gif_target(video)
        self.notify(f"{video.name} → {target.name} ({fps} fps, {width} px)…",
                    title="make gif")
        # produce-a-sibling: the generic runner fits (div stays open); an
        # existing gif refuses once, then overwrites on a second ^apply
        self._run_producer(
            "make gif",
            lambda path, ow, f=fps, w=width: gif.make_gif(
                path, fps=f, width=w, overwrite=ow),
            video)

    # -- folderize a video: wrap it (and its companions) into its own folder -------
    # The ebook "folderize" gesture on a video (videofolder.py). Single
    # file, deterministic target — so it runs immediately, no plan
    # preview, exactly like a single epub's sort, and reveals the video in
    # its new directory still editable (Wrapped).

    def action_folderize_video(self) -> None:
        video = self._video_target()
        if video is None or not videofolder.probe(video):
            return
        self.notify(f"{video.name} → {video.stem}/", title="folderize")
        self._folderize_video_worker(video)

    @work(thread=True, exclusive=True, group="folderize-video")
    def _folderize_video_worker(self, video: Path) -> None:
        landed, moved, errors = videofolder.execute(video)
        self.app.call_from_thread(self._folderize_video_done, video, landed,
                                  moved, errors)

    def _folderize_video_done(self, video: Path, landed: Path, moved: int,
                              errors: list[tuple[Path, str]]) -> None:
        if landed == video:                     # the video itself never moved
            _, reason = errors[0] if errors else (None, "nothing to move")
            self.notify(f"{video.name}: {reason}", title="folderize",
                        severity="error", timeout=8)
            return
        parts = [f"{moved} file{'s' if moved != 1 else ''} → "
                 f"{landed.parent.name}/"]
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} left behind — {path.name}: {reason}")
        self.notify(" · ".join(parts), title="folderize", timeout=8,
                    severity="warning" if errors else "information")
        fs.clear_cache()                        # the subtree just changed
        self.post_message(self.Wrapped(landed))

    # -- shift subs: the inline wizard div ----------------------------------------

    @property
    def _shift_pending(self) -> bool:
        return self._shift_open and self._shift_target_ms != self._shift_applied_ms

    def action_shift_subs(self) -> None:
        video = self._video_target()
        if video is None or self._video_srt is None:
            return
        if self._shift_open:        # react-style toggle…
            if self._shift_pending:     # …but pending edits pin it open
                self.notify("unsaved shift — ^s to write, esc to discard",
                            title="shift subs", severity="warning")
                self.query_one("#shift-control", ShiftControl).focus()
            else:
                self._shift_hide()
                self.app.action_focus_tree()
            return
        self._shift_load_worker(video, self._video_srt)

    @work(thread=True, exclusive=True, group="shift-load")
    def _shift_load_worker(self, video: Path, srt_path: Path) -> None:
        try:
            entries = srt.read(srt_path)
        except Exception as error:
            self.app.call_from_thread(
                self.notify, str(error), title="shift subs", severity="error")
            return
        self.app.call_from_thread(self._shift_loaded, video, entries)

    def _shift_loaded(self, video: Path, entries: list[srt.Entry]) -> None:
        if self.path != video:                  # selection moved on: drop it
            return
        if not entries:
            self.notify("no cues found", title="shift subs",
                        severity="warning")
            return
        self._shift_entries = entries
        self._shift_target_ms = 0
        self._shift_applied_ms = 0
        self._shift_open = True
        self.query_one("#shift-div").display = True
        self._shift_refresh()
        self._sync_pane_bar()                   # save joins the bar
        self.app.reveal_details()               # narrow: display, then focus
        self.query_one("#shift-control", ShiftControl).focus()

    def _shift_nudge(self, delta_ms: int) -> None:
        if not self._shift_open:
            return
        self._shift_target_ms += delta_ms
        self._shift_refresh()

    def _shift_refresh(self) -> None:
        self.query_one("#shift-control", ShiftControl).update(
            srt.format_shift(self._shift_target_ms))
        self.query_one("#shift-mark", Static).update(
            "✓" if self._shift_pending else "")

    def _shift_close(self) -> None:
        """esc on the control: pending goes through ConfirmSave (the
        div refuses to close silently), clean just closes."""
        if self._shift_pending:
            self.action_release()
        else:
            self._shift_hide()
            self.app.action_focus_tree()

    def _shift_hide(self) -> None:
        self._shift_open = False
        self._shift_entries = None
        self._shift_target_ms = 0
        self._shift_applied_ms = 0
        self.query_one("#shift-div").display = False
        self._sync_pane_bar()

    @work(thread=True, exclusive=True, group="save")
    def _shift_save_worker(self, video: Path, srt_path: Path,
                           entries: list[srt.Entry], target_ms: int,
                           release: bool) -> None:
        # recompute from the ORIGINAL parse, write the total (nudge model)
        try:
            srt.write(srt.shift(entries, target_ms), srt_path)
        except Exception as error:
            self.app.call_from_thread(self._save_failed, error)
            return
        self.app.call_from_thread(self._shift_saved, video, srt_path,
                                  target_ms, release)

    def _shift_saved(self, video: Path, srt_path: Path, target_ms: int,
                     release: bool) -> None:
        self.notify(f"{srt_path.name} written "
                    f"({srt.format_shift(target_ms).strip()})",
                    title="shift subs")
        if self.path == video:
            self._shift_applied_ms = target_ms  # ✓ clears, div stays open
            self._shift_refresh()
        if release:                             # via ConfirmSave: close out
            if self.path == video:
                self._shift_hide()
            self.app.action_focus_tree()
