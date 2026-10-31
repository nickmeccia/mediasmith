"""Shrink a comic to reading size.

Nick's problem, with his own files as the evidence (2026-10-31): a
single issue has gone from 30–60 MB to 150–280 MB. Measured across the
four worst in ~/Documents/Comics, the weight is in two places and
neither of them is the drawing:

- **Encoder settings.** Every page is 4:4:4 chroma and quality 95–100 —
  one book's luma quantization table is all ones, which is quality 100.
  Re-encoding at q85 / 4:2:0 / progressive, at the SAME pixel size,
  took a 6.3 MB page to 1.4 MB.
- **Oversampling.** The two Cyberpunk books are ~3975 × 6113, about
  24 megapixels a page — a 600 DPI print scan. No iPad can show it.

Sizing follows from the device. A 2019 iPad Pro is 2732 × 2048 (12.9")
or 2388 × 1668 (11"); the 2024 13" is 2752 × 2064, and that is the
tallest panel Apple has shipped. A comic page is taller and narrower
than the screen, so reading height is what binds, and a page 3000 px
tall covers every one of them with room left to zoom.

**Height is the cap, not the long edge.** A double-page spread is as
tall as a single page and twice as wide (3975 × 3056 in Nick's files);
capping its long edge would shrink its height below a single page's and
make each half blurrier than the pages around it. Capping height leaves
a spread alone and halves a 6113 px page.

Output is JPEG whatever went in: Synology's DS File is how Nick reads
these off the NAS, and WebP support across Synology's iOS apps is
unreliable and undocumented (checked 2026-10-31).

Nothing is written until a page comes out SMALLER. A page that would
grow is left exactly as it was.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

__all__ = ["HEIGHT", "QUALITY", "SUFFIXES", "Page", "ShrinkPlan",
           "Shrunk", "Kept", "Failed", "probe", "iter_pages", "build_plan",
           "apply"]

HEIGHT = 3000
"""Default height cap, in pixels. Above every iPad Apple has shipped
(2752 is the tallest) with room to zoom into."""

QUALITY = 85
"""Default JPEG quality. At the same pixel size this alone is a 4–5×
saving over the q95–100 these files arrive at; below ~80 the flat
colour areas comics are full of start to band."""

SUBSAMPLING = 2         # 4:2:0 — half the chroma, invisible on line art

SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

SAMPLE = 3
"""Pages encoded to estimate a folder. The preview says how many."""

TOLERANCE = 1.05
"""How far OVER the cap a page may be and still be left at its own size.

A 3056 px page resampled to 3000 loses sharpness to save almost
nothing — 2% of the pixels. The cap is what a page may not greatly
exceed, not a size every page must be made exactly."""


def would_resize(height: int, cap: int = HEIGHT) -> bool:
    """Whether a page this tall is worth resampling at all."""
    return height > cap * TOLERANCE


@dataclass(frozen=True)
class Page:
    path: Path
    before: int                     # bytes on disk
    width: int
    height: int

    @property
    def after_size(self) -> tuple[int, int]:
        """What this page becomes at the plan's cap (set by build_plan)."""
        return self.width, self.height


@dataclass(frozen=True)
class ShrinkPlan:
    """What shrinking this selection would do, and roughly what it saves.

    The estimate is honest about being one: encoding every page twice —
    once to preview, once to keep — would double the slowest part of the
    job, so a few pages are encoded and the ratio is carried across the
    rest. ``sampled`` says how many.
    """
    root: Path
    pages: tuple[Page, ...]
    height: int = HEIGHT
    quality: int = QUALITY
    sampled: int = 0
    sample_before: int = 0
    sample_after: int = 0

    @property
    def empty(self) -> bool:
        return not self.pages

    @property
    def before_total(self) -> int:
        return sum(page.before for page in self.pages)

    @property
    def ratio(self) -> float:
        """Measured on the sample: what fraction of the bytes survive."""
        if not self.sample_before:
            return 1.0
        return self.sample_after / self.sample_before

    @property
    def after_total(self) -> int:
        return round(self.before_total * self.ratio)

    @property
    def saved(self) -> int:
        return max(0, self.before_total - self.after_total)

    @property
    def tallest(self) -> int:
        return max((page.height for page in self.pages), default=0)

    @property
    def resizes(self) -> bool:
        """Whether any page is far enough over the cap to resample."""
        return would_resize(self.tallest, self.height)


