"""Shrinking a comic (comics.py, todo-6).

Everything here runs on JPEGs made in the test — never on the real
books in ~/Documents/Comics, which this feature REWRITES IN PLACE.
"""
import random

import pytest
from PIL import Image

from mediasmith import comics


def make_page(path, width=1988, height=3056, quality=100, colour=(200, 40, 40)):
    """A page shaped like the real thing: big, q100, 4:4:4 — which is
    what Nick's files actually are."""
    image = Image.new("RGB", (width, height), colour)
    # some detail, or JPEG compresses a flat rectangle to nothing and
    # the sizes stop being comparable to a real page
    for y in range(0, height, 7):
        for x in range(0, width, 11):
            image.putpixel((x, y), ((x * 7) % 256, (y * 3) % 256, 90))
    image.save(path, "JPEG", quality=quality, subsampling=0)
    return path


@pytest.fixture()
def book(tmp_path):
    folder = tmp_path / "Scratch 001"
    folder.mkdir()
    for n in range(4):
        make_page(folder / f"page-{n:03}.jpg")
    return folder


def test_a_run_of_pages_is_a_comic(book):
    assert comics.probe(book) is True


def test_an_album_folder_is_not(tmp_path):
    """A music folder has a cover.jpg in it and is not a comic."""
    folder = tmp_path / "Album"
    folder.mkdir()
    make_page(folder / "cover.jpg", 600, 600)
    make_page(folder / "back.jpg", 600, 600)
    make_page(folder / "disc.jpg", 600, 600)
    (folder / "01 Song.mp3").write_bytes(b"not really audio")
    assert comics.probe(folder) is False


def test_two_images_are_not_a_comic(tmp_path):
    folder = tmp_path / "Pics"
    folder.mkdir()
    make_page(folder / "a.jpg", 600, 600)
    make_page(folder / "b.jpg", 600, 600)
    assert comics.probe(folder) is False


def test_the_plan_measures_every_page_and_samples_a_few(book):
    plan = comics.build_plan(book)
    assert len(plan.pages) == 4
    assert plan.sampled == 3                 # first, middle, last
    assert plan.before_total == sum(p.stat().st_size for p in book.iterdir())
    assert 0 < plan.ratio < 1
    assert plan.after_total < plan.before_total


def test_a_page_near_the_cap_is_not_resampled(book):
    """3056 → 3000 would cost sharpness to save 2% of the pixels."""
    plan = comics.build_plan(book, height=3000)
    assert plan.tallest == 3056
    assert plan.resizes is False
    list(comics.apply(plan))
    with Image.open(next(iter(sorted(book.iterdir())))) as image:
        assert image.height == 3056          # same pixels, fewer bytes


def test_a_tall_page_is_capped_by_HEIGHT_not_the_long_edge(tmp_path):
    """A spread is as tall as a page and twice as wide; capping its long
    edge would make each half blurrier than the pages around it."""
    folder = tmp_path / "Book"
    folder.mkdir()
    make_page(folder / "page.jpg", 3975, 6113)      # a 600-DPI scan
    make_page(folder / "spread.jpg", 3975, 3056)    # a double page
    make_page(folder / "last.jpg", 1988, 3056)
    plan = comics.build_plan(folder, height=3000)
    list(comics.apply(plan))
    with Image.open(folder / "page.jpg") as image:
        assert image.size == (1951, 3000)
    with Image.open(folder / "spread.jpg") as image:
        assert image.size == (3975, 3056)           # untouched
    with Image.open(folder / "last.jpg") as image:
        assert image.size == (1988, 3056)


def test_applying_replaces_the_pages_in_place(book):
    before = {p.name: p.stat().st_size for p in book.iterdir()}
    events = list(comics.apply(comics.build_plan(book)))
    assert all(isinstance(e, comics.Shrunk) for e in events), events
    after = {p.name: p.stat().st_size for p in book.iterdir()}
    assert sorted(after) == sorted(before)           # same names, in order
    assert sum(after.values()) < sum(before.values()) / 2


def noisy(width, height, seed=0):
    """Content JPEG cannot cheat on — which is what makes a re-encode
    bigger than a heavily compressed original."""
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height))
    image.putdata([(rng.randrange(256), rng.randrange(256),
                    rng.randrange(256)) for _ in range(width * height)])
    return image


def test_a_page_that_would_grow_is_left_alone(tmp_path):
    """Re-encoding an already-tiny page can inflate it. Then nothing
    should happen to it at all."""
    folder = tmp_path / "Book"
    folder.mkdir()
    for n in range(3):
        noisy(400, 600, n).save(folder / f"p{n}.jpg", "JPEG", quality=20)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    events = list(comics.apply(comics.build_plan(folder)))
    assert all(isinstance(e, comics.Kept) for e in events), events
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_a_png_page_becomes_a_jpg_and_the_png_goes(tmp_path):
    folder = tmp_path / "Book"
    folder.mkdir()
    for n in range(3):
        # noise: a PNG of it is far bigger than the JPEG, which is the
        # case where converting is worth doing
        noisy(900, 1400, n).save(folder / f"p{n}.png", "PNG")
    events = list(comics.apply(comics.build_plan(folder)))
    assert all(isinstance(e, comics.Shrunk) for e in events), events
    assert sorted(p.name for p in folder.iterdir()) == [
        "p0.jpg", "p1.jpg", "p2.jpg"]


def test_an_unreadable_page_is_reported_not_raised(book):
    (book / "page-000.jpg").write_bytes(b"not an image at all")
    plan = comics.build_plan(book)
    assert len(plan.pages) == 3              # it could not be measured
    assert all(isinstance(e, comics.Shrunk) for e in comics.apply(plan))


def test_nothing_is_written_while_only_planning(book):
    before = {p.name: p.read_bytes() for p in book.iterdir()}
    comics.build_plan(book)
    assert {p.name: p.read_bytes() for p in book.iterdir()} == before


def test_a_single_image_can_be_planned_on_its_own(book):
    page = sorted(book.iterdir())[0]
    plan = comics.build_plan(page)
    assert [p.path for p in plan.pages] == [page]
    assert plan.root == book
