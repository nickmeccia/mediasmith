"""Illustrator rescue: the artwork an .ai file hides outside its artboard.

An .ai file saved with "Create PDF Compatible File" is two documents in one
container (Nick, 2026-09-28):

    the PDF portion       what Affinity, Preview, Inkscape and every other
                          non-Adobe reader opens — and Illustrator writes
                          ONLY the artboard into it
    the AI portion        ``/AIPrivateData1..N``, Illustrator's own legacy
                          art stream, which carries the WHOLE canvas

So the scratch work a designer parks beside the artboard survives the save
and is invisible to everything but Illustrator. Enlarging the artboard or
the PDF ``/MediaBox`` reveals nothing: the paths are not in the half of the
file that got enlarged. This module reads the other half.

``read_canvas`` is the cheap question — it parses the AI portion's header
comments and compares the artwork bounds against the artboard, so the pane
can ask "is anything out there?" without translating a single path.
``recover`` is the answer: every path in the document, written beside the
source as a PDF (or SVG) whose page box covers the whole canvas, with the
original coordinates preserved so on-artboard work stays where it was.

What survives the trip: paths, fills, strokes, compound holes, clipping
groups, linear gradients, and the document's own CMYK ICC profile (carried
into the PDF verbatim; resolved through littleCMS for the SVG's RGB).
What does not, and is reported in ``Recovery.skipped`` rather than dropped
in silence: placed/embedded rasters, live text, mesh and radial gradients
(flattened to their first stop), patterns, and symbols. The product is
flattened artwork — layer and group NAMES are not reconstructed.

IO-free in the house sense: no printing, no widgets. It reads and writes
files, so callers run it in a thread worker.
"""

from __future__ import annotations

import re
import sys
import zlib
from dataclasses import dataclass, field

if sys.version_info >= (3, 14):
    from compression import zstd
else:
    from backports import zstd
from pathlib import Path

EXTENSIONS = {".ai"}
"""Not in ``kinds.IMAGE_EXTENSIONS``: an .ai file is not a picture the pane
can render, and nothing else in the app reads one."""

FORMATS = ("pdf", "svg")
"""Recovery targets, in button order. PDF is first because it keeps the
CMYK numbers and the embedded profile; SVG converts to RGB."""

SUFFIX = "-full-canvas"
"""Appended to the stem so a rescue never collides with the source."""


# -- what the file says about itself -----------------------------------------


@dataclass(frozen=True)
class Canvas:
    """The two rectangles that matter, in PDF points, as ``(x0, y0, x1, y1)``."""

    artwork: tuple[float, float, float, float]
    artboard: tuple[float, float, float, float] | None

    @property
    def offboard(self) -> bool:
        """True when artwork pokes outside the artboard — the whole reason
        this module exists. A hair of tolerance keeps a path that merely
        touches the edge from reading as hidden work."""
        if self.artboard is None:
            return False
        ax0, ay0, ax1, ay1 = self.artwork
        bx0, by0, bx1, by1 = self.artboard
        return (ax0 < bx0 - 1 or ay0 < by0 - 1
                or ax1 > bx1 + 1 or ay1 > by1 + 1)

    @property
    def hidden(self) -> tuple[float, float, float, float] | None:
        """How far the artwork overruns each edge: ``(left, bottom, right,
        top)`` in points, or None when nothing is out there."""
        if not self.offboard or self.artboard is None:
            return None
        ax0, ay0, ax1, ay1 = self.artwork
        bx0, by0, bx1, by1 = self.artboard
        return (max(0.0, bx0 - ax0), max(0.0, by0 - ay0),
                max(0.0, ax1 - bx1), max(0.0, ay1 - by1))


@dataclass(frozen=True)
class Recovery:
    """What ``recover`` produced."""

    target: Path
    canvas: Canvas
    paths: int
    skipped: tuple[str, ...] = ()


EDGES = ("left", "bottom", "right", "top")
"""Order of ``Canvas.hidden``."""


