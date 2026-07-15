"""Poster fetch engine: TheMovieDB posters for one video file.

Ported from mediasmith-v1 ``tools/videosmith/download-posters`` with the
CLI shed: requests → urllib (artfetch house style), prints → events, and
the recursive folder walk dropped (the UI invokes per video). The parts
that carry tuned judgment survive intact — the title/year resolution
ladder (container tag → filename → folder name, first candidate with a
year wins) and the dhash near-duplicate collapse (fingerprint cheap
thumbnails, keep the highest-resolution copy, Hamming ≤ 5 ⇒ same poster).

Where the files land (Nick's local/network split):
  - local volume  → beside the video, in its own folder;
  - network volume (under /Volumes) → a staging folder
    ``~/Downloads/Videosmith/<Film (Year)>/`` for hand curation.

Contract for frontends (the subsync pattern):
  - ``run()`` is a generator that performs the work and yields Event
    dataclasses; blocking work (network) happens inside it, between
    yields. Run it on a worker thread.
  - Every network read goes through one injectable ``fetch(url) ->
    bytes`` seam — tests fake TMDB with a dict of canned responses.
  - The ``MEDIASMITH_OFFLINE`` guard belongs in the UI handler
    (artfetch pattern), before run() is ever created.
"""

from __future__ import annotations

import io
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Union

from .text import sanitize_filename

USER_AGENT = "mediasmith/0.1"

TMDB = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/"
THUMB_SIZE = "w185"      # small render used only for de-duplication hashing
DEDUP_HAMMING = 5        # dhash distance ≤ this ⇒ "the same poster"

STAGING_DIR = Path.home() / "Downloads" / "Videosmith"
"""Network-volume videos stage here (never write posters to the NAS
unreviewed); local videos take posters straight into their own folder."""

API_KEY_HELP = (
    "No TheMovieDB API key found.\n"
    "1. Create a free account at https://www.themoviedb.org/\n"
    "2. Settings → API → request a key → copy the \"API Key (v3 auth)\"\n"
    "3. export TMDB_API_KEY=…  or  save it to "
    "~/.config/mediasmith/tmdb_api_key"
)


# ─────────────────────────────────────────────────────────────────────────────
# Events — everything a frontend can be told
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Identified:
    """The film the video resolved to (TMDB's canonical name once
    matched): "Alien (1979)"."""
    label: str


@dataclass(frozen=True)
class PhaseStarted:
    """A slow step begins; it is over when the next event arrives."""
    label: str


@dataclass(frozen=True)
class Progress:
    """One unit of a counted phase ('fingerprinting' | 'downloading')."""
    phase: str
    done: int
    total: int


@dataclass(frozen=True)
class Done:
    folder: Path
    saved: int
    duplicates: int          # near-duplicates never downloaded
    existing: int            # refused overwrites (file already there)


@dataclass(frozen=True)
class Failed:
    """Terminal: nothing was (or will be) downloaded."""
    reason: str


Event = Union[Identified, PhaseStarted, Progress, Done, Failed]

Fetch = Callable[[str], bytes]


# ─────────────────────────────────────────────────────────────────────────────
# Pieces (each independently testable)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_api_key() -> str | None:
    key = os.environ.get("TMDB_API_KEY", "").strip()
    if key:
        return key
    cfg = Path.home() / ".config" / "mediasmith" / "tmdb_api_key"
    if cfg.is_file():
        return cfg.read_text(encoding="utf-8").strip() or None
    return None


