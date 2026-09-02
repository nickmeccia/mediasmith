"""Poster engine tests: canned TMDB responses in, files + events out.

No network anywhere: every test injects ``fetch`` as a dict lookup of
URL → bytes (the engine's one seam)."""

import io
import json
import urllib.parse
from pathlib import Path

import pytest
from PIL import Image

from mediasmith import posters


# -- fixtures ---------------------------------------------------------------


def png(color, size=(30, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def poster_entry(path: str, width=1000, height=1500, lang="en") -> dict:
    return {"file_path": path, "width": width, "height": height,
            "iso_639_1": lang}


class FakeTMDB:
    """fetch(url) backed by canned responses; records every URL."""

    def __init__(self, responses: dict[str, bytes]):
        self.responses = responses
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if url not in self.responses:
            raise OSError(f"unexpected URL: {url}")
        return self.responses[url]


def search_url(**params) -> str:
    return (f"{posters.TMDB}/search/movie?"
            + urllib.parse.urlencode(params))


def images_url(movie_id: int, key: str) -> str:
    return f"{posters.TMDB}/movie/{movie_id}/images?api_key={key}"


def make_tmdb(movie: dict, poster_entries: list[dict],
              images: dict[str, bytes], key="k",
              query="Alien", year=1979) -> FakeTMDB:
    responses = {
        # the FIRST attempt _search makes (see its docstring): the
        # original release year, not the broad `year`
        search_url(api_key=key, query=query, include_adult="true",
                   primary_release_year=year):
            json.dumps({"results": [movie]}).encode(),
        images_url(movie["id"], key):
            json.dumps({"posters": poster_entries}).encode(),
    }
    for file_path, data in images.items():
        responses[posters.IMG_BASE + posters.THUMB_SIZE + file_path] = data
        responses[posters.IMG_BASE + "original" + file_path] = data
    return FakeTMDB(responses)


ALIEN = {"id": 42, "title": "Alien", "release_date": "1979-05-25"}


# -- title/year resolution ----------------------------------------------------


def test_resolve_prefers_container_title(tmp_path):
    video = tmp_path / "movie file.mkv"
    assert posters.resolve_title_year(
        video, "Alien.1979.1080p.BluRay") == ("Alien", 1979)


def test_resolve_falls_back_to_filename(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    assert posters.resolve_title_year(video, None) == ("Alien", 1979)


def test_resolve_folder_name_supplies_the_year(tmp_path):
    # the filename yields a bare title; the folder candidate has the year
    video = tmp_path / "Alien (1979)" / "movie.mkv"
    title, year = posters.resolve_title_year(video, None)
    assert (title, year) == ("Alien", 1979)


def test_resolve_trims_a_stranded_separator(tmp_path):
    """Nick's naming, 2026-08-22: "<year> — <title>". guessit takes the
    year off the front and leaves the em dash welded to the title."""
    video = tmp_path / "2017 — Ghost In The Shell.mp4"
    assert posters.resolve_title_year(video, None) == (
        "Ghost In The Shell", 2017)


def test_clean_title_keeps_a_titles_own_punctuation():
    assert posters.clean_title("Airplane!") == "Airplane!"
    assert posters.clean_title("WALL·E") == "WALL·E"
    assert posters.clean_title("— Ghost —") == "Ghost"


def test_resolve_keeps_a_numeric_title_suffix(tmp_path):
    """Unpinned, guessit reads "2049" as season 20 episode 49 and hands
    back "Blade Runner"; type="movie" keeps the whole title."""
    video = tmp_path / "Blade Runner 2049.mkv"
    assert posters.resolve_title_year(video, None) == ("Blade Runner 2049",
                                                       None)


def test_resolve_query_reports_the_source_it_used(tmp_path):
    video = tmp_path / "movie file.mkv"
    guess = posters.resolve_query(video, "Alien.1979.1080p.BluRay")
    assert guess == ("Alien", 1979, "Alien.1979.1080p.BluRay")


# -- picking the right film out of the search results ------------------------


def hit(title, year, popularity=1.0, id=1) -> dict:
    return {"id": id, "title": title, "release_date": f"{year}-01-01",
            "popularity": popularity}


def test_search_asks_for_the_primary_release_year_first():
    """TMDB's `year` matches ANY release date, so a re-released classic
    answers for the remake's year (Nick, 2026-08-22: Ghost in the Shell
    2017 fetched the 1995 anime). `primary_release_year` does not."""
    remake = hit("Ghost in the Shell", 2017, popularity=18.2)
    tmdb = FakeTMDB({
        search_url(api_key="k", query="Ghost in the Shell",
                   include_adult="true", primary_release_year=2017):
            json.dumps({"results": [remake]}).encode(),
    })
    assert posters._search(tmdb, "k", "Ghost in the Shell", 2017) == remake
    assert len(tmdb.urls) == 1          # exact title + year: no more asking


def test_search_prefers_the_matching_year_over_the_popular_film():
    """Same query, both films back: TMDB ranks the 1995 anime first."""
    anime = hit("Ghost in the Shell", 1995, popularity=18.13, id=1)
    remake = hit("Ghost in the Shell", 2017, popularity=18.26, id=2)
    tmdb = FakeTMDB({
        search_url(api_key="k", query="Ghost in the Shell",
                   include_adult="true", primary_release_year=2017):
            json.dumps({"results": [anime, remake]}).encode(),
    })
    assert posters._search(tmdb, "k", "Ghost in the Shell", 2017) == remake


def test_search_looks_past_a_wrong_but_non_empty_first_answer():
    """"2001 A Space Odyssey" parses as title "A Space Odyssey" + year
    2001, and primary_release_year=2001 answers with documentaries that
    happen to share the year. Every attempt is scored into one pool, and
    the raw filename is the last query."""
    docs = [hit("NASA: A Space Odyssey Vol. 3", 2001, popularity=0.6)]
    film = hit("2001: A Space Odyssey", 1968, popularity=23.6, id=9)
    tmdb = FakeTMDB({
        search_url(api_key="k", query="A Space Odyssey",
                   include_adult="true", primary_release_year=2001):
            json.dumps({"results": docs}).encode(),
        search_url(api_key="k", query="A Space Odyssey",
                   include_adult="true", year=2001):
            json.dumps({"results": docs}).encode(),
        search_url(api_key="k", query="A Space Odyssey",
                   include_adult="true"):
            json.dumps({"results": docs}).encode(),
        search_url(api_key="k", query="2001 A Space Odyssey",
                   include_adult="true"):
            json.dumps({"results": [film]}).encode(),
    })
    assert posters._search(tmdb, "k", "A Space Odyssey", 2001,
                           "2001 A Space Odyssey") == film


def test_search_keeps_an_earlier_hit_when_a_later_query_fails():
    good = hit("Alien", 1979, popularity=26.7)
    tmdb = FakeTMDB({
        search_url(api_key="k", query="Alien", include_adult="true",
                   primary_release_year=1979):
            json.dumps({"results": [good]}).encode(),
    })
    # only the first attempt is canned; an exact title + year stops there
    assert posters._search(tmdb, "k", "Alien", 1979, "Alien.1979") == good


def test_title_grade_ranks_exact_over_contained_over_unrelated():
    wanted = frozenset({"ghost in the shell"})
    assert posters._title_grade("Ghost.in.the.Shell", wanted) == 2
    assert posters._title_grade("Ghost in the Shell 2: Innocence",
                                wanted) == 1
    assert posters._title_grade("Akira", wanted) == 0


# -- target folder rule -------------------------------------------------------


def test_local_video_targets_its_own_folder(tmp_path):
    video = tmp_path / "Movies" / "Alien.mkv"
    assert (posters.target_folder(video, "Alien (1979)")
            == video.parent / "Alien (1979)")


def test_network_video_targets_the_staging_folder():
    video = Path("/Volumes/NAS/VIDEO/Alien/Alien.mkv")
    assert (posters.target_folder(video, "Alien (1979)")
            == posters.STAGING_DIR / "Alien (1979)")


def test_target_folder_sanitizes_the_label(tmp_path):
    video = tmp_path / "x.mkv"
    folder = posters.target_folder(video, 'Alien: Director "Cut" (1979)')
    assert "/" not in folder.name and ":" not in folder.name


# -- dhash dedup ---------------------------------------------------------------


def test_dhash_close_for_resizes_far_for_different_art():
    art = Image.new("L", (64, 64))
    art.putdata([(x * 4 + y) % 256 for y in range(64) for x in range(64)])
    buf_full, buf_small = io.BytesIO(), io.BytesIO()
    art.save(buf_full, format="PNG")
    art.resize((32, 32)).save(buf_small, format="PNG")
    a = posters.dhash(buf_full.getvalue())
    b = posters.dhash(buf_small.getvalue())
    other = Image.new("L", (64, 64))
    other.putdata([(y * 7 - x * 3) % 256 for y in range(64)
                   for x in range(64)])
    buf_other = io.BytesIO()
    other.save(buf_other, format="PNG")
    c = posters.dhash(buf_other.getvalue())
    assert posters.hamming(a, b) <= posters.DEDUP_HAMMING
    assert posters.hamming(a, c) > posters.DEDUP_HAMMING


def test_dhash_unreadable_bytes_is_none():
    assert posters.dhash(b"not an image") is None


# -- run() ---------------------------------------------------------------------


def drain(events):
    events = list(events)
    return events, events[-1]


def test_run_happy_path_saves_posters(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    # a solid color dhashes to ~0; give the second image a falling ramp
    # (mostly-ones hash) so the pair reads as two distinct posters
    ramp = Image.new("L", (64, 64))
    ramp.putdata([(y * 7 - x * 3) % 256 for y in range(64)
                  for x in range(64)])
    buf = io.BytesIO()
    ramp.save(buf, format="PNG")
    images = {"/a.png": png("red"), "/b.png": buf.getvalue()}
    tmdb = make_tmdb(ALIEN, [poster_entry("/a.png"), poster_entry("/b.png")],
                     images)
    events, last = drain(posters.run(video, fetch=tmdb, api_key="k"))
    assert isinstance(last, posters.Done)
    assert last.saved == 2 and last.duplicates == 0 and last.existing == 0
    assert last.folder == tmp_path / "Alien (1979)"
    assert (last.folder / "a.png").read_bytes() == images["/a.png"]
    assert (last.folder / "b.png").exists()
    labels = [e.label for e in events if isinstance(e, posters.Identified)]
    assert labels == ["Alien (1979)"]


def test_run_keeps_english_and_textless_drops_other_languages(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    # three visually distinct images so dedup keeps them all
    def ramp(mul, sub):
        art = Image.new("L", (64, 64))
        art.putdata([(y * mul - x * sub) % 256 for y in range(64)
                     for x in range(64)])
        buf = io.BytesIO()
        art.save(buf, format="PNG")
        return buf.getvalue()
    entries = [poster_entry("/en.png", lang="en"),
               poster_entry("/none.png", lang=None),
               poster_entry("/fr.png", lang="fr")]
    images = {"/en.png": png("red"), "/none.png": ramp(7, 3),
              "/fr.png": ramp(5, 11)}
    tmdb = make_tmdb(ALIEN, entries, images)
    _, last = drain(posters.run(video, fetch=tmdb, api_key="k"))
    assert isinstance(last, posters.Done) and last.saved == 2
    assert (last.folder / "en.png").exists()
    assert (last.folder / "none.png").exists()       # textless key art kept
    assert not (last.folder / "fr.png").exists()      # other language dropped


def test_run_no_english_posters_fails(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    tmdb = make_tmdb(ALIEN, [poster_entry("/fr.png", lang="fr")],
                     {"/fr.png": png("green")})
    _, last = drain(posters.run(video, fetch=tmdb, api_key="k"))
    assert isinstance(last, posters.Failed)
    assert "no English posters" in last.reason


def test_run_collapses_near_duplicates(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    # same art twice (the second a lower-resolution copy) + one distinct
    art = Image.new("L", (64, 64))
    art.putdata([(x * 4 + y) % 256 for y in range(64) for x in range(64)])
    big, small = io.BytesIO(), io.BytesIO()
    art.save(big, format="PNG")
    art.resize((32, 32)).save(small, format="PNG")
    other = Image.new("L", (64, 64))
    other.putdata([(y * 7 - x * 3) % 256 for y in range(64)
                   for x in range(64)])
    buf_other = io.BytesIO()
    other.save(buf_other, format="PNG")
    images = {"/big.png": big.getvalue(), "/small.png": small.getvalue(),
              "/other.png": buf_other.getvalue()}
    entries = [poster_entry("/big.png", 2000, 3000),
               poster_entry("/small.png", 500, 750),
               poster_entry("/other.png", 1000, 1500)]
    tmdb = make_tmdb(ALIEN, entries, images)
    _, last = drain(posters.run(video, fetch=tmdb, api_key="k"))
    assert last.saved == 2 and last.duplicates == 1
    assert (last.folder / "big.png").exists()      # the hi-res copy won
    assert not (last.folder / "small.png").exists()


def test_run_refuses_overwrite(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    folder = tmp_path / "Alien (1979)"
    folder.mkdir()
    (folder / "a.png").write_bytes(b"precious")
    tmdb = make_tmdb(ALIEN, [poster_entry("/a.png")],
                     {"/a.png": png("red")})
    _, last = drain(posters.run(video, fetch=tmdb, api_key="k"))
    assert last.saved == 0 and last.existing == 1
    assert (folder / "a.png").read_bytes() == b"precious"


def test_run_retries_search_without_year(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    tmdb = make_tmdb(ALIEN, [poster_entry("/a.png")],
                     {"/a.png": png("red")})
    empty = json.dumps({"results": []}).encode()
    for params in (dict(primary_release_year=1979), dict(year=1979)):
        tmdb.responses[search_url(api_key="k", query="Alien",
                                  include_adult="true", **params)] = empty
    tmdb.responses[search_url(api_key="k", query="Alien",
                              include_adult="true")] = json.dumps(
        {"results": [ALIEN]}).encode()
    _, last = drain(posters.run(video, fetch=tmdb, api_key="k"))
    assert isinstance(last, posters.Done) and last.saved == 1


def test_run_no_match_fails(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    empty = json.dumps({"results": []}).encode()
    tmdb = FakeTMDB({
        search_url(api_key="k", query="Alien", include_adult="true",
                   primary_release_year=1979): empty,
        search_url(api_key="k", query="Alien", include_adult="true",
                   year=1979): empty,
        search_url(api_key="k", query="Alien", include_adult="true"): empty,
        # the last attempt: the raw filename, in case the "year" was
        # part of the title all along (see _search)
        search_url(api_key="k", query="Alien.1979",
                   include_adult="true"): empty,
    })
    _, last = drain(posters.run(video, fetch=tmdb, api_key="k"))
    assert isinstance(last, posters.Failed)
    assert "no TheMovieDB match" in last.reason
    assert not (tmp_path / "Alien (1979)").exists()   # nothing created


def test_run_no_api_key_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.setattr(posters, "resolve_api_key", lambda: None)
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    _, last = drain(posters.run(video, fetch=FakeTMDB({})))
    assert isinstance(last, posters.Failed)
    assert "themoviedb.org" in last.reason


def test_run_search_error_fails_cleanly(tmp_path):
    video = tmp_path / "Alien.1979.mkv"
    video.touch()
    _, last = drain(posters.run(video, fetch=FakeTMDB({}), api_key="k"))
    assert isinstance(last, posters.Failed)
    assert "search failed" in last.reason


# -- find_poster: the read half — what the details pane shows -----------------


def a_video(tmp_path, name="Alien.1979.mkv") -> Path:
    from mediasmith import fs
    video = tmp_path / name
    video.write_bytes(b"not a real video")
    fs.clear_cache()
    return video


def an_image(path: Path) -> Path:
    from mediasmith import fs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png((10, 20, 30)))
    fs.clear_cache()
    return path


def test_find_poster_prefers_art_named_after_the_video(tmp_path):
    video = a_video(tmp_path)
    an_image(tmp_path / "loose.jpg")
    own = an_image(tmp_path / "Alien.1979.jpg")
    assert posters.find_poster(video) == own


def test_find_poster_looks_inside_the_poster_folder(tmp_path):
    video = a_video(tmp_path)
    inside = an_image(tmp_path / "Alien (1979)" / "a.png")   # run()'s folder
    assert posters.find_poster(video) == inside


def test_find_poster_falls_back_to_loose_art(tmp_path):
    video = a_video(tmp_path)
    loose = an_image(tmp_path / "poster.jpg")
    assert posters.find_poster(video) == loose


def test_find_poster_ignores_folders_that_are_not_art(tmp_path):
    from mediasmith import fs
    video = a_video(tmp_path)
    (tmp_path / "Extras").mkdir()
    (tmp_path / "Extras" / "notes.txt").write_text("x")
    fs.clear_cache()
    assert posters.find_poster(video) is None


def test_find_poster_claims_nothing_loose_when_videos_share_a_folder(tmp_path):
    from mediasmith import fs
    video = a_video(tmp_path)
    (tmp_path / "Aliens.1986.mkv").write_bytes(b"x")
    an_image(tmp_path / "poster.jpg")
    an_image(tmp_path / "Some Folder" / "b.png")
    fs.clear_cache()
    assert posters.find_poster(video) is None
    # …but a folder named after the video is still unambiguous
    mine = an_image(tmp_path / "Alien.1979" / "c.png")
    assert posters.find_poster(video) == mine