def measure(box: tuple[float, float, float, float] | None) -> str:
    """A rectangle as the pane prints it: ``936 × 936 pt``."""
    if box is None:
        return "—"
    return "%g × %g pt" % (round(box[2] - box[0], 2), round(box[3] - box[1], 2))


def describe_hidden(canvas: Canvas) -> str:
    """Which edges the artwork runs past, and by how far — the pane's
    one-line answer to "is anything out there?"."""
    hidden = canvas.hidden
    if hidden is None:
        return "nothing outside the artboard"
    over = [(EDGES[i], value) for i, value in enumerate(hidden) if value > 1]
    if len(over) == 1:
        return "%g pt past the %s edge" % (round(over[0][1]), over[0][0])
    return " · ".join("%g pt %s" % (round(value), edge) for edge, value in over)


def is_illustrator(path: Path) -> bool:
    return path.suffix.lower() in EXTENSIONS


def read_canvas(path: Path) -> Canvas | None:
    """Parse the AI portion's header. None when the file carries no AI art
    stream (a PDF renamed .ai, or a save with PDF compatibility only)."""
    try:
        text = art_stream(path)
    except (OSError, ValueError, zlib.error, zstd.ZstdError):
        return None
    art = _bbox(text, "%%HiResBoundingBox:") or _bbox(text, "%%BoundingBox:")
    if art is None:
        return None
    board = _bbox(text, "%AI3_Cropmarks:")
    if board is None:
        board = _media_box(path)
    return Canvas(art, board)


def _bbox(text: str, marker: str) -> tuple[float, float, float, float] | None:
    at = text.find(marker)
    if at < 0:
        return None
    parts = text[at + len(marker):text.find("\n", at)].split()
    try:
        values = [float(v) for v in parts[:4]]
    except ValueError:
        return None
    return tuple(values) if len(values) == 4 else None  # type: ignore[return-value]


def _media_box(path: Path) -> tuple[float, float, float, float] | None:
    """The PDF portion's page box — the artboard, for a file whose AI header
    omits ``%AI3_Cropmarks``."""
    m = re.search(rb"/MediaBox\s*\[([\d\.\s-]+)\]", path.read_bytes())
    if not m:
        return None
    values = [float(v) for v in m.group(1).split()]
    return tuple(values) if len(values) == 4 else None  # type: ignore[return-value]


# -- getting at the AI portion ------------------------------------------------


def art_stream(path: Path) -> str:
    """The document's legacy AI art stream, decompressed and newline-normalized.

    Four container shapes, newest first: ``/AIPrivateData`` streams
    Zstandard-compressed behind ``%AI24_ZStandard_Data`` (Illustrator 2020
    and later), the same streams zlib-compressed behind
    ``%AI12_CompressedData`` (CS through 2019), uncompressed, and a bare
    PostScript .ai (AI8 and earlier), which IS the art stream."""
    data = path.read_bytes()
    if data[:4] == b"%PDF":
        blob = b"".join(_stream(data, n) for n in _private_objects(data))
        if not blob:
            raise ValueError("no AI private data in this .ai")
    else:
        blob = data
    at = blob.find(b"%AI24_ZStandard_Data")
    if at >= 0:
        blob = zstd.ZstdDecompressor().decompress(blob[at + 20:])
    else:
        at = blob.find(b"%AI12_CompressedData")
        if at >= 0:
            blob = zlib.decompressobj().decompress(blob[at + 20:])
    return blob.decode("latin-1").replace("\r\n", "\n").replace("\r", "\n")


def _private_objects(data: bytes) -> list[int]:
    """Object numbers of the ``/AIPrivateDataN`` streams, in N order — the
    stream is split across them and the pieces only mean anything joined."""
    found: list[tuple[int, int]] = []
    for m in re.finditer(rb"/AIPrivateData(\d+)\s+(\d+)\s+0\s+R", data):
        found.append((int(m.group(1)), int(m.group(2))))
    return [obj for _, obj in sorted(found)]


