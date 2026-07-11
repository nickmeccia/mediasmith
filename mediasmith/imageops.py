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


def convert(path: Path, fmt: str) -> Path:
    """Convert ``path`` to ``fmt`` beside itself. Raises on unknown
    formats, same-format no-ops, and existing targets."""
    pil_fmt = _PIL_FORMAT.get(fmt.lower())
    if pil_fmt is None:
        raise ValueError(f"no writer for .{fmt}")
    target = path.with_suffix("." + fmt.lower())
    if target == path:
        raise ValueError(f"{path.name} is already .{fmt}")
    if target.exists():
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


def resize(path: Path, width: int, height: int) -> Path:
    """Resize to exactly width × height, written beside the source as
    ``name (WxH).ext``. Never overwrites."""
    if width < 1 or height < 1:
        raise ValueError("dimensions must be positive")
    target = path.with_name(f"{path.stem} ({width}x{height}){path.suffix}")
    if target.exists():
        raise FileExistsError(f"{target.name} already exists")
    img = _open(path)
    fmt = img.format or _PIL_FORMAT.get(path.suffix.lstrip(".").lower())
    resized = img.resize((width, height))
    resized.save(target, format=fmt, **_save_kwargs(img, fmt or ""))
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
