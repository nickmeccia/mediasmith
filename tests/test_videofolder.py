"""Video folderize: wrap a video (and its companions) into its own folder."""

from mediasmith import fs, videofolder
from tests.mediafactory import make_png


def make_video(path, data=b"not a real video"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    fs.clear_cache()
    return path


def test_wrap_dir_is_the_filename_without_its_extension(tmp_path):
    video = make_video(tmp_path / "Alien (1979).mkv")
    assert videofolder.wrap_dir(video) == tmp_path / "Alien (1979)"
    assert videofolder.wrapped_path(video) == \
        tmp_path / "Alien (1979)" / "Alien (1979).mkv"


def test_probe_is_false_for_a_video_already_in_its_own_folder(tmp_path):
    video = make_video(tmp_path / "Alien (1979)" / "Alien (1979).mkv")
    assert videofolder.probe(video) is False


def test_probe_is_true_when_the_folder_is_named_something_else(tmp_path):
    video = make_video(tmp_path / "Movies" / "Alien (1979).mkv")
    assert videofolder.probe(video) is True


def test_probe_ignores_non_videos(tmp_path):
    assert videofolder.probe(make_video(tmp_path / "notes.txt")) is False


def test_execute_moves_the_video_into_a_folder_named_after_it(tmp_path):
    video = make_video(tmp_path / "Alien.1979.mkv")
    landed, moved, errors = videofolder.execute(video)
    assert errors == []
    assert moved == 1
    assert landed == tmp_path / "Alien.1979" / "Alien.1979.mkv"
    assert landed.exists() and not video.exists()


def test_subtitles_ride_along(tmp_path):
    video = make_video(tmp_path / "Movies" / "Alien.1979.mkv")
    srt = video.with_suffix(".en.srt")
    srt.write_text("1\n")
    (video.parent / "Other.mkv").write_bytes(b"x")   # keeps it a multi-video dir
    (video.parent / "unrelated.srt").write_text("1\n")
    fs.clear_cache()
    landed, moved, errors = videofolder.execute(video)
    assert errors == []
    assert (landed.parent / "Alien.1979.en.srt").exists()
    assert (video.parent / "unrelated.srt").exists()  # not this film's
    assert moved == 2


def test_sole_video_takes_its_art_with_it(tmp_path):
    video = make_video(tmp_path / "Movies" / "Alien.1979.mkv")
    make_png(video.parent / "poster.jpg")            # loose art
    art = video.parent / "Alien (1979)"              # a poster folder
    art.mkdir()
    make_png(art / "a.png")
    notes = video.parent / "Notes"                   # not art: left behind
    notes.mkdir()
    (notes / "read.txt").write_text("x")
    fs.clear_cache()
    landed, moved, errors = videofolder.execute(video)
    assert errors == []
    assert (landed.parent / "poster.jpg").exists()
    assert (landed.parent / "Alien (1979)" / "a.png").exists()
    assert notes.exists()                            # stayed put
    assert moved == 3


def test_art_stays_put_when_the_folder_holds_several_videos(tmp_path):
    video = make_video(tmp_path / "Movies" / "Alien.1979.mkv")
    (video.parent / "Aliens.1986.mkv").write_bytes(b"x")
    make_png(video.parent / "poster.jpg")
    fs.clear_cache()
    landed, moved, errors = videofolder.execute(video)
    assert errors == []
    assert moved == 1                                # the video alone
    assert (video.parent / "poster.jpg").exists()


def test_an_existing_folder_named_after_the_video_is_reused(tmp_path):
    video = make_video(tmp_path / "Movies" / "Alien.1979.mkv")
    wrapper = video.parent / "Alien.1979"            # e.g. an old poster folder
    wrapper.mkdir()
    make_png(wrapper / "a.png")
    fs.clear_cache()
    landed, moved, errors = videofolder.execute(video)
    assert errors == []
    assert landed == wrapper / "Alien.1979.mkv"      # moved in, never into itself
    assert (wrapper / "a.png").exists()


def test_execute_refuses_to_overwrite(tmp_path):
    video = make_video(tmp_path / "Movies" / "Alien.1979.mkv", b"new")
    wrapper = video.parent / "Alien.1979"
    wrapper.mkdir()
    (wrapper / "Alien.1979.mkv").write_bytes(b"precious")
    fs.clear_cache()
    landed, moved, errors = videofolder.execute(video)
    assert moved == 0
    assert landed == video                           # nothing moved
    assert (wrapper / "Alien.1979.mkv").read_bytes() == b"precious"
    assert len(errors) == 1
