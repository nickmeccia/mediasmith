import pytest

from mediasmith import adapters, kinds

from .mediafactory import make_epub


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
    assert d.fields["author sort"] == ""      # absent → empty, fillable
    assert d.fields["series number"] == ""
    assert d.cover is not None and d.cover[:4] == b"\x89PNG"


def test_book_author_sort_and_series_number_read(tmp_path):
    path = make_epub(tmp_path / "Dune.epub", author_sort="Herbert, Frank",
                     series_index="1")
    d = adapters.read_details(path)
    assert d.fields["author sort"] == "Herbert, Frank"
    assert d.fields["series number"] == "1"


def test_write_book_author_sort_and_series_number_roundtrip(media_tree):
    # media_tree's Dune.epub has neither: exercises the add-missing path
    # (creator gains opf:file-as, series_index meta gets inserted).
    path = media_tree / "Books" / "Dune.epub"
    adapters.write_details(path, {"author sort": "Herbert, Frank",
                                  "series number": "3"})
    d = adapters.read_details(path)
    assert d.fields["author sort"] == "Herbert, Frank"
    assert d.fields["series number"] == "3"
    assert d.fields["author"] == "Frank Herbert"     # text untouched
    # clearing removes them again
    adapters.write_details(path, {"author sort": "", "series number": ""})
    d = adapters.read_details(path)
    assert d.fields["author sort"] == ""
    assert d.fields["series number"] == ""


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
    # Fake video: the container parser fails, and that must mean None, not a raise.
    title = adapters.probe_video_title(
        media_tree / "Movies" / "Alien (1979)" / "Alien.1979.mkv")
    assert title is None


# -- write half ---------------------------------------------------------------


def test_audio_reads_all_tags_present(media_tree):
    from mutagen.easyid3 import EasyID3
    path = media_tree / "Music" / "01 Song One.mp3"
    easy = EasyID3(str(path))
    easy["bpm"] = "120"                     # not in AUDIO_FIELDS
    easy.save()
    d = adapters.read_details(path)
    assert list(d.fields)[:len(adapters.AUDIO_FIELDS)] == adapters.AUDIO_FIELDS
    assert d.fields["bpm"] == "120"


def test_write_audio_tags_roundtrip(media_tree):
    path = media_tree / "Music" / "01 Song One.mp3"
    adapters.write_details(path, {"title": "Renamed Song", "genre": "Rock",
                                  "artist": ""})
    d = adapters.read_details(path)
    assert d.fields["title"] == "Renamed Song"
    assert d.fields["genre"] == "Rock"
    assert d.fields["artist"] == ""         # emptied tag is removed


def test_write_book_metadata_roundtrip(media_tree):
    path = media_tree / "Books" / "Dune.epub"
    adapters.write_details(path, {"title": "Dune Messiah", "series": "Dune 2",
                                  "publisher": "", "language": "fr"})
    d = adapters.read_details(path)
    assert d.fields["title"] == "Dune Messiah"
    assert d.fields["series"] == "Dune 2"
    assert d.fields["publisher"] == ""
    assert d.fields["language"] == "fr"
    assert d.fields["author"] == "Frank Herbert"     # untouched
    assert d.cover is not None                       # zip survived the rewrite


def test_write_book_adds_missing_element(media_tree):
    path = make_epub(media_tree / "Books" / "bare.epub", series=None)
    adapters.write_details(path, {"series": "New Series"})
    d = adapters.read_details(path)
    assert d.fields["series"] == "New Series"


def test_write_escapes_markup(media_tree):
    path = media_tree / "Books" / "Dune.epub"
    adapters.write_details(path, {"title": 'A & B <"C">'})
    d = adapters.read_details(path)
    assert d.fields["title"] == 'A & B <"C">'


