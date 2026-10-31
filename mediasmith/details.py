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
import sys
from functools import partial
from pathlib import Path

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from rich.segment import Segment
from textual.content import Content
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, Static

from . import (adapters, artfetch, booksort, calibre, casing, comics, epub,
               illustrator,
               folderize, fs, gif, imageops, images, kinds, multiartist,
               omnibus, posters, progress, srt, standardize, subsync, trace,
               videofolder)
from . import actions
from .actions import (ACTIONS, CONTEXTUAL, FILE, Action, ActionBar,
                      ActionButton)
from .images import image_widget
from .text import READING

PANELS = [kinds.AUDIO, kinds.VIDEO, kinds.BOOK, kinds.IMAGE,
          kinds.VECTOR, kinds.FOLDER, kinds.OTHER]


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


def _subs_job(video: Path) -> str:
    """Job key for a subtitle fetch — per video: fetches run side by side."""
    return f"get-subs:{video}"


def _posters_job(video: Path) -> str:
    return f"posters:{video}"


def _convert_job(source: Path) -> str:
    return f"convert:{source}"


PANE_ACTIONS = [
    # The pane's three bars, composed ONCE with the full palette; selection
    # changes only show and hide buttons (_sync_pane_bar) — the
    # compose-once rule. Each Action names the bar it lives on
    # (actions.CONTEXTUAL / FILE / ACTIONS, and see that module for what
    # each bar means); the bars compose in list order.
    #
    # LABELS (Nick, 2026-10-26 — always-available-actions-3): the chord is
    # no longer spliced into the word, so the words are capitalized and
    # read as themselves. The Actions bar prints POSITIONAL chords only
    # (^1…^9, or ⌥1…⌥9 under tmux) and its specs carry no letter at all:
    # a key that works without being printed is exactly what the strip
    # contract forbids. The Contextual and File bars keep their letters —
    # those are few, fixed, and the same everywhere.
    #
    # -- contextual: what the pane's STATE offers
    Action("save", "Save", "s", button_id="save-btn", bar=CONTEXTUAL),
    # the way back up the path, printed while focus is down here (todo-6)
    Action("exit", "Exit", key_label="ESC", bar=CONTEXTUAL),
    # while any plan preview is up, these two own the bar
    Action("plan_apply", "Apply", "a", bar=CONTEXTUAL),
    Action("plan_cancel", "Cancel", key_label="ESC", bar=CONTEXTUAL),
    # …and while a QUESTION is up, its answers own it instead (Nick's
    # answer #5, 2026-10-26: the micro-modals became bar states). Each
    # set is shown alone, so the reused letters never collide.
    Action("confirm_save", "Save", "s", bar=CONTEXTUAL),
    Action("confirm_discard", "Discard", "d", bar=CONTEXTUAL),
    Action("confirm_keep", "Keep Editing", key_label="ESC", bar=CONTEXTUAL),
    Action("case_keep", "Rename, Keep Contents", "k", bar=CONTEXTUAL),
    Action("case_purge", "Rename, Delete Contents", "d", bar=CONTEXTUAL),
    Action("case_cancel", "Cancel", key_label="ESC", bar=CONTEXTUAL),
    # -- file: what EVERY file offers. The tree's own commands, wearing
    # buttons (Nick's "File" bar) — so they keep one meaning everywhere,
    # and ^DEL keeps the shape no single char can express. Paste has no
    # button on purpose: it belongs to the destination, not to this file.
    Action("open", "Open", "o", bar=FILE),
    Action("cut", "Cut", "x", bar=FILE),
    # ^c is reserved (interrupt): ^y stands in — logged in notes/qa/todo-2.md
    Action("copy", "Copy", "y", bar=FILE),
    Action("delete", "Delete", key_label="^DEL", bar=FILE),
    # -- actions: what this KIND offers, in spec order per kind
    # book (epub): split omnibus rides first
    Action("split_omnibus", "Split Omnibus"),
    Action("convert_mobi", "Convert to MOBI"),
    Action("convert_azw3", "Convert to AZW3"),
    Action("create_opf", "Write OPF"),
    Action("standardize", "Clean"),
    Action("book_cover", "Upload Cover"),
    Action("extract_cover", "Extract Cover"),
    # a single epub's sort is "Folderize" (spec); the FOLDER context keeps
    # the old word via its own button below — same handlers
    Action("sort_book", "Folderize"),
    # mobi/azw3
    Action("convert_epub", "Convert to EPUB"),
    # image — rotate/resize precede the converts (spec order)
    Action("rotate", "Rotate"),
    Action("resize", "Resize"),
    Action("crop", "Crop"),
    Action("trace", "Trace"),
    # comics: the one action that reads a FOLDER of images as a thing
    # (comics.py). Sitting here puts it after the image operations on an
    # image and before the folder ones on a folder — move it, Nick, if
    # the grouping reads wrong on either.
    Action("shrink", "Shrink"),
    Action("convert_jpg", "Convert to JPG"),
    Action("convert_png", "Convert to PNG"),
    Action("convert_tiff", "Convert to TIFF"),
    Action("convert_webp", "Convert to WEBP"),
    # vector: recover the artwork an .ai parks outside its artboard
    # (illustrator.py). Two buttons, one per product, the convert_* way.
    Action("rescue_pdf", "Rescue to PDF"),
    Action("rescue_svg", "Rescue to SVG"),
    # video: the subtitle suite, then posters/gif (spec order, minus
    # "watch" — it is the universal "Open" button on the File bar now)
    Action("get_subs", "Fetch Subtitles"),
    Action("clean_subs", "Clean Subs"),
    Action("shift_subs", "Shift Subs"),
    Action("download_posters", "Download Posters"),
    Action("gif", "Make GIF"),
    # the ebook gesture on a video (2026-08-22)
    Action("folderize_video", "Folderize"),
    # folder probes: sort keeps its folder word so a folder never shows
    # two "Folderize" buttons
    Action("sort", "Sort"),
    Action("folderize", "Folderize"),
    Action("strip_multi_artist", "Strip Multi-Artist"),
]

EDITABLE_KINDS: frozenset[str] = frozenset(PANELS)
"""Every kind whose details can take focus for editing — which is all of
them: every selection can at least be renamed. Audio and book carry a
metadata form; image, plain folder, video, and other edit as a
filename-only form (no fields) — rename is the edit, modeled on the
folder panel. Album-like folders never reach here: they descend into the
bulk form of their contents before the folder panel is consulted."""

DEBOUNCE_SECONDS = 0.15

PANEL_LABEL = {
    # kind → the widest label in its panel. The FILENAME row shares this
    # width, because its value has to line up with every other value
    # (Nick, 2026-10-26: "their values should be left-aligned together").
    # Audio and book are driven by their EditForm instead, whose widest
    # label depends on which tags the file actually carries.
    kinds.VIDEO: "embedded title",
    kinds.IMAGE: "dimensions",
    kinds.VECTOR: "artboard",
    kinds.FOLDER: "contains",
    kinds.OTHER: "type",
}

SPINNER = "⣷⣯⣟⡿⢿⣻⣽⣾"
"""Braille frames for a value (or a button group) still loading. Shown
AT THE PLACE the content will appear, so the wait is where the answer
will be (Nick, todo-6 ⁸)."""

SPIN_SECONDS = 0.1


LABEL_GUTTER = 3
"""Cells a field label's column adds to its text.

The label is a CHIP whose background touches the connector (todo-6 ⁴):
a cell of padding each side of the word. The third cell is the margin
Nick specified (⁷) — one cell after the widest FOCUSABLE label, which
works out to two after the widest read-only one, because a read-only
label has no trailing pad of its own. Either way every value in a panel
starts in the same column.
"""


class Spine(Widget):
    """THE PATH, drawn (always-available-actions-3, Layer 1/2).

    One widget down the details pane's left edge rather than a prefix on
    every row: it reads where the rows ARE and draws the line beside
    them — ``╭`` at the first, ``├──`` beside each row that holds a
    control, ``│`` between and below them, and ``╯`` where the line
    turns left toward the tree row the pane is about. A wrapped bar's
    second line gets ``│──``: it is the same row continuing, not a new
    junction.

    Nick asked (2026-10-26) for a better answer than his mockup's
    hand-patched ``├``, whose vertical and horizontal halves wanted
    different colors in one cell. This is it: the spine owns its own
    COLUMN, so the junction cell belongs to the spine and the stub that
    leaves it is a separate cell. One cell, one color.
    """

    MARGIN = 2
    """Blank cells between the tree's column and the line (todo-6 ³). The
    RUN crosses them on the exit row, which is why they belong to this
    widget rather than to the pane's padding — the stroke has to be
    continuous."""

    STUB = 2
    """The horizontal nub from the line to the row's own chip. The chip
    starts in the very next cell: its background touches the line
    (todo-6 ⁴/⁵)."""

    WIDTH = MARGIN + 1 + STUB

    COMPONENT_CLASSES = {"spine--path"}
    """The traversed stretch's color ($traversed-path-fg, in CSS)."""

    @property
    def _path_style(self):
        return self.get_component_rich_style("spine--path", partial=True)

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        # the width is the sum of the parts above, set HERE so there is one
        # source of truth: a CSS literal drifted from it once already
        self.styles.width = self.WIDTH
        self._exit: int | None = None
        """Pane-local y where the line turns toward the tree, if that row
        is on screen."""
        self._heads: set[int] = set()    # rows that hold a control
        self._tails: set[int] = set()    # a wrapped bar's later lines
        self._first: int | None = None
        self._last: int | None = None
        self._path: tuple[int, int] | None = None
        self._focused_row: int | None = None

    def restub(self) -> None:
        """Recompute the shape. The PANE calls this when its rows move,
        the tree scrolls, or focus travels; ``render_line`` then costs
        nothing.

        It used to walk the DOM per LINE, which is a query over every row
        in every panel (~100 widgets) forty times per repaint — on a pane
        that repaints constantly, it doubled the test suite's runtime
        (2026-10-27). Rendering is a hot path: look once.
        """
        pane = self.parent
        if pane is None:
            self._heads, self._tails, self._first = set(), set(), None
            self.refresh()
            return
        top = self.region.y
        heads: set[int] = set()
        tails: set[int] = set()
        block = None
        try:
            block = pane.query_one("#art-block")
        except Exception:
            pass
        for row in pane.query(".prow, ActionBar"):
            # ``prow`` = a row the path reaches: something focusable lives
            # on it. A read-only value row is not one (todo-6).
            if not row.display or not row.region.height:
                continue
            if (block is not None and row is not block
                    and block in row.ancestors):
                # inside the artwork block: the BRANCH reaches those, so
                # the main line does not stub them twice (todo-6 ⁴)
                continue
            at = row.region.y - top
            if at < 0:
                continue
            heads.add(at)
            if isinstance(row, ActionBar):
                # a WRAPPED bar keeps stubbing: its later lines hold
                # buttons too. A tall field row (an image) does not — the
                # line just runs past it. Only the lines that HOLD
                # buttons are stubbed: a wrapped bar now leaves a blank
                # line between its rows, and a blank line is not a row
                # the path can reach (todo-6).
                tails.update(at + off for off in row.row_offsets() if off)
        self._heads, self._tails = heads, tails
        self._first = min(heads) if heads else None
        self._last = max(heads | tails) if heads else None
        self._exit = self._exit_row()
        self._focused_row = self._focused_row_y()
        self._path = (None if self._exit is None or self._focused_row is None
                      else (min(self._exit, self._focused_row),
                            max(self._exit, self._focused_row)))
        self.refresh()

    def _exit_row(self) -> int | None:
        """Where the line turns toward the tree: the selected row's own
        screen line, in this widget's coordinates. None when that row is
        scrolled out of sight — the line then simply runs past."""
        try:
            tree = self.app.query_one("LibraryTree")
        except Exception:
            return None
        at = getattr(tree, "cursor_screen_y", lambda: None)()
        if at is None:
            return None
        local = at - self.region.y
        return local if 0 <= local < self.region.height else None

    def _focused_row_y(self) -> int | None:
        """The row holding focus, if it is one of ours. The line between
        it and the exit is the PATH, and it is lit (todo-6 ⁶)."""
        focused = self.app.focused
        pane = self.parent
        if focused is None or pane is None:
            return None
        top = self.region.y
        for node in (focused, *focused.ancestors):
            if node is pane or not isinstance(node, Widget):
                break
            if node.region.height and ("prow" in node.classes
                                       or isinstance(node, ActionBar)):
                return node.region.y - top
        return None

    def _junction(self, up: bool, down: bool,
                  left: bool, right: bool) -> str:
        """The box character for the arms that meet in this cell. ``left``
        is the run arriving from the tree; ``right`` the stub to this
        row's own chip."""
        return {
            (True, True, True, True): "┼",
            (True, True, True, False): "┤",
            (True, True, False, True): "├",
            (True, True, False, False): "│",
            (False, True, True, True): "┬",
            (False, True, True, False): "╮",
            (False, True, False, True): "╭",
            (True, False, True, True): "┴",
            (True, False, True, False): "╯",
            (True, False, False, True): "╰",
            (False, False, True, True): "─",
        }.get((up, down, left, right), " ")

    def render_line(self, y: int) -> Strip:
        """The line's four-or-five cells at ``y``.

        The PATH — from the selected tree row to the focused element —
        shows only the arms it actually uses, so it reads as one unbroken
        stroke: no ``┼``, no ``├``, no ``┤`` anywhere along it (Nick,
        todo-6 ³ / ⁸). Off the path, the line keeps the junctions that
        describe the pane's own shape.
        """
        plain = self.rich_style
        lit = self._path_style
        first, last, exit_at = self._first, self._last, self._exit
        if first is None or last is None:
            return Strip.blank(self.WIDTH, plain)
        low = first if exit_at is None else min(first, exit_at)
        high = last if exit_at is None else max(last, exit_at)
        if not low <= y <= high:
            return Strip.blank(self.WIDTH, plain)
        stub = y in self._heads or y in self._tails
        at_exit = y == exit_at
        focused_here = y == self._focused_row
        path = self._path
        on_path = path is not None and path[0] <= y <= path[1]
        if on_path:
            # along the path, each cell carries ONLY the path's own arms
            up = y > path[0]
            down = y < path[1]
            if at_exit:
                # ² : the run is only a PATH when focus has travelled down
                # it. With the node itself focused there is no travel, so
                # the junction keeps the pane's shape instead.
                glyph = self._junction(up=up, down=down, left=True,
                                       right=False)
            elif focused_here:
                glyph = self._junction(up=up, down=down, left=False,
                                       right=True)
            else:
                glyph = self._junction(up=True, down=True, left=False,
                                       right=False)
        else:
            glyph = self._junction(up=y > low, down=y < high,
                                   left=at_exit, right=stub)
        margin = "─" * self.MARGIN if at_exit else " " * self.MARGIN
        tail = "─" * self.STUB if stub else " " * self.STUB
        return Strip([
            # the RUN crossing the margin — a line, never a block, and
            # lit only when the path travels it (todo-6 ²)
            Segment(margin, lit if (at_exit and on_path) else plain),
            Segment(glyph, lit if on_path else plain),
            # the stub into the FOCUSED row is the path's last step (⁶)
            Segment(tail, lit if (focused_here and on_path) else plain),
        ], self.WIDTH)