def _stream(data: bytes, number: int) -> bytes:
    """One PDF stream's bytes, by ``/Length`` — no filter is applied, because
    Illustrator writes these unfiltered."""
    m = re.search(rb"(?<![0-9])" + str(number).encode() + rb"\s+0\s+obj", data)
    if not m:
        return b""
    head = data.find(b"stream", m.end())
    if head < 0:
        return b""
    length = re.search(rb"/Length\s+(\d+)", data[m.end():head])
    if not length:
        return b""
    at = head + 6
    if data[at:at + 2] == b"\r\n":
        at += 2
    elif data[at:at + 1] in (b"\r", b"\n"):
        at += 1
    return data[at:at + int(length.group(1))]


def icc_profile(path: Path) -> tuple[bytes, bool] | None:
    """The document's embedded CMYK profile as ``(stream bytes, deflated)``.

    Illustrator tags its CMYK against an ICC profile; reusing that exact
    profile is what keeps the rescue's colours identical to the original
    instead of merely close."""
    data = path.read_bytes()
    for m in re.finditer(rb"(\d+)\s+0\s+obj\s*<<([^>]*?/N\s+4[^>]*?)>>stream", data):
        raw = _stream(data, int(m.group(1)))
        if raw:
            return raw, b"/FlateDecode" in m.group(2)
    return None


# -- the art stream's own language --------------------------------------------

_TOKEN = re.compile(r"\(((?:[^()\\]|\\.)*)\)|(\[|\])|(<[^>]*>)|([^\s\[\]()<>]+)")

_UNSUPPORTED = {
    "XI": "placed image", "XF": "placed image", "XG": "placed image",
    "Tx": "live text", "TX": "live text", "To": "live text",
    "Xp": "pattern fill", "Np": "pattern", "Pb": "plugin object",
    "Bh": "mesh gradient",
}

_PAINT = {
    "f": ("fill", True), "F": ("fill", False),
    "s": ("stroke", True), "S": ("stroke", False),
    "b": ("both", True), "B": ("both", False),
    "n": ("none", True), "N": ("none", False),
}


def _num(value: float) -> str:
    text = "%.4f" % value
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass
class _State:
    """The paint settings a run of subpaths shares. A change flushes."""

    fill: str = "0 g"
    stroke: str = "0 G"
    width: str = "1 w"
    cap: str = "0 J"
    join: str = "0 j"
    miter: str = "10 M"
    dash: str = "[] 0 d"

    @property
    def line(self) -> str:
        return " ".join((self.width, self.cap, self.join, self.miter, self.dash))


