"""Image Trace: bitmap → black-and-white vector, through potrace.

Illustrator's Image Trace, as far as potrace can follow it (Nick,
2026-09-16). The controls wear ILLUSTRATOR'S names and scales — potrace's
own (turdsize, alphamax, opttolerance) never leave this module:

    threshold     0–255   pixels darker than this trace as black
    paths         0–100%  how tightly curves hug the pixels  → opttolerance
    corners       0–100%  how readily a bend becomes a corner → alphamax
    noise         1–100px speckles up to this area are dropped → turdsize
    invert        on/off  trace the light areas instead
    ignore white  on/off  off fills the white shapes too     → --opaque

The defaults are potrace's own defaults expressed on those scales (paths
80% = opttolerance 0.2, corners 25% = alphamax 1.0, noise 2 = turdsize 2),
so the first preview is potrace's best guess, not a mapping accident.

potrace reads only PNM/BMP, so Pillow does the decoding (every format in
kinds.IMAGE_EXTENSIONS) and the threshold, and pipes a 1-bit PBM over
stdin — no ImageMagick. The live preview is potrace's PGM backend: the
trace rendered straight to a greyscale raster at the exact pixel size of
the pane, so no SVG rasterizer is needed either.

Why the binary and not the pure-Python port (potracer), measured
2026-09-16 on a detail-dense image: 1 MP 0.14s vs 4.2s, 4 MP 0.54s vs
46s, 9 MP 1.2s vs 3½ min — the port can't keep a stepper live. Every
call sits behind ``preview`` and ``trace``, so a port can replace the
binary later without the pane noticing; the port would have to supply
the SVG/EPS/PDF writers and the preview rasterizer the binary brings.

IO-free in the house sense: no printing, no widgets. It does spawn
potrace and read/write files, so callers run it in a thread worker.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

FORMATS = ("svg", "eps", "pdf")
"""The format picker's options, in cycle order."""

_SEARCH_DIRS = (Path("/opt/homebrew/bin"), Path("/usr/local/bin"))
"""Homebrew's two prefixes: an app launched outside a login shell may not
have either on PATH."""

INSTALL_HINT = "potrace not found — install it with: brew install potrace"


@dataclass(frozen=True)
class Stepper:
    """One numeric control: its range and how far one arrow press goes."""

    name: str
    label: str
    minimum: int
    maximum: int
    step: int
    big_step: int           # ⇧←→
    unit: str = ""


STEPPERS = (
    Stepper("threshold", "threshold", 0, 255, 1, 10),
    Stepper("paths", "paths", 0, 100, 1, 10, "%"),
    Stepper("corners", "corners", 0, 100, 1, 10, "%"),
    Stepper("noise", "noise", 1, 100, 1, 10, " px"),
)

TOGGLES = (("invert", "invert"), ("ignore_white", "ignore white"))

CONTROLS: tuple[tuple[str, str], ...] = (
    *((s.name, s.label) for s in STEPPERS), *TOGGLES, ("format", "format"))
"""Every control as (name, label), top to bottom — the pane's row order."""

PREVIEW_CONTROLS = frozenset({*(s.name for s in STEPPERS), "invert"})
"""Controls whose change alters the preview. Format only picks the file
the save writes; ignore white only adds white fills, which a preview
drawn on white can't show."""

_STEPPERS = {s.name: s for s in STEPPERS}


@dataclass(frozen=True)
class TraceSettings:
    threshold: int = 128
    paths: int = 80
    corners: int = 25
    noise: int = 2
    invert: bool = False
    ignore_white: bool = True
    format: str = "svg"

    def nudged(self, name: str, steps: int) -> TraceSettings:
        """One arrow press on control ``name``: a stepper moves ``steps``
        (clamped), a toggle flips, the format cycles in ``steps``'
        direction."""
        if name in _STEPPERS:
            spec = _STEPPERS[name]
            value = min(spec.maximum,
                        max(spec.minimum, getattr(self, name) + steps))
            return replace(self, **{name: value})
        if name == "format":
            index = FORMATS.index(self.format)
            step = 1 if steps > 0 else -1
            return replace(self, format=FORMATS[(index + step) % len(FORMATS)])
        if name in dict(TOGGLES):
            return replace(self, **{name: not getattr(self, name)})
        raise KeyError(name)

    def display(self, name: str) -> str:
        """The control's value as the pane prints it."""
        value = getattr(self, name)
        if isinstance(value, bool):
            return "on" if value else "off"
        if name in _STEPPERS:
            return f"{value}{_STEPPERS[name].unit}"
        return str(value)

    # -- the Illustrator → potrace mapping -----------------------------------

    @property
    def alphamax(self) -> float:
        """corners 0% → 4/3 (potrace's "no corners"), 100% → 0 (all
        corners, a polygon)."""
        return round(4 / 3 * (100 - self.corners) / 100, 4)

    @property
    def opttolerance(self) -> float:
        """paths 100% → 0 (curves hug every pixel), 0% → 1.0 (loose)."""
        return round((100 - self.paths) / 100, 4)

    @property
    def turdsize(self) -> int:
        return self.noise