def test_rename(media_tree):
    path = media_tree / "Music" / "01 Song One.mp3"
    new = adapters.rename(path, "01 First Song.mp3")
    assert new == path.with_name("01 First Song.mp3")
    assert new.exists() and not path.exists()
    assert adapters.rename(new, new.name) == new     # same name: no-op
    with pytest.raises(ValueError):
        adapters.rename(new, "")
    with pytest.raises(ValueError):
        adapters.rename(new, "a/b.mp3")
    with pytest.raises(FileExistsError):
        adapters.rename(new, "02 Song Two.mp3")


def test_can_write(media_tree):
    assert adapters.can_write(media_tree / "Music" / "01 Song One.mp3")
    assert adapters.can_write(media_tree / "Books" / "Dune.epub")
    assert not adapters.can_write(media_tree / "notes.txt")
    assert not adapters.can_write(media_tree / "Books")


def test_save_details_writes_then_renames(media_tree):
    path = media_tree / "Music" / "02 Song Two.mp3"
    new = adapters.save_details(path, "02 Second Song.mp3",
                                {"title": "Second Song"})
    assert new.name == "02 Second Song.mp3" and new.exists()
    assert adapters.read_details(new).fields["title"] == "Second Song"


def test_write_cover_roundtrip(media_tree):
    from .mediafactory import make_png
    path = media_tree / "Music" / "02 Song Two.mp3"   # starts coverless
    art = make_png(color=(10, 200, 10))
    adapters.write_cover(path, art)
    assert adapters.cover_bytes(path) == art
    art2 = make_png(color=(10, 10, 200))              # replace, not append
    adapters.write_cover(path, art2)
    assert adapters.cover_bytes(path) == art2
    from mutagen.id3 import ID3
    assert len(ID3(str(path)).getall("APIC")) == 1


def test_write_cover_rejects_unknown_kind(media_tree):
    with pytest.raises(ValueError):
        adapters.write_cover(media_tree / "notes.txt", b"\xff\xd8\xffdata")


def test_save_details_with_art(media_tree):
    from .mediafactory import make_png
    path = media_tree / "Music" / "02 Song Two.mp3"
    art = make_png(color=(1, 2, 3))
    new = adapters.save_details(path, "02 Art.mp3", {"title": "Arted"},
                                art=art)
    assert new.name == "02 Art.mp3"
    assert adapters.cover_bytes(new) == art
    assert adapters.read_details(new).fields["title"] == "Arted"


# -- bulk ----------------------------------------------------------------------


def test_read_bulk_merges_and_marks_mixed(media_tree):
    music = media_tree / "Music"
    paths = [music / "01 Song One.mp3", music / "02 Song Two.mp3"]
    bulk = adapters.read_bulk(paths)
    assert bulk.kind == kinds.AUDIO
    assert bulk.fields["artist"] == "The Band"       # unanimous
    assert "artist" not in bulk.mixed
    assert bulk.fields["title"] == ""                # divergent
    assert "title" in bulk.mixed
    assert bulk.fields["albumartist"] == ""          # set on one file only
    assert "albumartist" in bulk.mixed
    assert bulk.cover is None and bulk.cover_mixed   # one has art, one hasn't
    assert bulk.size > 0


def test_save_bulk_applies_and_reports_failures(media_tree, monkeypatch):
    music = media_tree / "Music"
    paths = [music / "01 Song One.mp3", music / "02 Song Two.mp3"]
    errors = adapters.save_bulk(paths, {"album": "Bulk Album"})
    assert errors == []
    for p in paths:
        assert adapters.read_details(p).fields["album"] == "Bulk Album"

    real = adapters.write_details
    def flaky(path, fields):
        if "Two" in path.name:
            raise ValueError("boom")
        real(path, fields)
    monkeypatch.setattr(adapters, "write_details", flaky)
    errors = adapters.save_bulk(paths, {"genre": "Rock"})
    assert len(errors) == 1 and "Two" in errors[0][0].name
    assert adapters.read_details(paths[0]).fields["genre"] == "Rock"


