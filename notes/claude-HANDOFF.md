# Handoff briefs — remaining claude-TODO features

Written by Fable 5 (2026-07-11) for the model finishing the queue.
Read CLAUDE.md first — especially "The action pattern cookbook", which
this file assumes. Each brief below maps one feature onto a pattern
that already ships in this repo, sketches the engine API, and lists
the tests to write. The UI wiring is deliberately formulaic; the
judgment has been spent here so you don't have to re-derive it.

**Definition of done, per feature (no exceptions):**

1. Engine logic in its own IO-free-ish module + pure pytest coverage.
2. UI wiring per the cookbook; Pilot tests for the new interactions.
3. Full suite green, then the snapshot fuzz gate (see cookbook) — zero
   deaths. Add any new chords to `tests/fuzz.py` KEYS.
4. A checklist section in notes/QA-TODO.md (what Nick should try).
5. An inline `(Claude, date: …)` reply under the feature's entry in
   notes/claude-TODO.md recording what shipped and what was decided.
6. One commit, message explaining decisions, ending with the gate note.

**Worked examples to copy from (commit 830bad9 + 5591410):**

- Plain button that produces a file → `extract_cover` / `create_opf`
  (details.py "produce-a-sibling" section).
- Folder action, smart visibility, plan preview → folderize
  (folderize.py + details.py "folderize" section).
- Long-running external tool in a worker → `_convert_worker`.
- Options-before-action ("wizard") → the art-path input row
  (`ArtPathInput`): an inline row/div toggled visible under the
  buttons. Nick hates modals; never add one beyond ConfirmSave.


## #5 Fix multi-artist — DONE (Fable, 2026-07-11, second session)

Shipped per this brief (`fi^x multi-artist`, ^x as suggested). One
structural change worth knowing: folderize's apply/cancel became the
shared `plan_apply`/`plan_cancel` pair — `plan_preview_open()` /
`_show_plan_preview()` / `_plan_root()` in details.py are the generic
mechanism, and `action_plan_apply` dispatches to whichever plan is
open. A future plan-shaped action (standardize-formatting's folder
mode, #12) should add its `_<name>_plan` field and a dispatch branch,
not new buttons. The preview container ids are now `#plan-preview` /
`#plan-tree`. Original brief below.

## #5 original brief (superseded)

- **Engine DONE (Fable, 2026-07-11): `mediasmith/multiartist.py` +
  `tests/test_multiartist.py` (7 tests green). Only the UI wiring
  remains.** The engine API: `probe(root)`, `build_plan(root) ->
  MultiArtistPlan(groups)`, `execute(plan) -> (fixed, errors)`.
- Pattern: folderize exactly — probe → button → plan preview →
  apply/cancel. Reuse the same preview Static (or add a sibling) and
  the same bar-ownership trick in `_sync_pane_bar`. Preview shows,
  per album: `album → main` then each file's old artists (see v1's
  preview text for tone).