class _Art:
    """Translates the AI art stream into PDF content operators.

    Two things in the format are not obvious and are the whole reason this
    reads the way it does:

    * A run of subpaths that share paint settings is ONE PDF path filled with
      the nonzero rule — which is exactly how Illustrator writes its own PDF
      half. It is also what makes compound holes work: a hole is a subpath
      wound the other way (the ``D`` operator records the direction, so the
      coordinates already carry it), not a separate shape.
    * A gradient object inside a group (``Bb``…``BB``) does not paint itself
      on top of the group — every path collected in that group is the CLIP
      the gradient is painted through. Miss this and a gradient logo comes
      back as a black silhouette with a gradient patch on it.
    """

    def __init__(self) -> None:
        self.ops: list[str] = []
        self.sub: list[str] = []
        self.done: list[str] = []
        self.state = _State()
        self.painted = _State()
        self.paint = "fill"
        self.in_gradient = False
        self.gradient_name: str | None = None
        self.matrix: str | None = None
        self.fills = 0
        self.skipped: set[str] = set()
        self.min_x = self.min_y = float("inf")
        self.max_x = self.max_y = float("-inf")

    # -- geometry -------------------------------------------------------

    def _point(self, x: float, y: float) -> None:
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)

    def bounds(self) -> tuple[float, float, float, float]:
        if self.min_x > self.max_x:
            return (0.0, 0.0, 0.0, 0.0)
        return (self.min_x, self.min_y, self.max_x, self.max_y)

    # -- painting -------------------------------------------------------

    def _operator(self) -> str:
        return {"fill": "f", "stroke": "S", "both": "B", "none": "n"}[self.paint]

    def flush(self) -> None:
        if self.done:
            if self.paint in ("fill", "both"):
                self.ops.append(self.painted.fill)
            if self.paint in ("stroke", "both"):
                self.ops.append(self.painted.stroke)
                self.ops.append(self.painted.line)
            self.ops.extend(self.done)
            self.ops.append(self._operator())
            self.fills += 1
            self.done = []
        self.painted = _State(**vars(self.state))

    def _restyle(self, **changes: str) -> None:
        if self.done and any(getattr(self.state, k) != v for k, v in changes.items()):
            self.flush()
        for key, value in changes.items():
            setattr(self.state, key, value)
        if not self.done:
            self.painted = _State(**vars(self.state))

    def _end_subpath(self, close: bool) -> None:
        if not self.sub:
            return
        if close:
            self.sub.append("h")
        self.done.extend(self.sub)
        self.sub = []

    # -- the loop -------------------------------------------------------

    def run(self, section: str) -> None:
        stack: list[float | str] = []
        for line in section.split("\n"):
            if line.startswith("%"):
                continue
            for m in _TOKEN.finditer(line):
                if m.group(4) is None:
                    stack.append(m.group(1) or m.group(2) or m.group(3) or "")
                    continue
                token = m.group(4)
                try:
                    stack.append(float(token))
                    continue
                except ValueError:
                    pass
                stack = self._operator_token(token, stack)
        self._end_subpath(False)
        self.flush()

    def _operator_token(self, op: str, stack: list) -> list:
        numbers = [v for v in stack if isinstance(v, float)]

        if op == "m" and len(numbers) >= 2:
            x, y = numbers[-2:]
            self._point(x, y)
            self.sub.append("%s %s m" % (_num(x), _num(y)))
        elif op in ("l", "L") and len(numbers) >= 2:
            x, y = numbers[-2:]
            self._point(x, y)
            self.sub.append("%s %s l" % (_num(x), _num(y)))
        elif op in ("c", "C") and len(numbers) >= 6:
            a = numbers[-6:]
            for i in (0, 2, 4):
                self._point(a[i], a[i + 1])
            self.sub.append(" ".join(_num(v) for v in a) + " c")
        elif op in ("v", "V", "y", "Y") and len(numbers) >= 4:
            a = numbers[-4:]
            for i in (0, 2):
                self._point(a[i], a[i + 1])
            self.sub.append(" ".join(_num(v) for v in a) + " " + op.lower())

        # colour and line settings
        elif op == "g" and numbers:
            self._restyle(fill="%s g" % _num(numbers[-1]))
        elif op == "G" and numbers:
            self._restyle(stroke="%s G" % _num(numbers[-1]))
        elif op == "k" and len(numbers) >= 4:
            self._restyle(fill="/CS0 cs " + " ".join(_num(v) for v in numbers[-4:]) + " scn")
        elif op == "K" and len(numbers) >= 4:
            self._restyle(stroke="/CS0 CS " + " ".join(_num(v) for v in numbers[-4:]) + " SCN")
        elif op in ("x", "X", "p", "P"):
            self.skipped.add("pattern or spot colour")
        elif op == "w" and numbers:
            self._restyle(width="%s w" % _num(numbers[-1]))
        elif op == "J" and numbers:
            self._restyle(cap="%d J" % int(numbers[-1]))
        elif op == "j" and numbers:
            self._restyle(join="%d j" % int(numbers[-1]))
        elif op == "M" and numbers:
            self._restyle(miter="%s M" % _num(numbers[-1]))
        elif op == "d":
            pattern = " ".join(_num(v) for v in numbers[:-1]) if len(numbers) > 1 else ""
            phase = _num(numbers[-1]) if numbers else "0"
            self._restyle(dash="[%s] %s d" % (pattern, phase))

        # paint
        elif op in _PAINT:
            mode, close = _PAINT[op]
            if self.in_gradient:
                self._paint_gradient(close)
            else:
                self.paint = mode
                self._end_subpath(close)
        elif op == "u" or op == "U":
            pass                        # compound path: its subpaths merge
        elif op in ("*u", "*U"):
            self.flush()                # group boundary
        elif op == "W":
            pass                        # clip flag; the gradient path carries it

        # gradients
        elif op == "Bb":
            self.in_gradient = True
        elif op == "Bg":
            names = [v for v in stack if isinstance(v, str)]
            self.gradient_name = names[0] if names else None
        elif op in ("Xm", "Bm"):
            if len(numbers) >= 6:
                self.matrix = " ".join(_num(v) for v in numbers[-6:]) + " cm"
        elif op == "BB":
            self.in_gradient = False

        elif op in _UNSUPPORTED:
            self.skipped.add(_UNSUPPORTED[op])

        return []

    def _paint_gradient(self, close: bool) -> None:
        """Paint the shading through everything the group collected."""
        self._end_subpath(close)
        self.ops.append("q")
        self.ops.extend(self.done)
        self.ops.append("W n")
        self.ops.append(self.matrix or "1 0 0 1 0 0 cm")
        self.ops.append("/Sh0 sh")
        self.ops.append("Q")
        self.done = []
        self.in_gradient = False


