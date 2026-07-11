"""Fix-multi-artist engine: tangle detection, the AC/DC guard, plans."""

from pathlib import Path

from mediasmith import multiartist
from tests.mediafactory import make_mp3


def _album(root: Path, artist_dir: str, album_dir: str, tracks) -> Path:
    folder = root / artist_dir / album_dir
    folder.mkdir(parents=True, exist_ok=True)
    for name, tags in tracks:
        make_mp3(folder / name, tags=tags)
    return folder


def test_slash_joined_artist_is_tangled(tmp_path):
    _album(tmp_path, "Jax Jones", "Singles", [
        ("01 a.mp3", {"title": "a", "album": "Singles",
                      "artist": "Jax Jones/Rebecca Black/sooyeon",
                      "albumartist": "Jax Jones"}),
    ])
    plan = multiartist.build_plan(tmp_path)
    assert len(plan.groups) == 1
    group = plan.groups[0]
    assert group.main == "Jax Jones"
    assert group.changes[0].artists == ("Jax Jones", "Rebecca Black",
                                        "sooyeon")


def test_slashed_band_name_matching_folder_is_left_alone(tmp_path):
    # the AC/DC guard: sanitized artist string == artist folder name
    _album(tmp_path, "AC-DC", "Highway to Hell", [
        ("01 a.mp3", {"title": "a", "album": "Highway to Hell",
                      "artist": "AC/DC", "albumartist": "AC/DC"}),
    ])
    assert multiartist.build_plan(tmp_path).empty
    assert multiartist.probe(tmp_path) is False


def test_slashed_name_without_matching_folder_is_tangled(tmp_path):
    # same tags, dumped loose: no folder evidence → treated as multi
    _album(tmp_path, "Downloads", "mixed", [
        ("01 a.mp3", {"title": "a", "album": "Highway to Hell",
                      "artist": "AC/DC", "albumartist": "AC/DC"}),
    ])
    plan = multiartist.build_plan(tmp_path)
    assert len(plan.groups) == 1
    assert plan.groups[0].main == "AC"     # the known cost of no evidence


def test_main_artist_prefers_album_artist(tmp_path):
    _album(tmp_path, "X", "Split EP", [
        ("01 a.mp3", {"title": "a", "album": "Split EP",
                      "artist": "Band A/Band B", "albumartist": "Band A"}),
        ("02 b.mp3", {"title": "b", "album": "Split EP",
                      "artist": "Band B", "albumartist": "Band A"}),
    ])
    plan = multiartist.build_plan(tmp_path)
    group = plan.groups[0]
    assert group.main == "Band A"
    # track 2 is single-artist but wrong: still changed to main
    assert {c.path.name for c in group.changes} == {"01 a.mp3", "02 b.mp3"}


def test_clean_album_plans_nothing(tmp_path):
    _album(tmp_path, "The Band", "Alpha", [
        ("01 a.mp3", {"title": "a", "album": "Alpha",
                      "artist": "The Band", "albumartist": "The Band"}),
    ])
    assert multiartist.build_plan(tmp_path).empty
    assert multiartist.probe(tmp_path) is False


def test_execute_rewrites_both_tags(tmp_path):
    folder = _album(tmp_path, "Jax Jones", "Singles", [
        ("01 a.mp3", {"title": "a", "album": "Singles",
                      "artist": "Jax Jones/Rebecca Black",
                      "albumartist": "Jax Jones"}),
    ])
    plan = multiartist.build_plan(tmp_path)
    fixed, errors = multiartist.execute(plan)
    assert (fixed, errors) == (1, [])
    from mutagen import File as MutagenFile
    audio = MutagenFile(str(folder / "01 a.mp3"), easy=True)
    assert audio.tags["artist"] == ["Jax Jones"]
    assert audio.tags["albumartist"] == ["Jax Jones"]
    # second pass: nothing left
    assert multiartist.build_plan(tmp_path).empty


def test_probe_respects_budget(tmp_path):
    _album(tmp_path, "Jax Jones", "Singles", [
        ("01 a.mp3", {"title": "a", "album": "Singles",
                      "artist": "A/B", "albumartist": "A"}),
    ])
    assert multiartist.probe(tmp_path) is True
    assert multiartist.probe(tmp_path, budget=0) is False
