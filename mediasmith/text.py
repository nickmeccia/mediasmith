"""Small text helpers shared across engines. Ported from
mediasmith-v1 ``smithkit.text`` (the parts v2 actually uses)."""

from __future__ import annotations

import re

_FS_ILLEGAL = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def infer_author_sort(author: str) -> str:
    """'First Last' → 'Last, First'; pass-through if already sorted or a
    single token."""
    author = author.strip()
    if not author or "," in author:
        return author
    parts = author.split()
    if len(parts) < 2:
        return author
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def sanitize_filename(s: str, max_len: int = 120) -> str:
    """Strip filesystem-illegal characters and collapse whitespace."""
    s = _FS_ILLEGAL.sub("", s)
    s = re.sub(r"\s+", " ", s).strip().strip(".")
    return (s[:max_len].strip() or "_")


def series_index_2d(raw) -> str | None:
    """A calibre series index as a two-digit-padded string ("1" → "01",
    "2.5" → "02.5"), or None when it isn't numeric — so a book without a
    real position isn't sorted as "00"."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value == int(value):
        return f"{int(value):02d}"
    return f"{value:04.1f}"          # 2.5 → "02.5", 10.5 → "10.5"


def compose_book_name(author_sort: str, title: str, series: str | None = None,
                      series_index=None) -> str:
    """The library name a book earns — the ONE source of truth for the
    shelf convention (Nick's spec, 2026-08-07). A book in a series with a
    numeric index gets "Author Sort - Series - NN - Title" (NN two-digit),
    so the shelf sorts by author, then series, then reading order; any
    other book gets "Author Sort - Title". Both sort (folder + file names)
    and the omnibus splitter (its output files) route through here."""
    idx = series_index_2d(series_index)
    if series and idx:
        stem = f"{author_sort} - {series} - {idx} - {title}"
    else:
        stem = f"{author_sort} - {title}"
    return sanitize_filename(stem)


def sanitize_component(s: str) -> str:
    """Looser sanitizer for a single path component (keeps more, swaps
    separators for dashes)."""
    s = re.sub(r'[/\\:*?"<>|]', "-", s)
    return s.strip().strip(".") or "_"