# -- gradients ----------------------------------------------------------------


@dataclass
class _Gradient:
    linear: bool = True
    stops: list[tuple[float, tuple[float, float, float, float]]] = field(
        default_factory=list)


def _gradients(text: str) -> dict[str, _Gradient]:
    out: dict[str, _Gradient] = {}
    for m in re.finditer(r"%AI5_BeginGradient: \((.*?)\)\n(.*?)%AI5_EndGradient",
                         text, re.S):
        name, block = m.group(1), m.group(2)
        kind = re.search(r"\(.*?\) (\d+) (\d+) Bd", block)
        grad = _Gradient(linear=(kind.group(1) == "0") if kind else True)
        for stop in re.finditer(r"^([-\d\. ]+) %_BS$", block, re.M):
            values = [float(v) for v in stop.group(1).split()]
            if len(values) >= 5:
                grad.stops.append((values[-1], tuple(values[:4])))  # type: ignore[arg-type]
        grad.stops.sort()
        out[name] = grad
    return out


# -- writers ------------------------------------------------------------------


def _shading_objects(grad: _Gradient, first: int, icc: bool) -> dict[int, str]:
    """An axial shading plus its colour function, numbered from ``first``."""
    space = "%d 0 R" % (_ICC_OBJECT + 1) if icc else "/DeviceCMYK"
    stops = grad.stops
    if len(stops) == 2:
        function = ("<</FunctionType 2/Domain[0 1]/N 1/C0[%s]/C1[%s]>>"
                    % (" ".join(_num(v) for v in stops[0][1]),
                       " ".join(_num(v) for v in stops[-1][1])))
        return {first: ("<</ShadingType 2/ColorSpace %s/Coords[0 0 1 0]"
                        "/Domain[0 1]/Extend[true true]/Function %d 0 R"
                        "/AntiAlias false>>" % (space, first + 1)),
                first + 1: function}
    # three or more stops: stitch one exponential per segment
    objects: dict[int, str] = {}
    pieces, bounds, encode = [], [], []
    span = (stops[-1][0] - stops[0][0]) or 1.0
    for i in range(len(stops) - 1):
        number = first + 2 + i
        objects[number] = ("<</FunctionType 2/Domain[0 1]/N 1/C0[%s]/C1[%s]>>"
                           % (" ".join(_num(v) for v in stops[i][1]),
                              " ".join(_num(v) for v in stops[i + 1][1])))
        pieces.append("%d 0 R" % number)
        encode.append("0 1")
        if i:
            bounds.append(_num((stops[i][0] - stops[0][0]) / span))
    objects[first] = ("<</ShadingType 2/ColorSpace %s/Coords[0 0 1 0]/Domain[0 1]"
                      "/Extend[true true]/Function %d 0 R/AntiAlias false>>"
                      % (space, first + 1))
    objects[first + 1] = ("<</FunctionType 3/Domain[0 1]/Functions[%s]"
                          "/Bounds[%s]/Encode[%s]>>"
                          % (" ".join(pieces), " ".join(bounds), " ".join(encode)))
    return objects


