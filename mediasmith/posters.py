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
    ``~/Downloads/Mediasmith/<Film (Year)>/`` for hand curation.

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
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, NamedTuple, Union

from . import fs, kinds
from .text import sanitize_filename

USER_AGENT = "mediasmith/0.1"

TMDB = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/"
THUMB_SIZE = "w185"      # small render used only for de-duplication hashing
DEDUP_HAMMING = 5        # dhash distance ≤ this ⇒ "the same poster"

STAGING_DIR = Path.home() / "Downloads" / "Mediasmith"
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


_EDGE_DASHES = re.compile(r"^[\s\-\u2010-\u2015_\u00b7]+"
                          r"|[\s\-\u2010-\u2015_\u00b7]+$")
"""Dashes and separators guessit leaves stranded at a title's edge."""


def clean_title(title: str) -> str:
    """Trim separator debris off a guessed title.

    ``2017 — Ghost In The Shell`` guesses as ``— Ghost In The Shell``:
    guessit takes the year off the front and hands back the em dash that
    joined them (Nick, 2026-08-22). Only leading/trailing dashes, spaces
    and interpuncts go — a title's own punctuation ("Airplane!") stays.
    """
    return _EDGE_DASHES.sub("", title) or title


class Guess(NamedTuple):
    """What the title ladder made of a video."""

    title: str
    year: int | None
    source: str
    """The raw string this came from — kept because guessit can take a
    year off a title that CONTAINS one ("2001 A Space Odyssey" parses as
    "A Space Odyssey" + 2001), and then only the raw string finds the
    film. ``_search`` uses it as a last query and as a second yardstick
    for scoring."""


def resolve_query(video: Path,
                  container_title: str | None = None) -> Guess:
    """Best-effort (title, year, source): the container's embedded title
    tag, then the filename, then the folder name — first candidate
    guessit gives a year for wins (v1's ladder).

    ``type="movie"`` is pinned: without it guessit reads a numeric title
    suffix as season/episode ("Blade Runner 2049" → S20E49, "Ocean's 11"
    → episode 11) and hands back a truncated title (Nick, 2026-08-22).
    Posters are only ever fetched for films here.
    """
    from guessit import guessit
    candidates = [c for c in (container_title, video.stem, video.parent.name)
                  if c]
    fallback: Guess | None = None
    for candidate in candidates:
        try:
            guess = guessit(candidate, {"type": "movie"})
        except Exception:
            continue
        title = guess.get("title")
        if not title:
            continue
        title = clean_title(str(title))
        if not title:
            continue
        year = guess.get("year")
        if year:
            return Guess(title, int(year), candidate)
        if fallback is None:
            fallback = Guess(title, None, candidate)
    return fallback or Guess(video.stem, None, video.stem)


def resolve_title_year(video: Path,
                       container_title: str | None = None
                       ) -> tuple[str, int | None]:
    """``resolve_query`` without the source — the shape v1 had."""
    guess = resolve_query(video, container_title)
    return guess.title, guess.year


def target_folder(video: Path, label: str) -> Path:
    """Local video → a poster folder beside it; network volume → the
    staging folder (QA note: '/Volumes' is the network heuristic)."""
    name = sanitize_filename(label)
    if video.parts[:2] == ("/", "Volumes"):
        return STAGING_DIR / name
    return video.parent / name


POSTER_FOLDER_BUDGET = 8
"""How many sibling directories ``find_poster`` may list before giving
up on rule 2. The read happens on the debounce, not in a worker (it is
normally one cached listing), so a video parked in a folder of fifty
subdirectories must not stall the pane on SMB — folderize's PROBE_BUDGET
bargain: a false negative beats a NAS meltdown. The directory named
after the video is always looked at first, so the budget only ever costs
the image-only guess."""


def image_only_folder(folder: Path) -> bool:
    """A folder of nothing but images — what ``run`` leaves behind, and
    the shape that identifies a poster folder under a title that isn't
    the video's filename. Empty or mixed folders say no."""
    try:
        entries = fs.list_dir(folder)
    except OSError:
        return False
    images = 0
    for entry in entries:
        if entry.name.startswith("."):          # .DS_Store and friends
            continue
        if entry.is_dir:
            return False
        if Path(entry.name).suffix.lower() not in kinds.IMAGE_EXTENSIONS:
            return False
        images += 1
    return images > 0


def _first_image(folder: Path) -> Path | None:
    try:
        entries = fs.list_dir(folder)
    except OSError:
        return None
    return next((folder / e.name for e in entries
                 if not e.is_dir and not e.name.startswith(".")
                 and Path(e.name).suffix.lower() in kinds.IMAGE_EXTENSIONS),
                None)


