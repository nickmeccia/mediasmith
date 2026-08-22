"""Policy tests for the subsync engine — no network, no alass.

The v1 DEBUG_NOTES.md parity suite, made permanent: monkeypatch the four
external probes (``import_subliminal``, ``download_best``,
``read_release_name``, ``alass_correction_ms``) and drive ``run()``.
These encode the ground-truth-tuned policy; a failure here means the
policy changed, which needs new playback evidence, not a code tweak.
"""

from pathlib import Path

import pytest

from mediasmith import subsync

SRT_BYTES = b"1\n00:00:10,000 --> 00:00:12,000\nhello\n"
ASS_BYTES = b"[Script Info]\nTitle: x\n"


class FakeSub:
    def __init__(self, content=SRT_BYTES, matches=frozenset({"title"}),
                 label="Fake.Release-GRP"):
        self.content = content
        self.filename = label
        self.id = label
        self._matches = set(matches)

    def get_matches(self, video):
        return self._matches


class FakeS:
    """Stands in for the _Subliminal bag; scan_video returns a dummy."""

    def scan_video(self, path):
        return object()

    def compute_score(self, sub, video):
        return 123


@pytest.fixture()
def video(tmp_path, monkeypatch):
    """A fake video file with every probe stubbed to a quiet default."""
    path = tmp_path / "Film.mkv"
    path.write_bytes(b"not a video")
    monkeypatch.setattr(subsync, "import_subliminal", lambda: FakeS())
    monkeypatch.setattr(subsync, "read_release_name", lambda p: None)
    monkeypatch.setattr(subsync, "alass_correction_ms",
                        lambda v, s, o: (_ for _ in ()).throw(
                            AssertionError("alass ran unexpectedly")))
    return path


def drain(target, **kw):
    """Run the engine on one target; return (events, file_results)."""
    events = list(subsync.run([target], **kw))
    results = [e.result for e in events if isinstance(e, subsync.FileDone)]
    return events, results


def stub_download(monkeypatch, *subs_per_call):
    """download_best returns these values on successive calls."""
    queue = list(subs_per_call)
    monkeypatch.setattr(subsync, "download_best",
                        lambda S, v, providers: queue.pop(0))


def stub_alass(monkeypatch, corr, shifted=b"1\n00:00:11,000 --> "
                                           b"00:00:13,000\nhello\n"):
    def fake(video, sub, out):
        if corr is not None:
            out.write_bytes(shifted)
        return corr
    monkeypatch.setattr(subsync, "alass_correction_ms", fake)


def test_existing_subtitle_skips(video, monkeypatch):
    video.with_suffix(".srt").write_bytes(SRT_BYTES)
    _, [result] = drain(video)
    assert result.category == "skip"
    assert result.installed is None


def test_force_refetches_over_existing(video, monkeypatch):
    existing = video.with_suffix(".srt")
    existing.write_bytes(b"1\n00:00:01,000 --> 00:00:02,000\nold\n")
    stub_download(monkeypatch, FakeSub(matches={"hash"}))
    _, [result] = drain(video, force=True)
    assert result.category == "ok"
    assert existing.read_bytes() == SRT_BYTES       # replaced


def test_hash_match_installs_untouched(video, monkeypatch):
    # exact file match: already timed to this encode; alass must not run
    # (the fixture's alass stub raises if reached)
    stub_download(monkeypatch, FakeSub(matches={"hash"}))
    _, [result] = drain(video)
    assert result.category == "ok"
    assert "no sync needed" in result.status
    assert video.with_suffix(".srt").read_bytes() == SRT_BYTES


def test_small_correction_applied_silently(video, monkeypatch):
    stub_download(monkeypatch, FakeSub())
    stub_alass(monkeypatch, corr=56)
    _, [result] = drain(video)
    assert result.category == "ok"
    assert result.status == "synced (+56ms)"
    assert b"00:00:11,000" in video.with_suffix(".srt").read_bytes()


def test_clamp_boundary_is_inclusive(video, monkeypatch):
    stub_download(monkeypatch, FakeSub())
    stub_alass(monkeypatch, corr=subsync.ALASS_CLAMP_MS)
    _, [result] = drain(video)
    assert result.category == "ok"                  # 2000ms: still silent


def test_large_shift_applied_but_flagged(video, monkeypatch):
    # Drive +32s was REAL; 300 +38s was wrong — magnitude can't pre-judge,
    # so the policy applies and flags (the Scott Pilgrim lesson).
    stub_download(monkeypatch, FakeSub())
    stub_alass(monkeypatch, corr=subsync.ALASS_CLAMP_MS + 1)
    _, [result] = drain(video)
    assert result.category == "check"
    assert "verify" in result.status
    assert b"00:00:11,000" in video.with_suffix(".srt").read_bytes()


