"""Subtitle download + sync engine (the v1 flagship, ported).

A faithful port of mediasmith-v1's ``lib/engines/subtitle_sync.py``. The
timing policy in here was tuned against ground truth (Nick watching real
playback — see the v1 DEBUG_NOTES.md beside the old CLI); **do not change
it casually**:

  - an exact file-hash match is installed untouched (already timed to
    this encode — alass is not allowed to touch it);
  - otherwise alass syncs the sub: a correction ≤ ``ALASS_CLAMP_MS`` is
    applied silently; a larger one is still applied (a big *constant*
    offset is normal for transcodes — different intros) but flagged for
    review, unless ``safe=True``, which rejects large shifts and keeps
    the original timing.

Selection is a targeted lookup, not a bake-off: recover the release name
from the file's embedded container 'title' tag (survives renaming), ask
OpenSubtitles — and, only if that misses, every provider — for the
single best match, and download just that one.

Contract for frontends:
  - ``run()`` is a generator that performs the work and yields Event
    dataclasses; blocking work (network, alass) happens *inside* it,
    between yields. Run it on a worker thread if your UI must stay live.
  - A ``PhaseStarted`` event marks the start of a slow step; it is over
    when the next event arrives — that is the hook for spinners.
  - Events never require a response; the input is entirely up-front.
  - The engine itself is network-honest; the ``MEDIASMITH_OFFLINE``
    guard belongs in the UI handler (artfetch pattern), before run()
    is ever created.

Testing without the network (proven in v1): monkeypatch
``download_best`` / ``read_release_name`` / ``alass_correction_ms`` /
``import_subliminal`` on this module and drive ``run()`` directly —
see tests/test_subsync.py.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Union

from . import container, kinds

VIDEO_EXTENSIONS = kinds.VIDEO_EXTENSIONS
SUBTITLE_EXTENSIONS = kinds.SUBTITLE_SUFFIXES
WATERMARK_PHRASES = ['UKsubtitles', 'MemoryOnSmells', 'Addic7ed.com']

# Provider strategy: OpenSubtitles first (best coverage + exact file-hash
# lookup), then widen to all providers only if it comes up empty.
PROVIDER_TIERS = (("OpenSubtitles", ['opensubtitles']), ("all providers", None))

# Corrections up to this are applied silently (reliable). Larger ones are
# still applied but flagged for review — unless safe=True, which rejects them.
ALASS_CLAMP_MS = 2000


# ─────────────────────────────────────────────────────────────────────────────
# Events — everything a frontend can be told
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FileResult:
    """Final verdict for one video. ``category`` drives styling:
    'ok' (trustworthy), 'check' (installed, eyeball the sync),
    'missing' (nothing installed), 'skip' (already had a subtitle)."""
    video: Path
    rel: Path                 # video path relative to its run root
    category: str
    status: str               # short human description of what happened
    installed: str | None     # filename installed beside the video, or None


@dataclass(frozen=True)
class DirStarted:
    directory: Path
    root: Path                # rel paths and the summary tree hang off this


@dataclass(frozen=True)
class DirMissing:
    directory: Path


@dataclass(frozen=True)
class DirScanned:
    count: int


@dataclass(frozen=True)
class FileStarted:
    video: Path
    rel: Path


@dataclass(frozen=True)
class ReleaseFound:
    release: str


@dataclass(frozen=True)
class PhaseStarted:
    """A slow, blocking step has begun (network search, alass). It ends when
    the next event arrives — animate a spinner until then."""
    label: str


@dataclass(frozen=True)
class Note:
    """An informational line about the current file (weak match, score…)."""
    text: str


@dataclass(frozen=True)
class FileDone:
    result: FileResult


@dataclass(frozen=True)
class Counts:
    installed: int = 0
    skipped: int = 0
    failed: int = 0

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.installed + other.installed,
                      self.skipped + other.skipped,
                      self.failed + other.failed)


@dataclass(frozen=True)
class DirDone:
    root: Path
    counts: Counts
    results: tuple[FileResult, ...]


@dataclass(frozen=True)
class RunDone:
    totals: Counts
    # (root, results) per target directory, for the end-of-run summary trees
    trees: tuple[tuple[Path, tuple[FileResult, ...]], ...]


Event = Union[DirStarted, DirMissing, DirScanned, FileStarted, ReleaseFound,
              PhaseStarted, Note, FileDone, DirDone, RunDone]


# ─────────────────────────────────────────────────────────────────────────────
# subliminal (a real dependency — see the note below)
# ─────────────────────────────────────────────────────────────────────────────
#
# This used to hunt for a Homebrew keg under /opt/homebrew/Cellar/subliminal
# and splice it in with site.addsitedir. subliminal is a pure-Python package
# that pip-installs cleanly, so it is a plain dependency now and the whole
# discovery apparatus is gone — with it went the .pth indirection that made a
# missing certifi read as "subliminal not found" (2026-08-22).
#
# import_subliminal() survives as the TEST SEAM, not as discovery: the engine
# takes its subliminal callables through this one bag so tests can monkeypatch
# it (tests/test_subsync.py) and drive run() with no network.


class _Subliminal:
    """A small bag of the subliminal/babelfish callables this engine uses."""
    __slots__ = ("scan_video", "download_best_subtitles", "Video",
                 "compute_score", "Language")


def import_subliminal() -> "_Subliminal":
    from babelfish import Language
    from subliminal import (Video, compute_score, download_best_subtitles,
                            scan_video)
    s = _Subliminal()
    s.scan_video, s.download_best_subtitles = scan_video, download_best_subtitles
    s.Video, s.compute_score, s.Language = Video, compute_score, Language
    return s


def check_requirements() -> list[str]:
    """Return a list of problems (empty = good to go). Never exits or prints."""
    problems = []
    if not shutil.which('alass-cli'):
        problems.append("Missing tool: alass-cli — install with: brew install alass")
    try:
        import_subliminal()
    except ImportError as error:
        # subliminal ships with mediasmith now, so this is a broken install
        # (or a frozen build missing its entry-point metadata), not a
        # missing brew formula — say what actually failed.
        problems.append(f"subliminal could not be imported — {error}")
    return problems


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────

def find_videos(target: Path) -> list[Path]:
    """A single video file → just it. A folder → every video under it (recursive)."""
    if target.is_file():
        return [target] if target.suffix.lower() in VIDEO_EXTENSIONS else []
    videos = []
    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for f in sorted(files):
            if Path(f).suffix.lower() in VIDEO_EXTENSIONS:
                videos.append(Path(root) / f)
    return videos


def find_subtitle(video_path: Path) -> Path | None:
    base = str(video_path.with_suffix(''))
    for ext in SUBTITLE_EXTENSIONS:
        sub = Path(base + ext)
        if sub.exists():
            return sub
    return None


def is_watermarked(content: bytes) -> bool:
    try:
        text = content.decode('utf-8', errors='replace')
        return any(phrase in text for phrase in WATERMARK_PHRASES)
    except Exception:
        return False


def first_timestamp_ms(path: Path) -> int | None:
    try:
        for line in path.read_text(errors='replace').splitlines():
            if '-->' in line:
                m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', line.strip())
                if m:
                    h, mi, s, ms = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                    return h * 3_600_000 + mi * 60_000 + s * 1_000 + ms
    except Exception:
        pass
    return None


def subtitle_ext(content: bytes) -> str | None:
    """Detect the subtitle format from its bytes: 'srt', 'ass', or None if unknown."""
    if not content:
        return None
    raw = content[3:] if content[:3] == b'\xef\xbb\xbf' else content
    head = raw.lstrip()[:1]
    if head.isdigit():        # SRT begins with a cue index
        return 'srt'
    if head == b'[':          # ASS/SSA begins with [Script Info]
        return 'ass'
    return None


def _confident(matches: set) -> bool:
    """A match is trustworthy if it nailed the exact file, the movie title, or the series."""
    return bool(matches & {'hash', 'title', 'series'})


def _sub_label(sub) -> str:
    return str(getattr(sub, 'filename', None) or getattr(sub, 'release', None) or sub.id)


def build_tree(root: Path, results: tuple[FileResult, ...] | list[FileResult]) -> dict:
    """Nest results by directory for the summary tree: dirs are dicts,
    leaves are FileResults. Frontends render this however they like."""
    tree: dict = {}
    for r in results:
        try:
            parts = r.video.relative_to(root).parts
        except ValueError:
            parts = (r.video.name,)
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = r
    return tree


# ─────────────────────────────────────────────────────────────────────────────
# External probes (monkeypatch these to test the policy without IO)
# ─────────────────────────────────────────────────────────────────────────────

def read_release_name(video_path: Path) -> str | None:
    """
    Return the release name stored in the file's container 'title' tag
    (e.g. 'Aliens.1986.SE.1080p.BluRay.x265-RARBG'), which survives renaming
    the file. This is the release info VLC shows in its title bar. Read from
    the container header directly (``container.read_title``) — no ffprobe;
    returns None if the format is unhandled or the file is untagged.
    """
    title = container.read_title(video_path)
    if not title:
        return None
    # Only treat it as a release if it actually looks like one (has a year or a
    # source/quality token), not a human-friendly "Aliens" display title.
    if re.search(r"\b(19|20)\d{2}\b|\b(1080p|720p|2160p|BluRay|WEB[- ]?DL|WEBRip|HDTV|BDRip|x264|x265|HEVC)\b",
                 title, re.IGNORECASE):
        return title
    return None


def alass_correction_ms(video_path: Path, subtitle_path: Path, out_path: Path) -> int | None:
    """Run alass, return the absolute correction applied (ms), or None on failure."""
    before = first_timestamp_ms(subtitle_path)
    if before is None:
        return None
    result = subprocess.run(
        ['alass-cli', str(video_path), str(subtitle_path), str(out_path)],
        capture_output=True
    )
    if result.returncode != 0:
        return None
    after = first_timestamp_ms(out_path)
    if after is None:
        return None
    return abs(after - before)


def download_best(S: "_Subliminal", video, providers):
    """Ask subliminal for the single best subtitle, downloading only that one."""
    kwargs = {'only_one': True}
    if providers is not None:
        kwargs['providers'] = providers
    res = S.download_best_subtitles({video}, {S.Language('eng')}, **kwargs)
    subs = res.get(video, [])
    return subs[0] if subs else None


# ─────────────────────────────────────────────────────────────────────────────
# Selection + timing policy
# ─────────────────────────────────────────────────────────────────────────────

# guessit-derived attributes that subliminal scores releases on.
_RELEASE_ATTRS = ("title", "year", "season", "episode", "source",
                  "resolution", "release_group", "video_codec", "audio_codec")


def _scan_with_release(video_path: Path, S: "_Subliminal"):
    """
    Build the subliminal Video for matching. Start from the real file (so its
    hashes/size stay correct for exact hash matches), then overlay the release
    attributes parsed from the container's embedded title — which survives
    renaming and is where the real release info (group/source/resolution/year)
    lives. ``Video.name`` is read-only, so we overlay attributes rather than
    rebuilding the object.
    """
    video = S.scan_video(str(video_path))
    release = read_release_name(video_path)
    if not release:
        return video, None
    try:
        rel = S.Video.fromname(release)        # rich release attrs via guessit
    except Exception:
        return video, release
    for attr in _RELEASE_ATTRS:
        val = getattr(rel, attr, None)
        if val and hasattr(video, attr):
            try:
                setattr(video, attr, val)
            except AttributeError:
                pass                            # skip any read-only attribute
    return video, release


@dataclass
class _Outcome:
    """Result of trying to get a subtitle for one video."""
    path: Path | None   # temp file to install, or None if nothing usable
    status: str
    category: str       # 'ok' | 'check' | 'missing'


def _best_subtitle_events(video_path: Path, S: "_Subliminal", tmpdir: Path,
                          safe: bool) -> Iterator[Event]:
    """Generator version of the lookup: yields progress events, *returns* the
    :class:`_Outcome` (retrieve it via ``yield from``). Policy is documented
    in the module docstring — tuned, don't tweak."""
    try:
        video, release = _scan_with_release(video_path, S)
    except Exception as e:
        return _Outcome(None, f"scan failed: {e}", 'missing')
    if release:
        yield ReleaseFound(release)

    sub, matches = None, set()
    for tier_label, providers in PROVIDER_TIERS:
        yield PhaseStarted(f"searching {tier_label}…")
        try:
            cand = download_best(S, video, providers)
        except Exception as e:
            yield Note(f"{tier_label}: search failed — {e}")
            continue
        if cand is None:
            continue
        try:
            cand_matches = cand.get_matches(video)
        except Exception:
            cand_matches = set()
        if _confident(cand_matches):
            sub, matches = cand, cand_matches
            break
        yield Note(f"{tier_label}: only a weak match — widening search")

    search = f"no match — search: {release}" if release else "no subtitle match found"
    if sub is None:
        return _Outcome(None, search, 'missing')

    content = sub.content
    if not content or is_watermarked(content):
        return _Outcome(None, f"best match unusable (watermarked); {search}", 'missing')
    ext = subtitle_ext(content)
    if ext is None:
        return _Outcome(None, f"best match unsupported format; {search}", 'missing')

    try:
        score = S.compute_score(sub, video)
    except Exception:
        score = 0
    label = _sub_label(sub)
    src = tmpdir / f"candidate.{ext}"
    src.write_bytes(content)
    yield Note(f"match (score={score}): {label[:60]}")

    # Exact same file → the sub is already timed to it; don't let alass touch it.
    if 'hash' in matches:
        return _Outcome(src, "no sync needed (exact file match)", 'ok')

    # alass can only sync SRT; an .ass release match is installed as-is.
    if ext != 'srt':
        return _Outcome(src, f"can't sync .{ext} — original timing kept", 'check')

    out = tmpdir / "synced.srt"
    yield PhaseStarted("syncing with alass…")
    corr = alass_correction_ms(video_path, src, out)
    if corr is None:
        return _Outcome(src, "alass couldn't sync — original timing kept", 'check')
    if corr <= ALASS_CLAMP_MS:
        return _Outcome(out, f"synced (+{corr}ms)", 'ok')
    if safe:
        return _Outcome(src, f"large shift {corr}ms rejected (safe) — original kept", 'check')
    return _Outcome(out, f"synced (+{corr}ms) — large shift, verify", 'check')


