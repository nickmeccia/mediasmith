from mediasmith import adapters, kinds


def test_audio_details(media_tree):
    d = adapters.read_details(media_tree / "Music" / "01 Song One.mp3")
    assert isinstance(d, adapters.AudioDetails)
    assert d.fields["title"] == "Song One"
    assert d.fields["artist"] == "The Band"
    assert d.fields["albumartist"] == "The Band"
    assert d.fields["genre"] == ""          # absent tags are empty, not missing
    assert d.size > 0
    assert d.cover is not None and d.cover[:4] == b"\x89PNG"


def test_audio_without_cover(media_tree):
    d = adapters.read_details(media_tree / "Music" / "02 Song Two.mp3")
    assert d.cover is None


def test_video_details(media_tree):
    d = adapters.read_details(
        media_tree / "Movies" / "Alien (1979)" / "Alien.1979.mkv")
    assert isinstance(d, adapters.VideoDetails)
    assert d.subtitle_name == "Alien.1979.srt"
    assert d.poster_name == "poster.jpg"
    assert d.poster_bytes is not None
    assert d.size > 0


def test_book_details(media_tree):
    d = adapters.read_details(media_tree / "Books" / "Dune.epub")
    assert isinstance(d, adapters.BookDetails)
    assert d.fields["title"] == "Dune"
    assert d.fields["author"] == "Frank Herbert"
    assert d.fields["series"] == "Dune"
    assert d.fields["publisher"] == "Chilton Books"
    assert d.cover is not None and d.cover[:4] == b"\x89PNG"


def test_image_details(media_tree):
    d = adapters.read_details(media_tree / "Pics" / "photo.png")
    assert isinstance(d, adapters.ImageDetails)
    assert d.data[:4] == b"\x89PNG"


def test_folder_details(media_tree):
    d = adapters.read_details(media_tree / "Music")
    assert isinstance(d, adapters.FolderDetails)
    assert d.counts[kinds.AUDIO] == 2

    top = adapters.read_details(media_tree)
    assert top.counts[kinds.FOLDER] == 5
    assert top.counts[kinds.OTHER] == 1


def test_other_details(media_tree):
    d = adapters.read_details(media_tree / "notes.txt")
    assert isinstance(d, adapters.OtherDetails)
    assert d.suffix == ".txt"


def test_probe_video_title_survives_junk(media_tree):
    # Fake video: ffprobe (if present) fails, and that must mean None, not a raise.
    title = adapters.probe_video_title(
        media_tree / "Movies" / "Alien (1979)" / "Alien.1979.mkv")
    assert title is None
