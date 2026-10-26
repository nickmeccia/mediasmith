# Distributable Binary — the standing answer

**Context for this file.** Nick asked on 2026-08-22 whether mediasmith
could ship as a distributable binary. The answer is yes, with a ceiling.
This file exists so the question does not have to be re-derived from
scratch: it records what was already done, what is left, what is merely
tedious, and what is genuinely impossible. Read it before answering the
question again.

**The one-line answer:** a binary removes the *Python* dependency, not
the *toolchain* dependency. mediasmith shells out to four tools that
cannot reasonably be bundled, so even a perfect binary ships as "works
fully if you also have ffmpeg, potrace, and Calibre." That is the ceiling, and no
amount of build engineering raises it.


## What a binary buys, precisely

- The user does not need Python, `uv`, or the repo on disk.
- Launch is one file, no dependency sync on startup (`bin/mediasmith`
  currently defers to `uv run` on every launch).
- It is the prerequisite for the portfolio goal in CLAUDE.md's roadmap —
  handing someone a thing that runs.

What it does NOT buy: independence from ffmpeg, alass, potrace, or
Calibre. See "The external four" below.


## Already retired — do not redo this work

Session 6 (2026-08-22) removed three shell-outs. They are done; this
section is here so a future session does not re-open them.

- [x] **subliminal** — was a Homebrew keg discovered at runtime and
      spliced in with `site.addsitedir`. Now a plain `pyproject.toml`
      dependency. `import_subliminal()` survives only as the test seam.
- [x] **ffprobe** — was two subprocess calls reading `format_tags=title`.
      Now `mediasmith/container.py`: mutagen's `©nam` atom for mp4/m4v,
      enzyme's EBML header for mkv. Verified 12/12 against ffprobe on
      the real library; 10–50 ms over SMB vs ~1 s to spawn.
      `.avi`/`.mov` are deliberately unhandled — 0 of 71 sampled library
      files carry a title tag at all, so ffprobe answered None too.
- [x] **`open`** — `details.launch` was hardcoded to macOS `open`. Now
      branches darwin / win32 / xdg-open. This stays a subprocess on
      purpose: every library that wraps it is a platform check plus a
      Popen, which is not worth a dependency.


## Blockers inside this codebase

Small, real, and all must be fixed before any build is worth trusting.

- [ ] **`crash.log` writes into the bundle.** `app.py:531` resolves it as
      `Path(__file__).resolve().parent.parent / "crash.log"`. Under a
      PyInstaller onefile that is the temp extraction dir, deleted on
      exit — so the crash log for the exact failure you want to debug
      vanishes with the process. Under a signed .app it is read-only and
      the `except OSError: pass` swallows it silently. **Fix:** write to
      a user-writable path (`~/.local/state/mediasmith/` or alongside
      the existing `~/.config/mediasmith/`), frozen or not.

- [ ] **Hidden package data.** Two dependencies ship non-`.py` payloads
      that a naive build drops:
      - `guessit` — its `config/` and `data/` directories;
      - `textual` — `tree-sitter/*.scm` highlight grammars.
      **Fix:** `--collect-data guessit --collect-all textual`.

- [ ] **Entry-point metadata (the silent one).** subliminal discovers its
      providers through stevedore entry points, which read installed
      package *metadata* — exactly what a freezer strips. Without
      `--copy-metadata subliminal`, provider discovery returns an empty
      list and subtitle fetch fails with no error that points at the
      cause. Verified working in the venv (12 providers, `opensubtitles`
      loads); this is specifically a frozen-build hazard.
      **Smoke test any build by listing providers, not by importing.**

- [ ] **Python 3.14.** The venv runs 3.14.6 and freezer support for a
      just-released CPython lags. `requires-python` is `>=3.12`, so
      building against a 3.12/3.13 venv is a free fallback. Verify
      current PyInstaller/Nuitka support before assuming either works.

- [x] **`textual-image`'s import-time terminal probe** — already handled.
      `images.py` guards the import and degrades to images-off
      (CLAUDE.md rule 3). Freezing changes nothing here.

Non-issues, checked: `posters.py` writes to `~/Downloads/Videosmith` and
reads `~/.config/mediasmith/tmdb_api_key` — both correctly outside the
bundle. A binary user still has to place that TMDB key by hand; worth a
line in the README if a build ever ships.


## The external four — the real ceiling

Ordered by how hard they are to remove. None is a build-system problem;
all four are "what would replace this." (potrace joined 2026-09-16.)

### 1. ffmpeg — `gif.py` (replaceable, real port)

Video→GIF needs actual decoding, so no pure-Python rewrite exists. The
answer is **PyAV**: real bindings to the libav\* libraries whose wheels
ship those libraries inside, so it pip-installs and freezes with no
ffmpeg on the user's machine.

Costs, honestly:
- `av.filter.Graph` does expose `palettegen`/`paletteuse`, so the tuned
  two-pass algorithm survives — but `palettegen` only emits after the
  whole stream passes through, so the clean two-`run()` function becomes
  manual frame pumping with an explicit flush. Expect gif.py to roughly
  triple in size.
