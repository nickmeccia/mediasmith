"""SRT engine: parsing, cleaning, shifting."""

from mediasmith import srt

SAMPLE = """\
1
00:00:01,000 --> 00:00:02,500
Subtitles by CoolGuy99

2
00:00:05,000 --> 00:00:07,000
<font color="#00ff00">Hello there.</font>

3
00:00:09,000 --> 00:00:10,000
Visit www.example.com for more

4
00:01:00,000 --> 00:01:02,000
Plain dialogue.

5
00:59:59,000 --> 01:00:01,000
{\\c&H00FF00&}Colored{\\c} goodbye.
"""


def test_parse_and_render_round_trip():
    entries = srt.parse(SAMPLE)
    assert len(entries) == 5
    assert entries[0].start_ms == 1000
    assert entries[4].end_ms == 3_601_000
    reparsed = srt.parse(srt.render(entries))
    assert reparsed == entries


def test_parse_skips_malformed_blocks():
    text = "not a number\n00:00:01,000 --> x\nhuh\n\n" + SAMPLE
    assert len(srt.parse(text)) == 5


def test_parse_handles_bom(tmp_path):
    p = tmp_path / "a.srt"
    p.write_bytes(b"\xef\xbb\xbf" + SAMPLE.encode())
    assert len(srt.read(p)) == 5


def test_clean_strips_color_keeps_text():
    result = srt.clean(srt.parse(SAMPLE), credits=False)
    texts = ["\n".join(e.lines) for e in result.kept]
    assert "Hello there." in texts
    assert "Colored goodbye." in texts
    assert result.color_stripped == 2
    assert not any("<font" in t or "{\\c" in t for t in texts)


def test_clean_drops_edge_credits_keeps_mid_urls():
    entries = srt.parse(SAMPLE)
    # sandwich the URL cue in padding so it sits far from both edges
    middle = srt.Entry(30_000, 31_000, ("Chat.",))
    padded = ([entries[0]] + [middle] * 8 + [entries[2]]
              + [middle] * 8 + [entries[3]])
    result = srt.clean(padded, colors=False)
    kept_text = "\n".join("\n".join(e.lines) for e in result.kept)
    assert "CoolGuy99" not in kept_text            # edge credit dropped
    assert "www.example.com" in kept_text          # now mid-file: kept
    assert len(result.removed) == 1


def test_clean_removes_markup_only_husks():
    text = "1\n00:00:01,000 --> 00:00:02,000\n<font color=\"#fff\"></font>\n"
    result = srt.clean(srt.parse(text))
    assert result.kept == []
    assert len(result.removed) == 1


def test_shift_clamps_at_zero_never_drops():
    entries = srt.parse(SAMPLE)
    shifted = srt.shift(entries, -2_000)
    assert len(shifted) == len(entries)
    assert shifted[0].start_ms == 0                # clamped
    assert shifted[3].start_ms == 58_000


def test_shift_is_recomputed_from_original():
    entries = srt.parse(SAMPLE)
    # nudging +10s then deciding on -1s total: apply -1s to the
    # ORIGINAL, not -11s to the +10s copy — same result, no drift
    assert srt.shift(entries, -1_000) == srt.shift(
        srt.shift(entries, 0), -1_000)


def test_format_shift():
    assert srt.format_shift(0) == " 0:00.0"
    assert srt.format_shift(1_500) == "+0:01.5"
    assert srt.format_shift(-6_000) == "-0:06.0"
    assert srt.format_shift(65_500) == "+1:05.5"
