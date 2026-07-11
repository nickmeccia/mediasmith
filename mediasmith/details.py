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
from pathlib import Path

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from . import adapters, artfetch, fs, kinds
from .images import image_widget

PANELS = [kinds.AUDIO, kinds.VIDEO, kinds.BOOK, kinds.IMAGE,
          kinds.FOLDER, kinds.OTHER]

EDITABLE_KINDS: frozenset[str] = frozenset({kinds.AUDIO, kinds.BOOK})
"""Kinds whose details can take focus for editing."""

DEBOUNCE_SECONDS = 0.15

LABEL_GUTTER = 2   # spaces between a field label and its input


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n:.0f} B"
        n /= 1024


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

    def action_left_or_release(self) -> None:
        if self.cursor_position == 0:
            self.screen.query_one(DetailsPane).action_release()
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
        pane = self.screen.query_one(DetailsPane)
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
        width = max((len(n) for n in self._names), default=0) + LABEL_GUTTER
        self.label_width = width
        for i, row in enumerate(self._rows()):
            if i < len(self._names):
                name = self._names[i]
                row.query_one(Label).update(f"{name:<{width}}")
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
        self.dismiss(ev.button.id or "cancel")

    def action_choose(self, choice: str) -> None:
        self.dismiss(choice)


class DetailsPane(VerticalScroll, can_focus=True):

    BINDINGS = [
        Binding("escape", "release", "back", show=False),
        # ←/→ : between the art-method buttons when one is focused;
        # otherwise ← duplicates esc (inside a field, FieldInput owns ←)
        Binding("left", "pane_left", "back", show=False),
        Binding("right", "pane_right", show=False),
        Binding("ctrl+s", "save", "save", show=False),
        Binding("ctrl+o", "art_path", "art path", show=False),
        Binding("ctrl+f", "art_fetch", "art fetch", show=False),
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

    def can_edit(self) -> bool:
        """Focus may enter this pane only when the shown kind is editable."""
        return self.kind in EDITABLE_KINDS and self._readable

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
                yield Static("", id="art-mark", classes="fmark")
            with Horizontal(id="row-art-buttons"):
                yield Label("", id="art-buttons-pad", classes="fkey")
                yield Button("path  ^o", id="art-btn-path", compact=True)
                yield Button("fetch  ^f", id="art-btn-fetch", compact=True)
            with Horizontal(id="row-art-path"):
                yield Label("", id="art-path-pad", classes="fkey")
                yield ArtPathInput(id="art-path", compact=True)

        with Vertical(id="panel-video", classes="panel"):
            width = len("embedded title") + LABEL_GUTTER
            yield self._row("size", "video-size", width)
            yield self._row("embedded title", "video-title", width)
            yield self._row("subtitles", "video-subs", width)
            yield self._row("posters", "video-posters", width)
            yield image_widget(self.images, id="cover-video")

        with Vertical(id="panel-book", classes="panel"):
            yield EditForm(12, id="form-book")
            yield image_widget(self.images, id="cover-book")

        with Vertical(id="panel-image", classes="panel"):
            yield self._row("size", "image-size", 4 + LABEL_GUTTER)
            yield image_widget(self.images, id="cover-image")

        with Vertical(id="panel-folder", classes="panel"):
            yield self._row("contains", "folder-counts", 8 + LABEL_GUTTER)

        with Vertical(id="panel-other", classes="panel"):
            width = 4 + LABEL_GUTTER
            yield self._row("size", "other-size", width)
            yield self._row("type", "other-type", width)

        yield Button("save  ^s", id="save-btn", compact=True)
        # parked below save while its final home is decided (audio only);
        # width matches the standard audio field labels (tracknumber)
        yield self._row("info", "audio-info", 11 + LABEL_GUTTER,
                        row_id="row-audio-info")

    def on_mount(self) -> None:
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False
        self.query_one("#row-fname").display = False
        self.query_one("#save-btn").display = False
        self.query_one("#row-audio-info").display = False
        self.query_one("#row-art-path").display = False

    # -- value plumbing ----------------------------------------------------------

    def _set(self, id: str, value: str) -> None:
        self.query_one(f"#{id}", Static).update(value)

    def _set_cover(self, id: str, data: bytes | None) -> None:
        widget = self.query_one(f"#{id}")
        if isinstance(widget, Static):     # images off / unavailable
            return
        try:
            if data:
                from PIL import Image as PILImage
                widget.image = PILImage.open(io.BytesIO(data))
                widget.display = True
            else:
                widget.display = False
        except Exception:
            widget.display = False

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
        self.query_one("#save-btn").display = False
        self.query_one("#row-audio-info").display = False
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False

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
        self._hide_art_path()

    def _apply_pending(self) -> None:
        if self._pending is None:
            return
        target = self._pending
        if isinstance(target, list):
            self._begin_bulk(target, origin=None)
            return
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

    # -- bulk view: one form applied to many files -----------------------------------

    @property
    def loading_bulk(self) -> bool:
        return self.paths is not None and not self._readable

    def focus_when_loaded(self) -> None:
        """Descend (enter on a folder/selection) once the bulk read lands."""
        self._focus_after_load = True

    def _count_label(self) -> str:
        n = len(self.paths or [])
        noun = "audio file" if self.kind == kinds.AUDIO else "book"
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
        self.query_one("#save-btn").display = False
        self.query_one("#row-audio-info").display = False
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

    def _bulk_read_failed(self, paths: list[Path], error: Exception) -> None:
        if self.paths == paths:
            self.query_one("#dtitle", Label).update(
                f"{self._count_label()} — unreadable ({error})")

    def _fill_bulk(self, paths: list[Path], bulk: adapters.BulkDetails) -> None:
        if self.paths != paths:             # selection moved on: drop it
            return
        self.kind = bulk.kind
        self._readable = True
        self.query_one(f"#panel-{bulk.kind}").display = True
        self.query_one("#dtitle", Label).update(
            f"{self._count_label()} selected")
        self.query_one("#save-btn").display = True
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
        if self._focus_after_load:
            self._focus_after_load = False
            self.focus()

    def _show_editable(self, editable: bool) -> None:
        """Editable selections show the filename input; others the title."""
        self.query_one("#dtitle").display = not editable
        self.query_one("#row-fname").display = editable
        self.query_one("#save-btn").display = editable
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
        self._set("video-title", "…")
        self._set("video-subs", d.subtitle_name or "none")
        self._set("video-posters", d.poster_name or "none")
        self._set_cover("cover-video", d.poster_bytes)
        self._probe_title(path)

    @work(thread=True, exclusive=True, group="probe")
    def _probe_title(self, path: Path) -> None:
        title = adapters.probe_video_title(path) or "—"
        if self.path == path:
            self.app.call_from_thread(self._set, "video-title", title)

    def _fill_book(self, path: Path, d: adapters.BookDetails) -> None:
        self.query_one("#form-book", EditForm).set_fields(d.fields)
        self._set_cover("cover-book", d.cover)

    def _fill_image(self, path: Path, d: adapters.ImageDetails) -> None:
        self._set("image-size", human_size(d.size))
        self._set_cover("cover-image", d.data)

    def _fill_folder(self, path: Path, d: adapters.FolderDetails) -> None:
        summary = " · ".join(
            f"{d.counts[k]} {k}{'s' if d.counts[k] != 1 else ''}"
            for k in (kinds.FOLDER, kinds.VIDEO, kinds.AUDIO,
                      kinds.BOOK, kinds.IMAGE, kinds.OTHER)
            if d.counts.get(k)) or "empty"
        self._set("folder-counts", summary)

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
        if not self.can_edit():
            return []
        fields = ([] if self.paths is not None
                  else [self.query_one("#fname", Input)])
        form = self._active_form()
        if form is not None:
            fields.extend(form.inputs())
        if self.kind == kinds.AUDIO:
            fields.append(self.query_one("#art-field", ArtField))
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
        if self._pending_art is not None:
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
        if ev.input.id != "art-path":       # method input: not a field
            self._refresh_marks()

    def focus(self, scroll_visible: bool = True):
        """Focusing the pane means editing: land on the filename input."""
        inputs = self._field_inputs()
        if inputs:
            inputs[0].focus(scroll_visible)
            return self
        return super().focus(scroll_visible)

    def _move_field(self, delta: int) -> None:
        inputs = self._field_inputs()
        if not inputs:
            return
        focused = self.app.focused
        if focused in inputs:
            index = max(0, min(len(inputs) - 1, inputs.index(focused) + delta))
        else:
            index = 0
        inputs[index].focus()

    # -- art method buttons: one more row below the fields, laid out
    # left-to-right; ↓ from the art slot reaches them, ↑ returns ------------------

    def _art_buttons(self) -> list[Button]:
        if self.kind != kinds.AUDIO or not self.can_edit():
            return []
        return [self.query_one("#art-btn-path", Button),
                self.query_one("#art-btn-fetch", Button)]

    def action_field_next(self) -> None:
        focused = self.app.focused
        buttons = self._art_buttons()
        if focused in buttons:
            return                              # bottom row: clamp
        if isinstance(focused, ArtField) and buttons:
            buttons[0].focus()
            return
        self._move_field(+1)

    def action_field_prev(self) -> None:
        focused = self.app.focused
        if focused in self._art_buttons():
            self.query_one("#art-field", ArtField).focus()
            return
        self._move_field(-1)

    def action_pane_left(self) -> None:
        focused = self.app.focused
        buttons = self._art_buttons()
        if focused in buttons:
            index = buttons.index(focused)
            if index > 0:
                buttons[index - 1].focus()
                return                          # leftmost falls through: release
        self.action_release()

    def action_pane_right(self) -> None:
        focused = self.app.focused
        buttons = self._art_buttons()
        if focused in buttons:
            index = buttons.index(focused)
            if index < len(buttons) - 1:
                buttons[index + 1].focus()

    def action_release(self) -> None:
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

        subject = (self._count_label() if self.paths is not None
                   else self.path.name if self.path is not None else "?")
        self.app.push_screen(ConfirmSave(subject), decided)

    def _restore_baseline(self) -> None:
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

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        actions = {"save-btn": self.action_save,
                   "art-btn-path": self.action_art_path,
                   "art-btn-fetch": self.action_art_fetch}
        action = actions.get(ev.button.id or "")
        if action is not None:
            ev.stop()
            action()

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
            self._begin_bulk(paths, origin=self.path)   # re-read: new baseline
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
