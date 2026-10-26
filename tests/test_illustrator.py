"""Illustrator rescue: reading the AI half of an .ai file, and the two
constructs that decide whether the rescue looks like the original — a run of
subpaths merging into one nonzero fill, and a gradient group reading as a
clip rather than a fill."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from mediasmith import illustrator
from mediasmith.illustrator import Canvas

from .mediafactory import make_illustrator


def _content(pdf: bytes) -> str:
    """The page's content stream — written uncompressed, so it reads back."""
    body = pdf.split(b"stream\n", 1)[1]
    return body.split(b"\nendstream", 1)[0].decode("latin-1")


# -- reading the canvas -------------------------------------------------------


def test_reads_artwork_and_artboard_from_the_ai_half(tmp_path):
    canvas = illustrator.read_canvas(make_illustrator(tmp_path / "logo.ai"))
    assert canvas.artwork == (20, 20, 280, 80)
    assert canvas.artboard == (0, 0, 200, 200)


def test_artwork_past_the_artboard_reads_as_hidden_work(tmp_path):
    canvas = illustrator.read_canvas(make_illustrator(tmp_path / "logo.ai"))
    assert canvas.offboard
    assert canvas.hidden == (0, 0, 80, 0)          # 280 - 200 past the right edge


def test_artwork_inside_the_artboard_hides_nothing(tmp_path):
    canvas = illustrator.read_canvas(
        make_illustrator(tmp_path / "logo.ai", offboard=False))
    assert not canvas.offboard
    assert canvas.hidden is None


def test_an_edge_hugging_path_is_not_hidden_work():
    canvas = Canvas(artwork=(0, 0, 200.4, 200), artboard=(0, 0, 200, 200))
    assert not canvas.offboard


def test_uncompressed_private_data_reads_the_same(tmp_path):
    compressed = illustrator.read_canvas(make_illustrator(tmp_path / "a.ai"))
    plain = illustrator.read_canvas(
        make_illustrator(tmp_path / "b.ai", compressed=False))
    assert compressed == plain


def test_zstandard_private_data_reads_the_same(tmp_path):
    """Illustrator 2020+ swapped zlib for Zstandard (``%AI24_ZStandard_Data``);
    missed, the canvas reads as nothing and the rescue buttons never show."""
    zlibbed = illustrator.read_canvas(make_illustrator(tmp_path / "a.ai"))
    zstded = illustrator.read_canvas(
        make_illustrator(tmp_path / "b.ai", compressed="zstd"))
    assert zstded == zlibbed


def test_a_bare_postscript_ai_is_its_own_art_stream(tmp_path):
    """AI8 and earlier have no PDF wrapper — the file IS the art stream."""
    path = make_illustrator(tmp_path / "old.ai", compressed=False,
                            pdf_container=False)
    canvas = illustrator.read_canvas(path)
    assert canvas.artwork == (20, 20, 280, 80)


def test_a_file_with_no_ai_half_reads_as_nothing(tmp_path):
    path = tmp_path / "flat.ai"
    path.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n")
    assert illustrator.read_canvas(path) is None


def test_a_file_that_is_not_a_pdf_at_all_reads_as_nothing(tmp_path):
    path = tmp_path / "junk.ai"
    path.write_bytes(b"not a document")
    assert illustrator.read_canvas(path) is None


# -- recovery -----------------------------------------------------------------


def test_recovers_beside_the_source_under_a_distinct_name(tmp_path):
    source = make_illustrator(tmp_path / "logo.ai")
    result = illustrator.recover(source)
    assert result.target == tmp_path / "logo-full-canvas.pdf"
    assert result.target.exists()
    assert source.exists()                          # the source is never touched


def test_the_page_box_covers_the_off_artboard_work(tmp_path):
    result = illustrator.recover(make_illustrator(tmp_path / "logo.ai"))
    box = re.search(r"/MediaBox\[([\d\. ]+)\]",
                    result.target.read_bytes().decode("latin-1")).group(1)
    assert float(box.split()[2]) >= 280