def test_bulk_paths_for_folder(media_tree):
    music = media_tree / "Music"
    paths = adapters.bulk_paths_for_folder(music)
    assert paths is not None and len(paths) == 2     # album-like: qualifies
    (music / "cover.jpg").write_bytes(b"x")          # unwritable files ignored
    import mediasmith.fs as fs
    fs.clear_cache()
    assert len(adapters.bulk_paths_for_folder(music)) == 2
    assert adapters.bulk_paths_for_folder(media_tree) is None      # has subdirs
    assert adapters.bulk_paths_for_folder(media_tree / "Pics") is None  # no writables
    assert adapters.bulk_paths_for_folder(media_tree / "Empty") is None


def test_bulk_paths_rejects_mixed_kinds(media_tree):
    from .mediafactory import make_epub
    music = media_tree / "Music"
    make_epub(music / "notes.epub")
    import mediasmith.fs as fs
    fs.clear_cache()
    assert adapters.bulk_paths_for_folder(music) is None


# -- cover extraction + metadata.opf ------------------------------------------


def _jpeg_bytes() -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_extract_cover_writes_png_sibling(tmp_path):
    from .mediafactory import make_png
    cover = make_png()
    book = make_epub(tmp_path / "Dune.epub", cover=cover)
    target = adapters.extract_cover(book)
    assert target == tmp_path / "cover.png"          # named for its real format
    assert target.read_bytes() == cover


def test_extract_cover_names_jpeg_jpg(tmp_path):
    cover = _jpeg_bytes()
    book = make_epub(tmp_path / "Dune.epub", cover=cover)
    assert adapters.extract_cover(book) == tmp_path / "cover.jpg"


def test_extract_cover_without_cover_raises(tmp_path):
    book = make_epub(tmp_path / "Plain.epub", cover=None)
    with pytest.raises(ValueError, match="no embedded cover"):
        adapters.extract_cover(book)


def test_extract_cover_never_overwrites(tmp_path):
    from .mediafactory import make_png
    book = make_epub(tmp_path / "Dune.epub", cover=make_png())
    existing = tmp_path / "cover.png"
    existing.write_bytes(b"precious")
    with pytest.raises(FileExistsError):
        adapters.extract_cover(book)
    assert existing.read_bytes() == b"precious"


def test_create_opf_from_book_metadata(tmp_path):
    book = make_epub(tmp_path / "Dune.epub")
    target = adapters.create_opf(book)
    assert target == tmp_path / "metadata.opf"
    text = target.read_text()
    assert "<dc:title>Dune</dc:title>" in text
    assert 'opf:file-as="Herbert, Frank"' in text
    assert ">Frank Herbert</dc:creator>" in text
    assert 'name="calibre:series" content="Dune"' in text
    assert "<dc:publisher>Chilton Books</dc:publisher>" in text
    # the spurious-index bug fix-series-meta existed to clean up:
    # no series → no series meta at all, and never an index of 0
    assert 'series_index" content="0"' not in text


def test_create_opf_without_series(tmp_path):
    book = make_epub(tmp_path / "Solo.epub", title="Solo",
                     author="Plainname", series=None)
    text = adapters.create_opf(book).read_text()
    assert "calibre:series" not in text
    assert 'opf:file-as="Plainname"' in text         # single word: unchanged


def test_create_opf_never_overwrites(tmp_path):
    book = make_epub(tmp_path / "Dune.epub")
    existing = tmp_path / "metadata.opf"
    existing.write_text("precious")
    with pytest.raises(FileExistsError):
        adapters.create_opf(book)
    assert existing.read_text() == "precious"


def test_create_folder_finds_a_free_name(tmp_path):
    first = adapters.create_folder(tmp_path)
    assert first == tmp_path / "untitled folder" and first.is_dir()
    second = adapters.create_folder(tmp_path)
    assert second == tmp_path / "untitled folder 2" and second.is_dir()
    third = adapters.create_folder(tmp_path)
    assert third == tmp_path / "untitled folder 3" and third.is_dir()
