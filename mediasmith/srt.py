"""SRT engine: parse, render, clean, shift.

Consolidates mediasmith-v1's ``subtitle-clean-srt`` and
``subtitle-shift-srt``, which each carried their own copy of the same
parser. The cleaning regexes and the edge-cue rule are taken verbatim
from v1 — they're field-tested against real subtitle files; don't
"improve" them without a failing sample in hand.

Pure logic; the UI decides when to read and write files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ARROW_RE = re.compile(
    r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})')

FONT_TAG_RE = re.compile(r'</?font\b[^>]*>', re.IGNORECASE)
ASS_COLOR_RE = re.compile(r'\{\\[1-4]?c(?:&H[0-9A-Fa-f]{2,8}&?)?\}',
                          re.IGNORECASE)

EDGE_CUES = 5
"""Only cues this close to either end of the file are eligible for
credit removal — a URL spoken as dialogue mid-film stays put."""

WATERMARK_RE = re.compile('|'.join([
    r'\bsub(?:title)?s?\s+(?:by|from|downloaded)\b',
    r'\bsync(?:ed)?\s*(?:&|and|/)?\s*correct(?:ed|ions?)?\b',
    r'\b(?:synced|sync|resync(?:ed)?|corrected|encoded|translat(?:ed|ion)'
    r'|transcri(?:bed|ption)|caption(?:s|ed|ing)?|provided|ripped'
    r'|improved|edited)\s+by\b',
    r'opensubtitles', r'addic7ed', r'subscene', r'podnapisi',
    r'tvsubtitles',
    r'\byify\b', r'\byts\b', r'explosiveskull', r'osdb\.link',
    r'www\.', r'https?://', r'\b\w+\.(?:com|org|net|me|tv|link|info)\b',
    r'\bdownloaded\s+from\b', r'\brate\s+this\s+subtitle\b',
    r'\bsupport\s+us\b', r'\badvertise\s+your\s+product\b',
    r'\bplease\s+rate\b', r'\bhelp\s+other\s+users\b',
]), re.IGNORECASE)


def ts_to_ms(ts: str) -> int:
    h, m, s_ms = ts.replace(',', ':').split(':', 2)
    s, ms = s_ms.split(':')
    return (int(h) * 3_600_000 + int(m) * 60_000
            + int(s) * 1_000 + int(ms))


def ms_to_ts(ms: int) -> str:
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


@dataclass(frozen=True)
class Entry:
    start_ms: int
    end_ms: int
    lines: tuple[str, ...]      # text lines only, no timing/index

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def timing_line(self) -> str:
        return f"{ms_to_ts(self.start_ms)} --> {ms_to_ts(self.end_ms)}"


def parse(text: str) -> list[Entry]:
    """Cues from SRT text; malformed blocks are skipped, not fatal."""
    entries: list[Entry] = []
    for block in re.split(r'\n{2,}', text.strip()):
        block_lines = block.strip().splitlines()
        if len(block_lines) < 2:
            continue
        try:
            int(block_lines[0].strip())
        except ValueError:
            continue
        m = ARROW_RE.match(block_lines[1].strip())
        if not m:
            continue
        entries.append(Entry(ts_to_ms(m.group(1)), ts_to_ms(m.group(2)),
                             tuple(block_lines[2:])))
    return entries


def read(path: Path) -> list[Entry]:
    return parse(path.read_text(encoding="utf-8-sig"))


def render(entries: list[Entry]) -> str:
    """SRT text, renumbered from 1."""
    parts = [f"{i}\n{e.timing_line()}\n" + "\n".join(e.lines)
             for i, e in enumerate(entries, 1)]
    return "\n\n".join(parts) + "\n"


def write(entries: list[Entry], path: Path) -> None:
    path.write_text(render(entries), encoding="utf-8")


def shift(entries: list[Entry], delta_ms: int) -> list[Entry]:
    """Shift every cue by ``delta_ms``, clamped at 0. Never drops a
    cue. Always shift from the ORIGINAL parse and rewrite to the total
    (v1's nudge model) so back-and-forth adjustments can't lose cues."""
    return [Entry(max(0, e.start_ms + delta_ms),
                  max(0, e.end_ms + delta_ms), e.lines)
            for e in entries]


def format_shift(ms: int) -> str:
    """0 → ' 0:00.0', 1500 → '+0:01.5', -6000 → '-0:06.0'."""
    sign = '+' if ms > 0 else ('-' if ms < 0 else ' ')
    a = abs(ms)
    minutes, rem = divmod(a, 60_000)
    secs, msec = divmod(rem, 1_000)
    return f"{sign}{minutes}:{secs:02d}.{msec // 100}"


def _strip_color(lines: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    changed = False
    out = []
    for line in lines:
        cleaned = FONT_TAG_RE.sub('', line)
        cleaned = ASS_COLOR_RE.sub('', cleaned)
        if cleaned != line:
            changed = True
        out.append(cleaned)
    return tuple(out), changed


def is_watermark(entry: Entry) -> bool:
    return any(WATERMARK_RE.search(line) for line in entry.lines)


@dataclass(frozen=True)
class CleanResult:
    kept: list[Entry]
    removed: list[Entry]        # credit cues + markup-only husks
    color_stripped: int         # cues whose markup was removed

    @property
    def unchanged(self) -> bool:
        return not self.removed and not self.color_stripped


def clean(entries: list[Entry], *, colors: bool = True,
          credits: bool = True) -> CleanResult:
    """Strip color markup and drop credit "watermark" cues near the
    file's edges."""
    removed: list[Entry] = []
    if credits:
        edge = {i for i in range(len(entries))
                if i < EDGE_CUES or i >= len(entries) - EDGE_CUES}
        kept = []
        for i, e in enumerate(entries):
            (removed if i in edge and is_watermark(e) else kept).append(e)
        entries = kept

    color_count = 0
    if colors:
        cleaned = []
        for e in entries:
            lines, changed = _strip_color(e.lines)
            color_count += changed
            # a cue that was nothing but markup has no reason to stay
            if any(line.strip() for line in lines):
                cleaned.append(Entry(e.start_ms, e.end_ms, lines))
            else:
                removed.append(e)
        entries = cleaned

    return CleanResult(kept=entries, removed=removed,
                       color_stripped=color_count)