def find_poster(video: Path) -> Path | None:
    """The poster the details pane shows for ``video`` — the read half of
    ``target_folder``. A preference ladder, cached listings only (NAS
    rule), most specific first:

    1. ``<video stem>.jpg`` beside the video — art named for the file;
    2. a poster folder: a sibling directory named after the video, or —
       when this is the folder's ONLY video, so the folder is about this
       one film — any image-only sibling directory (``run`` names its
       folder after TMDB's title, not after the file);
    3. a loose sibling image, again only when this is the only video
       here; in a folder of many videos a stray image belongs to no one
       in particular, so nothing shows.
    """
    parent = video.parent
    try:
        entries = fs.list_dir(parent)
    except OSError:
        return None
    stem = video.stem.lower()
    sole = sum(1 for e in entries
               if not e.is_dir
               and Path(e.name).suffix.lower() in kinds.VIDEO_EXTENSIONS) == 1

    folders: list[Path] = []
    loose: list[Path] = []
    for entry in entries:
        path = parent / entry.name
        if entry.is_dir:
            if entry.name.lower() == stem:
                folders.insert(0, path)             # named for the video
            elif sole:
                folders.append(path)
            continue
        if Path(entry.name).suffix.lower() not in kinds.IMAGE_EXTENSIONS:
            continue
        if path.stem.lower() == stem:
            return path                             # 1: the video's own art
        loose.append(path)

    for folder in folders[:POSTER_FOLDER_BUDGET]:   # 2: a poster folder
        if folder.name.lower() == stem or image_only_folder(folder):
            image = _first_image(folder)
            if image is not None:
                return image

    return loose[0] if sole and loose else None     # 3: loose art


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


def _normalize(text: str) -> str:
    """Titles compared the way a human would: case, punctuation and
    spacing folded away ("Ghost in the Shell" == "ghost.in.the.shell")."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _title_grade(candidate: str, wanted: frozenset[str]) -> int:
    """2 = the same title, 1 = one contains the other, 0 = unrelated."""
    name = _normalize(candidate)
    if name in wanted:
        return 2
    if any(w and (w in name or name in w) for w in wanted):
        return 1
    return 0


def _score(movie: dict, wanted: frozenset[str], year: int | None) -> tuple:
    """Rank one search result: how well the title matches, then the year,
    then TMDB's popularity. Popularity alone picks the famous film over
    the right one; the year alone picks a documentary that happens to
    share it (see ``_search``)."""
    released = (movie.get("release_date") or "")[:4]
    return (_title_grade(movie.get("title") or "", wanted),
            year is not None and released == str(year),
            float(movie.get("popularity") or 0.0))


def _search(fetch: Fetch, key: str, title: str, year: int | None,
            source: str | None = None) -> dict | None:
    """The movie ``title`` (+``year``) names — not the one TMDB ranks first.

    Three corrections, all from one miss (Nick, 2026-08-22:
    ``Ghost.in.the.Shell.2017…`` fetched the 1995 anime's posters):

    1. TMDB's ``year`` matches ANY release date a film carries, so the
       1995 anime — which had a 2017 re-release — comes back for
       year=2017. ``primary_release_year`` is the ORIGINAL release and
       is the parameter that disambiguates. It is tried first, then the
       broad ``year`` (for a film whose TMDB primary date disagrees with
       the release name), then no year at all.
    2. ``results[0]`` is popularity order, which fails the same way: the
       1995 film outranks the 2017 one on the same query. Results are
       scored, not taken off the top.
    3. The narrowest query is not always the best one. "2001 A Space
       Odyssey" parses as title "A Space Odyssey" + year 2001, and
       ``primary_release_year=2001`` answers with three NASA
       documentaries — a non-empty result set of the wrong film. So
       every attempt is scored into ONE pool rather than the first
       non-empty one winning, and the raw filename joins the queries.

    Attempts stop early on an exact title with a matching year: the
    ordinary case costs one request, and only a genuinely ambiguous
    name pays for the rest.
    """
    def query(text: str, extra: dict) -> list[dict]:
        params = {"api_key": key, "query": text, "include_adult": "true",
                  **extra}
        return _get_json(fetch, f"{TMDB}/search/movie",
                         params).get("results", [])

    attempts: list[tuple[str, dict]] = []
    if year:
        attempts.append((title, {"primary_release_year": year}))
        attempts.append((title, {"year": year}))
    attempts.append((title, {}))
    wanted = {_normalize(title)}
    if source and _normalize(source) not in wanted:
        # the year may be part of the title, not a year at all
        attempts.append((source, {}))
        wanted.add(_normalize(source))
    frozen = frozenset(wanted)

    best: dict | None = None
    best_score: tuple | None = None
    for text, extra in attempts:
        try:
            results = query(text, extra)
        except OSError:
            if best is not None:
                break               # keep what we already found
            raise
        for movie in results:
            score = _score(movie, frozen, year)
            if best_score is None or score > best_score:
                best, best_score = movie, score
        if best_score is not None and best_score[0] == 2 and best_score[1]:
            break                   # exact title AND year: nothing beats it
    return best


def run(video: Path, *, fetch: Fetch = default_fetch,
        api_key: str | None = None,
        container_title: str | None = None,
        dedup: bool = True) -> Iterator[Event]:
    key = api_key or resolve_api_key()
    if not key:
        yield Failed(API_KEY_HELP)
        return

    title, year, source = resolve_query(video, container_title)
    label = title + (f" ({year})" if year else "")

    yield PhaseStarted(f"searching TheMovieDB for {label}…")
    try:
        movie = _search(fetch, key, title, year, source)
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

    # English or textless — keep iso_639_1 == "en" plus language-neutral
    # key art (iso_639_1 == null); other languages are dropped.
    posters = [p for p in posters if p.get("iso_639_1") in ("en", None)]
    if not posters:
        yield Failed(f"no English posters available for {label}")
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
