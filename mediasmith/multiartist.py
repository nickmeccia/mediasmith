"""Fix-multi-artist engine: collapse featured/split artist tags to the
album's main artist.

Some sources (deemix, split releases) tag featured artists as extra
values in the artist/albumartist frames, or as one slash-joined string
('Jax Jones/Rebecca Black/sooyeon'). This plans, per album, setting
both tags on every track to the album's main artist.

Evaluated against mediasmith-v1 ``fix-multi-artist`` rather than
ported: v1 treated every slash as a separator, so a legitimately
slashed band name (AC/DC, 156/Silence) would be collapsed to its first
segment; its only mitigation was a manual exclude checkbox in the
preview. v2 adds the folder guard — when the unsplit artist string,
sanitized, matches the album's artist-folder name, the slash is part
of the name and the album is left alone. v1's per-album checkboxes are
replaced by scoping: the action applies to whatever folder it was
invoked on, so excluding an album means invoking on less.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .folderize import iter_audio
from .text import sanitize_component as sanitize

PROBE_BUDGET = 200


@dataclass(frozen=True)
class Change:
    path: Path
    artists: tuple[str, ...]        # old, split
    album_artists: tuple[str, ...]  # old, split


@dataclass(frozen=True)
class Group:
    """One album (folder + album tag) with at least one tangled file."""
    folder: Path
    album: str
    main: str                       # what every track will be set to
    changes: tuple[Change, ...]


@dataclass(frozen=True)
class MultiArtistPlan:
    root: Path
    groups: tuple[Group, ...] = field(default_factory=tuple)

    @property
    def empty(self) -> bool:
        return not self.groups

    @property
    def file_count(self) -> int:
        return sum(len(g.changes) for g in self.groups)


def split_artists(values) -> list[str]:
    """Flatten a tag's value list, splitting slash-joined strings."""
    out: list[str] = []
    for value in values:
        out.extend(part.strip() for part in str(value).split("/")
                   if part.strip())
    return out


def read_file(path: Path):
    """(artists, album_artists, album, raw_artist, raw_album_artist)
    or None if unreadable/untagged."""
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(path), easy=True)
    except Exception:
        return None
    if audio is None or audio.tags is None:
        return None
    raw_artists = [str(v) for v in audio.tags.get("artist", [])]
    raw_album_artists = [str(v) for v in audio.tags.get("albumartist", [])]
    artists = split_artists(raw_artists)
    album_artists = split_artists(raw_album_artists)
    album_values = audio.tags.get("album", [])
    album = str(album_values[0]).strip() if album_values else ""
    if not artists and not album_artists:
        return None
    return artists, album_artists, album, raw_artists, raw_album_artists


def _name_matches_folder(raw_values: list[str], file: Path) -> bool:
    """The slash guard: a single raw value whose sanitized form equals
    the artist-folder name (two levels up) is a band NAME with a slash
    in it, not a multi-artist list."""
    if len(raw_values) != 1:
        return False
    return sanitize(raw_values[0].strip()) == file.parent.parent.name


def is_tangled(artists: list[str], album_artists: list[str],
               raw_artists: list[str], raw_album_artists: list[str],
               file: Path) -> bool:
    if len(artists) <= 1 and len(album_artists) <= 1:
        return False
    if (len(artists) > 1
            and not _name_matches_folder(raw_artists, file)):
        return True
    if (len(album_artists) > 1
            and not _name_matches_folder(raw_album_artists, file)):
        return True
    return False


def build_plan(root: Path) -> MultiArtistPlan:
    """Scan ``root`` and plan the albums that need fixing. Reads tags
    of every audio file beneath it — run in a worker."""
    groups: dict[tuple[Path, str], list] = {}
    for file in sorted(iter_audio(root)):
        info = read_file(file)
        if info is None:
            continue
        artists, album_artists, album, raw_a, raw_aa = info
        groups.setdefault((file.parent, album), []).append(
            (file, artists, album_artists, raw_a, raw_aa))

    plan_groups: list[Group] = []
    for (folder, album), files in sorted(groups.items()):
        if not any(is_tangled(a, aa, ra, raa, f)
                   for f, a, aa, ra, raa in files):
            continue
        # main artist: first album-artist value seen, else first artist
        main = (next((aa[0] for _, _, aa, _, _ in files if aa), None)
                or next(a[0] for _, a, _, _, _ in files if a))
        changes = tuple(
            Change(f, tuple(a), tuple(aa))
            for f, a, aa, _, _ in files
            if a != [main] or aa != [main])
        if changes:
            plan_groups.append(Group(folder=folder, album=album,
                                     main=main, changes=changes))
    return MultiArtistPlan(root=root, groups=tuple(plan_groups))


def probe(root: Path, budget: int = PROBE_BUDGET) -> bool:
    """Whether any file under ``root`` is tangled — the button test."""
    spent = 0
    for file in iter_audio(root, max_dirs=max(budget, 50)):
        if spent >= budget:
            return False
        spent += 1
        info = read_file(file)
        if info is None:
            continue
        artists, album_artists, _, raw_a, raw_aa = info
        if is_tangled(artists, album_artists, raw_a, raw_aa, file):
            return True
    return False


def execute(plan: MultiArtistPlan) -> tuple[int, list[tuple[Path, str]]]:
    """Set artist and albumartist to each group's main artist.
    Returns (fixed, errors)."""
    fixed = 0
    errors: list[tuple[Path, str]] = []
    for group in plan.groups:
        for change in group.changes:
            try:
                from mutagen import File as MutagenFile
                audio = MutagenFile(str(change.path), easy=True)
                audio.tags["artist"] = [group.main]
                audio.tags["albumartist"] = [group.main]
                audio.save()
                fixed += 1
            except Exception as error:
                errors.append((change.path, str(error)))
    return fixed, errors
