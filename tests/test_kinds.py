from pathlib import Path

from mediasmith import kinds


def test_kinds_by_extension():
    assert kinds.kind_of(Path("a.mp3"), is_dir=False) == kinds.AUDIO
    assert kinds.kind_of(Path("a.FLAC"), is_dir=False) == kinds.AUDIO
    assert kinds.kind_of(Path("a.mkv"), is_dir=False) == kinds.VIDEO
    assert kinds.kind_of(Path("a.epub"), is_dir=False) == kinds.BOOK
    assert kinds.kind_of(Path("a.png"), is_dir=False) == kinds.IMAGE
    assert kinds.kind_of(Path("a.txt"), is_dir=False) == kinds.OTHER
    assert kinds.kind_of(Path("no_extension"), is_dir=False) == kinds.OTHER


def test_folder_beats_extension():
    # A directory named like a file is still a folder.
    assert kinds.kind_of(Path("weird.mp3"), is_dir=True) == kinds.FOLDER


def test_is_dir_from_filesystem(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    f = tmp_path / "f.mp3"
    f.write_bytes(b"")
    assert kinds.kind_of(d) == kinds.FOLDER
    assert kinds.kind_of(f) == kinds.AUDIO