@dataclass(frozen=True)
class Shrunk:
    path: Path
    before: int
    after: int


@dataclass(frozen=True)
class Kept:
    """A page left alone: re-encoding it would not have helped."""
    path: Path
    before: int
    would_be: int


@dataclass(frozen=True)
class Failed:
    path: Path
    reason: str


def iter_pages(root: Path) -> Iterator[Path]:
    """The images in ``root``, in reading order. One level only: a comic
    folder is a flat run of pages."""
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.is_file() and entry.suffix.lower() in SUFFIXES:
            yield entry


OTHER_MEDIA = {".mp3", ".flac", ".m4a", ".opus", ".wav", ".aac", ".ogg",
               ".mkv", ".mp4", ".m4v", ".avi", ".mov",
               ".epub", ".mobi", ".azw3", ".pdf", ".cbz", ".cbr"}


def probe(root: Path) -> bool:
    """Whether this folder looks like a run of PAGES.

    Three or more images and nothing else that is media. The second half
    is what keeps the button off an album folder, which has a cover.jpg
    in it and is not a comic (todo-6).
    """
    images = 0
    try:
        entries = list(root.iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix in SUFFIXES:
            images += 1
        elif suffix in OTHER_MEDIA:
            return False
    return images >= 3


def _measure(path: Path) -> Page | None:
    from PIL import Image
    try:
        with Image.open(path) as image:
            width, height = image.size
        return Page(path=path, before=path.stat().st_size,
                    width=width, height=height)
    except Exception:
        return None


def _encode(image, quality: int) -> bytes:
    import io
    buffer = io.BytesIO()
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(buffer, "JPEG", quality=quality, subsampling=SUBSAMPLING,
               optimize=True, progressive=True)
    return buffer.getvalue()


def _shrunk_bytes(path: Path, height: int, quality: int) -> bytes:
    """The page as it would be written. Never upscales."""
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        if would_resize(image.height, height):
            width = max(1, round(image.width * height / image.height))
            image = image.resize((width, height), Image.LANCZOS)
        return _encode(image, quality)


def build_plan(paths, height: int = HEIGHT, quality: int = QUALITY,
               sample: int = SAMPLE) -> ShrinkPlan:
    """Plan a shrink of ``paths`` (a folder, or the images themselves).

    Thread-only: it reads every page's header and encodes a few of them.
    """
    paths = [Path(p) for p in (paths if isinstance(paths, (list, tuple))
                               else [paths])]
    root = paths[0] if len(paths) == 1 and paths[0].is_dir() else (
        paths[0].parent if paths else Path("."))
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(iter_pages(path))
        elif path.suffix.lower() in SUFFIXES:
            files.append(path)
    pages = tuple(page for page in (_measure(f) for f in sorted(set(files)))
                  if page is not None)
    if not pages:
        return ShrinkPlan(root=root, pages=(), height=height, quality=quality)

    # the sample: first, middle and last, so a cover and an interior
    # page both count toward the ratio
    picks = sorted({0, len(pages) // 2, len(pages) - 1})[:max(1, sample)]
    before = after = 0
    taken = 0
    for index in picks:
        page = pages[index]
        try:
            data = _shrunk_bytes(page.path, height, quality)
        except Exception:
            continue
        before += page.before
        after += min(len(data), page.before)    # a page that grows is kept
        taken += 1
    return ShrinkPlan(root=root, pages=pages, height=height,
                      quality=quality, sampled=taken,
                      sample_before=before, sample_after=after)


def apply(plan: ShrinkPlan) -> Iterator[Shrunk | Kept | Failed]:
    """Do it, one page at a time, IN PLACE.

    A generator so the caller can report progress and stop; thread-only.
    Each page is written to a temporary file beside itself and renamed
    over the original, so an interrupted run leaves whole pages, never
    half of one. A page that would grow is left untouched — including
    its name, which is what the reader sorts by.
    """
    for page in plan.pages:
        try:
            data = _shrunk_bytes(page.path, plan.height, plan.quality)
        except Exception as error:
            yield Failed(page.path, str(error))
            continue
        if len(data) >= page.before:
            yield Kept(page.path, page.before, len(data))
            continue
        target = page.path.with_suffix(".jpg")
        temporary = page.path.with_name(page.path.name + ".shrinking")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
            if target != page.path:         # .png became .jpg
                page.path.unlink(missing_ok=True)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            yield Failed(page.path, str(error))
            continue
        yield Shrunk(target, page.before, len(data))
