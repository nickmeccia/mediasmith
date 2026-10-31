"""Image operations: convert, resize, rotate. Pillow-backed, pure.

House rules (match the rest of the app):
- products land beside the source and never overwrite (FileExistsError);
- rotation is the one in-place edit — it's what Nick means by "rotate";
  JPEG rotation re-encodes (quality 95, noted to the caller via the
  ``lossy`` return) because a lossless-jpeg dep wasn't worth adding
  unasked.
"""

from __future__ import annotations

from pathlib import Path

CONVERT_FORMATS = ("jpg", "png", "webp", "tiff")
"""Offered conversions, in button order. HEIC is out (Pillow can't
write it); AVIF only with a plugin — revisit if Nick asks."""

_PIL_FORMAT = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG",
               "webp": "WEBP", "tiff": "TIFF", "tif": "TIFF",
               "gif": "GIF"}

_NO_ALPHA = {"JPEG"}

_FORMAT_ALIASES = {"jpeg": "jpg", "tif": "tiff"}


def normalize_format(suffix: str) -> str:
    """One name per format, for the convert palette: a ``.jpeg`` file's
    own-format button is ``jpg``."""
    name = suffix.lstrip(".").lower()
    return _FORMAT_ALIASES.get(name, name)


def _open(path: Path):
    from PIL import Image
    return Image.open(path)


def _save_kwargs(img, fmt: str) -> dict:
    kwargs: dict = {}
    exif = img.info.get("exif")
    if exif and fmt in ("JPEG", "WEBP", "TIFF"):
        kwargs["exif"] = exif
    if fmt == "JPEG":
        kwargs["quality"] = 95
    return kwargs


def convert(path: Path, fmt: str, overwrite: bool = False) -> Path:
    """Convert ``path`` to ``fmt`` beside itself. Raises on unknown
    formats, same-format no-ops, and (unless ``overwrite``) existing
    targets."""
    pil_fmt = _PIL_FORMAT.get(fmt.lower())
    if pil_fmt is None:
        raise ValueError(f"no writer for .{fmt}")
    target = path.with_suffix("." + fmt.lower())
    if target == path:
        raise ValueError(f"{path.name} is already .{fmt}")
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target.name} already exists")
    img = _open(path)
    if pil_fmt in _NO_ALPHA and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    img.save(target, format=pil_fmt, **_save_kwargs(img, pil_fmt))
    return target


def fit_dimensions(width: int, height: int, *, new_width: int | None,
                   new_height: int | None) -> tuple[int, int]:
    """Aspect-linked resize math (the UI's "link" checkbox): give one
    dimension, get both. Give both and they pass through (unlinked)."""
    if new_width and new_height:
        return new_width, new_height
    if new_width:
        return new_width, max(1, round(height * new_width / width))
    if new_height:
        return max(1, round(width * new_height / height)), new_height
    return width, height


def resize(path: Path, width: int, height: int,
           overwrite: bool = False) -> Path:
    """Resize to exactly width × height, written beside the source as
    ``name (WxH).ext``. Refuses to overwrite unless ``overwrite``."""
    if width < 1 or height < 1:
        raise ValueError("dimensions must be positive")
    target = path.with_name(f"{path.stem} ({width}x{height}){path.suffix}")
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target.name} already exists")
    img = _open(path)
    fmt = img.format or _PIL_FORMAT.get(path.suffix.lstrip(".").lower())
    resized = img.resize((width, height))
    resized.save(target, format=fmt, **_save_kwargs(img, fmt or ""))
    return target


# -- crop ---------------------------------------------------------------------
# A terminal cannot drag a rectangle, so a crop is said in numbers: how
# much comes off each EDGE. Ratios are offered beside them because the
# crops this app is actually for — album art that is not square, a
# poster with letterboxing, a scanned page with a border — are mostly
# "make it this shape, from the middle" (Nick, todo-6).

CROP_RATIOS: tuple[str, ...] = ("free", "1:1", "4:3", "3:2", "16:9",
                                "3:4", "2:3", "9:16")
"""Offered aspect ratios, in stepper order. ``free`` leaves the edges
alone; the rest recompute them as the largest centred rectangle."""

EDGES = ("left", "top", "right", "bottom")


def parse_ratio(name: str) -> tuple[int, int] | None:
    """(w, h) for a ratio name, or None for ``free``/nonsense."""
    if ":" not in name:
        return None
    try:
        width, height = (int(part) for part in name.split(":", 1))
    except ValueError:
        return None
    return (width, height) if width > 0 and height > 0 else None


def centred_edges(width: int, height: int, ratio: str) -> dict[str, int]:
    """The edges that leave the largest centred rectangle of ``ratio``.

    An odd remainder goes to the right/bottom edge, so the result is
    exactly the ratio rather than a pixel off it.
    """
    parsed = parse_ratio(ratio)
    if parsed is None:
        return {edge: 0 for edge in EDGES}
    want_w, want_h = parsed
    if width * want_h > height * want_w:         # too wide: trim the sides
        keep = max(1, round(height * want_w / want_h))
        spare = width - keep
        return {"left": spare // 2, "right": spare - spare // 2,
                "top": 0, "bottom": 0}
    keep = max(1, round(width * want_h / want_w))  # too tall: trim top/bottom
    spare = height - keep
    return {"left": 0, "right": 0,
            "top": spare // 2, "bottom": spare - spare // 2}


def crop_box(width: int, height: int, edges) -> tuple[int, int, int, int]:
    """PIL's (left, upper, right, lower) for these edge trims.

    Clamped so the box always keeps at least one pixel: a stepper held
    down must stop at the middle, not invert the image.
    """
    left = max(0, min(int(edges.get("left", 0)), width - 1))
    top = max(0, min(int(edges.get("top", 0)), height - 1))
    right = max(0, min(int(edges.get("right", 0)), width - 1 - left))
    bottom = max(0, min(int(edges.get("bottom", 0)), height - 1 - top))
    return left, top, width - right, height - bottom


def crop_size(width: int, height: int, edges) -> tuple[int, int]:
    left, top, right, bottom = crop_box(width, height, edges)
    return right - left, bottom - top


def crop(path: Path, edges, overwrite: bool = False) -> Path:
    """Crop ``path`` by these edge trims, beside the source as
    ``name (cropped).ext``. Refuses to overwrite unless ``overwrite``."""
    target = path.with_name(f"{path.stem} (cropped){path.suffix}")
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target.name} already exists")
    img = _open(path)
    box = crop_box(img.width, img.height, edges)
    if box == (0, 0, img.width, img.height):
        raise ValueError("nothing is being cropped")
    fmt = img.format or _PIL_FORMAT.get(path.suffix.lstrip(".").lower())
    cropped = img.crop(box)
    cropped.save(target, format=fmt, **_save_kwargs(img, fmt or ""))
    return target


def rotate(path: Path, quarter_turns: int = 1) -> tuple[Path, bool]:
    """Rotate clockwise by 90° × ``quarter_turns``, in place. Returns
    (path, lossy) — lossy is True for re-encoded JPEGs."""
    from PIL import Image
    turns = quarter_turns % 4
    if turns == 0:
        return path, False
    img = _open(path)
    fmt = img.format or _PIL_FORMAT.get(path.suffix.lstrip(".").lower())
    transpose = {1: Image.Transpose.ROTATE_270,   # PIL rotates CCW
                 2: Image.Transpose.ROTATE_180,
                 3: Image.Transpose.ROTATE_90}[turns]
    rotated = img.transpose(transpose)
    rotated.save(path, format=fmt, **_save_kwargs(img, fmt or ""))
    return path, fmt == "JPEG"