- The `runner` seam that keeps tests off a real ffmpeg has no equivalent;
  you would mock a filtergraph or accept a slow test on a tiny fixture.
- ~35–40 MB per platform.
- **Licensing, which is the part that bites:** PyAV's wheels bundle
  LGPL-built ffmpeg. Distributing a binary containing it puts LGPL
  obligations on you, notably the relink provision, which a onefile
  bundle does not naturally satisfy. That is a lawyer-shaped problem,
  not a code-shaped one.

Note the local `ffmpeg` binary is only ~388 KB because Homebrew links it
against shared libs — the real payload is the dylibs, so do not size this
from `which ffmpeg`.

### 2. alass — `subsync.py` (no library exists)

A Rust binary implementing a specific split-penalty alignment algorithm.
No Python port. Three options, none free:

- **Bundle the compiled binary as package data** and keep exec'ing it —
  still a subprocess, but the user installs nothing. Requires a build per
  platform/arch, and **check its license first** (believed GPL-3, which
  has consequences for what you ship beside it).
- **Swap in `ffsubsync`** — pip-installable, pure Python, same job by FFT
  correlation. But CLAUDE.md flags subtitle sync as empirically-tuned
  policy ported deliberately from v1 with a DEBUG_NOTES.md behind it;
  changing the aligner discards that tuning. It also shells out to
  ffmpeg itself to extract audio from video, so it removes the alass
  dependency by deepening the ffmpeg one — it does not reduce the count
  of external tools unless you were dropping subtitle sync anyway.
- **Reimplement in Python** — not realistic.

### 3. Calibre `ebook-convert` — `calibre.py` (the impossibility)

**This one does not get solved.** `/Applications/calibre.app` is 1.1 GB.
It is a full application with its own Python runtime, and `ebook-convert`
is not a library with a CLI on top — it is an application entry point.
There is no pip-installable equivalent that converts epub↔mobi↔azw3 at
comparable fidelity.

The good news is that it is already narrowed to one button. Cover
extraction and `.opf` writing are in-house through `epub.py`/`epublib`;
`calibre.py` implements only `convert()`, called from exactly one place
(`details.py:1880`). Calibre is not a broad dependency — it is a single
feature that is absent when Calibre is absent, and `find_ebook_convert()`
already degrades gracefully.

**Accept this.** A binary that says "book conversion needs Calibre
installed" is the correct product, not a compromise.

### 4. potrace — `trace.py` (chosen with the port measured)

Image Trace (2026-09-16) shells out to Homebrew's `potrace`. A
pure-Python port exists (`potracer`, pip-installable, freezes cleanly),
and Nick chose the binary with the numbers in hand. Timed on a
detail-dense image, one full trace per preview refresh:

| image | potrace | potracer |
|-------|---------|----------|
| 1 MP  | 0.14 s  | 4.2 s    |
| 4 MP  | 0.54 s  | 46 s     |
| 9 MP  | 1.2 s   | 3½ min   |

The port can't keep the stepper live. Swapping it in later is contained
— the pane only calls `trace.preview` and `trace.trace` — but the port
returns curves only, so it would also need the SVG/EPS/PDF writers and
the preview rasterizer that the binary brings. potrace is one small C
binary, so bundling it as package data is the likelier road than the
port — check its GPL obligations before shipping it beside mediasmith.


## Distribution mechanics — not code, but not free

- [ ] **One artifact per OS/arch.** macOS arm64 and x86_64 are separate
      builds (or a universal2 build); Linux and Windows again separate.
      No cross-compilation — each needs its own build machine or CI job.
- [ ] **macOS code signing and notarization.** An unsigned binary
      downloaded from the internet is Gatekeeper-blocked on anyone
      else's Mac. This needs a paid Apple Developer ID and a
      notarization step in the build. **This is the largest single cost
      in this entire document** — larger than the PyAV port.
- [ ] **Size.** The venv is already 81 MB; a bundle lands in that
      neighborhood before PyAV, well over 100 MB with it.


## The alternative that keeps winning

`uv tool install git+https://github.com/<user>/mediasmith` is one
command, works on every platform from a single artifact, needs no code
signing, and updates with `uv tool upgrade`. It is the same `uv` that
`bin/mediasmith` already depends on.

For a TUI whose audience already has a terminal, this covers most of what
a binary would. A frozen binary earns its keep specifically when the
target user should not have to know Python exists — and since ffmpeg and
Calibre remain prerequisites regardless, that user is still being asked
to install things.


## When to revisit

Build the binary when one of these becomes true:

- The portfolio demo needs a download link rather than an install command
  (though textual-serve + `--demo`, already a CLAUDE.md goal, may serve
  that better than a binary).
- You are willing to pay for an Apple Developer ID and wire notarization
  into CI.
- GIF export matters enough to justify the PyAV port and its LGPL
  question.

Until then the honest summary is: **the codebase is close to
binary-ready and the remaining code work is a day, but the distribution
work is weeks and the toolchain ceiling never moves.**