_ICC_OBJECT = 20
"""Fixed object number for the ICC stream — it is written last and out of
band because its bytes are binary."""


def _pdf(content: str, box: tuple[float, float, float, float],
         grad: _Gradient | None, icc: tuple[bytes, bool] | None,
         title: str) -> bytes:
    objects: dict[int, str] = {
        1: "<</Type/Catalog/Pages 3 0 R>>",
        2: ("<</Type/ExtGState/BM/Normal/CA 1/ca 1/OP false/op false"
            "/OPM 1/SA true>>"),
        3: "<</Type/Pages/Count 1/Kids[4 0 R]>>",
        10: "<</Title(%s)/Producer(mediasmith)>>" % title,
    }
    resources = "<</ExtGState<</GS0 2 0 R>>"
    if icc:
        objects[_ICC_OBJECT + 1] = "[/ICCBased %d 0 R]" % _ICC_OBJECT
        resources += "/ColorSpace<</CS0 %d 0 R>>" % (_ICC_OBJECT + 1)
    if grad:
        objects.update(_shading_objects(grad, 5, icc is not None))
        resources += "/Shading<</Sh0 5 0 R>>"
    resources += ">>"
    objects[4] = ("<</Type/Page/Parent 3 0 R/MediaBox[%s]/Resources %s"
                  "/Contents 7 0 R>>"
                  % (" ".join(_num(v) for v in box), resources))
    objects[7] = ("<</Length %d>>stream\n%s\nendstream"
                  % (len(content.encode("latin-1")), content))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += ("%d 0 obj\n%s\nendobj\n" % (number, objects[number])).encode("latin-1")
    if icc:
        raw, deflated = icc
        offsets[_ICC_OBJECT] = len(out)
        head = "<</N 4%s/Length %d>>" % ("/Filter/FlateDecode" if deflated else "",
                                         len(raw))
        out += ("%d 0 obj\n%s\nstream\n" % (_ICC_OBJECT, head)).encode("latin-1")
        out += raw + b"\nendstream\nendobj\n"

    start = len(out)
    top = max(offsets) + 1
    out += ("xref\n0 %d\n" % top).encode() + b"0000000000 65535 f \n"
    for number in range(1, top):
        out += ("%010d 00000 n \n" % offsets.get(number, 0)).encode()
    out += ("trailer\n<</Size %d/Root 1 0 R/Info 10 0 R>>\nstartxref\n%d\n%%%%EOF\n"
            % (top, start)).encode()
    return bytes(out)


def _to_rgb(colours: list[tuple[float, ...]],
            icc: tuple[bytes, bool] | None) -> list[str]:
    """CMYK → sRGB hex, through the document's own profile when littleCMS can
    read it (Pillow ships it), and through the naive formula when it can't."""
    naive = ["#%02X%02X%02X" % tuple(
        max(0, min(255, round(255 * (1 - c[i]) * (1 - c[3])))) for i in range(3))
        for c in colours]
    if not colours or icc is None:
        return naive
    raw, deflated = icc
    try:
        import io
        from PIL import Image, ImageCms
        profile = zlib.decompress(raw) if deflated else raw
        source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        image = Image.new("CMYK", (len(colours), 1))
        image.putdata([tuple(round(255 * v) for v in c[:4]) for c in colours])
        converted = ImageCms.profileToProfile(
            image, source, ImageCms.createProfile("sRGB"), outputMode="RGB")
        return ["#%02X%02X%02X" % pixel for pixel in converted.getdata()]
    except Exception:
        return naive