- Decisions already inside the engine (don't relitigate):
  - **The AC/DC guard:** a slash-joined artist string is NOT tangled
    when the unsplit string, sanitized, equals the artist-folder name
    two levels up. v1 would have retagged AC/DC as "AC".
  - v1's per-album include/exclude checkboxes are dropped; scoping is
    the substitute (invoke on less to exclude). If Nick wants
    checkboxes, that's a new interaction pattern — flag it first.
- Pilot tests: button appears on a tangled folder, absent on clean;
  preview → apply rewrites tags (assert via mutagen).
- Key suggestion: none of "fix multi artist"'s letters are free — use
  `Action("fix_multi_artist", "fix multi-artist", "x")`? ctrl+x is
  Input cut, but no inputs are focusable on folder views, so it's
  safe there. Nick renames keys at will; note it in QA-TODO.

## #6 Video: container field + download posters — DONE (Fable, 2026-07-15)

Shipped per this brief. Deltas the next model should know:

- Container is the suffix name only, shown instantly from `_read_video`
  — the ffprobe fold-in was skipped (Nick asked for the suffix; the
  demuxer name added noise for no request). `probe_video_title` is
  unchanged.
- `mediasmith/posters.py` follows subsync's generator-of-events shape
  with ONE injectable `fetch(url)->bytes` seam — tests fake all of
  TMDB through it (tests/test_posters.py, 15 tests). guessit joined
  pyproject.
- Local videos get a "Film (Year)" folder BESIDE the video (not loose
  files — they'd hijack the video panel's poster row); network
  (/Volumes) stages to ~/Downloads/Videosmith/ as v1 did.
- The ^d chord came from a RESERVED_KEYS audit (with ^e): against
  Textual 8's real bindings, d/e are Input-editing chords only — same
  safety class as the already-used a/k/u/v/w/x. QA-TODO has the full
  audit note; the ctrl-letter pool is exhausted AGAIN, so #10 still
  needs Nick's ctrl+shift-layer decision.

## #6 original brief (superseded)

- Container: `adapters._read_video` gains
  `container: str` — just the suffix name ("mkv") is what Nick asked
  for ("satisfied if merely viewable"); add a `container` row to
  `panel-video`. If you want the real demuxer name, ffprobe
  `format_name` is already probed in `probe_video_title`'s style —
  fold both into one ffprobe call in `_probe_title` (one process, two
  fields; keep the selection-moved check).
- Download posters: port `mediasmith-v1 tools/videosmith/
  download-posters/download-posters.py` into
  `mediasmith/posters.py`. Keep: TMDB key resolution (env var, then
  ~/.config/mediasmith/tmdb_api_key), guessit → filename → folder
  title resolution, dhash near-duplicate dropping. Replace `requests`
  with urllib (artfetch.py shows the house style) to avoid a new dep;
  guessit IS worth adding to pyproject (release-name parsing is not
  worth rewriting).
- Nick's local/network split: file on a local volume → posters into
  the file's folder; on a network volume → the v1 staging folder
  (~/Downloads/Videosmith/<Film (Year)>/). Detect network with
  `path.parts[:2] == ("/", "Volumes")` — document in QA-TODO that
  this heuristic is up for review.
- Button on video files: `download posters` — needs no can_edit;
  chords already fire from the tree (that's why App.on_key exists).
  Progress via notify at start/end; it downloads N images, so this is
  the longest worker yet — consider notify per ~5 posters.
- Honor `MEDIASMITH_OFFLINE` (artfetch.py pattern) — the fuzz gate
  presses every chord.
- Tests: engine with a fake fetcher (inject a `fetch(url)->bytes`
  callable, don't hit TMDB); dhash dedup on generated images; the
  local/network target rule. Pilot: button present on video, absent
  elsewhere; a monkeypatched download lands files + FileCreated.

## #7 Subtitles — DONE (Fable, 2026-07-11, second session)

Shipped whole: `mediasmith/subsync.py` (faithful v1 port +
tests/test_subsync.py, 14 policy tests), four buttons (`get subs ^k`,
`clean subs ^u`, `shift subs ^v`, `watch ^w`), and the shift div.
What the next model needs to know:

- **The shift div is the wizard-pattern exemplar** (an inline div,
  focusable readout, ^s ties into the pane's dirty/ConfirmSave flow,
  save button joins the bar while open). Image-resize (#9) and
  video→gif (#13) should copy it: same CSS block (`#shift-div` in
  app.py), same `_shift_*` state-machine shape in details.py.
- ShiftControl is the first focusable widget inside a non-editable
  kind's panel; `_nav_items` special-cases it. A second such widget
  (resize inputs) should generalize that branch, not add another
  special case.
- get subs passes `force=True` when a sub exists (explicit press =
  re-fetch) — flagged for Nick's veto in QA-TODO.
- `watch` uses a `launch()` seam (details.py) — monkeypatch that, not
  subprocess.Popen: `subprocess.run` calls Popen internally, so a
  global patch breaks the ffprobe title probe (learned the hard way).
- The original brief is kept below for reference.

## #7 original brief (superseded)

- Read `mediasmith-v1/lib/engines/subtitle_sync.py` AND its
  DEBUG_NOTES.md before anything. CLAUDE.md rule: that engine's
  policy is empirically tuned — **port, don't rewrite.** It already
  follows the events-from-generators pattern this repo wants.
- **`mediasmith/srt.py` is DONE (Fable, 2026-07-11) +
  `tests/test_srt.py` (9 tests green):** Entry/parse/read/render/
  write, `clean()` (v1 regexes verbatim), `shift()` (clamp at 0,
  recompute-from-original nudge model), `format_shift()` for the
  shift div's display. The dl+sync engine port and all UI remain.
- Buttons on a video file (visibility):
  - `clean subs` — only when a sibling .srt exists
    (`VideoDetails.subtitle_name` already knows). Runs clean() on it,
    in place; notify what was stripped.
  - `get subs` — the v1 dl+sync engine port; worker streams events →
    notify. `dzr-srt`-style external tools may be broken on Nick's
    machine; implement assuming they work (his instruction).
  - `shift subs` — a toggleable inline div under the video fields
    (react-style, exactly Nick's spec): total-shift display,
    ←/→ ±0.1s, ⇧←/→ ±1s, ⇞/⇟ ±10s (steal v1's _ShiftState: target vs
    applied, recompute from ORIGINAL every write so nudging never
    loses cues). Pending shift ties into the pane's dirty/✓ flow —
    the div refuses to close while pending (ConfirmSave applies).
    This is the one feature where focus enters a non-editable kind's
    pane — model it on ArtPathInput's cancel/blur behavior rather
    than widening EDITABLE_KINDS.
  - `watch` — launch the video + subs in the player to check
    alignment: `open -a` on macOS… IINA/VLC take `--sub-file`-style
    args; plain `open` can't pass them, so use
    `subprocess.Popen(["open", video])` as the safe default and note
    in QA-TODO that wiring the sub file needs Nick to name his player.
- Fuzz: add the new chords; the shift div's arrow keys ride existing
  KEYS already.

## #8 + #9 Images — DONE (Fable, 2026-07-15, session 2)

Shipped per this brief. Deltas the next model needs:

- **The key-space question is RESOLVED: contextual reuse** (Nick's
  pick from the QA-TODO session-3 options). Image chords reuse
  book/audio-only letters (^p jpg, ^g png, ^b webp, ^f tiff, ^e
  resize, ^o rotate, ^a apply-in-div); the per-bar duplicate-key
  assert moved from ActionBar.__init__ to set_visible, which asserts
  no two *visible* buttons share a chord. #10/#12/#13 can now mint
  chords the same way — pick letters whose other owners can't share
  a context, and let the assert police it.
- Images joined EDITABLE_KINDS, so the resize div rides the normal
  editable-nav path (_field_inputs grows the div's controls while
  open) — the ShiftControl special case in _nav_items stayed the
  only one; no generalization was needed after all.
- Textual's command palette (a system ctrl+p binding that wins before
  App.on_key) had been silently eating convert-to-epub; it's now
  disabled app-wide (ENABLE_COMMAND_PALETTE = False).
- Book _convert now refuses under MEDIASMITH_OFFLINE — that's what
  let ^p/^b/^y join fuzz KEYS (ebook-convert spawns are too heavy for
  the gate). Every seed's walk re-dealt, as always.
- A same-path re-preview (FileCreated → tree reload → cursor re-emit)
  used to slam wizard state shut; _apply_pending now carries the open
  resize div across it. Video→gif (#13) will want the same carry.
- .tiff/.tif joined IMAGE_EXTENSIONS (a tiff convert must produce a
  file the app can view).

## #8 + #9 original brief (superseded)

- Rename (do first, it's small): add `kinds.IMAGE` to
  `EDITABLE_KINDS`, give `_fill_image` a `_show_editable` path like
  audio/book but with an empty field form (filename only). Check
  `_field_inputs`/save flow — `save_details` already handles
  fields={} + rename. Pilot: enter on an image focuses fname; rename
  on disk works (copy test_book rename assertions).
- **Engine DONE (Fable, 2026-07-11): `mediasmith/imageops.py` +
  `tests/test_imageops.py` (7 tests green). Only the UI wiring
  remains.** API and locked decisions:
  - `convert(path, fmt)` — offer `CONVERT_FORMATS` minus current
    (heic excluded: Pillow can't write it; avif needs a plugin —
    revisit only if Nick asks). RGBA→JPEG flattens; EXIF preserved
    where the format allows. Beside source, refuse-overwrite.
  - `resize(path, w, h)` — writes `name (WxH).ext` beside the source
    (files are precious; metadata is edit-in-place, pixels are not).
    `fit_dimensions()` is the aspect-link math for the resize div.
  - `rotate(path, quarter_turns)` — the one in-place op; returns
    `(path, lossy)`, lossy=True for re-encoded JPEGs → notify
    "re-encoded". No jpegtran dep without asking Nick.
- Convert buttons: pane bar, own format hidden — copy the book
  convert visibility code verbatim.
- Resize div: Nick specified it — button toggles an inline div with
  two numeric inputs and a "link" checkbox (aspect ratio). Textual
  `Checkbox` widget exists; inputs are `FieldInput` with `type=
  "integer"`. Editing aspect-linked: changing one field recomputes
  the other on change when linked. Apply button in the div. This div
  + the shift-subs div together define the wizard pattern — keep them
  visually identical.
- Tests: engine (every fmt round-trip via tiny PIL images, RGBA→jpg,
  refuse-overwrite, aspect math), Pilot (toggle div, linked fields
  recompute, apply creates file).

## #10 Folders — DONE (Fable, 2026-07-15, session 2)

Shipped per this brief. Deltas:

- Keys: the brief's "^n new" was taken by Move in the interim; new
  folder is ⌘⇧N and trash is ⌘⌫ (Finder's chords, App bindings,
  kitty-protocol) with chord-less buttons on folder views as the
  phone fallback. Contextual reuse couldn't help here: these show on
  every folder alongside l/x/n/s/o/f/a contexts.
- send2trash joined the deps (the brief's preference); trash honors
  MEDIASMITH_OFFLINE so the fuzz gate can't fill the real Trash.
- Expanded-rename restore didn't need _pending_restore — the Saved
  handler collects the open subtree's paths, remaps old→new prefixes,
  reloads the parent, and re-expands (app.py on_details_pane_saved).
- Rename gap: album-like folders open as the bulk form (no filename
  field) — renaming those has no UI; flagged to Nick.
- Two messages joined the pane: FolderCreated (reload → cursor →
  descend into rename) and Trashed (reload parent, climb out if the
  context row died).

## #10 original brief (superseded)

- Rename: add `kinds.FOLDER` to EDITABLE_KINDS *carefully* — the
  folder panel currently descends into bulk-edit for album-like
  folders (`bulk_paths_for_folder`); plain folders should now show a
  fname-only form like images. `adapters.rename` already works on
  dirs (`path.rename`); the tree's Saved handler already reloads.
  Watch: renaming an EXPANDED folder — reload the parent node and
  re-expand via `_pending_restore` (see `anchor`).
- New folder: keybinding on the tree (strip: `^n new`), creates
  "untitled folder" in the highlighted dir (or its parent when a file
  is highlighted), then puts the cursor on it and descends into the
  rename field — Finder's flow. `fs.clear_cache()` + reload first.
- Delete: button on the folder view AND a tree keybinding; use
  ConfirmSave-style modal? No — Nick hates modals, but delete is
  destructive: send to macOS Trash via `subprocess.run(["osascript",
  "-e", 'tell app "Finder" to delete POSIX file "…"])` or
  `send2trash` dep (prefer send2trash: 0 deps of its own, testable).
  Trash means no confirm needed — that's the design out of the modal
  trap. Notify "moved to Trash".
- Tests: engine none needed beyond adapters.rename (covered); Pilot
  for new-folder flow, delete-to-trash (monkeypatch send2trash),
  rename with expansion restore.

## #11 Omnibus splitter — DONE (Fable, 2026-07-15)

Shipped per this brief as the third plan-shaped action (dispatch
branch on the shared plan_apply/plan_cancel, exactly as the #5 note
prescribed). Deltas:

- The 571 v1 lines held up on close read; parsing/writing ported
  faithfully into `mediasmith/omnibus.py`. `epub.rewrite_epub` did NOT
  fit (it rewrites one epub in place; the splitter assembles new zips
  from slices) — the splitter keeps its own writer.
- v1's interactive flows (title renaming, flat-TOC boundary entry)
  are not portable to a plan preview; flat-TOC omnibuses therefore
  don't get the button (probe requires boundaries WITH children).
  Flagged to Nick in QA-TODO — a wizard div could restore it.
- `make_omnibus` in tests/mediafactory.py builds a two-book omnibus
  under OEBPS/ (exercises zip-path resolution + the asset scan).
- Key is ^e (the other recovered letter — see #6 note).

## #11 original brief (superseded)

- v1 `tools/booksmith/omnibus-splitter/omnibus-splitter.py` (571
  lines) is regex/ET-based NCX parsing + epub slicing. Port the
  detection + split into `mediasmith/omnibus.py`; it has NO deps and
  its logic looked sound on skim — port faithfully, consolidate its
  epub writing onto `epub.rewrite_epub` where it fits.
- Button `split omnibus` on epubs, visible only when
  `detect_books(navpoints)` finds >1 book (run detection in the same
  fill-late probe slot as the folderize probe — cheap: one zip read).
  Output: one epub per book beside the source ("Author Sort -
  Title.epub", v1 convention), refuse-overwrite, FileCreated per
  book.
- Tests: build a tiny omnibus epub in mediafactory (two navpoint
  trees) — detection, split round-trip (each output opens, has its
  chapters), non-omnibus → no button.

## #12 addendum — "sort" DONE too (Fable, 2026-07-16)

Nick answered the [a]/[b] question inline in claude-TODO, extending
[a]: wrap ALL of a book's files (epub/mobi/azw3/opf/cover) into one
"Author Sort - Title/" folder. Shipped as the fourth plan-shaped
action: mediasmith/booksort.py (stem = book identity; sidecars ride
only when unambiguous; no-epub groups skipped, never guessed; wrapper
folders are no-ops), key ^t (contextual reuse — extract-cover is
single-epub-only). Files keep their names (v1 renamed the epub to
match the folder) — flagged for his veto.

Also this session: two real gate deaths, root-caused via the newly
kept pty to a ConfirmSave double-dismiss (ScreenStackError = silent
app death; fixed — first answer wins). The harness got a seatbelt
WRITE-JAIL, per-seed pty capture kept on death, and --first. Full
story: QA-TODO "Fuzz deaths: solved" + the gate-discipline memory.

## #12 Standardize formatting — DONE (Fable, 2026-07-15, session 2);
## "sort" awaited Nick's pick (answered — see addendum above)

Formatting shipped per this brief (mediasmith/standardize.py — the
436 v1 lines evaluated: extractors/detection ported verbatim as tuned
policy; the rebuild now carries metadata + cover, which v1 dropped).
Deltas:

- Key: ^d contextual-reuse (download-posters is video-only).
- Output: "Name (clean).epub" sibling, refuse-overwrite; folder mode
  is DIRECT children only; acts directly with streamed notifications
  (nothing moves, so no plan preview) — the folder button is
  probe-gated on "any direct epub lacking its clean sibling".
- mobi/azw3 not offered (convert first); --style override not
  surfaced. Both flagged to Nick.
- make_epub in mediafactory now writes an NCX (calibre always does;
  the engine requires one).
- **"Sort" folders is NOT built.** The brief's assumption was wrong on
  one point: Nick's BOOKS volume sorts by genre/pipeline above the
  per-book level, so "sort" isn't inferable. The v1 convention IS
  clear — one "Author Sort - Title/" folder per book with cover.jpg +
  metadata.opf — and the question is put to Nick inline in claude-TODO
  ("Sort" folders entry). If he picks it, build it as the fourth
  plan-shaped action on the shared plan_apply/plan_cancel pair.

## #12 original brief (superseded)

- Read `tools/booksmith/standardize-formatting/standardize-formatting.py`
  (436 lines, unread by me — evaluate before porting).
- Nick's decisions from the TODO: works on single book AND folder →
  two buttons, same engine. "Sort folders" = the folder-scoped
  normalize; his parked question (normalize-metadata-as-folder-
  action) leans no — build "sort" first, leave normalize out, note it.
- Follow folderize's preview pattern for anything that renames or
  moves; plain in-place cleanups can act directly with a notify.

## #13 Video → GIF

- `mediasmith/gif.py`: ffmpeg two-pass palette
  (`palettegen`/`paletteuse`), options: fps (default 12), width
  (default 480), start/duration optional. Output beside source,
  refuse-overwrite.
- UI: the wizard div again (fps/width inputs + make button). ffmpeg
  presence check like calibre. Worker + FileCreated. Low priority —
  do it last of the builds; it's Nick's treat, make the defaults tasty.

## #15 Search design + folder Move — RESOLVED

Nick picked, same evening (decisions recorded at the top of
notes/claude-PROPOSALS.md): **search is out of mediasmith entirely**
(download tools move to ~/code/downloader; the anna-search strategy
audit lives there too), and **Move shipped as M1** with a single
stateful chord (^n lift/place — ^x/^v collide with pane actions;
tree bindings starve app-wide chords, a constraint to remember).
Lift state lives on the App (`app.lifted`) so it survives path-bar
jumps. ⚠ ^n was the last free ctrl-letter — resolve the key-space
question in QA-TODO before wiring #10 New/Delete. Original brief
below.

## #15 original brief (superseded)

- Nick wants proposals before code: a unified search (Deezer, Anna's
  Archive, future serial scraping) and a Move interaction. Write
  notes/claude-PROPOSALS.md with 2–3 options each and one
  recommendation each. Constraints he's stated: global keybinding is
  his straw man; he hates modals; phone-width must work. Consider: a
  search *panel* that swaps into the details column (like narrow
  "view") with a query input + result list, kind-aware (audio results
  on audio contexts); Move as "mark destination" two-step in the tree
  (cut/paste with visible pending state on the strip) — precedent:
  every dual-pane file manager. Do not implement without his pick.

## Gate discipline (why snapshots)

Two workflow rules learned the hard way (2026-07-11, session 3):

- **Never chain `pytest | tail … && fuzz`** — the pipe masks pytest's
  exit code, so the gate runs (and can pass!) over a red suite. Use
  `set -o pipefail`, or run pytest unpiped and read the tail after.
  A Move commit briefly claimed a green suite this way; caught and
  amended minutes later, but the trap is silent.
- **Any new pane-bar button breaks every exact-list bar assertion**
  (`_bar_names(app) == [...]`) — that's by design (they pin the
  palette per kind); expect to touch them whenever the palette grows,
  and re-run the FULL suite before committing, not just `-k feature`.

Run the fuzz gate from a snapshot copy, not the working tree — the
children re-import the package every seed, so live edits during a
run produce false deaths (or mask real ones):

    rsync -a --exclude .git --exclude .venv --exclude __pycache__ \
        ~/code/mediasmith/ /tmp/ms-snap/
    cd /tmp/ms-snap && ~/code/mediasmith/.venv/bin/python tests/fuzz.py

If a seed dies: re-run that seed alone WITH pty capture before
concluding anything. The 2026-07-11 seed-7 "load flake" turned out to
be real: when the subtitle chords joined KEYS, every seed's random
walk re-dealt, and seeds 7+11 reproducibly climbed the parent ladder
into /dev, where the folderize probe worker crashed on
DirEntry.is_dir() over /dev/fd (EBADF) — an unhandled worker
exception is app death, and it looked "silent" because nobody kept
the pty output. Fixed in folderize.iter_audio (+ regression test).
Standing lessons: any KEYS change re-deals every walk, so previously
clean seeds prove nothing; engine walkers must survive hostile
filesystems (/dev, dead symlinks) because the browser can reach /;
and a death with no crash.log and no wedge message can be EITHER a
swallowed CancelledError (details.py docstring) or a worker crash —
only the pty tail tells them apart. A capture harness (fuzz_debug.py:
one seed, tees pty to a file, prints the last keys) is trivial to
rebuild from tests/fuzz.py's attempt().