def test_safe_rejects_large_shift(video, monkeypatch):
    stub_download(monkeypatch, FakeSub())
    stub_alass(monkeypatch, corr=32_000)
    _, [result] = drain(video, safe=True)
    assert result.category == "check"
    assert "original kept" in result.status
    assert video.with_suffix(".srt").read_bytes() == SRT_BYTES


def test_alass_failure_keeps_original(video, monkeypatch):
    # Stardust / Ocean's Eleven: alass failing does not mean the sub is
    # bad — install it with original timing, flag for an eyeball.
    stub_download(monkeypatch, FakeSub())
    stub_alass(monkeypatch, corr=None)
    _, [result] = drain(video)
    assert result.category == "check"
    assert "couldn't sync" in result.status
    assert video.with_suffix(".srt").read_bytes() == SRT_BYTES


def test_watermarked_content_rejected(video, monkeypatch):
    bad = SRT_BYTES.replace(b"hello", b"Addic7ed.com")
    stub_download(monkeypatch, FakeSub(content=bad), None)
    _, [result] = drain(video)
    assert result.category == "missing"
    assert not video.with_suffix(".srt").exists()


def test_ass_installed_as_is_for_review(video, monkeypatch):
    stub_download(monkeypatch, FakeSub(content=ASS_BYTES))
    _, [result] = drain(video)
    assert result.category == "check"
    assert result.installed == "Film.ass"
    assert video.with_suffix(".ass").read_bytes() == ASS_BYTES


def test_weak_match_widens_to_all_providers(video, monkeypatch):
    weak = FakeSub(matches={"resolution"})          # not hash/title/series
    good = FakeSub(matches={"title"})
    stub_download(monkeypatch, weak, good)
    stub_alass(monkeypatch, corr=100)
    events, [result] = drain(video)
    notes = [e.text for e in events if isinstance(e, subsync.Note)]
    assert any("weak match" in n for n in notes)
    assert result.category == "ok"


def test_no_match_anywhere_is_missing(video, monkeypatch):
    stub_download(monkeypatch, None, None)
    _, [result] = drain(video)
    assert result.category == "missing"
    assert result.installed is None


def test_run_totals_and_tree(video, monkeypatch):
    stub_download(monkeypatch, FakeSub(matches={"hash"}))
    events, _ = drain(video)
    done = events[-1]
    assert isinstance(done, subsync.RunDone)
    assert done.totals == subsync.Counts(installed=1)
    ((root, results),) = done.trees
    assert root == video.parent
    tree = subsync.build_tree(root, results)
    assert tree["Film.mkv"].category == "ok"


def test_subtitle_ext_detection():
    assert subsync.subtitle_ext(SRT_BYTES) == "srt"
    assert subsync.subtitle_ext(b"\xef\xbb\xbf" + SRT_BYTES) == "srt"
    assert subsync.subtitle_ext(ASS_BYTES) == "ass"
    assert subsync.subtitle_ext(b"WEBVTT\n") is None
    assert subsync.subtitle_ext(b"") is None


# -- Homebrew discovery: the keg reaches its deps through a .pth ---------------


def test_import_subliminal_processes_the_kegs_pth_files(tmp_path, monkeypatch):
    """A Homebrew formula venv points at its dependency kegs with .pth
    files (subliminal 2.7.1 ships homebrew_deps.pth → the certifi keg),
    and only ``site.addsitedir`` executes those. A bare sys.path.insert
    imported subliminal and then died on certifi, which surfaced as
    "subliminal Python package not found" (2026-08-22)."""
    keg = tmp_path / "site-packages"
    dep = tmp_path / "dep"
    (keg / "subliminal").mkdir(parents=True)
    dep.mkdir()
    (keg / "homebrew_deps.pth").write_text(
        f"import site; site.addsitedir({str(dep)!r})\n")
    monkeypatch.setattr(subsync, "find_subliminal_pythonpath", lambda: str(keg))
    monkeypatch.setattr(subsync, "_SITE_ADDED", False)
    monkeypatch.setattr("sys.path", list(__import__("sys").path))
    with pytest.raises(ImportError):        # the stub package is empty
        subsync.import_subliminal()
    import sys
    assert str(dep) in sys.path             # the .pth ran


def test_check_requirements_names_the_real_import_failure(monkeypatch):
    monkeypatch.setattr(subsync, "SUBLIMINAL_PYTHONPATH",
                        "/opt/keg/site-packages")

    def boom():
        raise ImportError("No module named 'certifi'")

    monkeypatch.setattr(subsync, "import_subliminal", boom)
    problems = subsync.check_requirements()
    reported = [p for p in problems if "subliminal" in p]
    assert len(reported) == 1
    assert "certifi" in reported[0]         # not "install with: brew install"
    assert "/opt/keg/site-packages" in reported[0]
