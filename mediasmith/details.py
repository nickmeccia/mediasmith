"""Right pane: read-only details of the highlighted path.

Composed ONCE — one hidden panel per file kind; a selection change only
swaps values and visibility. Never rebuild this pane with
``remove_children()`` per selection: a cancelled removal can leak
CancelledError into the app's message pump, which Textual treats as a
silent quit (reproduced crash in the v1 prototype).
"""

from __future__ import annotations

import io
from pathlib import Path

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Label, Static

from . import adapters, kinds
from .images import image_widget

PANELS = [kinds.AUDIO, kinds.VIDEO, kinds.BOOK, kinds.IMAGE,
          kinds.FOLDER, kinds.OTHER]

DEBOUNCE_SECONDS = 0.15


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n:.0f} B"
        n /= 1024


class DetailsPane(VerticalScroll, can_focus=True):

    BINDINGS = [
        Binding("tab", "app.focus_tree", "tree", show=False),
        Binding("shift+tab", "app.focus_tree", "tree", show=False),
    ]

    def __init__(self, *, images: str = "auto", **kw) -> None:
        super().__init__(**kw)
        self.images = images
        self.path: Path | None = None
        self.kind: str | None = None
        self._pending: Path | None = None
        self._debounce = None

    # -- static layout ---------------------------------------------------------

    def _row(self, key: str, id: str) -> Horizontal:
        return Horizontal(Label(f"{key:>13} ", classes="fkey"),
                          Static("", id=id, classes="fval"), classes="frow")

    def compose(self):
        yield Label("", id="dtitle", classes="dtitle")

        with Vertical(id="panel-audio", classes="panel"):
            for name in adapters.AUDIO_FIELDS:
                yield self._row(name, f"audio-{name}")
            yield self._row("info", "audio-info")
            yield image_widget(self.images, id="cover-audio")

        with Vertical(id="panel-video", classes="panel"):
            yield self._row("size", "video-size")
            yield self._row("embedded title", "video-title")
            yield self._row("subtitles", "video-subs")
            yield self._row("posters", "video-posters")
            yield image_widget(self.images, id="cover-video")

        with Vertical(id="panel-book", classes="panel"):
            for name in adapters.BOOK_FIELDS:
                yield self._row(name, f"book-{name}")
            yield image_widget(self.images, id="cover-book")

        with Vertical(id="panel-image", classes="panel"):
            yield self._row("size", "image-size")
            yield image_widget(self.images, id="cover-image")

        with Vertical(id="panel-folder", classes="panel"):
            yield self._row("contains", "folder-counts")

        with Vertical(id="panel-other", classes="panel"):
            yield self._row("size", "other-size")
            yield self._row("type", "other-type")

    def on_mount(self) -> None:
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False

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

    def preview(self, path: Path, immediate: bool = False) -> None:
        """Debounced: browsing quickly must not read every file passed over."""
        self._pending = path
        if self._debounce is not None:
            self._debounce.stop()
            self._debounce = None
        if immediate:
            self._apply_pending()
        else:
            self._debounce = self.set_timer(DEBOUNCE_SECONDS, self._apply_pending)

    def _apply_pending(self) -> None:
        if self._pending is None:
            return
        self.path = self._pending
        self.kind = kinds.kind_of(self.path)
        title = self.query_one("#dtitle", Label)
        title.update(self.path.name)
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = (panel == self.kind)
        try:
            details = adapters.read_details(self.path)
        except Exception as error:
            title.update(f"{self.path.name} — unreadable ({error})")
            return
        getattr(self, f"_fill_{self.kind}")(self.path, details)

    def _fill_audio(self, path: Path, d: adapters.AudioDetails) -> None:
        for name in adapters.AUDIO_FIELDS:
            self._set(f"audio-{name}", d.fields[name] or "—")
        self._set("audio-info",
                  f"{d.length_seconds:.0f}s · {human_size(d.size)}")
        self._set_cover("cover-audio", d.cover)

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
        for name in adapters.BOOK_FIELDS:
            self._set(f"book-{name}", d.fields[name] or "—")
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
