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


def sanitize_component(s: str) -> str:
    """Looser sanitizer for a single path component (keeps more, swaps
    separators for dashes)."""
    s = re.sub(r'[/\\:*?"<>|]', "-", s)
    return s.strip().strip(".") or "_"