def default_fetch(url: str) -> bytes:
    """One network read. May raise OSError (urllib wraps HTTP errors)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def resolve_title_year(video: Path,
                       container_title: str | None = None
                       ) -> tuple[str, int | None]:
    """Best-effort (title, year): the container's embedded title tag,
    then the filename, then the folder name — first candidate guessit
    gives a year for wins (v1's ladder, verbatim)."""
    from guessit import guessit
    candidates = [c for c in (container_title, video.stem, video.parent.name)
                  if c]
    fallback: tuple[str, int | None] | None = None
    for candidate in candidates:
        try:
            guess = guessit(candidate)
        except Exception:
            continue
        title = guess.get("title")
        if not title:
            continue
        year = guess.get("year")
        if year:
            return str(title), int(year)
        if fallback is None:
            fallback = (str(title), None)
    return fallback or (video.stem, None)


def target_folder(video: Path, label: str) -> Path:
    """Local video → a poster folder beside it; network volume → the
    staging folder (QA note: '/Volumes' is the network heuristic)."""
    name = sanitize_filename(label)
    if video.parts[:2] == ("/", "Volumes"):
        return STAGING_DIR / name
    return video.parent / name


def dhash(data: bytes, size: int = 8) -> int | None:
    """64-bit difference hash of an image; None if it can't be read."""
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(data)).convert("L").resize((size + 1,
                                                                size))
    except Exception:
        return None
    px = list(img.getdata())
    bits = 0
    for row in range(size):
        base = row * (size + 1)
        for col in range(size):
            bits = (bits << 1) | (1 if px[base + col] > px[base + col + 1]
                                  else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ─────────────────────────────────────────────────────────────────────────────
# The run
# ─────────────────────────────────────────────────────────────────────────────

def _get_json(fetch: Fetch, url: str, params: dict) -> dict:
    return json.loads(fetch(url + "?" + urllib.parse.urlencode(params)))


def _search(fetch: Fetch, key: str, title: str,
            year: int | None) -> dict | None:
    """Top movie hit for title (+year), retrying without the year."""
    def query(with_year: bool) -> list[dict]:
        params = {"api_key": key, "query": title, "include_adult": "true"}
        if with_year and year:
            params["year"] = year
        return _get_json(fetch, f"{TMDB}/search/movie",
                         params).get("results", [])

    results = query(with_year=True)
    if not results and year:
        results = query(with_year=False)
    return results[0] if results else None


def run(video: Path, *, fetch: Fetch = default_fetch,
        api_key: str | None = None,
        container_title: str | None = None,
        dedup: bool = True) -> Iterator[Event]:
    key = api_key or resolve_api_key()
    if not key:
        yield Failed(API_KEY_HELP)
        return

    title, year = resolve_title_year(video, container_title)
    label = title + (f" ({year})" if year else "")

    yield PhaseStarted(f"searching TheMovieDB for {label}…")
    try:
        movie = _search(fetch, key, title, year)
    except OSError as error:
        yield Failed(f"search failed: {error}")
        return
    if not movie:
        yield Failed(f"no TheMovieDB match for {label}")
        return

    canon_title = movie.get("title") or title
    canon_year = (movie.get("release_date") or "")[:4] or (str(year)
                                                           if year else "")
    label = canon_title + (f" ({canon_year})" if canon_year else "")
    yield Identified(label)

    try:
        posters = _get_json(fetch, f"{TMDB}/movie/{movie['id']}/images",
                            {"api_key": key}).get("posters", [])
    except OSError as error:
        yield Failed(f"image lookup failed: {error}")
        return
    if not posters:
        yield Failed(f"no posters available for {label}")
        return

    # highest resolution first, so dedup keeps the best copy of each look
    posters.sort(key=lambda p: p.get("width", 0) * p.get("height", 0),
                 reverse=True)

    duplicates = 0
    if dedup:
        yield PhaseStarted(f"fingerprinting {len(posters)} posters…")
        kept: list[dict] = []
        hashes: list[int] = []
        for i, poster in enumerate(posters, 1):
            try:
                thumb = fetch(IMG_BASE + THUMB_SIZE + poster["file_path"])
            except OSError:
                thumb = None
            fingerprint = dhash(thumb) if thumb else None
            if fingerprint is not None and any(
                    hamming(fingerprint, h) <= DEDUP_HAMMING for h in hashes):
                duplicates += 1
                continue
            if fingerprint is not None:
                hashes.append(fingerprint)
            kept.append(poster)
            yield Progress("fingerprinting", i, len(posters))
        posters = kept

    folder = target_folder(video, label)
    folder.mkdir(parents=True, exist_ok=True)

    yield PhaseStarted(f"downloading {len(posters)} posters…")
    saved = existing = 0
    for i, poster in enumerate(posters, 1):
        target = folder / Path(poster["file_path"]).name
        if target.exists():                     # refuse-overwrite, per file
            existing += 1
            continue
        try:
            data = fetch(IMG_BASE + "original" + poster["file_path"])
        except OSError:
            continue
        target.write_bytes(data)
        saved += 1
        yield Progress("downloading", i, len(posters))

    yield Done(folder=folder, saved=saved, duplicates=duplicates,
               existing=existing)