# ─────────────────────────────────────────────────────────────────────────────
# The run
# ─────────────────────────────────────────────────────────────────────────────

def _file_events(video: Path, rel: Path, S: "_Subliminal",
                 force: bool, safe: bool) -> Iterator[Event]:
    """Process one video; yields events, returns its FileResult."""
    if not force and find_subtitle(video):
        return FileResult(video, rel, 'skip', "already had a subtitle", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        outcome = yield from _best_subtitle_events(video, S, Path(tmpdir), safe)

        if outcome.path is None:
            return FileResult(video, rel, 'missing', outcome.status, None)

        # Name the subtitle exactly like the video so VLC auto-loads it:
        # Aliens.mp4 -> Aliens.srt  (or .ass, matching the downloaded format).
        dest = video.with_suffix(outcome.path.suffix)
        try:
            shutil.copy2(outcome.path, dest)
            return FileResult(video, rel, outcome.category, outcome.status, dest.name)
        except Exception as e:
            return FileResult(video, rel, 'missing', f"install failed: {e}", None)


def run(targets: list[str | Path], *, force: bool = False,
        safe: bool = False) -> Iterator[Event]:
    """
    Process every target (video files, or folders searched recursively) and
    yield events. ``force`` re-fetches over existing sibling subtitles;
    ``safe`` rejects large alass shifts instead of flag-and-apply.
    """
    S = import_subliminal()

    totals = Counts()
    trees: list[tuple[Path, tuple[FileResult, ...]]] = []

    for target in targets:
        directory = Path(target)
        if not directory.exists():
            yield DirMissing(directory)
            continue

        # Accept a single file or a folder. Tree/relative paths hang off root.
        root = directory.parent if directory.is_file() else directory
        yield DirStarted(directory, root)

        videos = find_videos(directory)
        yield DirScanned(len(videos))

        results: list[FileResult] = []
        for video in videos:
            rel = video.relative_to(root)
            yield FileStarted(video, rel)
            result = yield from _file_events(video, rel, S, force, safe)
            results.append(result)
            yield FileDone(result)

        counts = Counts(
            installed=sum(1 for r in results if r.category in ('ok', 'check')),
            skipped=sum(1 for r in results if r.category == 'skip'),
            failed=sum(1 for r in results if r.category == 'missing'),
        )
        totals += counts
        trees.append((root, tuple(results)))
        yield DirDone(root, counts, tuple(results))

    yield RunDone(totals, tuple(trees))