def test_the_page_box_covers_work_parked_at_negative_coordinates(tmp_path):
    """Illustrator's canvas runs negative; a box anchored at 0,0 cropped
    everything parked left of or below the origin."""
    source = make_illustrator(tmp_path / "neg.ai", compressed=False,
                              pdf_container=False)
    source.write_bytes(source.read_bytes().replace(
        b"220 20 m\r280 20 L\r280 80 L\r220 80 L",
        b"-280 -80 m\r-220 -80 L\r-220 -20 L\r-280 -20 L"))
    for fmt in ("pdf", "svg"):
        target = illustrator.recover(source, fmt).target.read_bytes()
        if fmt == "pdf":
            # the page stays at 0,0 (Preview blanks a negative origin) and
            # a cm carries the canvas onto it
            box = re.search(rb"/MediaBox\[([\d\. -]+)\]", target).group(1)
            x0, y0, x1, y1 = (float(v) for v in box.split())
            assert (x0, y0) == (0, 0) and x1 >= 360 and y1 >= 160
            assert _content(target).startswith("1 0 0 1 304 104 cm")
        else:
            root = ET.fromstring(target)
            width, height = (float(v) for v in root.get("viewBox").split()[2:])
            assert width >= 360 and height >= 160   # -280..80 × -80..80


def test_both_squares_survive_the_translation(tmp_path):
    result = illustrator.recover(make_illustrator(tmp_path / "logo.ai"))
    content = _content(result.target.read_bytes())
    assert "20 20 m" in content                     # the on-artboard square
    assert "220 20 m" in content                    # the hidden one


def test_a_run_of_subpaths_sharing_paint_becomes_one_fill(tmp_path):
    """Illustrator's own PDF writer merges them, and compound holes depend on
    it: a hole is a subpath wound the other way, not a separate shape."""
    result = illustrator.recover(make_illustrator(tmp_path / "logo.ai"))
    assert result.paths == 1
    assert _content(result.target.read_bytes()).count("\nf") == 1


def test_refuses_to_overwrite_unless_told(tmp_path):
    source = make_illustrator(tmp_path / "logo.ai")
    first = illustrator.recover(source)
    with pytest.raises(FileExistsError):
        illustrator.recover(source)
    first.target.write_bytes(b"stale")
    illustrator.recover(source, overwrite=True)
    assert first.target.read_bytes() != b"stale"


def test_an_unknown_format_is_refused(tmp_path):
    with pytest.raises(ValueError):
        illustrator.recover(make_illustrator(tmp_path / "logo.ai"), "eps")


def test_a_file_with_no_artwork_is_refused(tmp_path):
    path = tmp_path / "flat.ai"
    path.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n")
    with pytest.raises(ValueError):
        illustrator.recover(path)


def test_constructs_the_translator_cannot_carry_are_reported(tmp_path):
    result = illustrator.recover(
        make_illustrator(tmp_path / "logo.ai", placed_image=True))
    assert "placed image" in result.skipped


# -- the gradient group -------------------------------------------------------


def test_a_gradient_group_becomes_a_clip_not_a_fill(tmp_path):
    """The construct that decides whether a gradient logo comes back as a
    gradient or as a black silhouette with a gradient patch on it."""
    result = illustrator.recover(
        make_illustrator(tmp_path / "logo.ai", gradient=True))
    content = _content(result.target.read_bytes())
    assert "W n" in content                         # the group clips
    assert "/Sh0 sh" in content                     # the shading paints
    assert "20 20 m" in content                     # through the group's paths


def test_the_gradient_reaches_the_page_resources(tmp_path):
    result = illustrator.recover(
        make_illustrator(tmp_path / "logo.ai", gradient=True))
    pdf = result.target.read_bytes().decode("latin-1")
    assert "/Shading<</Sh0" in pdf
    assert "/ShadingType 2" in pdf
    assert "/FunctionType 2" in pdf


# -- svg ----------------------------------------------------------------------


def test_the_svg_is_parseable_and_covers_the_whole_canvas(tmp_path):
    result = illustrator.recover(make_illustrator(tmp_path / "logo.ai"), "svg")
    root = ET.fromstring(result.target.read_text())
    assert float(root.get("viewBox").split()[2]) >= 280