def _svg_path(ops: list[str]) -> str:
    """PDF path operators → one SVG ``d``. ``v``/``y`` become full cubics —
    SVG's ``S`` reflects the previous control point, which is not the same
    curve."""
    out: list[str] = []
    cx = cy = "0"
    for op in ops:
        parts = op.split()
        kind = parts[-1]
        if kind == "m":
            out.append("M%s %s" % (parts[0], parts[1]))
            cx, cy = parts[0], parts[1]
        elif kind == "l":
            out.append("L%s %s" % (parts[0], parts[1]))
            cx, cy = parts[0], parts[1]
        elif kind == "c":
            out.append("C%s" % " ".join(parts[:6]))
            cx, cy = parts[4], parts[5]
        elif kind == "v":                       # control 1 is the current point
            out.append("C%s %s %s %s" % (cx, cy, " ".join(parts[:2]),
                                         " ".join(parts[2:4])))
            cx, cy = parts[2], parts[3]
        elif kind == "y":                       # control 2 is the end point
            out.append("C%s %s %s" % (" ".join(parts[:2]), " ".join(parts[2:4]),
                                      " ".join(parts[2:4])))
            cx, cy = parts[2], parts[3]
        elif kind == "h":
            out.append("Z")
    return " ".join(out)


def _svg(art: _Art, box: tuple[float, float, float, float],
         grad: _Gradient | None, icc: tuple[bytes, bool] | None) -> str:
    left, bottom = box[0], box[1]
    width, height = box[2] - left, box[3] - bottom

    wanted: list[tuple[float, ...]] = []
    index: dict[tuple[float, ...], int] = {}

    def register(colour: tuple[float, ...]) -> int:
        if colour not in index:
            index[colour] = len(wanted)
            wanted.append(colour)
        return index[colour]

    for op in art.ops:
        m = re.match(r"/CS0 (?:cs|CS) ([\d\. ]+) (?:scn|SCN)$", op)
        if m:
            register(tuple(float(v) for v in m.group(1).split()))
    for _, colour in (grad.stops if grad else []):
        register(colour)
    rgb = _to_rgb(wanted, icc)

    def colour_of(op: str) -> str:
        m = re.match(r"/CS0 (?:cs|CS) ([\d\. ]+) (?:scn|SCN)$", op)
        if m:
            return rgb[index[tuple(float(v) for v in m.group(1).split())]]
        value = int(round(float(op.split()[0]) * 255))
        return "#%02X%02X%02X" % (value, value, value)

    body: list[str] = []
    fill, stroke, width_px = "#000000", "none", "1"
    current: list[str] = []
    clips = 0
    i = 0
    while i < len(art.ops):
        op = art.ops[i]
        if op.endswith(("scn", " g")):
            fill = colour_of(op)
            current = []
        elif op.endswith(("SCN", " G")):
            stroke = colour_of(op)
            current = []
        elif op.endswith(" d"):
            width_px = op.split()[0]
            current = []
        elif op == "q":
            end = art.ops.index("W n", i)
            clips += 1
            body.append('<clipPath id="c%d"><path d="%s"/></clipPath>'
                        % (clips, _svg_path(art.ops[i + 1:end])))
            body.append('<g clip-path="url(#c%d)"><rect x="%s" y="%s" width="%s" '
                        'height="%s" fill="url(#gradient)"/></g>'
                        % (clips, _num(left), _num(bottom),
                           _num(width), _num(height)))
            i = art.ops.index("Q", end)
            current = []
        elif op in ("f", "S", "B", "n"):
            if op != "n" and current:
                paint = ('fill="%s"' % fill) if op in ("f", "B") else 'fill="none"'
                if op in ("S", "B"):
                    paint += ' stroke="%s" stroke-width="%s"' % (stroke, width_px)
                body.append('<path d="%s" %s/>' % (_svg_path(current), paint))
            current = []
        elif not op.endswith(" cm") and op != "/Sh0 sh":
            current.append(op)
        i += 1

    defs = ""
    if grad and art.matrix:
        a, b, _c, _d, e, f = [float(v) for v in art.matrix.split()[:6]]
        c0 = rgb[index[grad.stops[0][1]]]
        c1 = rgb[index[grad.stops[-1][1]]]
        defs = ('<linearGradient id="gradient" gradientUnits="userSpaceOnUse" '
                'x1="%s" y1="%s" x2="%s" y2="%s">'
                '<stop offset="0" stop-color="%s"/>'
                '<stop offset="1" stop-color="%s"/></linearGradient>'
                % (_num(e), _num(f), _num(a + e), _num(b + f), c0, c1))

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="%spt" height="%spt" '
            'viewBox="0 0 %s %s">\n<defs>%s</defs>\n'
            '<g transform="translate(%s,%s) scale(1,-1)">\n%s\n</g>\n</svg>\n'
            % (_num(width), _num(height), _num(width), _num(height), defs,
               _num(-left), _num(box[3]), "\n".join(body)))