class ArtSpine(Widget):
    """The path's BRANCH: from the album-art label, down past the picture,
    into the method buttons (Nick, todo-6 ⁴).

    The label itself is not focusable — it describes the picture, and what
    takes focus is Import and Fetch below it. So the line leaves the
    label, runs down beside the artwork, and turns into the buttons: the
    path says "these belong to that", which a chip on the label could not.
    """

    WIDTH = 4

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.styles.width = self.WIDTH
        self._bar_line: int | None = None

    def restub(self) -> None:
        """Find the row the method buttons sit on, in our coordinates."""
        stack = self.parent
        line = None
        if stack is not None:
            try:
                bar = stack.query_one("#art-bar")
            except Exception:
                bar = None
            if bar is not None and bar.display and bar.region.height:
                line = bar.region.y - self.region.y
        if line != self._bar_line:
            self._bar_line = line
            self.refresh()

    def render_line(self, y: int) -> Strip:
        style = self.rich_style
        bar = self._bar_line
        if bar is None or bar <= 0:
            return Strip.blank(self.WIDTH, style)
        if y == 0:
            text = "─╮  "          # leaving the label
        elif y < bar:
            text = " │  "          # down beside the picture
        elif y == bar:
            text = " ╰──"          # into the buttons
        else:
            return Strip.blank(self.WIDTH, style)
        return Strip([Segment(text, style)], self.WIDTH)


class FieldLabel(Label):
    """A field's name, painted as the row's CHIP.

    The mockup marks a focusable row by putting a block behind its LABEL
    — grey for "focusable", PRIMARY for "this is the one with focus" —
    and leaves the VALUE as plain text. The block hugs the word plus one
    cell of padding; the rest of the label column stays unpainted, so
    the values still line up down the pane (always-available-actions-3,
    Layer 1 vs Layer 2).

    The paint is markup rather than CSS because it covers only part of
    the widget, so the focus edge is applied from Python —
    ``DetailsView._sync_element_chrome``, the same watcher that colors
    the chords inside button labels.
    """

    def __init__(self, text: str = "", width: int = 0,
                 focusable: bool = True, **kw) -> None:
        super().__init__(**kw)
        self._text = text
        self._width = width
        self._focusable = focusable
        """Whether this row's value can be EDITED. A read-only row gets no
        chip and no stub from the Spine, so the two of them together say
        which rows the arrow keys reach (Nick, todo-6)."""
        self._active = False
        self._paint()

    def set_text(self, text: str, width: int | None = None) -> None:
        if width is not None:
            self._width = width
        self._text = text
        self._paint()

    def set_active(self, value: bool) -> None:
        """Whether this row's control is the thing with focus."""
        if value != self._active:
            self._active = value
            self._paint()

    def _paint(self) -> None:
        if not self._text:
            self.update("")
            return
        pad = " " * max(0, self._width - len(self._text) - 2)
        if not self._focusable:
            # a read-only row: plain label text, no block behind it, and
            # it starts where a chip's text would (todo-6 ⁴). One cell
            # MORE padding than a chip gets, because it has no trailing
            # pad of its own — which is how both land in one column (⁷).
            self.update(Content.from_markup(
                f" [$muted]{self._text}[/]{pad} "))
            return
        fg = "$focused-fg" if self._active else "$focusable-fg"
        bg = "$focused-bg" if self._active else "$focusable-bg"
        # a cell of padding INSIDE the block, each side: the background
        # touches the connector's stub on the left (todo-6 ⁴)
        self.update(Content.from_markup(
            f"[{fg} on {bg}] {self._text} [/]{pad}"))


def _panel_width(kind: str) -> int:
    """ONE label column per panel, as wide as the widest label it can
    show — the filename row included, since its value has to line up with
    the rest (Nick, todo-6 ⁷)."""
    widest = max(len(PANEL_LABEL.get(kind, "")), len("filename"))
    return widest + LABEL_GUTTER


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n:.0f} B"
        n /= 1024


def audio_info_label(filetypes: tuple[str, ...], bitrates: tuple[int, int],
                     length_seconds: float, size: int) -> str:
    """The audio info line: type · bitrate · length · size.

    Takes the bulk shapes so one selection or many render identically; a
    part nothing reported (an unknown bitrate, say) drops out of the line
    rather than printing a dash.
    """
    low, high = bitrates
    if not high:
        rate = ""
    elif low and round(low / 1000) != round(high / 1000):
        rate = f"{round(low / 1000)}–{round(high / 1000)} kbps"
    else:
        rate = f"{round(high / 1000)} kbps"
    return " · ".join(part for part in
                      ("/".join(filetypes), rate, f"{length_seconds:.0f}s",
                       human_size(size)) if part)


def _mk(text: str) -> str:
    """Escape a filename for Textual content markup."""
    return text.replace("[", r"\[")


PLAN_PREVIEW_LINES = 40


def render_shrink(plan) -> str:
    """The shrink preview: what each page costs now, and what the whole
    thing would cost after. The estimate names its own sample, because
    an estimate that does not is a promise (comics.py)."""
    pages = len(plan.pages)
    tall = plan.tallest
    resizing = plan.resizes
    lines = [
        f"{pages} page{'s' if pages != 1 else ''}, "
        f"{human_size(plan.before_total)} → "
        f"[bold]{human_size(plan.after_total)}[/]  "
        f"[dim]({plan.ratio:.0%}, estimated from "
        f"{plan.sampled} page{'s' if plan.sampled != 1 else ''})[/]",
        "",
        f"  JPEG quality {plan.quality}, 4:2:0 chroma",
    ]
    if resizing:
        lines.append(f"  tallest page {tall}px → {plan.height}px "
                     f"[dim](a spread keeps its width)[/]")
    else:
        lines.append(f"  {tall}px tall, near enough to {plan.height} — "
                     f"[dim]re-encoded, not resampled[/]")
    lines += ["",
              "  [dim]Pages are REPLACED. A page that would grow is left"
              " alone.[/]", ""]
    for page in plan.pages[:8]:
        lines.append(f"    {_mk(page.path.name)}  "
                     f"[dim]{page.width}×{page.height}, "
                     f"{human_size(page.before)}[/]")
    if pages > 8:
        lines.append(f"    [dim]…and {pages - 8} more[/]")
    return "\n".join(lines)


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
        #
        # ⌥+digit rides along: it is the positional chord's tmux-proof
        # spelling, and it reaches us as a PRINTABLE character (the macOS
        # Option glyph), so a field would otherwise type "¡" instead of
        # pressing button one.
        if not (event.key.startswith("ctrl+")
                or actions.ordinal_for_key(event.key) is not None):
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

    async def _matches(self) -> list[fs.CachedPath]:
        base, prefix = os.path.split(self.value)
        prefix = prefix.lower()
        # off the event loop: the completion may point at the NAS, and a
        # sleeping SMB disk answers a listing in seconds (see fs rule 3)
        children = await fs.acached_children(base or "/")
        return [child for child in children
                if child.name.lower().startswith(prefix)
                and (child.is_dir()
                     or kinds.kind_of(child, is_dir=False) == kinds.IMAGE)]

    async def action_complete(self) -> None:
        matches = await self._matches()
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

    async def _matches(self) -> list[fs.CachedPath]:
        base, prefix = os.path.split(self.value)
        prefix = prefix.lower()
        # off the event loop: the completion may point at the NAS, and a
        # sleeping SMB disk answers a listing in seconds (see fs rule 3)
        children = await fs.acached_children(base or "/")
        return [child for child in children
                if child.name.lower().startswith(prefix)
                and (child.is_dir()
                     or kinds.kind_of(child, is_dir=False) == kinds.IMAGE)]

    async def action_complete(self) -> None:
        matches = await self._matches()
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
    """Open a file in its default app (the ^open action's seam —
    monkeypatch this in tests, subprocess.run shares Popen).

    Handing a path to the desktop is the one shell-out with no library
    behind it: every package that claims to wrap this is a subprocess
    call plus a platform check, so mediasmith does the platform check
    itself rather than take a dependency for three lines.
    """
    if sys.platform == "win32":
        os.startfile(path)                              # noqa: S606
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(path)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


TRACE_HINT = "←→ adjust · ⇧←→ ×10 · esc close"


class TraceControl(Static, can_focus=True):
    """One Image Trace control: a stepper like ShiftControl. ←→ nudge a
    number by one (⇧ by ten), flip a switch, or cycle the format."""

    BINDINGS = [
        Binding("left", "nudge(-1)", show=False),
        Binding("right", "nudge(1)", show=False),
        Binding("shift+left", "nudge(-1, True)", show=False),
        Binding("shift+right", "nudge(1, True)", show=False),
        Binding("escape", "close", show=False),
    ]

    def __init__(self, control: str, **kwargs) -> None:
        super().__init__("", classes="trace-control", **kwargs)
        self.control = control

    def action_nudge(self, direction: int, big: bool = False) -> None:
        self.screen.query_one(DetailsView)._trace_nudge(
            self.control, direction, big)

    def action_close(self) -> None:
        self.screen.query_one(DetailsView)._trace_close()


CROP_CONTROLS: tuple[tuple[str, str], ...] = (
    ("ratio", "ratio"), ("left", "left"), ("top", "top"),
    ("right", "right"), ("bottom", "bottom"))
"""Crop's rows, top to bottom. Ratio first because it is usually the
whole answer — "make it square" — and the edges below it are the
adjustment (Nick, todo-6)."""

CROP_STEP, CROP_BIG_STEP = 1, 25
"""←→ move one pixel, ⇧←→ twenty-five. A page is thousands of pixels
tall, so the big step is what gets you there and the small one is what
lands it."""


class CropControl(Static, can_focus=True):
    """One crop control: ←→ nudge an edge (⇧ by twenty-five) or cycle
    the ratio. Shaped like TraceControl, which is the stepper the trace
    wizard established."""

    BINDINGS = [
        Binding("left", "nudge(-1)", show=False),
        Binding("right", "nudge(1)", show=False),
        Binding("shift+left", "nudge(-1, True)", show=False),
        Binding("shift+right", "nudge(1, True)", show=False),
        Binding("escape", "close", show=False),
    ]

    def __init__(self, control: str, **kwargs) -> None:
        super().__init__("", classes="crop-control", **kwargs)
        self.control = control

    def action_nudge(self, direction: int, big: bool = False) -> None:
        self.screen.query_one(DetailsView)._crop_nudge(
            self.control, direction, big)

    def action_close(self) -> None:
        self.screen.query_one(DetailsView)._crop_close()


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
            with Horizontal(classes="frow prow"):
                yield FieldLabel(classes="fkey")
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
                   mixed: frozenset[str] = frozenset(),
                   extra: int = 0) -> None:
        """``mixed`` names (bulk view: values diverge across the files)
        show empty with a "(mixed)" placeholder; typing into one means
        "apply this to every file"."""
        self._names = list(fields)[:self._pool]
        self._mixed = mixed
        labels = adapters.FIELD_LABELS
        # the FILENAME row shares this column, so it sets the floor: a
        # file with few tags must not leave its own name sticking out
        # (todo-6 ⁷)
        width = max((len(labels.get(n, n)) for n in self._names),
                    default=0, ) + LABEL_GUTTER
        width = max(width, len("filename") + LABEL_GUTTER,
                    len("album art") + LABEL_GUTTER)
        # ``extra``: cells the panel needs beyond its widest label — the
        # audio panel reserves the art branch's column so the picture
        # lines up with the other values (todo-6 ⁴)
        width += extra
        self.label_width = width
        for i, row in enumerate(self._rows()):
            if i < len(self._names):
                name = self._names[i]
                row.query_one(FieldLabel).set_text(
                    labels.get(name, name), width)
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
                yield FieldLabel(label, width, classes="fkey")
                yield OmniInput(id=wid, compact=True, classes="fval")
        for i in range(self.POOL):
            with Vertical(classes="omni-book", id=f"omni-book-{i}"):
                yield Label("", id=f"omni-head-{i}", classes="omni-head")
                with Horizontal(classes="frow"):
                    yield FieldLabel("title", width, classes="fkey")
                    yield OmniInput(id=f"omni-title-{i}", compact=True,
                                    classes="fval")
                with Horizontal(classes="frow"):
                    yield FieldLabel("series no.", width, classes="fkey")
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