def find_potrace() -> Path | None:
    found = shutil.which("potrace")
    if found:
        return Path(found)
    for folder in _SEARCH_DIRS:
        candidate = folder / "potrace"
        if candidate.exists():
            return candidate
    return None


def load_gray(path: Path):
    """The source as an 8-bit greyscale Pillow image, upright (EXIF
    orientation applied) and with any transparency laid over white — a
    transparent logo traces as the logo, not as a black box."""
    from PIL import Image, ImageOps
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    if image.mode in ("RGBA", "LA", "PA"):
        ground = Image.new("RGBA", image.size, (255, 255, 255, 255))
        ground.alpha_composite(image.convert("RGBA"))
        image = ground
    return image.convert("L")


def bitmap(gray, settings: TraceSettings) -> bytes:
    """The 1-bit PBM potrace traces: black where the pixel is darker than
    the threshold (lighter, inverted)."""
    import io
    black, white = (255, 0) if settings.invert else (0, 255)
    table = [black if level < settings.threshold else white
             for level in range(256)]
    buffer = io.BytesIO()
    gray.point(table, mode="1").save(buffer, format="PPM")
    return buffer.getvalue()


def potrace_args(settings: TraceSettings, backend: str,
                 size: tuple[int, int] | None = None) -> list[str]:
    """potrace's flags for ``settings`` (the tool path and I/O excluded).
    ``size`` is the PGM preview's pixel box."""
    args = ["-b", backend,
            "-t", str(settings.turdsize),
            "-a", str(settings.alphamax),
            "-O", str(settings.opttolerance)]
    if size is not None:
        args += ["-W", str(size[0]), "-H", str(size[1])]
    if not settings.ignore_white and backend in FORMATS:
        args.append("--opaque")
    return args


def _run(args: list[str], pbm: bytes) -> bytes:
    tool = find_potrace()
    if tool is None:
        raise RuntimeError(INSTALL_HINT)
    result = subprocess.run([str(tool), *args, "-o", "-", "-"],
                            input=pbm, capture_output=True)
    if result.returncode != 0:
        snippet = result.stderr.decode(errors="ignore")[-300:].strip()
        raise RuntimeError(f"potrace failed: {snippet}")
    return result.stdout


def fit(width: int, height: int, box_width: int,
        box_height: int) -> tuple[int, int]:
    """The largest ``width``×``height``-shaped size inside the box — never
    cropped, never stretched, never below one pixel."""
    scale = min(box_width / width, box_height / height)
    return (max(1, min(box_width, round(width * scale))),
            max(1, min(box_height, round(height * scale))))


def preview(gray, settings: TraceSettings, size: tuple[int, int]):
    """The traced shapes rendered to a ``size`` greyscale Pillow image
    (anti-aliased — potrace's PGM backend draws the vector, it does not
    resample the bitmap)."""
    import io
    from PIL import Image
    data = _run(potrace_args(settings, "pgm", size), bitmap(gray, settings))
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def target_for(source: Path, settings: TraceSettings) -> Path:
    return source.with_suffix("." + settings.format)


def trace(source: Path, settings: TraceSettings,
          overwrite: bool = False) -> Path:
    """Trace ``source`` at full resolution into ``settings.format`` beside
    it. Refuses to overwrite (FileExistsError) unless ``overwrite``;
    writes to a hidden sibling first, so a failure never leaves a partial
    file under the real name."""
    target = target_for(source, settings)
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target.name} already exists")
    if find_potrace() is None:
        raise RuntimeError(INSTALL_HINT)
    data = _run(potrace_args(settings, settings.format),
                bitmap(load_gray(source), settings))
    temp = target.parent / (".trace-tmp-" + target.name)
    try:
        temp.write_bytes(data)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return target