# -- the action ---------------------------------------------------------------


def target_for(source: Path, fmt: str = "pdf") -> Path:
    return source.with_name(source.stem + SUFFIX + "." + fmt.lower())


def recover(source: Path, fmt: str = "pdf", overwrite: bool = False) -> Recovery:
    """Write every path in ``source`` — artboard and beyond — beside it.

    Coordinates are the document's own, so on-artboard work lands where it
    always was and the rescued work sits off to whichever side it was parked.
    Refuses to overwrite (FileExistsError) unless ``overwrite``."""
    fmt = fmt.lower()
    if fmt not in FORMATS:
        raise ValueError("no writer for .%s" % fmt)
    target = target_for(source, fmt)
    if target.exists() and not overwrite:
        raise FileExistsError("%s already exists" % target.name)

    text = art_stream(source)
    start, end = text.find("%AI5_BeginLayer"), text.rfind("%AI5_EndLayer")
    if start < 0:
        raise ValueError("no artwork in this .ai")

    art = _Art()
    art.run(text[start:end if end > start else len(text)])
    if not art.fills and not art.ops:
        raise ValueError("no artwork in this .ai")

    gradients = _gradients(text)
    grad = gradients.get(art.gradient_name or "")
    if grad and not grad.linear:
        art.skipped.add("radial gradient (flattened)")
    if grad and len(grad.stops) < 2:
        grad = None

    x0, y0, x1, y1 = art.bounds()
    # the origin stays in the box, and so does work parked left of or below
    # it — Illustrator's canvas runs negative on both axes
    box = (round(x0 - 24) if x0 < 0 else 0.0,
           round(y0 - 24) if y0 < 0 else 0.0,
           round(x1 + 24), round(y1 + 24))
    icc = icc_profile(source) if source.read_bytes()[:4] == b"%PDF" else None

    if fmt == "pdf":
        # the page starts at 0,0 and one cm carries the canvas onto it:
        # Preview and Quick Look draw a negative-origin MediaBox as blank
        left, bottom = box[0], box[1]
        ops = (["1 0 0 1 %s %s cm" % (_num(-left), _num(-bottom))]
               if left or bottom else []) + art.ops
        target.write_bytes(_pdf("\n".join(ops),
                                (0.0, 0.0, box[2] - left, box[3] - bottom),
                                grad, icc, source.stem + SUFFIX))
    else:
        target.write_text(_svg(art, box, grad, icc), encoding="utf-8")

    return Recovery(target=target,
                    canvas=Canvas((x0, y0, x1, y1), _bbox(text, "%AI3_Cropmarks:")),
                    paths=art.fills,
                    skipped=tuple(sorted(art.skipped)))