# The app has NO MODAL SCREENS (Nick's answer #5, 2026-10-26). It had
# exactly two — ConfirmSave and ConfirmCaseRename, both destructive forks
# mid-write whose answer could not be inferred — and both are now states
# of the Contextual bar instead: the answers appear as buttons where the
# work is, the first one takes focus, and nothing else is reachable until
# one is pressed (DetailsView.ask). The cookbook rule that options go
# inline rather than in a modal now has no exception.


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

    class Settled(Message):
        """The pane finished showing ``path``: the read landed AND every
        late-filling probe answered, so the button bar has stopped
        changing shape. The positional chords resolve against a settled
        bar and never against a half-built one (Nick, 2026-10-26) — the
        printed number must not move under a finger already on its way
        down."""

        def __init__(self, path: Path | list[Path]) -> None:
            super().__init__()
            self.path = path

    def can_edit(self) -> bool:
        """Focus may enter this pane only when the shown kind is editable."""
        return self.kind in EDITABLE_KINDS and self._readable

    @property
    def settled(self) -> bool:
        """True when what the bar shows is what the selection has earned:
        the read is in and no probe is still out. ``Settled`` fires on the
        edge into this state; a buffered chord waits for it."""
        return self._readable and not self.busy

    @property
    def reading(self) -> bool:
        """A read is in flight: a selection on its way in, or a forced
        re-read of the one already on screen."""
        return self._pending is not None or self.loading_bulk

    @property
    def busy(self) -> bool:
        """The bar may still change shape — a read is in flight, or a
        button probe hasn't answered. The chord buffer drains when this
        goes false; ``settled`` adds that the read SUCCEEDED."""
        return self.reading or bool(self._probes_out)

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
        self._probes_out: set[str] = set()   # button probes still out
        self._spinning: set[str] = set()     # value ids showing a spinner
        self._spin_at = 0
        self._spin_timer = None
        self._all_chords: frozenset[str] | None = None   # lazy: needs compose
        self._question: tuple[list[str], object] | None = None
        """An open question: its answer actions, and what to call with the
        answer (see `ask`). While set, the Contextual bar owns focus."""
        self._asked_from = None
        """What had focus when the question went up, so answering it can
        put the user back where they were."""
        self._keep: frozenset[str] = frozenset()    # divs a re-read keeps open
        self._jobs: progress.JobToasts | None = None    # lazy: needs .app
        self._standardize_single = False    # a one-book run closes its toast
        self._pending_art: bytes | None = None   # unsaved replacement art
        self._baseline_art: bytes | None = None  # what discard restores
        self._art_candidates: list[artfetch.CoverCandidate] = []
        self._art_index = 0
        self._book_cover = False    # shown book has an extractable cover
        self._omnibus_ready = False     # probe: this epub holds ≥2 books
        self._omnibus_plan: omnibus.OmnibusPlan | None = None
        self._omnibus_editing = False   # the editable split form is on show
        self._folderize_ready = False   # probe: this folder has work to do
        self._shrink_ready = False      # probe: this folder is a comic
        self._shrink_plan: comics.ShrinkPlan | None = None
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
        self._trace_open = False
        # settings outlive the div: the next image opens where the last
        # one left off (Illustrator remembers its last trace too)
        self._trace_settings = trace.TraceSettings()
        self._trace_gray = None         # full-res greyscale source (PIL)
        self._crop_open = False
        self._crop_ratio = "free"
        self._crop_edges = {edge: 0 for edge in imageops.EDGES}
        self._crop_source = None        # the whole image, for the preview
        self._crop_gen = 0
        self._crop_debounce = None
        self._trace_source = None       # the original, for "view source"
        self._trace_view = "trace"      # which one the picture shows
        self._trace_gen = 0             # bumps per render: stale drops
        self._trace_debounce = None
        self._image_data: bytes | None = None   # shown image's bytes
        # refuse-overwrite escape hatch: (action title, source) armed by a
        # refusal; the next same-action press on the same file overwrites
        self._overwrite_arm: tuple[str, Path] | None = None

    # -- static layout ---------------------------------------------------------

    def _row(self, key: str, id: str, width: int,
             row_id: str | None = None) -> Horizontal:
        """One label+value row, READ-ONLY: a name and a value the user
        cannot edit. It carries no ``prow`` class, so the Spine draws no
        stub to it and its label wears no chip (Nick, todo-6) — between
        them, those two say which rows the arrow keys reach."""
        return Horizontal(FieldLabel(key, width, focusable=False,
                                     classes="fkey"),
                          Static("", id=id, classes="fval-static"),
                          classes="frow", id=row_id)

    def compose(self):
        # the path, drawn down the pane's left edge (Spine): docked, so it
        # does not scroll, and it reads the rows' SCREEN positions — which
        # keeps it aligned whether the pane scrolls or the tree does
        yield Spine(id="spine")
        yield Label("", id="dtitle", classes="dtitle")
        with Horizontal(id="row-fname", classes="frow prow"):
            yield FieldLabel("filename", len("filename") + LABEL_GUTTER,
                             id="fname-label", classes="fkey")
            yield FieldInput(id="fname", compact=True)
            yield Static("", id="fname-mark", classes="fmark")

        with Vertical(id="panel-audio", classes="panel"):
            yield EditForm(24, id="form-audio")
            # album art is the last field: label column matches the form,
            # image top-aligned with the label, left-aligned with inputs,
            # and a blank line above it (todo-6) — the artwork is its own
            # group, not the tail of the tag list
            yield Static("", classes="fgap")
            # ONE block (todo-6 ⁴): the label, the path's branch, and the
            # stack of things the branch leads to. The label describes the
            # picture rather than taking focus, so it wears no chip — the
            # BRANCH is what says the buttons below belong to it.
            with Horizontal(id="art-block", classes="prow"):
                yield FieldLabel(id="art-label", focusable=False,
                                 classes="fkey")
                yield ArtSpine(id="art-spine")
                with Vertical(id="art-stack"):
                    with Horizontal(id="row-art"):
                        yield Static("-", id="art-none",
                                     classes="fval-static")
                        with ArtField(id="art-field"):
                            yield image_widget(self.images, id="cover-audio")
                            yield Label("", id="cover-audio-dims",
                                        classes="cover-dims")
                        yield Static("", id="art-mark", classes="fmark")
                    # ^i Import (Nick, todo-6 ⁵). ctrl+i and TAB are the
                    # same byte outside the kitty protocol — see
                    # actions.RESERVED_KEYS for what that costs.
                    yield ActionBar(
                        Action("art_path", "Import", "i",
                               button_id="art-btn-path"),
                        Action("art_fetch", "Fetch", "f",
                               button_id="art-btn-fetch"),
                        id="art-bar")
                    with Horizontal(id="row-art-path"):
                        yield ArtPathInput(id="art-path", compact=True)

        with Vertical(id="panel-video", classes="panel"):
            width = _panel_width(kinds.VIDEO)
            yield self._row("embedded title", "video-title", width)
            yield self._row("container", "video-container", width)
            yield self._row("codec", "video-codec", width)
            yield self._row("size", "video-size", width)
            yield self._row("subtitles", "video-subs", width)
            yield self._row("posters", "video-posters", width)
            with Vertical(id="shift-div"):
                with Horizontal(id="shift-row", classes="prow"):
                    yield FieldLabel("shift", width, classes="fkey")
                    yield ShiftControl(" 0:00.0", id="shift-control")
                    yield Static("", id="shift-mark", classes="fmark")
                yield Static(SHIFT_HINT, id="shift-hint")
            with Vertical(id="gif-div"):    # the third wizard div
                with Horizontal(id="gif-row", classes="prow"):
                    yield FieldLabel("gif", width, classes="fkey")
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
            # the poster is a FIELD, exactly as album art is (Nick,
            # todo-6): its own label in the panel's column, the picture
            # top-aligned with it, and a blank line above it separating
            # the artwork from the metadata
            yield Static("", classes="fgap")
            with Horizontal(id="row-poster", classes="prow"):
                yield FieldLabel("poster", _panel_width(kinds.VIDEO),
                                 id="poster-label", classes="fkey")
                yield Static("-", id="poster-none", classes="fval-static")
                with ArtField(id="poster-field"):
                    yield image_widget(self.images, id="cover-video")
                    yield Label("", id="cover-video-dims",
                                classes="cover-dims")

        with Vertical(id="panel-book", classes="panel"):
            yield EditForm(12, id="form-book")
            # the cover is a FIELD too (todo-6), label column and all
            yield Static("", classes="fgap")
            with Horizontal(id="row-cover", classes="prow"):
                yield FieldLabel(id="cover-label", classes="fkey")
                yield Static("-", id="cover-none", classes="fval-static")
                with ArtField(id="cover-field"):
                    yield image_widget(self.images, id="cover-book")
                    yield Label("", id="cover-book-dims",
                                classes="cover-dims")
            # cover method: a path input toggled by the ^f cover button
            # (mirrors audio art-path). Enter applies, esc cancels.
            with Vertical(id="book-cover-div"):
                yield CoverPathInput(id="book-cover-path", compact=True)
                yield Static("⏎ apply · esc cancel", id="book-cover-hint")

        with Vertical(id="panel-image", classes="panel"):
            width = _panel_width(kinds.IMAGE)
            yield self._row("size", "image-size", width,
                            row_id="row-image-size")
            yield self._row("dimensions", "image-dims", width,
                            row_id="row-image-dims")
            with Vertical(id="resize-div"):     # the wizard div, shift-style
                with Horizontal(id="resize-row", classes="prow"):
                    yield FieldLabel("resize", width, classes="fkey")
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
            with Vertical(id="crop-div"):       # Crop
                crop_width = len("bottom") + LABEL_GUTTER
                for name, label in CROP_CONTROLS:
                    with Horizontal(classes="crop-row prow"):
                        yield FieldLabel(label, crop_width, classes="fkey")
                        yield CropControl(name, id=f"crop-{name}")
                yield Static("", id="crop-result")
                yield ActionBar(
                    Action("crop_apply", "save", "s",
                           button_id="crop-apply-btn"),
                    id="crop-bar")
            with Vertical(id="trace-div"):      # Image Trace
                width = len("ignore white") + LABEL_GUTTER
                for name, label in trace.CONTROLS:
                    with Horizontal(classes="trace-row prow"):
                        yield FieldLabel(label, width, classes="fkey")
                        yield TraceControl(name, id=f"trace-{name}")
                yield Static(TRACE_HINT, id="trace-hint")
                yield ActionBar(
                    Action("trace_save", "save", "s",
                           button_id="trace-save-btn"),
                    Action("trace_view", "view source", "v",
                           button_id="trace-view-btn"),
                    id="trace-bar")
            yield image_widget(self.images, id="cover-image")

        with Vertical(id="panel-vector", classes="panel"):
            width = _panel_width(kinds.VECTOR)
            yield self._row("size", "vector-size", width)
            # the canvas rows fill in late: reading them inflates the .ai's
            # private data, which is worker work (_probe_canvas)
            yield self._row("artboard", "vector-artboard", width)
            yield self._row("artwork", "vector-artwork", width)
            yield self._row("hidden", "vector-hidden", width)

        with Vertical(id="panel-folder", classes="panel"):
            width = _panel_width(kinds.FOLDER)
            yield self._row("contains", "folder-counts", width)
            # recursive totals — a walk, so they fill in late (Nick, todo-5)
            yield self._row("files", "folder-files", width)
            yield self._row("size", "folder-size", width)
            with Vertical(id="plan-preview"):   # folderize, multi-artist, …
                yield Static("", id="plan-tree")

        with Vertical(id="panel-other", classes="panel"):
            width = _panel_width(kinds.OTHER)
            yield self._row("size", "other-size", width)
            yield self._row("type", "other-type", width)

        # not a kind panel: a transient editable form shown while a split
        # is being set up (books ≤ pool); the pane holds focus so metadata
        # is corrected before the write
        with Vertical(id="panel-omnibus"):
            yield OmnibusForm(id="omnibus-form")

        # the three bars, in the order the mockup stacks them: what the
        # STATE offers, then what every file offers, then what this kind
        # offers. Each composed once with the actions that name it. They
        # share one container so the blank line above the stack belongs to
        # the stack — an empty Contextual bar must not leave a gap, and
        # trace mode hides the lot with one display flip.
        with Vertical(id="bars"):
            for bar_name, bar_id in ((CONTEXTUAL, "contextual-bar"),
                                     (FILE, "file-bar"),
                                     (ACTIONS, "actions-bar")):
                yield ActionBar(
                    *[a for a in PANE_ACTIONS if a.bar == bar_name],
                    id=bar_id)
            # where the kind's actions WILL be, while their probes run
            # (todo-6 ⁸): a group that resolves to nothing simply never
            # appears, and the spinner goes with it
            yield Static("", id="actions-loading", classes="prow")
        # parked below save while its final home is decided (audio only);
        # width matches the widest standard audio label (album artist, 12)
        yield self._row("info", "audio-info",
                        len("album artist") + LABEL_GUTTER,
                        row_id="row-audio-info")

    def on_mount(self) -> None:
        # chord colors inside button labels are markup, not CSS: mirror
        # the pane's focus-within flip onto them by hand (theme.py)
        self.watch(self.screen, "focused", self._sync_element_chrome)
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
        self.query_one("#crop-div").display = False
        self.query_one("#trace-div").display = False
        self._sync_pane_bar()

    _spine_dirty = False

    def redraw_connector(self) -> None:
        """Re-shape the connector: the tree calls this when its cursor or
        its scroll moves, and the pane itself when its rows do."""
        self._spine_dirty = True
        self.call_after_refresh(self._redraw_spine)

    def _redraw_spine(self) -> None:
        if not self._spine_dirty:
            return
        self._spine_dirty = False
        try:
            self.query_one("#spine", Spine).restub()
        except NoMatches:
            pass            # teardown, or before compose
        try:
            self.query_one("#art-spine", ArtSpine).restub()
        except NoMatches:
            pass

    def _sync_element_chrome(self, focused) -> None:
        """Focus moved: light the ONE element that has it, and re-ask the
        Contextual bar — ``ESC Exit`` prints only while focus is in here.

        Backgrounds are CSS ($focusable-bg / $focused-bg), but two
        things are painted with markup because they cover part of a
        widget — the chord inside a button label, and a field's label
        chip — so those are applied here, on the focus edge.
        """
        # ⁵: inside a bar, the buttons LEFT of the focused one are what
        # the path came through — mark them so CSS can color them
        for bar in self.query(ActionBar):
            row = bar.buttons()
            # the watcher's own argument, not `has_focus`: this runs
            # BEFORE Textual applies the new focus to the widget, so
            # asking the widget lagged a keystroke behind (2026-10-30)
            at = next((i for i, b in enumerate(row) if b is focused), None)
            for i, button in enumerate(row):
                traversed = at is not None and i < at
                button.set_traversed(traversed)
                link = bar._link_after(button)
                if link is not None:
                    link.set_class(traversed, "-traversed")
        for label in self.query(FieldLabel):
            row = label.parent
            label.set_active(
                focused is not None and row is not None
                and (focused is row or row in focused.ancestors))
        self._sync_pane_bar()
        self.redraw_connector()     # the lit stretch follows focus
        try:                        # …and so does the tree's own run
            self.app.query_one("LibraryTree").refresh_run()
        except Exception:
            pass
        # a wizard div opening or closing is a focus move, and it changes
        # which bars are on show — so the positional chords settle here
        # too (set_ordinal is a no-op when the number hasn't moved)
        self._number_action_buttons()

    # -- value plumbing ----------------------------------------------------------

    def _set(self, id: str, value: str) -> None:
        self._spinning.discard(id)      # a real value ends the wait
        self.query_one(f"#{id}", Static).update(value)

    def _set_loading(self, *ids: str) -> None:
        """Show a spinner where these values will appear (todo-6 ⁸)."""
        self._spinning.update(ids)
        self._spin_frame()

    def _spin_frame(self) -> None:
        """Advance every spinner on screen, and keep the timer running
        only while there is something to spin."""
        frame = SPINNER[self._spin_at % len(SPINNER)]
        self._spin_at += 1
        alive = False
        for id in list(self._spinning):
            try:
                self.query_one(f"#{id}", Static).update(frame)
                alive = True
            except NoMatches:
                self._spinning.discard(id)
        if self._probing_actions():
            marker = self.query_one("#actions-loading", Static)
            marker.update(frame)
            marker.display = True
            alive = True
        else:
            # the wait is over — hide the marker HERE as well as in
            # _sync_pane_bar. A probe that answers "no actions" ends the
            # spin without changing the bars, so nothing else ran and the
            # last frame sat there frozen (Nick, todo-6).
            try:
                self.query_one("#actions-loading").display = False
            except NoMatches:
                pass
        if alive and self._spin_timer is None:
            self._spin_timer = self.set_interval(SPIN_SECONDS,
                                                 self._spin_frame)
        elif not alive and self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None

    def _probing_actions(self) -> bool:
        """Whether a KIND action may still be on its way — the Actions bar
        is empty and a button probe has yet to answer (todo-6 ⁸)."""
        if self._question is not None or self.plan_preview_open():
            return False
        try:
            bar = self.query_one("#actions-bar", ActionBar)
        except NoMatches:
            return False
        return bool(self._probes_out) and not bar.buttons()

    def _set_cover(self, id: str, data: bytes | None) -> None:
        widget = self.query_one(f"#{id}")
        size: tuple[int, int] | None = None
        truncated = False
        if isinstance(widget, Static):     # images off / unavailable
            size = _image_size(data)       # dims still show where a label exists
        else:
            try:
                if data:
                    # decoded HERE, not in the widget's render(): a damaged
                    # cover must fail where it can be caught (images.decode)
                    image, truncated = images.decode(data)
                    widget.image = image
                    widget.display = True
                    size = image.size
                else:
                    widget.display = False
            except Exception:
                widget.display = False
        self._set_cover_dims(f"{id}-dims", size, truncated)
        # the slot's "-" shows when there is no picture in it (todo-6:
        # the cover and the poster are fields, so they read like fields)
        none_id = {"cover-book": "cover-none",
                   "cover-video": "poster-none"}.get(id)
        if none_id is not None:
            self.query_one(f"#{none_id}", Static).display = size is None

    def _set_cover_dims(self, id: str, size: tuple[int, int] | None,
                        truncated: bool = False) -> None:
        """Print the cover's pixel dimensions ('600 × 600') beneath it, for
        the kinds that carry a dims label (album art, book cover, video
        poster). A salvaged image says so — the missing bottom of the art
        is the file's fault, not the pane's."""
        labels = self.query(f"#{id}")
        if not labels:
            return
        label = labels.first(Label)
        if size:
            label.update(f"{size[0]} × {size[1]}"
                         + (" · damaged" if truncated else ""))
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
        self._probes_out = set()
        self._keep = frozenset()
        self._focus_after_load = False
        self._baseline = None
        self._trace_hide(restore=False)
        self.query_one("#dtitle", Label).update("")
        self.query_one("#dtitle").display = True
        self.query_one("#row-fname").display = False
        self.query_one("#row-audio-info").display = False
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False
        self._sync_pane_bar()

    def preview(self, path: Path, immediate: bool = False,
                force: bool = False) -> None:
        """Debounced: browsing quickly must not read every file passed over.

        ``force`` re-reads a selection the pane is already showing — what
        a write that just landed needs, and the only thing that does.
        Without it, re-previewing the shown path is a NO-OP: the <1s Nick
        felt on ⏎ was this pane reading, synchronously, a file the
        debounce had already read 150ms after he landed on the row.
        """
        self._queue_preview(path, immediate, force)

    def preview_bulk(self, paths: list[Path], immediate: bool = False,
                     force: bool = False) -> None:
        """Multi-file selection preview: same debounce, merged details."""
        self._queue_preview(list(paths), immediate, force)

    def _queue_preview(self, target: Path | list[Path],
                       immediate: bool, force: bool = False) -> None:
        if force:
            adapters.forget(target[0].parent if isinstance(target, list)
                            else target)
        elif self._already_applied(target):
            # already on screen and settled: nothing to read, nothing to
            # rebuild. Pending edits and open wizard divs survive a
            # re-select for free, which the old re-read had to work for.
            self._pending = None
            if self._debounce is not None:
                self._debounce.stop()
                self._debounce = None
            self._claim_focus()
            return
        self._pending = target
        if self._debounce is not None:
            self._debounce.stop()
            self._debounce = None
        if immediate:
            self._apply_pending()
        else:
            self._debounce = self.set_timer(DEBOUNCE_SECONDS, self._apply_pending)

    def _already_applied(self, target: Path | list[Path]) -> bool:
        """True when a preview of ``target`` would rebuild what is already
        on screen — the short-circuit that makes a re-select free."""
        if not self._readable:
            return False
        if isinstance(target, list):
            return self.paths == target
        return self.paths is None and self.path == target

    def showing(self, target: Path | list[Path]) -> bool:
        """Whether the pane is about this selection — read or still
        reading. An album-like folder is about the FOLDER the tree's
        cursor is on and about the children its form edits, so a chord
        captured on the folder resolves against the form it opened
        (otherwise ^y on an album would wait forever for a bulk pane to
        call itself a folder — 2026-10-26)."""
        if isinstance(target, list):
            return self.paths == target
        return self.path == target

    def _reset_state(self, keep_trace: bool = False) -> None:
        self._readable = False
        self._probes_out = set()     # a new selection waits on its own probes
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
        self._shrink_ready = False
        self._folderize_plan = None
        self._rescue_ready = False
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
        if not keep_trace:
            self._trace_hide(restore=False)

    def _apply_pending(self) -> None:
        """Show the pending selection — from cache if it is there, from a
        worker if it is not. NOTHING here touches the filesystem: the read
        was the last event-loop call in the app (rule 4), and a spun-down
        SMB disk made it a freeze rather than a wait."""
        if self._pending is None:
            return
        target = self._pending
        if isinstance(target, list):
            self._pending = None
            self._begin_bulk(target, origin=None)
            return
        # re-previewing the SAME file (a resize/gif just landed and the
        # tree re-listed, or a rotate refreshed the pane) must not slam
        # an open wizard div shut under the user. Decided HERE, before the
        # read moves self.path, and carried to the apply step.
        same = target == self.path and self.paths is None
        self._keep = frozenset(
            name for name, open_now in (("resize", self._resize_open),
                                        ("gif", self._gif_open),
                                        ("trace", self._trace_open))
            if open_now and same)
        # self.path is the pane's TARGET from here on — set before the read,
        # not after it, so a worker that comes back late can tell whether
        # anyone still wants its answer (_apply_resolved's one guard).
        self.path = target
        self.paths = None
        resolved = adapters.peek(target)
        if resolved is not None:
            self._pending = None
            self._apply_resolved(resolved)
            return
        self._begin_read(target, same=same)

    def _begin_read(self, target: Path, same: bool = False) -> None:
        """The cold path: say what we know and read the rest in a thread.

        ``same`` is a FORCED re-read of what is already on screen (a write
        just landed): those values are stale by a hair, not wrong, so the
        panel and the bar stay up rather than flashing the whole pane
        through "reading…". Either way ``busy`` is true until the answer
        lands, so nothing treats the pane as settled meanwhile.
        """
        if same:
            self._read_worker(target, None)
            return
        self.kind = None
        self._reset_state(keep_trace="trace" in self._keep)
        self.query_one("#dtitle", Label).update(f"{target.name} — {READING}")
        self.query_one("#dtitle").display = True
        self.query_one("#row-fname").display = False
        self.query_one("#row-audio-info").display = False
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = False
        self._sync_pane_bar()
        # the tree knows is_dir from its DirEntry and could hand it
        # over; until it does, the worker pays the one stat
        self._read_worker(target, None)

    @work(thread=True, exclusive=True, group="read")
    def _read_worker(self, target: Path, is_dir: bool | None) -> None:
        # one pass for the kind, the album-folder probe, and the details:
        # three filesystem answers the pane used to take on its own thread
        try:
            resolved = adapters.resolve(target, is_dir=is_dir)
        except Exception as error:
            self.app.call_from_thread(self._read_failed, target, error)
            return
        self.app.call_from_thread(self._apply_resolved, resolved)

    def _read_failed(self, target: Path, error: Exception) -> None:
        if self.path != target or self.paths is not None:
            return                          # the cursor moved on
        if not self._dom_intact():
            return
        self._pending = None
        self._readable = False      # a forced re-read can land here too
        self.query_one("#dtitle", Label).update(
            f"{target.name} — unreadable ({error})")
        self._trace_hide(restore=False)
        self._show_editable(False)
        # a descent armed on a file that turns out unreadable must not fire
        # later, on whatever row the cursor reaches next
        descending = self._focus_after_load
        self._claim_focus()         # disarms (an unreadable pane can't focus)
        if descending:
            self.app.view_details()     # narrow: the error IS the view
        self._settle()

    def _apply_resolved(self, resolved: adapters.Resolved) -> None:
        """Fill the pane from a resolved selection. Synchronous and
        IO-free — equally the cache-hit path and the worker's callback."""
        target = resolved.path
        if self.path != target or self.paths is not None:
            return                  # a later selection already took over
        if not self._dom_intact():
            return                  # torn down under a worker callback
        self._pending = None
        self.kind = resolved.kind
        self._reset_state(keep_trace="trace" in self._keep)
        if resolved.bulk:           # an album-like folder edits as its contents
            self._begin_bulk(resolved.bulk, origin=target)
            return
        assert resolved.details is not None
        title = self.query_one("#dtitle", Label)
        title.update(self.path.name)
        for panel in PANELS:
            self.query_one(f"#panel-{panel}").display = (panel == self.kind)
        self.query_one("#row-audio-info").display = False   # _fill_audio shows it
        self._readable = True
        self._show_editable(self.can_edit())
        getattr(self, f"_fill_{self.kind}")(self.path, resolved.details)
        self._align_filename()      # the form's column is known now
        self._baseline = self._current_state()
        self._refresh_marks()
        if "resize" in self._keep and self.kind == kinds.IMAGE:
            # reopen without re-prefilling: the user's numbers stand
            self._resize_open = True
            self.query_one("#resize-div").display = True
        if "gif" in self._keep and self.kind == kinds.VIDEO:
            self._gif_open = True
            self.query_one("#gif-div").display = True
        if self._trace_open:
            # a trace just landed beside the image and the tree re-listed:
            # the fill re-showed what trace mode hides, so hide it again
            self._trace_apply_layout()
            self._trace_schedule()
        self._claim_focus()
        self._settle()

    # -- questions: the micro-modals, as a state of the Contextual bar -------
    # Nick's answer #5 (2026-10-26): "replace the modals with an inline
    # change to the contextual button bar … move focus to the first button
    # on this bar … and prevent the user from navigating away from this
    # button bar until the modal content is resolved." Both modals the app
    # had are questions of this shape — a destructive fork mid-write whose
    # answer cannot be inferred — so both became bar states, and anything
    # else of that shape uses `ask` rather than a new screen.

    def ask(self, choices: list[str], decided, prompt: str | None = None,
            title: str = "") -> None:
        """Put a question's answers on the Contextual bar and lock focus
        to them. ``choices`` are action names the bar already holds, the
        first takes focus, and nothing else is reachable until one of them
        is pressed. Any explanation rides a toast — the buttons ARE the
        question, as the mockup's unsaved-changes bar shows it."""
        self._question = (list(choices), decided)
        self._asked_from = self.app.focused      # "keep editing" goes back
        self._sync_pane_bar()
        self.app.reveal_details()
        self.query_one(f"#act-{choices[0]}", ActionButton).focus()
        if prompt:
            self.notify(prompt, title=title or "confirm",
                        severity="warning", timeout=12)

    @property
    def question_open(self) -> bool:
        return self._question is not None

    @property
    def focus_locked(self) -> bool:
        """Whether a sub-form has taken focus and confined the keys to
        its own controls (the lockdown, todo-4). A tree command from
        outside has to wait for it to be saved or cancelled — the one
        exception to "a printed chord works from anywhere"."""
        return self._focus_scope() is not None

    @property
    def focus_inside(self) -> bool:
        """Whether the thing with focus is in this pane — which is what
        makes ``ESC Exit`` worth printing."""
        focused = self.app.focused if self.is_attached else None
        return focused is not None and (focused is self
                                        or self in focused.ancestors)

    def _answer(self, choice: str) -> None:
        """Resolve the open question — first answer wins, as the modals'
        own guard did (a second dismiss was app death: fuzz seed 10)."""
        if self._question is None:
            return
        _, decided = self._question
        self._question = None
        self._sync_pane_bar()
        # back to the control the question interrupted, BEFORE the answer
        # runs: "keep editing" means carry on where you were, and any
        # other answer moves focus itself (to the tree, or into a plan)
        was, self._asked_from = self._asked_from, None
        if was is not None and was.is_attached and was.display:
            try:
                was.focus()
            except Exception:
                pass
        decided(choice)

    def action_confirm_save(self) -> None:
        self._answer("save")

    def action_confirm_discard(self) -> None:
        self._answer("discard")

    def action_confirm_keep(self) -> None:
        self._answer("cancel")

    def action_case_keep(self) -> None:
        self._answer("keep")

    def action_case_purge(self) -> None:
        self._answer("purge")

    def action_case_cancel(self) -> None:
        self._answer("cancel")

    def _claim_focus(self) -> None:
        """Descend if a descent was waiting on this read. ⏎ no longer
        blocks on the NAS — it arms this and lets the tree keep the keys."""
        if not self._focus_after_load:
            return
        self._focus_after_load = False
        if self.can_edit():
            self.focus()

    # -- settling: the read, then the button probes -----------------------------------

    BUTTON_PROBES = {
        # name → (the engine's test, the flag _sync_pane_bar reads). These
        # six are what `settled` waits for, because each one PUTS A BUTTON
        # on the bar: a late yes renumbers every button to its right. A
        # probe that fills only a VALUE (a video's header, a folder's
        # totals, an .ai's canvas) can land whenever it likes — no chord
        # moves when it does — so it stays outside this table.
        "folderize": (folderize, "probe", "_folderize_ready"),
        "shrink": (comics, "probe", "_shrink_ready"),
        "multiartist": (multiartist, "probe", "_multiartist_ready"),
        "omnibus": (omnibus, "probe", "_omnibus_ready"),
        "sort": (booksort, "probe", "_sort_ready"),
        "sort_book": (booksort, "probe_book", "_sort_ready"),
        "standardize": (standardize, "probe_folder", "_standardize_ready"),
    }
    """(module, attribute, flag) — looked up by NAME at call time, not
    bound here: a dict of function objects cannot be monkeypatched, which
    made the probes untestable from the app's side (2026-10-30)."""

    def _probe(self, name: str, path: Path) -> None:
        """Launch a button-bearing probe and remember the bar is still
        incomplete until it answers.

        One group PER PROBE, exclusive — so arrowing onto the next row
        cancels the row we left before its probe even starts. Six zip
        reads per keypress down a folder is how the NAS gets slow (rule
        4); a cancelled launch is safe because the new selection cleared
        and re-added the name it answers for. ``run_worker`` rather than
        ``@work`` because the group is per CALL, not per method.
        """
        self._probes_out.add(name)
        self.run_worker(partial(self._probe_body, name, path),
                        group=f"probe-{name}", exclusive=True, thread=True)

    def _probe_body(self, name: str, path: Path) -> None:
        module, attr, _ = self.BUTTON_PROBES[name]
        test = getattr(module, attr)
        try:
            ready = bool(test(path))
        except Exception:
            ready = False       # a probe that cannot answer offers no button
        try:
            self.app.call_from_thread(self._probed, name, path, ready)
        except Exception:
            pass        # every probe reports now, including during teardown
                        # (_probe_totals' guard, for the same reason)

    def _probed(self, name: str, path: Path, ready: bool) -> None:
        """One probe answered — ready or not, both end the wait. A thread
        can't be cancelled mid-read, so an answer for a selection already
        left behind lands here too: it must not settle the current one."""
        if self.path != path or not self._dom_intact():
            return
        self._probes_out.discard(name)
        if ready and not self.plan_preview_open():
            setattr(self, self.BUTTON_PROBES[name][2], True)
            self._sync_pane_bar()
        self._settle()

    def _settle(self) -> None:
        """Announce the busy→idle edge for the selection on show.

        Posted even when the read FAILED: the pane has stopped changing
        shape either way, and the buffered chords waiting on it have to
        be let go rather than wait for a bar that will never arrive.
        """
        if self.busy:
            return
        target = self.paths if self.paths is not None else self.path
        if target is not None:
            self.post_message(self.Settled(target))

    def all_chords(self) -> frozenset[str]:
        """Every chord ANY pane button can print, on show or not.

        The app buffers these while the pane is unsettled (Nick's answer
        #4), so the set has to be known before the bar that will answer
        them is built. Derived from the composed bars, so adding an
        action keeps it honest.
        """
        if self._all_chords is None:
            self._all_chords = frozenset(
                chord for button in self.query(ActionButton)
                if (chord := button.spec.chord) is not None)
        return self._all_chords

    # -- bulk view: one form applied to many files -----------------------------------

    @property
    def loading_bulk(self) -> bool:
        return self.paths is not None and not self._readable

    def invalidate(self) -> None:
        """Forget that what is on screen was read, without clearing it: the
        next preview of the same selection re-reads instead of
        short-circuiting. ^r refresh, and nothing else."""
        self._readable = False

    def focus_when_loaded(self) -> None:
        """Arm the descent: take focus as soon as the selection on its way
        in can hold it (_claim_focus), or immediately if it already is."""
        self._focus_after_load = True
        if not self.reading:
            self._claim_focus()

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
        form.set_fields(bulk.fields, bulk.mixed,
                        extra=ArtSpine.WIDTH if bulk.kind == kinds.AUDIO
                        else 0)
        self._align_filename()
        if bulk.kind == kinds.AUDIO:
            self.query_one("#art-label", FieldLabel).set_text(
                "album art", form.label_width - ArtSpine.WIDTH)
            self._set("audio-info",
                      audio_info_label(bulk.filetypes, bulk.bitrates,
                                       bulk.length_seconds, bulk.size))
            self.query_one("#row-audio-info").display = True
            self._baseline_art = bulk.cover
            self._art_mixed = bulk.cover_mixed
            self._show_art(bulk.cover, mixed=bulk.cover_mixed)
        else:
            self._label_cover()
            self._set_cover("cover-book", bulk.cover)
        self._baseline = self._current_state()
        self._refresh_marks()
        if self.path is not None:               # album-folder origin: the
            self._probe("folderize", self.path)    # folder actions still apply
            self._probe("shrink", self.path)
            self._probe("multiartist", self.path)
            self._probe("standardize", self.path)
            self._probe("sort", self.path)
        self._claim_focus()
        self._settle()

    def _show_editable(self, editable: bool) -> None:
        """Editable selections show the filename input; others the title."""
        self.query_one("#dtitle").display = not editable
        self.query_one("#row-fname").display = editable
        self._sync_pane_bar()
        if editable and self.path is not None:
            self.query_one("#fname", Input).value = self.path.name
        self._align_filename()

    def _align_filename(self) -> None:
        """Give the filename's chip the panel's label column, so its value
        lines up with every other value. A metadata form's column depends
        on the tags the file carries, so it is asked; a fixed panel's
        comes from PANEL_LABEL."""
        form = self._active_form()
        width = (form.label_width if form is not None and form.label_width
                 else _panel_width(self.kind or ""))
        self.query_one("#fname-label", FieldLabel).set_text("filename", width)

    def _fill_audio(self, path: Path, d: adapters.AudioDetails) -> None:
        form = self.query_one("#form-audio", EditForm)
        form.set_fields(d.fields, extra=ArtSpine.WIDTH)
        self.query_one("#art-label", FieldLabel).set_text(
            "album art", form.label_width - ArtSpine.WIDTH)
        self._set("audio-info",
                  audio_info_label((d.filetype,) if d.filetype else (),
                                   (d.bitrate, d.bitrate),
                                   d.length_seconds, d.size))
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
        # both fill in late: the title and the codec are header reads, and
        # a header on the NAS is not an event-loop call (rule 4)
        self._set_loading("video-title", "video-codec")
        self._set("video-subs", d.subtitle_name or "none")
        self._set("video-posters", d.poster_name or "none")
        self._set_cover("cover-video", d.poster_bytes)
        # clean/shift work on SRT only (the engine's format); .ass/.vtt
        # siblings still show in the row but get no buttons
        self._video_srt = (path.parent / d.subtitle_name
                           if d.subtitle_name
                           and d.subtitle_name.endswith(".srt") else None)
        self._sync_pane_bar()       # subtitle buttons appear with the file
        self._probe_container(path)

    @work(thread=True, exclusive=True, group="probe")
    def _probe_container(self, path: Path) -> None:
        """Title and codec in one worker: two reads of the same header."""
        title = adapters.probe_video_title(path) or "—"
        codec = adapters.probe_video_codec(path) or "—"
        if self.path == path:
            self.app.call_from_thread(self._set, "video-title", title)
            self.app.call_from_thread(self._set, "video-codec", codec)

    def _label_cover(self) -> None:
        """The book cover's label column is the book form's (todo-6)."""
        form = self.query_one("#form-book", EditForm)
        self.query_one("#cover-label", FieldLabel).set_text(
            "cover", form.label_width or len("cover") + LABEL_GUTTER)

    def _fill_book(self, path: Path, d: adapters.BookDetails) -> None:
        self.query_one("#form-book", EditForm).set_fields(d.fields)
        self._label_cover()
        self._set_cover("cover-book", d.cover)
        self._book_cover = d.cover is not None
        self._sync_pane_bar()       # extract-cover appears with the cover
        if path.suffix.lower() == ".epub":
            self._probe("omnibus", path)   # split button fills in late
            self._probe("sort_book", path)  # sort button fills in late too

    def _fill_image(self, path: Path, d: adapters.ImageDetails) -> None:
        self._set("image-size", human_size(d.size))
        has_dims = bool(d.width and d.height)
        self._set("image-dims",
                  f"{d.width} × {d.height}" if has_dims else "—")
        self._resize_base = (d.width, d.height) if has_dims else None
        self._image_data = d.data
        if not self._trace_open:        # the trace preview owns the picture
            self._set_cover("cover-image", d.data)
        self._sync_pane_bar()       # convert/resize/rotate ride the kind

    def _fill_folder(self, path: Path, d: adapters.FolderDetails) -> None:
        summary = " · ".join(
            f"{d.counts[k]} {k}{'s' if d.counts[k] != 1 else ''}"
            for k in (kinds.FOLDER, kinds.VIDEO, kinds.AUDIO,
                      kinds.BOOK, kinds.IMAGE, kinds.OTHER)
            if d.counts.get(k)) or "empty"
        self._set("folder-counts", summary)
        self._set_loading("folder-files", "folder-size")
        self._probe_totals(path)
        self._probe("folderize", path)
        self._probe("shrink", path)
        self._probe("multiartist", path)
        self._probe("standardize", path)
        self._probe("sort", path)

    @work(thread=True, exclusive=True, group="folder-totals")
    def _probe_totals(self, root: Path) -> None:
        """Files and bytes under the folder — one stat per file, so a
        worker, and a budget inside the walk (fs.tree_totals).

        The walk gives up as soon as the selection moves: a thread can't
        be cancelled from outside, and arrowing down a list of folders
        would otherwise leave one live walk per row on the same share.
        """
        try:
            totals = fs.tree_totals(root, should_stop=lambda: self.path != root)
        except OSError:
            totals = None
        try:
            self.app.call_from_thread(self._totals_probed, root, totals)
        except Exception:
            pass    # the app closed while we walked; there is nobody to tell
                    # (a walk outlives the pane by design — every other probe
                    # returns in milliseconds, this one can be seconds)

    def _totals_probed(self, root: Path, totals: fs.Totals | None) -> None:
        if self.path != root:               # selection moved on
            return
        if totals is None:                  # unreadable: say so, don't hang
            self._set("folder-files", "—")
            self._set("folder-size", "—")
            return
        # a budget-capped walk reports a FLOOR: "1,204+ files · 8.7 GB+"
        more = "" if totals.complete else "+"
        self._set("folder-files", f"{totals.files:,}{more}")
        self._set("folder-size", human_size(totals.bytes) + more)

    def _fill_vector(self, path: Path, d: adapters.VectorDetails) -> None:
        self._set("vector-size", human_size(d.size))
        for row in ("vector-artboard", "vector-artwork", "vector-hidden"):
            self._set(row, "—")
        if illustrator.is_illustrator(path):
            self._set_loading("vector-artboard", "vector-artwork",
                              "vector-hidden")
            self._probe_canvas(path)    # the canvas rows fill in late

    @work(thread=True, exclusive=True, group="canvas-probe")
    def _probe_canvas(self, path: Path) -> None:
        """Read the .ai's own header for its artboard and artwork bounds.

        Off the event loop on purpose: it inflates the file's private data
        (½ MB on a real logo), and the library lives on SMB."""
        canvas = illustrator.read_canvas(path)
        if canvas is not None:
            self.app.call_from_thread(self._canvas_probed, path, canvas)

    def _canvas_probed(self, path: Path, canvas) -> None:
        if self.path != path or self.kind != kinds.VECTOR:
            return                      # the selection moved while we read
        self._set("vector-artboard", illustrator.measure(canvas.artboard))
        self._set("vector-artwork", illustrator.measure(canvas.artwork))
        self._set("vector-hidden", illustrator.describe_hidden(canvas))
        self._rescue_ready = canvas.offboard
        self._sync_pane_bar()           # the buttons appear with the finding

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
        # the artwork slot is a field on every kind that has one (todo-6)
        art_slot = {kinds.AUDIO: "#art-field", kinds.BOOK: "#cover-field",
                    kinds.VIDEO: "#poster-field"}.get(self.kind or "")
        if art_slot is not None and self.paths is None:
            fields.append(self.query_one(art_slot, ArtField))
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
            # Save appears with the first edit and goes with the last
            # (todo-6), so the bar follows dirtiness keystroke by keystroke
            self._sync_pane_bar()

    def focus(self, scroll_visible: bool = True):
        """Focusing the pane means editing: land on the filename input
        (or, while Image Trace owns the panel, on its first control)."""
        if self._trace_open:
            self.query_one(TraceControl).focus(scroll_visible)
            return self
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

    NUMBERED_BARS = ("actions-bar",)
    """The one bar whose buttons wear ^1…^9 — "the filetype button bar",
    which is where Nick's complaint lives: too many unmemorable letters.

    Every other bar keeps LETTERS, because each is short and fixed and
    the letter means the same thing everywhere: save/apply/cancel on the
    Contextual bar, open/cut/copy/delete on the File bar, import/fetch
    under the album art, and a wizard's own save. A numbered bar prints
    no letters at all (action_markup), so these are the bars whose chords
    stay printed — and a printed chord is the only kind that works.
    """

    def _number_action_buttons(self) -> None:
        """Hand out ^1…^9 — per numbered bar, each starting at 1.

        Which bar answers a number is decided by focus, not by the label:
        a focused wizard confines dispatch to its own controls
        (_focus_scope), so its ^1 is its own.
        """
        active = self._active_bars()
        for bar in self.query(ActionBar):
            numbered = bar in active and bar.id in self.NUMBERED_BARS
            bar.number_from(1 if numbered else None)

    def _art_buttons(self) -> list[ActionButton]:
        if self.kind != kinds.AUDIO or not self.can_edit():
            return []
        return self.query_one("#art-bar", ActionBar).buttons()

    def _sync_pane_bar(self) -> None:
        """Show the buttons the current selection has earned, across all
        three bars — one decision, fanned out (the bars keep what they own).
        """
        names: set[str] = set()
        if self._question is not None:          # a question owns the bars
            names = set(self._question[0])
        elif self.plan_preview_open():          # …as does a preview
            names = {"plan_apply", "plan_cancel"}
        else:
            # The File bar: whatever this selection is, it can be handed
            # to the OS, carried, or trashed. These are the tree's own
            # commands wearing buttons, so they do NOT ride the save gate
            # the way they did when a button had to be focus-reachable
            # (Nick, 2026-10-26 — the actions are always available now).
            if self.path is not None or self.paths is not None:
                names |= {"cut", "copy", "delete"}
            if self._open_target() is not None:
                names.add("open")               # every single file, first
            if self.focus_inside:
                names.add("exit")               # the way back up (todo-6)
            if self.dirty:
                # only when there is something to save (Nick, todo-6): a
                # Save that writes nothing reads as a dead key
                names.add("save")
            # …and the KIND's own actions, which have nothing to do with
            # whether there are edits pending
            if self.can_edit():
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
                    names |= {"resize", "rotate", "crop", "trace", "shrink"}
                # the probe found work outside the artboard: the buttons
                # showing up ARE the finding (Nick, 2026-09-29)
                if (self.kind == kinds.VECTOR and self.paths is None
                        and self._rescue_ready):
                    names |= {"rescue_pdf", "rescue_svg"}
            if self._folderize_ready:           # probe: work to do below
                names.add("folderize")
            if self._shrink_ready:              # probe: a run of pages
                names.add("shrink")
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
                # (a pending shift is "dirty", so Save shows itself)
        try:
            bars = [self.query_one(f"#{id}", ActionBar)
                    for id in ("contextual-bar", "file-bar", "actions-bar")]
        except NoMatches:
            # a probe worker's call_from_thread can land mid-teardown,
            # after the pane's children are gone — a late result is
            # meaningless then, not an error (flaked the suite twice)
            return
        for bar in bars:
            # every bar gets the WHOLE set and keeps what it owns: one
            # decision about what this selection offers, three rows
            bar.set_visible(names)
        try:
            waiting = self._probing_actions()
            self.query_one("#actions-loading").display = waiting
            if waiting:
                self._spin_frame()
        except NoMatches:
            pass
        # the spine draws itself from where the rows ARE, so it has to be
        # told when they move — which is here: every selection change and
        # every bar change comes through this method. Coalesced, because
        # this method also runs on every probe answer.
        self._spine_dirty = True
        self.call_after_refresh(self._redraw_spine)
        self._number_action_buttons()   # positions moved with the visible set
        # the tree's ^f mirrors whatever folderize this selection earned,
        # and the strip only prints a key that works — so a bar change is
        # a strip change (Nick, 2026-08-22). Guarded like the query above:
        # a late probe result can land after the app is on its way out.
        try:
            self.app.sync_strips()
        except Exception:
            pass

    def job(self, key: str, title: str, message: str, *,
            severity: str = "information", done: bool = False,
            timeout: float = progress.FINAL_TIMEOUT) -> None:
        """Say ``message`` on the toast belonging to job ``key``.

        One running job owns ONE toast: the first report raises it, later
        ones replace its text in place, and ``done`` releases it to fade
        (Nick, 2026-08-22 — a five-second fetch used to look like a dead
        keypress, because each message's toast had gone before the next
        one came). ``key`` is the title where a job cannot overlap itself
        and title+path where it can: subtitle fetches and conversions run
        side by side on purpose.

        Thread workers reach this the usual way, through
        ``call_from_thread``.
        """
        if self._jobs is None:
            self._jobs = progress.JobToasts(self.app)
        self._jobs.report(key, title, message, severity=severity,
                          done=done, timeout=timeout)

    def job_dismiss(self, key: str) -> None:
        """Take a job's toast down with no final word — the PANE became
        the answer. A plan preview says everything "scanning…" was
        leading up to, so the toast would only be in the way."""
        if self._jobs is not None:
            self._jobs.dismiss(key)

    FOLDERIZE_WORD = "Folderize"
    """Three actions wear this word — a single epub's ``sort_book``, a
    video's ``folderize_video``, an audio folder's ``folderize``. Which
    one a selection offers is the kind's business; the word is how the
    one BUTTON is found (it is numbered, like every kind action)."""

    def folderize_action(self) -> Action | None:
        """The folderize on show for the current selection, or None.

        Reads the composed bar rather than re-deriving the rules: the
        button IS the contract. Kept as the seam the tests use — the
        special-case ^f dispatch it was written for is gone, because
        every action reaches the tree now (2026-10-26)."""
        try:
            bar = self.query_one("#actions-bar", ActionBar)
        except NoMatches:
            return None
        for button in bar.buttons():
            if button.spec.word == self.FOLDERIZE_WORD:
                return button.spec
        return None

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
        if self._question is not None:
            return set(self._question[0])   # a question answers only itself
        if self._within("#row-art-path"):       # Import Album Art
            return set()                        # ⏎ applies, esc cancels
        if self._within("#book-cover-div"):     # Import Cover
            return set()
        # each wizard's scope: its write, plus its own toggle chord (the
        # toggle is the sub-form's command — pinned-while-pending included)
        if self._within("#shift-div"):          # Shift Subtitles
            return {"save", "shift_subs"}       # ^s writes the shift
        if self._within("#crop-div"):           # Crop
            return {"crop_apply", "crop"}
        if self._within("#resize-div"):         # Resize Image
            return {"resize_apply", "resize"}
        if self._within("#gif-div"):            # Make GIF
            return {"gif_make", "gif"}
        if self._within("#trace-div"):          # Image Trace
            return {"trace_save", "trace_view"}
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

    def trigger_by_name(self, name: str) -> None:
        handler = getattr(self, f"action_{name}", None)
        if handler is not None:
            handler()

    def trigger(self, action: Action) -> None:
        handler = getattr(self, f"action_{action.name}", None)
        if handler is not None:
            handler()

    def on_action_bar_triggered(self, ev: ActionBar.Triggered) -> None:
        ev.stop()
        self.trigger(ev.action)

    def _nav_rows(self) -> list[list]:
        """What ↑↓ walks, a ROW at a time (Nick, 2026-10-26).

        Every field is a row of one; every BAR is a row of its buttons.
        So ↓ off the last field lands on the first button of the first
        bar, and ↓ again lands on the first button of the NEXT bar —
        rather than stepping sideways through nine converts to get past
        them. ←→ move inside a row (action_pane_left / _right).
        """
        return [item if isinstance(item, list) else [item]
                for item in self._nav_items()]

    def _nav_items(self) -> list:
        """The rows ↑↓ walks, top to bottom: the fields, then any open
        wizard's controls, then each visible BAR as one entry (a list of
        its buttons). A FOCUSED sub-view confines the walk to its own
        controls (focus lockdown, todo-4): save or cancel to leave."""
        if self._question is not None:
            return [[self.query_one(f"#act-{name}", ActionButton)
                     for name in self._question[0]]]
        if self._within("#shift-div"):          # its save is the pane ^s
            items: list = [self.query_one("#shift-control", ShiftControl)]
            save = self.query_one("#save-btn", ActionButton)
            if save.display:
                items.append([save])
            return items
        if self._within("#resize-div"):
            return [self.query_one("#resize-w", FieldInput),
                    self.query_one("#resize-h", FieldInput),
                    self.query_one("#resize-link", Checkbox),
                    self.query_one("#resize-bar", ActionBar).buttons()]
        if self._within("#crop-div"):
            return [*self.query(CropControl),
                    self.query_one("#crop-bar", ActionBar).buttons()]
        if self._within("#trace-div"):
            return [*self.query(TraceControl),
                    self.query_one("#trace-bar", ActionBar).buttons()]
        if self._within("#gif-div"):
            return [self.query_one("#gif-fps", FieldInput),
                    self.query_one("#gif-width", FieldInput),
                    self.query_one("#gif-bar", ActionBar).buttons()]
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
                # one LINE, one row: a bar that overflows is two bars to
                # the eye, so ↓ reaches the second one (Nick, todo-6)
                items.extend(bar.visual_rows())
        return items

    def _move_nav(self, delta: int) -> None:
        """↑↓ : one row up or down, landing on the row's first control."""
        rows = self._nav_rows()
        if not rows:
            return
        focused = self.app.focused
        at = next((i for i, row in enumerate(rows) if focused in row), None)
        if at is None:
            rows[0][0].focus()
            return
        rows[max(0, min(len(rows) - 1, at + delta))][0].focus()

    def action_field_next(self) -> None:
        self._move_nav(+1)

    def action_field_prev(self) -> None:
        self._move_nav(-1)

    def _visual_row(self, button: ActionButton) -> list:
        """The buttons drawn on the same LINE as this one."""
        bar = button.parent
        if not isinstance(bar, ActionBar):
            return []
        for row in bar.visual_rows():
            if button in row:
                return row
        return []

    def action_pane_left(self) -> None:
        focused = self.app.focused
        if (isinstance(focused, ActionButton)
                and isinstance(focused.parent, ActionBar)
                and focused in (row := self._visual_row(focused))):
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
                and focused in (row := self._visual_row(focused))):
            index = row.index(focused)          # focused-not-in-row: no-op
            if index < len(row) - 1:
                row[index + 1].focus()

    def action_exit(self) -> None:
        """The ESC Exit button, and esc itself: back up the path."""
        self.action_release()

    def action_release(self) -> None:
        if self._question is not None:
            # every question's last choice is its way out (keep editing /
            # cancel), and esc is printed on that button
            self.trigger_by_name(self._question[0][-1])
            return
        if self.plan_preview_open():        # esc backs out of a plan/split
            self.action_plan_cancel()       # (which returns focus to the tree)
            return
        if self._trace_open:                # esc (or ←) from a trace button
            self._trace_close()
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
        self.ask(["confirm_save", "confirm_discard", "confirm_keep"],
                 decided, f"Save changes to {subject}?", title="save")

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
        self.job("cover", "cover", "writing cover…")
        self._book_cover_worker(book, target)

    @work(thread=True, exclusive=True, group="book-cover")
    def _book_cover_worker(self, book: Path, image: Path) -> None:
        try:
            epub.set_cover(book, image.read_bytes())
        except Exception as error:
            self.app.call_from_thread(
                self.job, "cover", "cover", str(error),
                severity="error", done=True)
            return
        self.app.call_from_thread(self._book_cover_done, book)

    def _book_cover_done(self, book: Path) -> None:
        self.job("cover", "cover", "cover updated", done=True)
        if self.path == book:
            self.preview(book, immediate=True, force=True)   # the cover changed

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

    def _ack_save(self, subject: str) -> None:
        """Acknowledge a completed ^s (Nick, 2026-08-25). A single-file
        save used to land in silence — the ✓ marks simply cleared, which
        looks the same as a keypress that did nothing. Bulk saves and the
        subtitle shift already said so; this makes it the rule."""
        self.notify(f"{subject} saved", title="save")

    def _save_done(self, old: Path, new: Path, release: bool) -> None:
        self._ack_save(new.name)
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
            # ^i/^b/^y join tests/fuzz.py KEYS)
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
        self.job(_convert_job(source), "convert",
                 f"{source.name} → .{fmt}…")
        self._convert_worker(source, target)

    @work(thread=True, group="convert", exclusive=False)
    def _convert_worker(self, source: Path, target: Path) -> None:
        # conversions take seconds to minutes: never block the UI, and
        # let several queue up side by side — each with its own toast
        try:
            calibre.convert(source, target)
        except Exception as error:
            self.app.call_from_thread(
                self.job, _convert_job(source), "convert", str(error),
                severity="error", done=True)
            return
        self.app.call_from_thread(self._convert_done, source, target)

    def _convert_done(self, source: Path, target: Path) -> None:
        self.job(_convert_job(source), "convert", f"{target.name} created",
                 done=True)
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
        # done=True: this refusal ENDS the producer whose toast is open
        # (a gif announces itself before ffmpeg refuses the overwrite)
        self.job(self._produce_job(title, source), title,
                 f"{label} — press again to overwrite",
                 severity="warning", done=True)

    def action_rescue_pdf(self) -> None:
        self._rescue("pdf")

    def action_rescue_svg(self) -> None:
        self._rescue("svg")

    def _rescue(self, fmt: str) -> None:
        """Write the whole canvas beside the .ai — artboard and beyond."""
        path = self.path
        if (self.kind != kinds.VECTOR or path is None
                or self.paths is not None or not self._rescue_ready):
            return
        self._run_producer(
            f"rescue to {fmt}",
            lambda source, overwrite: illustrator.recover(
                source, fmt, overwrite=overwrite).target,
            path)

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

    @staticmethod
    def _produce_job(title: str, source: Path) -> str:
        """Producers run side by side (a gif and a cover extract at once),
        so the job is the action AND the file it came from."""
        return f"{title}:{source}"

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
            self.app.call_from_thread(
                self.job, self._produce_job(title, path), title, str(error),
                severity="warning", done=True)
            return
        self.app.call_from_thread(self._produced, title, path, target)

    def _produced(self, title: str, source: Path, target: Path) -> None:
        # closes the toast a slow producer (gif) opened when it started
        self.job(self._produce_job(title, source), title,
                 f"{target.name} created", done=True)
        self.post_message(self.FileCreated(target))

    # -- image actions: convert / resize / rotate (imageops.py) --------------------
    # Convert and resize are produce-a-sibling actions (refuse-overwrite
    # lives in the engine); rotate is the one in-place pixel edit. The
    # resize div is the second wizard div (shift-subs is the exemplar):
    # ^e toggles it, ⏎ or ^a applies, esc closes — resize never pends,
    # so there is no save-question leg.

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

    # -- crop: the fifth wizard div (Nick, todo-6) ---------------------------
    # A terminal cannot drag a rectangle, so the crop is said in numbers
    # and SHOWN in the picture: every nudge redraws the image cropped,
    # because a crop you cannot see is not a crop you can judge. The
    # ratio row is first — "make it square" is usually the whole answer,
    # and the edges under it are the adjustment.

    def action_crop(self) -> None:
        image = self._image_target()
        if image is None:
            return
        if self._crop_open:                 # react-style toggle
            div = self.query_one("#crop-div")
            inside = (self.app.focused is not None
                      and div in self.app.focused.ancestors)
            self._crop_close(restore=True)
            if inside:
                self.app.action_focus_tree()
            return
        self._crop_ratio = "free"
        self._crop_edges = {edge: 0 for edge in imageops.EDGES}
        self._crop_open = True
        self.query_one("#crop-div").display = True
        self._crop_sync()
        self.app.reveal_details()           # narrow: display, then focus
        self.query_one("#crop-ratio", CropControl).focus()
        self._sync_pane_bar()
        self._crop_load_worker(image)

    @work(thread=True, exclusive=True, group="crop-load")
    def _crop_load_worker(self, path: Path) -> None:
        # a whole-image decode, possibly off the NAS: never on the loop
        try:
            from PIL import ImageOps
            source, _ = images.decode(path.read_bytes())
            source = ImageOps.exif_transpose(source)
            if source.mode not in ("RGB", "RGBA", "L", "LA"):
                source = source.convert("RGBA")
        except Exception:
            return                          # no preview; the numbers still work
        self.app.call_from_thread(self._crop_loaded, path, source)

    def _crop_loaded(self, path: Path, source) -> None:
        if not self._crop_open or self.path != path:
            return
        self._crop_source = source
        self._crop_render()

    def _crop_close(self, restore: bool = True) -> None:
        if not self._crop_open:
            return
        self._crop_open = False
        self._crop_source = None
        if self._crop_debounce is not None:
            self._crop_debounce.stop()
            self._crop_debounce = None
        self.query_one("#crop-div").display = False
        if restore and self.path is not None:
            self.preview(self.path, immediate=True, force=True)
        self._sync_pane_bar()

    def _crop_base(self) -> tuple[int, int] | None:
        """The source's own size — the numbers are relative to it."""
        if self._crop_source is not None:
            return self._crop_source.size
        return self._resize_base

    def _crop_nudge(self, control: str, direction: int,
                    big: bool = False) -> None:
        if not self._crop_open:
            return
        base = self._crop_base()
        if control == "ratio":
            ratios = imageops.CROP_RATIOS
            at = (ratios.index(self._crop_ratio) + direction) % len(ratios)
            self._crop_ratio = ratios[at]
            if base is not None:
                self._crop_edges = imageops.centred_edges(
                    *base, self._crop_ratio)
        else:
            step = CROP_BIG_STEP if big else CROP_STEP
            value = self._crop_edges.get(control, 0) + direction * step
            self._crop_edges[control] = max(0, value)
            self._crop_ratio = "free"       # the edges are the truth now
        self._crop_sync()

    def _crop_sync(self) -> None:
        """Repaint the rows and the result line, and queue a redraw."""
        base = self._crop_base()
        for name, _ in CROP_CONTROLS:
            try:
                widget = self.query_one(f"#crop-{name}", CropControl)
            except NoMatches:
                continue
            if name == "ratio":
                widget.update(self._crop_ratio)
            else:
                widget.update(str(self._crop_edges.get(name, 0)))
        result = self.query_one("#crop-result", Static)
        if base is None:
            result.update("")
        else:
            width, height = imageops.crop_size(*base, self._crop_edges)
            result.update(f"[$muted]{base[0]} × {base[1]}  →  "
                          f"{width} × {height}[/]")
        if self._crop_debounce is not None:
            self._crop_debounce.stop()
        self._crop_debounce = self.set_timer(0.12, self._crop_render)

    def _crop_render(self) -> None:
        self._crop_debounce = None
        if not self._crop_open or self._crop_source is None:
            return
        cover = self.query_one("#cover-image")
        if isinstance(cover, Static):       # images off: numbers only
            return
        cover.display = True
        box = self._trace_box()             # same measurement, same picture
        if box is None:
            return
        columns, rows = box
        cell_width, cell_height = images.cell_pixels()
        self._crop_gen += 1
        self._crop_preview_worker(self._crop_gen, self.path,
                                  self._crop_source, dict(self._crop_edges),
                                  (columns * cell_width, rows * cell_height),
                                  (cell_width, cell_height), (columns, rows))

    @work(thread=True, exclusive=True, group="crop-preview")
    def _crop_preview_worker(self, gen: int, path: Path, source, edges: dict,
                             room: tuple[int, int],
                             cell: tuple[int, int],
                             box: tuple[int, int]) -> None:
        try:
            from PIL import Image
            cropped = source.crop(imageops.crop_box(*source.size, edges))
            scale = min(room[0] / cropped.width, room[1] / cropped.height, 1.0)
            size = (max(1, round(cropped.width * scale)),
                    max(1, round(cropped.height * scale)))
            picture = cropped.resize(size, Image.Resampling.LANCZOS)
        except Exception:
            return
        cells = (max(1, min(box[0], round(size[0] / cell[0]))),
                 max(1, min(box[1], round(size[1] / cell[1]))))
        self.app.call_from_thread(self._crop_previewed, gen, path, picture,
                                  cells)

    def _crop_previewed(self, gen: int, path: Path, picture,
                        cells: tuple[int, int]) -> None:
        if gen != self._crop_gen or not self._crop_open or self.path != path:
            return
        cover = self.query_one("#cover-image")
        cover.styles.width, cover.styles.height = cells
        cover.image = picture
        cover.display = True

    def action_crop_apply(self) -> None:
        image = self._image_target()
        if image is None or not self._crop_open:
            return
        base = self._crop_base()
        if base is not None and imageops.crop_size(
                *base, self._crop_edges) == base:
            self.notify("nothing is being cropped", title="crop",
                        severity="warning")
            return
        edges = dict(self._crop_edges)
        self._run_producer(
            "crop",
            lambda path, ow, e=edges: imageops.crop(path, e, overwrite=ow),
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
            self.preview(path, immediate=True, force=True)  # fresh image + size

    # -- image trace: the full-panel wizard (trace.py) -----------------------------
    # Illustrator's Image Trace (Nick, 2026-09-16). The fourth wizard div,
    # and the only one that TAKES OVER its panel: the pane bar, the filename
    # row, and the size/dimension rows step aside so the picture fills
    # every cell the details view has left under the controls. Each control
    # is a stepper (shift-subs' ←→ model); a nudge re-traces the FULL-
    # resolution source in a worker, and potrace draws the result at the
    # picture's exact pixel size — a preview, never a thumbnail of one.
    # Nothing pends (the source is never touched; save writes a sibling),
    # so esc simply closes: no save-question leg.

    def action_trace(self) -> None:
        image = self._image_target()
        if image is None or self._trace_open:
            return
        if trace.find_potrace() is None:
            self.notify(trace.INSTALL_HINT, title="image trace",
                        severity="error")
            return
        self._trace_status("loading…")
        self._trace_load_worker(image)

    @work(thread=True, exclusive=True, group="trace-load")
    def _trace_load_worker(self, path: Path) -> None:
        # a whole-image decode, possibly off the NAS: never on the loop
        try:
            from PIL import ImageOps
            gray = trace.load_gray(path)
            source, _ = images.decode(path.read_bytes())
            source = ImageOps.exif_transpose(source)    # match the trace
            if source.mode not in ("RGB", "RGBA", "L", "LA"):
                source = source.convert("RGBA")
        except Exception as error:
            self.app.call_from_thread(self._trace_load_failed, path, error)
            return
        self.app.call_from_thread(self._trace_loaded, path, gray, source)

    def _trace_load_failed(self, path: Path, error: Exception) -> None:
        if self.path == path:
            self._trace_status("")
        self.notify(str(error), title="image trace", severity="error")

    def _trace_loaded(self, path: Path, gray, source) -> None:
        self._trace_status("")
        if (self.path != path or self.kind != kinds.IMAGE
                or self.paths is not None or self._trace_open):
            return                              # selection moved on
        self._trace_gray = gray
        self._trace_source = source
        self._trace_view = "trace"
        self._resize_hide()                     # one wizard at a time
        self._trace_open = True
        self._trace_apply_layout()
        self._trace_refresh_controls()
        self.app.reveal_details()               # narrow: display, then focus
        self.query_one(TraceControl).focus()
        self.scroll_home(animate=False)
        if isinstance(self.query_one("#cover-image"), Static):
            self.notify("images are off — no preview, but save still traces",
                        title="image trace", severity="warning")
        self.call_after_refresh(self._trace_render)

    def _trace_apply_layout(self) -> None:
        """Show trace mode's pieces and hide the rest — or the reverse."""
        on = self._trace_open
        editable = self.can_edit()
        self.query_one("#trace-div").display = on
        self.query_one("#bars").display = not on
        self.query_one("#row-image-size").display = not on
        self.query_one("#row-image-dims").display = not on
        self.query_one("#dtitle").display = on or not editable
        self.query_one("#row-fname").display = editable and not on
        if not on:
            cover = self.query_one("#cover-image")
            cover.styles.width = None           # back to the .cover CSS
            cover.styles.height = None
        self.query_one("#trace-view-btn", ActionButton).set_word(
            "view source" if self._trace_view == "trace" else "view tracing")

    def _trace_status(self, status: str) -> None:
        """Say what the preview is doing beside the file name."""
        if self.path is None:
            return
        self.query_one("#dtitle", Label).update(
            self.path.name + (f" · {status}" if status else ""))

    def _trace_refresh_controls(self) -> None:
        for control in self.query(TraceControl):
            control.update(
                f"◂ {self._trace_settings.display(control.control)} ▸")

    def _trace_close(self) -> None:
        """esc: trace mode ends and focus ascends to the tree."""
        self._trace_hide()
        self.app.action_focus_tree()

    def _trace_hide(self, restore: bool = True) -> None:
        if not self._trace_open:
            return
        self._trace_open = False
        self._trace_gen += 1                    # in-flight previews: stale
        if self._trace_debounce is not None:
            self._trace_debounce.stop()
            self._trace_debounce = None
        self._trace_gray = None
        self._trace_source = None
        self._trace_view = "trace"
        self._trace_apply_layout()
        self._trace_status("")
        if restore:                             # the image, as it was
            self._set_cover("cover-image", self._image_data)

    def _trace_nudge(self, control: str, direction: int, big: bool) -> None:
        if not self._trace_open:
            return
        before = self._trace_settings
        stepper = next((s for s in trace.STEPPERS if s.name == control), None)
        steps = direction * (stepper.big_step if big and stepper
                             else stepper.step if stepper else 1)
        self._trace_settings = before.nudged(control, steps)
        self._trace_refresh_controls()
        if (self._trace_settings == before
                or control not in trace.PREVIEW_CONTROLS):
            return
        if self._trace_view == "source":        # a change shows its result
            self._trace_view = "trace"
            self._trace_apply_layout()
        self._trace_schedule()

    def _trace_schedule(self) -> None:
        """Debounced like the tree highlight: holding → re-traces once,
        when the key lets go, not once per repeat."""
        if self._trace_debounce is not None:
            self._trace_debounce.stop()
        self._trace_debounce = self.set_timer(DEBOUNCE_SECONDS,
                                              self._trace_render)

    def on_resize(self, event) -> None:
        # ONE handler per message per class: a second `on_resize` further
        # down the class body silently shadows the first (2026-10-27)
        self._spine_dirty = True
        self.call_after_refresh(self._redraw_spine)   # rows moved
        if self._trace_open:                    # the picture refits
            self._trace_schedule()

    def _trace_box(self) -> tuple[int, int] | None:
        """The (columns, rows) the picture may fill: from its own top-left
        corner to the pane's bottom-right, inside the scrollbars."""
        cover = self.query_one("#cover-image")
        area = self.scrollable_content_region
        if not cover.display or cover.region.width < 1:
            return None
        top = cover.region.y + round(self.scroll_y)
        columns = area.right - cover.region.x
        rows = area.bottom - top - cover.styles.margin.bottom
        if columns < 1 or rows < 1:
            return None
        return columns, rows

    def _trace_render(self) -> None:
        self._trace_debounce = None
        if not self._trace_open or self._trace_gray is None:
            return
        cover = self.query_one("#cover-image")
        if isinstance(cover, Static):           # images off: nothing to draw
            return
        cover.display = True                    # _trace_box measures it
        box = self._trace_box()
        if box is None:
            return
        columns, rows = box
        cell_width, cell_height = images.cell_pixels()
        width, height = trace.fit(*self._trace_gray.size,
                                  columns * cell_width, rows * cell_height)
        cells = (max(1, min(columns, round(width / cell_width))),
                 max(1, min(rows, round(height / cell_height))))
        self._trace_gen += 1
        if self._trace_view == "trace":
            self._trace_status("tracing…")
        self._trace_preview_worker(self._trace_gen, self.path,
                                   self._trace_view, self._trace_gray,
                                   self._trace_source, self._trace_settings,
                                   (width, height), cells)

    @work(thread=True, exclusive=True, group="trace-preview")
    def _trace_preview_worker(self, gen: int, path: Path, view: str, gray,
                              source, settings: trace.TraceSettings,
                              size: tuple[int, int],
                              cells: tuple[int, int]) -> None:
        # a full-resolution trace is ~0.1–1s: always a worker, and a
        # newer render makes this one's result stale (the gen check)
        try:
            if view == "source":
                from PIL import Image
                picture = source.resize(size, Image.Resampling.LANCZOS)
            else:
                picture = trace.preview(gray, settings, size)
        except Exception as error:
            self.app.call_from_thread(self._trace_preview_failed, gen, error)
            return
        self.app.call_from_thread(self._trace_previewed, gen, path, picture,
                                  cells)

    def _trace_previewed(self, gen: int, path: Path, picture,
                         cells: tuple[int, int]) -> None:
        if gen != self._trace_gen or not self._trace_open or self.path != path:
            return
        cover = self.query_one("#cover-image")
        cover.styles.width, cover.styles.height = cells
        cover.image = picture
        cover.display = True
        self._trace_status("")

    def _trace_preview_failed(self, gen: int, error: Exception) -> None:
        if gen != self._trace_gen or not self._trace_open:
            return
        self._trace_status("")
        self.notify(str(error), title="image trace", severity="error")

    def action_trace_view(self) -> None:
        """Illustrator's View menu, as one key: the tracing or the source."""
        if not self._trace_open:
            return
        self._trace_view = "source" if self._trace_view == "trace" else "trace"
        self._trace_apply_layout()
        self._trace_render()

    def action_trace_save(self) -> None:
        image = self._image_target()
        if image is None or not self._trace_open:
            return
        settings = self._trace_settings
        # per format: an armed overwrite of photo.svg must not carry over
        # to photo.pdf after the picker moves
        title = f"trace to {settings.format}"
        self.job(self._produce_job(title, image), title,
                 f"tracing {image.name}…")
        self._run_producer(
            title,
            lambda path, ow, s=settings: trace.trace(path, s, overwrite=ow),
            image)

    # -- folder plans: probe → button → preview → apply/cancel ---------------------
    # Folderize and fix-multi-artist share the mechanism: probes fill in
    # late (NAS rule); a button appears only when the subtree has work to
    # do; pressing it plans in a worker and swaps the folder panel to a
    # preview; ONE apply/cancel pair owns the bar until resolved —
    # whichever plan is open receives them.

    def plan_preview_open(self) -> bool:
        return (self._shrink_plan is not None
                or self._folderize_plan is not None
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
        if self._shrink_plan is not None:
            plan = self._shrink_plan
            self._shrink_plan = None
            self.job("shrink", "shrink", "re-encoding…")
            self._shrink_exec_worker(plan)
        elif self._folderize_plan is not None:
            plan = self._folderize_plan
            self._folderize_plan = None
            self.job("folderize", "folderize", "organizing…")
            self._folderize_exec_worker(plan)
        elif self._multiartist_plan is not None:
            plan = self._multiartist_plan
            self._multiartist_plan = None
            self.job("strip multi-artist", "strip multi-artist",
                     "stripping…")
            self._multiartist_exec_worker(plan)
        elif self._omnibus_plan is not None:
            plan = self._omnibus_plan
            editing = self._omnibus_editing
            if editing:                     # fold the form's corrections in
                plan = omnibus.with_edits(
                    plan, *self.query_one(OmnibusForm).edits(len(plan.books)))
            self._omnibus_plan = None
            self._omnibus_editing = False
            self.job("split omnibus", "split omnibus", "splitting…")
            self._omnibus_exec_worker(plan)
        elif self._sort_plan is not None:
            plan = self._sort_plan
            self._sort_plan = None
            self.job("sort", "sort", "wrapping…")
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
        self._shrink_plan = None
        if self.path is not None:               # restore the normal view
            self.preview(self.path, immediate=True, force=True)
        self.app.action_focus_tree()            # ascend out of the pane

    # -- case-only folder collisions ------------------------------------------------
    # Every wrapping action (folderize, video folderize, sort) asks the
    # same question before it writes: is a folder I mean to create already
    # here under a different spelling? On APFS/SMB the answer can't be
    # "make both" — see casing.py. The check lists directories, so it runs
    # inside the action's own worker; the answer comes back through the
    # modal and re-enters that worker with a resolution.

    def _case_gate(self, key: str, title: str,
                   pairs: list[tuple[Path, Path]], retry) -> None:
        def decided(choice: str | None) -> None:
            if choice in ("keep", "purge"):
                self.job(key, title, "renaming folders…")
                retry(choice)
                return
            self.job(key, title, "cancelled — folder casing left alone",
                     done=True, timeout=6)

        existing, wanted = pairs[0]
        more = f" (and {len(pairs) - 1} more)" if len(pairs) > 1 else ""
        self.ask(["case_keep", "case_purge", "case_cancel"], decided,
                 f"{existing.name}/ already exists where {wanted.name}/ "
                 f"should go{more}. This filesystem can't hold both "
                 f"spellings — rename it?", title=title)

    # -- shrink a comic ----------------------------------------------------------
    # The fifth plan-shaped action (comics.py). Unlike the other four it
    # REWRITES the files it names instead of moving them, so the preview
    # is doing more work than usual: it is the only confirmation there
    # is, and what it promises — the size — is what the user is here for.

    def _shrink_target(self):
        """What Shrink would act on: a folder of pages, or one image."""
        if self.paths is not None:
            return None
        if self.path is None:
            return None
        if self.kind == kinds.IMAGE:
            return self.path
        return self.path if self._shrink_ready else None

    def action_shrink(self) -> None:
        target = self._shrink_target()
        if target is None:
            return
        self.job("shrink", "shrink", "measuring…")
        self._shrink_plan_worker(target)

    @work(thread=True, exclusive=True, group="shrink-plan")
    def _shrink_plan_worker(self, target: Path) -> None:
        plan = comics.build_plan(target)
        self.app.call_from_thread(self._shrink_planned, target, plan)

    def _shrink_planned(self, target: Path,
                        plan: comics.ShrinkPlan) -> None:
        if self.path != target:                 # selection moved on
            self.job_dismiss("shrink")
            return
        if plan.empty:
            self.job("shrink", "shrink", "no images here", done=True)
            return
        if plan.saved <= 0:
            self.job("shrink", "shrink",
                     "already as small as this would make it", done=True)
            return
        self._shrink_plan = plan
        self.job_dismiss("shrink")          # the preview is the answer
        self._show_plan_preview(f"shrink {target.name}", render_shrink(plan))

    @work(thread=True, exclusive=True, group="shrink-exec")
    def _shrink_exec_worker(self, plan: comics.ShrinkPlan) -> None:
        done = kept = failed = 0
        before = after = 0
        total = len(plan.pages)
        for event in comics.apply(plan):
            if isinstance(event, comics.Shrunk):
                done += 1
                before += event.before
                after += event.after
            elif isinstance(event, comics.Kept):
                kept += 1
                before += event.before
                after += event.before
            else:
                failed += 1
            if (done + kept + failed) % 4 == 0:
                self.app.call_from_thread(
                    self.job, "shrink", "shrink",
                    f"page {done + kept + failed} of {total}…")
        saved = max(0, before - after)
        parts = [f"{done} page{'s' if done != 1 else ''}",
                 f"{human_size(saved)} saved"]
        if kept:
            parts.append(f"{kept} already small")
        if failed:
            parts.append(f"{failed} failed")
        self.app.call_from_thread(self.job, "shrink", "shrink",
                                  " · ".join(parts), done=True)
        self.app.call_from_thread(self._shrink_done, plan)

    def _shrink_done(self, plan: comics.ShrinkPlan) -> None:
        adapters.forget(plan.root)
        self.post_message(self.FolderChanged(plan.root))
        if self.path is not None:
            self.preview(self.path, immediate=True, force=True)

    # -- folderize --------------------------------------------------------------

    def action_folderize(self) -> None:
        root = self._plan_root()
        if root is None or not self._folderize_ready:
            return
        self.job("folderize", "folderize", "scanning…")
        self._folderize_plan_worker(root)

    @work(thread=True, exclusive=True, group="folderize-plan")
    def _folderize_plan_worker(self, root: Path) -> None:
        plan = folderize.build_plan(root)
        self.app.call_from_thread(self._folderize_planned, root, plan)

    def _folderize_planned(self, root: Path,
                           plan: folderize.FolderizePlan) -> None:
        if self.path != root:                   # selection moved on
            self.job_dismiss("folderize")  # nothing to report
            return
        if plan.empty:
            self.job("folderize", "folderize", "already organized",
                     done=True)
            self._folderize_ready = False
            self._sync_pane_bar()
            return
        self._folderize_plan = plan
        self.job_dismiss("folderize")       # the preview is the answer
        self._show_plan_preview(f"folderize {root.name}/", render_plan(plan))

    @work(thread=True, exclusive=True, group="folderize-exec")
    def _folderize_exec_worker(self, plan: folderize.FolderizePlan,
                               resolution: str | None = None) -> None:
        pairs = casing.clashes(folderize.wanted_dirs(plan))
        if pairs and resolution is None:
            self.app.call_from_thread(
                self._case_gate, "folderize", "folderize", pairs,
                lambda choice: self._folderize_exec_worker(plan, choice))
            return
        case_errors = (casing.resolve(pairs, purge=(resolution == "purge"))
                       if pairs else [])
        moved, skipped, errors = folderize.execute(plan)
        self.app.call_from_thread(
            self._folderize_done, plan.root, moved, skipped,
            case_errors + errors)

    def _folderize_done(self, root: Path, moved: int, skipped: int,
                        errors: list[tuple[Path, str]]) -> None:
        parts = [f"{moved} moved"]
        if skipped:
            parts.append(f"{skipped} skipped (missing tags)")
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} failed — {path.name}: {reason}")
        self.job("folderize", "folderize", " · ".join(parts), done=True,
                 timeout=8,
                 severity="warning" if errors else "information")
        fs.clear_cache()                        # the subtree just changed
        self.post_message(self.FolderChanged(root))
        if self.path == root:
            self.preview(root, immediate=True, force=True)  # fresh counts/probe

    # -- strip multi-artist ---------------------------------------------------------

    def action_strip_multi_artist(self) -> None:
        root = self._plan_root()
        if root is None or not self._multiartist_ready:
            return
        self.job("strip multi-artist", "strip multi-artist", "scanning…")
        self._multiartist_plan_worker(root)

    @work(thread=True, exclusive=True, group="multiartist-plan")
    def _multiartist_plan_worker(self, root: Path) -> None:
        plan = multiartist.build_plan(root)
        self.app.call_from_thread(self._multiartist_planned, root, plan)

    def _multiartist_planned(self, root: Path,
                             plan: multiartist.MultiArtistPlan) -> None:
        if self.path != root:                   # selection moved on
            self.job_dismiss("strip multi-artist")  # nothing to report
            return
        if plan.empty:
            self.job("strip multi-artist", "strip multi-artist",
                     "no tangled artists", done=True)
            self._multiartist_ready = False
            self._sync_pane_bar()
            return
        self._multiartist_plan = plan
        self.job_dismiss("strip multi-artist")
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
        self.job("strip multi-artist", "strip multi-artist",
                 " · ".join(parts), done=True, timeout=8,
                 severity="warning" if errors else "information")
        # tags changed in place — no tree structure change, just re-read
        if self.path == root:
            self.preview(root, immediate=True, force=True)  # fresh view/probes

    # -- split omnibus: the third plan-shaped action (epub, not folder) ------------

    def action_split_omnibus(self) -> None:
        path = self.path
        if (path is None or not self._omnibus_ready
                or self.paths is not None):
            return
        self.job("split omnibus", "split omnibus", "reading…")
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
            self.job_dismiss("split omnibus")  # nothing to report
            return
        if plan.empty:
            self.job("split omnibus", "split omnibus",
                     "not an omnibus after all", done=True)
            self._omnibus_ready = False
            self._sync_pane_bar()
            return
        self._omnibus_plan = plan
        self.job_dismiss("split omnibus")   # the form/preview is the answer
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
        self.job("split omnibus", "split omnibus", " · ".join(parts),
                 done=True, timeout=8,
                 severity="warning" if errors else "information")
        for path in written:
            self.post_message(self.FileCreated(path))
        if self.path == source:
            self.preview(source, immediate=True, force=True)   # the book is back

    # -- sort: wrap each book's files into "Author Sort - Title/" ------------------
    # The fourth plan-shaped action (booksort.py) — folderize's exact
    # shape on the shared plan_apply/plan_cancel pair. On a single epub the
    # same engine runs one-file and immediately (no preview): rename + wrap,
    # then reveal the book in its new directory, still editable (Wrapped).
    # One _sort_ready flag serves both contexts — they never coexist.

    def action_sort_book(self) -> None:
        # the single-epub button ("folderize", spec rename) — same engine
        self.action_sort()

    def action_sort(self) -> None:
        if not self._sort_ready:
            return
        if (self.kind == kinds.BOOK and self.paths is None
                and self.path is not None):
            # single ebook: no preview
            self.job("sort", "sort", "reading…")
            self._sort_book_worker(self.path)
            return
        root = self._plan_root()
        if root is None:
            return
        self.job("sort", "sort", "reading…")
        self._sort_plan_worker(root)

    @work(thread=True, exclusive=True, group="sort-book-exec")
    def _sort_book_worker(self, book: Path,
                          resolution: str | None = None) -> None:
        plan = booksort.plan_for_book(book)
        if plan is None:
            self.app.call_from_thread(
                self.job, "sort", "sort", f"{book.name}: no readable metadata",
                severity="warning", done=True)
            return
        pairs = casing.clashes(booksort.wanted_dirs(plan))
        if pairs and resolution is None:
            self.app.call_from_thread(
                self._case_gate, "sort", "sort", pairs,
                lambda choice: self._sort_book_worker(book, choice))
            return
        case_errors = (casing.resolve(pairs, purge=(resolution == "purge"))
                       if pairs else [])
        new_path = booksort.sorted_path(book, plan.groups[0].folder_name)
        moved, errors = booksort.execute(plan)
        self.app.call_from_thread(self._sort_book_done, book, new_path,
                                  moved, case_errors + errors)

    def _sort_book_done(self, book: Path, new_path: Path, moved: int,
                        errors: list[tuple[Path, str]]) -> None:
        if errors:
            _, reason = errors[0]
            self.job("sort", "sort", f"{book.name}: {reason}",
                     severity="error", done=True, timeout=8)
            return
        self.job("sort", "sort", f"wrapped into {new_path.parent.name}/",
                 done=True)
        fs.clear_cache()                        # the subtree just changed
        self.post_message(self.Wrapped(new_path))

    @work(thread=True, exclusive=True, group="sort-plan")
    def _sort_plan_worker(self, root: Path) -> None:
        plan = booksort.build_plan(root)
        self.app.call_from_thread(self._sort_planned, root, plan)

    def _sort_planned(self, root: Path, plan: booksort.SortPlan) -> None:
        if self.path != root:                   # selection moved on
            self.job_dismiss("sort")  # nothing to report
            return
        if plan.empty:
            self.job("sort", "sort", "every book here is already wrapped",
                     done=True)
            self._sort_ready = False
            self._sync_pane_bar()
            return
        self._sort_plan = plan
        self.job_dismiss("sort")
        self._show_plan_preview(f"sort {root.name}/", render_sort_plan(plan))

    @work(thread=True, exclusive=True, group="sort-exec")
    def _sort_exec_worker(self, plan: booksort.SortPlan,
                          resolution: str | None = None) -> None:
        pairs = casing.clashes(booksort.wanted_dirs(plan))
        if pairs and resolution is None:
            self.app.call_from_thread(
                self._case_gate, "sort", "sort", pairs,
                lambda choice: self._sort_exec_worker(plan, choice))
            return
        case_errors = (casing.resolve(pairs, purge=(resolution == "purge"))
                       if pairs else [])
        moved, errors = booksort.execute(plan)
        self.app.call_from_thread(self._sort_done, plan.root, moved,
                                  case_errors + errors)

    def _sort_done(self, root: Path, moved: int,
                   errors: list[tuple[Path, str]]) -> None:
        parts = [f"{moved} file{'s' if moved != 1 else ''} wrapped"]
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} failed — {path.name}: {reason}")
        self.job("sort", "sort", " · ".join(parts), done=True,
                 timeout=8,
                 severity="warning" if errors else "information")
        fs.clear_cache()                        # the subtree just changed
        self.post_message(self.FolderChanged(root))
        if self.path == root:
            self.preview(root, immediate=True, force=True)  # fresh counts/probes

    # -- standardize formatting: strip source cruft, rebuild clean -----------------
    # One engine, two contexts: a single epub, or every direct-child
    # epub of a folder (batch = v1's multi-file mode). Outputs are
    # "(clean)" siblings, so no plan preview — nothing moves.

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
        # who closes the toast: the batch summary, or the one book's result
        self._standardize_single = n == 1
        self.job("standardize", "standardize",
                 f"standardizing {n} book{'s' if n != 1 else ''}…")
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
                    self.job, "standardize", "standardize",
                    f"{event.source.name}: {event.reason}",
                    severity="warning", done=len(books) == 1, timeout=8)
        if len(books) > 1:
            summary = [f"{len(done)} standardized"]
            if failed:
                summary.append(f"{len(failed)} failed")
            self.app.call_from_thread(
                self.job, "standardize", "standardize", " · ".join(summary),
                done=True, timeout=8,
                severity="warning" if failed else "information")

    def _standardized(self, event: standardize.BookDone) -> None:
        # the batch summary closes the toast; a single book closes it here
        self.job("standardize", "standardize",
                 f"{event.target.name} · {event.style} · "
                 f"{event.chapters} chapter"
                 f"{'s' if event.chapters != 1 else ''}",
                 done=self._standardize_single)
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
        self.job("paste", "paste",
                 f"{'copying' if copy else 'moving'} {len(movable)}…")
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
        self.job("paste", "paste", " · ".join(parts), done=True, timeout=8,
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

    def _delete_target(self, cursor: Path | None = None) -> Path | None:
        """What ^del removes: the highlighted item itself — file OR folder
        (or an album-like folder shown as its contents). A shift-range bulk
        selection has no single target, so it is left alone.

        ``cursor`` is the TREE's highlighted row, and it wins when given:
        the pane's own ``self.path`` lags the highlight by the preview
        debounce, so a ^del within 150ms of an arrow key used to trash the
        row above (Nick, 2026-08-25) — or nothing at all, silently, when
        that stale row had since been deleted or renamed.
        """
        if cursor is not None:
            return cursor
        if self.path is not None:
            return self.path
        return None

    def action_delete(self, cursor: Path | None = None) -> None:
        root = self._delete_target(cursor)
        if root is None:
            # bulk shift-range (no single target) or an empty pane: say so
            # rather than swallowing the key
            self.notify("nothing to delete — highlight one file or folder",
                        title="delete", severity="warning")
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
            if not path.exists():       # the stat belongs HERE, not on the
                raise FileNotFoundError(   # event loop (rule 4)
                    f"{path.name} is already gone")
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
        # one toast for the whole fetch, updated as it reports (job())
        self.job(_subs_job(video), "get subs",
                 f"{video.name}: fetching subtitles…")
        self._get_subs_worker(video)

    @work(thread=True, group="get-subs", exclusive=False)
    def _get_subs_worker(self, video: Path) -> None:
        # like conversions: several fetches may run side by side, and a
        # clean on another file must not cancel one — so the job key
        # carries the video, not just the title
        key = _subs_job(video)
        def say(message: str, **kw) -> None:
            self.app.call_from_thread(self.job, key, "get subs", message, **kw)

        problems = subsync.check_requirements()
        if problems:
            say("\n".join(problems), severity="error", done=True, timeout=10)
            return
        # an explicit press on a file that already has a sub means
        # "re-fetch" — the one deliberate exception to refuse-overwrite
        force = subsync.find_subtitle(video) is not None
        try:
            finished = False
            for event in subsync.run([video], force=force):
                if isinstance(event, subsync.PhaseStarted):
                    say(event.label)
                elif isinstance(event, subsync.Note):
                    say(event.text)
                elif isinstance(event, subsync.FileDone):
                    finished = True
                    self.app.call_from_thread(self._got_subs, video,
                                              event.result)
            if not finished:        # never leave a toast running forever
                say("nothing came back", severity="warning", done=True)
        except Exception as error:
            say(str(error), severity="error", done=True)

    def _got_subs(self, video: Path, result: subsync.FileResult) -> None:
        self.job(_subs_job(video), "get subs",
                 f"{video.name}: {result.status}", done=True,
                 severity=("information" if result.category == "ok"
                           else "warning"), timeout=8)
        if result.installed:
            self.post_message(self.FileCreated(video.parent / result.installed))
            if self.path == video:
                self.preview(video, immediate=True, force=True)  # fresh subtitles

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
        self.job(_posters_job(video), "download posters",
                 f"{video.name}: identifying film…")
        self._posters_worker(video)

    @work(thread=True, group="posters", exclusive=False)
    def _posters_worker(self, video: Path) -> None:
        # the longest worker yet (N image downloads) — every phase and
        # every fifth download replaces the text in the ONE toast this
        # fetch owns, which is finally released by _posters_done
        key = _posters_job(video)
        def say(message: str, **kw) -> None:
            self.app.call_from_thread(self.job, key, "download posters",
                                      message, **kw)
        try:
            title = adapters.probe_video_title(video)
            for event in posters.run(video, container_title=title):
                if isinstance(event, posters.Failed):
                    say(event.reason, severity="warning", done=True,
                        timeout=10)
                elif isinstance(event, (posters.Identified,
                                        posters.PhaseStarted)):
                    say(event.label)
                elif isinstance(event, posters.Progress):
                    if event.phase == "downloading" and event.done % 5 == 0:
                        say(f"{event.done}/{event.total} downloaded…")
                elif isinstance(event, posters.Done):
                    self.app.call_from_thread(self._posters_done, video, event)
        except Exception as error:
            say(str(error), severity="error", done=True)

    def _posters_done(self, video: Path, done: posters.Done) -> None:
        parts = [f"{done.saved} poster{'s' if done.saved != 1 else ''} "
                 f"→ {done.folder}"]
        if done.duplicates:
            parts.append(f"{done.duplicates} near-duplicates skipped")
        if done.existing:
            parts.append(f"{done.existing} already there (kept)")
        self.job(_posters_job(video), "download posters", " · ".join(parts),
                 done=True, timeout=10)
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
        self.job(self._produce_job("make gif", video), "make gif",
                 f"{video.name} → {target.name} ({fps} fps, {width} px)…")
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
        self.job("folderize", "folderize", f"{video.name} → {video.stem}/")
        self._folderize_video_worker(video)

    @work(thread=True, exclusive=True, group="folderize-video")
    def _folderize_video_worker(self, video: Path,
                                resolution: str | None = None) -> None:
        pairs = casing.clashes([videofolder.wrap_dir(video)])
        if pairs and resolution is None:
            self.app.call_from_thread(
                self._case_gate, "folderize", "folderize", pairs,
                lambda choice: self._folderize_video_worker(video, choice))
            return
        case_errors = (casing.resolve(pairs, purge=(resolution == "purge"))
                       if pairs else [])
        landed, moved, errors = videofolder.execute(video)
        self.app.call_from_thread(self._folderize_video_done, video, landed,
                                  moved, case_errors + errors)

    def _folderize_video_done(self, video: Path, landed: Path, moved: int,
                              errors: list[tuple[Path, str]]) -> None:
        if landed == video:                     # the video itself never moved
            _, reason = errors[0] if errors else (None, "nothing to move")
            self.job("folderize", "folderize", f"{video.name}: {reason}",
                     severity="error", done=True, timeout=8)
            return
        parts = [f"{moved} file{'s' if moved != 1 else ''} → "
                 f"{landed.parent.name}/"]
        if errors:
            path, reason = errors[0]
            parts.append(f"{len(errors)} left behind — {path.name}: {reason}")
        self.job("folderize", "folderize", " · ".join(parts), done=True,
                 timeout=8,
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
        # the first nudge makes the shift pending, which is what puts Save
        # on the bar (todo-6: it shows only when there is something to
        # write) — and its ^s is how the wizard commits
        self._sync_pane_bar()

    def _shift_close(self) -> None:
        """esc on the control: pending goes through the save question (the
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
        if release:                             # via the question: close out
            if self.path == video:
                self._shift_hide()
            self.app.action_focus_tree()