def test_the_svg_carries_the_off_artboard_path(tmp_path):
    result = illustrator.recover(make_illustrator(tmp_path / "logo.ai"), "svg")
    root = ET.fromstring(result.target.read_text())
    drawn = " ".join(p.get("d") for p in
                     root.iter("{http://www.w3.org/2000/svg}path"))
    assert "M220 20" in drawn


def test_the_svg_gradient_is_a_clip_path(tmp_path):
    result = illustrator.recover(
        make_illustrator(tmp_path / "logo.ai", gradient=True), "svg")
    text = result.target.read_text()
    assert "<clipPath" in text
    assert 'url(#gradient)' in text
    assert "<linearGradient" in text


# -- housekeeping -------------------------------------------------------------


def test_only_ai_files_are_claimed(tmp_path):
    assert illustrator.is_illustrator(tmp_path / "logo.AI")
    assert not illustrator.is_illustrator(tmp_path / "logo.pdf")


def test_the_target_name_is_predictable_without_doing_the_work(tmp_path):
    source = tmp_path / "logo.ai"
    assert illustrator.target_for(source) == tmp_path / "logo-full-canvas.pdf"
    assert illustrator.target_for(source, "svg") == tmp_path / "logo-full-canvas.svg"


# -- the pane ------------------------------------------------------------------


def test_vector_extensions_land_in_their_own_kind(tmp_path):
    from mediasmith import kinds
    for name in ("logo.ai", "logo.AI", "art.eps", "art.svg", "doc.pdf"):
        assert kinds.kind_of(tmp_path / name, is_dir=False) == kinds.VECTOR
    assert kinds.kind_of(tmp_path / "notes.txt", is_dir=False) == kinds.OTHER


async def _select_the_ai(pilot, app):
    """Walk the tree onto the .ai and let the probe land."""
    from mediasmith.browser import LibraryTree
    tree = app.query_one(LibraryTree)
    for _ in range(20):
        if str(tree.cursor_node.label).startswith("logo"):
            break
        await pilot.press("down")
    await pilot.pause(0.6)              # debounce + the canvas probe worker


async def test_the_pane_reports_the_canvas(tmp_path):
    from mediasmith.app import MediasmithApp
    from mediasmith.details import DetailsView
    make_illustrator(tmp_path / "logo.ai")
    app = MediasmithApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _select_the_ai(pilot, app)
        details = app.query_one(DetailsView)
        assert details.kind == "vector"
        assert app.query_one("#panel-vector").display is True
        assert "200 × 200 pt" in str(app.query_one("#vector-artboard").render())
        assert "right edge" in str(app.query_one("#vector-hidden").render())


async def test_the_buttons_appear_only_when_work_is_hidden(tmp_path):
    from mediasmith.app import MediasmithApp
    from mediasmith.actions import ActionBar

    async def visible(root):
        app = MediasmithApp(root)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _select_the_ai(pilot, app)
            bar = app.query_one("#pane-bar", ActionBar)
            return {b.id for b in bar.query("Button") if b.display}

    hidden = tmp_path / "hidden"
    hidden.mkdir()
    make_illustrator(hidden / "logo.ai")
    clean = tmp_path / "clean"
    clean.mkdir()
    make_illustrator(clean / "logo.ai", offboard=False)

    on = await visible(hidden)
    off = await visible(clean)
    assert any("rescue" in (i or "") for i in on)
    assert not any("rescue" in (i or "") for i in off)


async def test_the_chord_writes_the_rescue_beside_the_source(tmp_path):
    """End to end: highlight the .ai, press ^p, the full-canvas PDF lands."""
    from mediasmith.app import MediasmithApp
    make_illustrator(tmp_path / "logo.ai")
    app = MediasmithApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _select_the_ai(pilot, app)
        await pilot.press("enter")              # descend into the pane
        await pilot.pause(0.3)
        await pilot.press("ctrl+p")
        await pilot.pause(0.8)                  # the producer worker
    assert (tmp_path / "logo-full-canvas.pdf").exists()
