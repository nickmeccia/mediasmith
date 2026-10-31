# mediasmith — architecture handoff

Context for Future Claude (and future Nick). This repo is a clean-slate
rewrite; everything before it is R&D, frozen at `~/code/mediasmith-v1`
(also on GitHub). Read this before writing any code.

## Terms of Art

Please read the Terms of Art document, found at 
`./notes/claude/terms-of-art.md`.

## What this app is

One fullscreen Textual TUI with a **file-browser model** — not v1's
menu-of-tools model. The UX was prototyped and user-approved in
`~/code/mediasmith-v1/mediasmith-ux/app.py`; that file is the reference
implementation to consult, not code to import.

```
┌─────────────────────┐ ┌───────────────────────────────┐
│ Tree View           │ │ Details View                  │
│ ┌─────────────────┐ │ │  · metadata per file kind     │
│ │ Path Input      │ │ │  · cover / poster image       │
│ └─────────────────┘ │ │  · contextual action buttons  │
│  directory tree     │ │    (shortcut chars accented)  │
│  ↑↓ navigate,       │ │  · batch bar when marks exist │
│  ←→ expand/collapse │ │                               │
└─────────────────────┘ └───────────────────────────────┘
┌───────────────────────────────────────────────────────┐
│ Command Strip — ONE line, state-driven, wraps narrow  │
└───────────────────────────────────────────────────────┘
```

- **Path Input is a sub-view OF Tree View** (todo-4, 2026-08-12): the
  `TreeView` container widget owns `PathInput` + `LibraryTree`; the pane
  border and focus state live on the container (`:focus-within`).
- Details view **follows the tree highlight** (debounced), no Enter needed.
- Marking files (`space`) grows a batch bar; batch actions apply only when
  all marked files share one kind. (Still to come — roadmap 4.)
- Actions are contextual per kind: video → download subtitles/posters,
  audio → editable tag form, book → Calibre-backed metadata, folder →
  whole-folder actions.
- **Every printed chord works from either view** (2026-10-26): a button's
  chord fires whether the tree or the pane holds focus, because the
  button is on screen either way. What is printed is still the whole
  contract — it just lives in two places now: `strip.py` holds the
  TREE's commands (navigate, expand/collapse, ⏎ edit, `^r`, `^.`,
  `^n`, `^q`), and the three bars hold the file's (`^o` `^x` `^y` `^DEL`
  by letter, every kind action by position). The one exception is a
  sub-form that owns focus — a wizard, an import input, the path input —
  which confines the keys to itself until you save or esc.

## Interaction model: focus moves along a path

Nick's core mental model, revised 2026-10-26 (`notes/mockups/always-
available-actions-3.txt`). It used to be a chain of command — each view
controlling the view beneath it, focus crossing a view boundary to reach
anything. Using it taught him the cost: every action needed a ⏎ to enter
details and an esc to leave, two keystrokes that "don't connect to my
mental model of what I'm doing — I visualize them almost as keys
modifying the action I intend."

So the views stopped being rooms you enter. **Focus is ONE element at a
time, it moves between ADJACENT elements with the arrow keys, and the
actions are available from wherever you are.** The chain survives as the
shape of the path, not as a wall between views.

```
   ╭─ the path ────────────────────────────────────────────────────────╮
   │                                                                   │
   │   ┌─────────────┐                                                 │
   │   │ path input  │  ^/ from the tree · esc or ⏎ leaves             │
   │   └──────┬──────┘  (it owns its keys while it has focus:          │
   │          │          typing a path fires no actions)               │
   │       ^/ │ esc                                                    │
   │   ┌──────▼──────┐                           ┌──────────────────┐  │
   │   │  tree view  │ ──── → or ⏎ descends ───► │  filename field  │  │
   │   │   (cursor)  │ ◄───── esc or ← ───────── └────────┬─────────┘  │
   │   └─────────────┘                                 ↑↓ │            │
   │     HOME BASE                              ┌────────▼─────────┐   │
   │     ↑↓ rows · → open/descend                │   the fields    │   │
   │     ← collapse/ascend · ⇥ fold              └────────┬────────┘   │
   │                                                   ↑↓ │            │
   │                                            ┌─────────▼────────┐   │
   │                                            │   a BAR = one    │   │
   │                                            │   row: ←→ within │   │
   │                                            └──────────────────┘   │
   ╰───────────────────────────────────────────────────────────────────╯

   and from ANY of those, every printed chord fires its action:

        the strip ────────► the TREE's commands  (↓↑ · → · ← · ^←
                                                  · ⏎ · ^r ^. ^n ^q)
        ^s Save ──────────► the Contextual bar — what the STATE offers
        ^o ^x ^y ^DEL ───► the File bar — what every file offers
        ^1 … ^9 ─────────► the Actions bar — what this KIND offers
                            (⌥1…⌥9 under tmux: ^N cannot cross it)
```

What is printed works, and what works is printed — the contract is
unchanged, but it now lives in TWO places, because the file commands wear
buttons that are on screen from the tree: **the strip speaks for the
tree, each bar speaks for the file.**

Two properties make "always available" safe, and they are not optional:

```
   ^3 pressed here ──┐
                     │  the TARGET is the tree's cursor, captured at the
   ↓ (cursor moves)  │  KEYPRESS — never the pane's 150ms-debounced copy
                     │  of it. (That cost a ^DEL the wrong row in session
                     ▼  9; always-available actions would hand the same
   …fires on the row    bug to all ~30 actions, most of which WRITE.)
   it was pressed on

   ^3 pressed while the bar is still being built:
        ┌──────────┐   buffered    ┌──────────┐   resolved against the
        │ keypress │ ───────────►  │  queue   │ ─ bar of the row it was
        └──────────┘  (depth 4)    └────┬─────┘   pressed on, once the
                                        │         pane says it settled
                 DetailsView.Settled ───┘         (read in AND every
                                                   button probe answered)
```

Consequences that follow from the model (don't break them):

- **Every descent is one step.** → or ⏎ on a file goes to the filename
  field; → on a folder opens the folder (its children ARE the next step).
  esc or ← comes back up. Nothing crosses two links at once.
- ↑↓ move a ROW at a time, and a BAR IS ONE ROW, entered at its first
  button (`DetailsView._nav_rows`). ←→ move inside a row. Getting past
  nine converts costs one keystroke, not nine.
- Within details: filename field first, inputs immediately editable on
  focus (cursor at end, nothing selected).
- Action methods (album art today): compact buttons under the target,
  left→right; ↓ from the field above reaches them as one row. Their
  results feed the same pending/✓/save flow.
- Focus lockdown survives and is the ONE exception to "always
  available": a focused sub-form (wizard, import input, plan form)
  confines ↑↓ and chords to its own controls (`_focus_scope` /
  `_nav_items`) — leave by saving or esc. The path input is the same
  rule one level up.
- Two actions take focus on purpose: a plan preview lands on its Apply
  button, and a wrap (video folderize, new folder) descends into the new
  thing's rename field.
- Bulk editing rides the same path: the browser's *selection* (shift
  range, or an album-like leaf folder ≡ its writable children) is what
  descends into details, and a chord captured on the FOLDER resolves
  against the bulk form it opens (`DetailsView.showing`). The bulk form
  writes only ✓-marked fields, to every file. Divergent values show a
  `(mixed)` placeholder; a mixed field emptied back out returns to
  "leave every file alone."

## Architecture rules

1. **Engine/frontend split.** All logic that isn't rendering lives in
   IO-free modules (no print, no widgets) that emit dataclass events from
   generators; the TUI is a thin renderer. Proven pattern:
   `mediasmith-v1/lib/engines/subtitle_sync.py` + its Textual frontend.
   Engines with empirically-tuned policy (subtitle sync — see its
   DEBUG_NOTES.md) get ported, not rewritten.

2. **The details pane is composed ONCE** — one hidden panel per file kind;
   selection changes only swap values and visibility. Never rebuild it with
   `remove_children()` per selection: a cancelled removal can leak
   `CancelledError` into the app's message pump, which Textual treats as a
   silent quit. This was a real, reproduced crash in the prototype.

3. **`textual-image` is imported at module top, before the App starts.**
   It probes the terminal for cell size at import; probing a live Textual
   terminal races user keystrokes and killed the prototype
   (ZeroDivisionError mid-browse). Guard the import; a failed probe
   degrades to images-off, never to a dead app. Keep an `--images
   auto|halfcell|unicode|off` flag for A/B and tmux.

4. **NAS performance is a feature, not an optimization.** The library
   lives on SMB (`/Volumes/Room of Requirement`); Music Library has ~3,000
   entries. Rules learned in v1 (see `mediasmith-v1/lib/pathsmith.py`):
   - list directories with `os.scandir` and DirEntry type info — never
     one `stat` per entry (7.7s vs 0.01s, measured);
   - cache listings for the process lifetime, keyed by the directory's
     mtime signature — revisits cost one stat, staleness is impossible;
   - debounce highlight-driven file reads (~150ms) — and debounce TYPING
     just as hard: a path keystroke that re-roots the tree is a whole
     directory read (2026-08-22);
   - anything slower than a tag read (ffprobe, network) runs in a thread
     worker and fills in late; verify the selection hasn't moved before
     applying the result;
   - **no filesystem call belongs on the event loop, cached or not.** A
     cache HIT still pays the mtime `stat`, and a sleeping SMB disk
     answers a stat in seconds — long enough to freeze the whole TUI,
     which is exactly how Nick lost a session (2026-08-22). `fs` exposes
     an async front door for this: `alist_dir`, `acached_children`,
     `ais_dir`, `anode_type`. The plain functions are thread-only.
   - the DETAILS read obeys the same rule since 2026-10-26.
     `adapters.resolve` (kind + album-folder probe + `read_details`, one
     pass) runs in a worker and its answer is cached — bounded, keyed by
     PATH, never by an mtime signature, because validating one is a stat.
     The cache is invalidated by the WRITER instead (every write in
     `adapters` forgets its own path) and by `^r`, which drops both
     caches. `adapters.peek` is the only read safe on the event loop: it
     never touches the filesystem. A descent onto the row already shown
     therefore costs nothing — that duplicate synchronous read was the
     "<1s delay entering details view" Nick complained of.

5. **Every color lives in `mediasmith/theme.py`** (Nick's palette,
   todo-4, four states since 2026-10-30: focusable / triggerable /
   focused / traversed). CSS holds only STATE — which token applies
   when. Never hardcode a hex or named color anywhere else; add a token
   instead, INCLUDING the ones Textual would derive for you: `$surface`,
   the Input placeholder grey and the Tree's guides were each a colour
   on screen that Nick could not reach from theme.py, and
   `test_every_colour_on_screen_comes_from_the_theme` now fails if one
   returns. Chord colors inside button labels are markup, not CSS.

   **A Style's colors are not what the terminal paints.** `reverse`
   (SGR 7) tells the TERMINAL to swap a cell's two colors, so a focused
   button styled `focused-fg on focused-bg` reached Ghostty as orange
   text on the canvas — while every headless check read
   `fg=#1b1b1b bg=#ffa62b` and passed, because a render dump reports
   `reverse` as a FLAG beside the colors rather than applied to them.
   Textual's `$button-focus-text-style` defaults to `"b reverse"`;
   theme.py overrides it. For anything that measures right and looks
   wrong, drive the app in a real pty and read the escape codes it
   writes (`tests/fuzz.py` has the pattern) — that is the only view
   that includes the terminal.

## The action pattern cookbook (2026-07-11, revised 2026-10-26)

Contextual actions are standardized; **do not invent a new shape for a
new feature — copy one of these.** Worked examples live in commits
830bad9 and 5591410; per-feature briefs in `notes/claude/handoff.md`.

Adding any action, end to end:

1. `Action("name", "Word")` appended to `PANE_ACTIONS` (details.py).
   A kind action needs NO key: the Actions bar is positional, so it
   answers to `^1…^9` by where it prints (`^N` locally, `⌥N` under
   tmux — `actions.chord_prefix`). Words are capitalized and the chord
   is NOT spliced into them any more: one shape for every button,
   `^3 Fetch Subtitles` (`actions.action_markup`). Name the bar with
   `bar=CONTEXTUAL` or `bar=FILE` only for something that belongs to
   the pane's STATE or to every file; those two bars keep letters,
   and a letter must never work without being printed. Note anything
   Nick should rename in `notes/qa/todo-2.md` (the active QA ledger).
   Never use `actions.RESERVED_KEYS`. Input-eaten chords are fine on
   buttons: `FieldInput.on_key` forwards a chord to a visible button
   before Input can eat it.
2. A visibility rule in `_sync_pane_bar` — every bar is composed ONCE
   with the full palette; context only shows/hides, and one `names`
   set fans out to all three. Expensive detection runs in a worker and
   fills in late; if it puts a BUTTON on the bar, register it in
   `DetailsView.BUTTON_PROBES` so `settled` waits for it — a probe
   that lands late renumbers every button to its right, and a
   positional chord must never move under a finger already on its way
   down (Nick, 2026-10-26).
3. An `action_<name>` handler. Chords fire from EITHER view
   (`App.on_key` → `_chord` → `DetailsView.action_for_key`, filtered
   by `_focus_scope`), so the handler's target comes from the app's
   capture, not from focus: it acts on the row the cursor was on when
   the key went down. Guard by kind/state, never by focus.
4. Slow work in `@work(thread=True)` + `call_from_thread`; check the
   selection hasn't moved before applying results.
5. Filesystem products: refuse-overwrite everywhere (no silent
   clobbering, no prompts); post `FileCreated(path)` /
   `FolderChanged(path)` so the tree re-lists in place.
5b. Long work reports through ONE toast, not a stream of them
   (progress.py, 2026-08-22): `self.job(key, title, message)` raises it,
   later calls replace its text, `done=True` releases it to fade. The
   key is the title where a job can't overlap itself, title+path where
   it can. One-shot messages — refusals, guards, validation — stay
   `self.notify`.
6. Options-before-action ("wizard"): an inline div toggled under the
   fields (art-path row is the exemplar; image-resize and subtitle-
   shift follow it). **There are NO MODALS** (Nick, 2026-10-26). The app
   had exactly two, both destructive forks mid-write whose answer could
   not be inferred — save/discard/keep-editing, and a folder that
   already exists under a different casing — and both are now QUESTIONS
   on the Contextual bar: `DetailsView.ask(choices, decided, prompt)`
   swaps the bar's buttons for the answers, focuses the first, locks
   ↑↓/←→/chords to that bar until one is pressed, and puts focus back
   where it was. Any explanation rides a toast; the buttons are the
   question. A new fork of that shape uses `ask`, never a screen.
6b. Anything the user's keypress WRITES says so when it lands — a
   silent success reads as a dead key (`^s` acknowledges through the
   same toast the converts use, 2026-08-25).
7. Multi-file plans (folderize, multi-artist): engine builds a
   dataclass plan → pane previews it → `apply`/`cancel` own the bar;
   esc from the tree cancels.
8. New chords go into `tests/fuzz.py` KEYS; network code honors
   `MEDIASMITH_OFFLINE` (the fuzz gate presses everything).

Run the fuzz gate **from a snapshot copy** of the repo (children
re-import the package each seed; live edits corrupt the run):

    rsync -a --exclude .git --exclude .venv --exclude __pycache__ \
        ~/code/mediasmith/ /tmp/ms-snap/ &&
    cd /tmp/ms-snap && ~/code/mediasmith/.venv/bin/python tests/fuzz.py

A death with no crash.log and no "wedged" line = silent exit; re-run
that seed alone before assuming regression (seed 7 died once under
load, 2026-07-11, then survived 17 re-runs), and keep the pty output
of any dying run.

## Testing policy

Test-driven, calibrated by layer — this replaces Nick-as-only-QA:

- **Logic and adapters: test-first.** File-kind detection, metadata
  read/write adapters, path completion, cache invalidation, batch rules —
  pure pytest, fast.
- **Interaction: Pilot tests with each feature.** Textual's `run_test()`
  drives keypresses and asserts state ("space marks", "up from top row
  focuses path bar"). Written alongside the feature, kept as regression.
- **Visuals: snapshot-freeze after design settles** (pytest-textual-
  snapshot). No test-first for look-and-feel; don't punish iteration.
- **Fuzz harness: first-class, non-negotiable.** Random-keypress stress in
  a real pty (N seeds × ~75s, zero deaths required). Both prototype
  crashes were input races that only this caught — no unit test would
  have. Port the harness from the v1 session pattern; run it before
  declaring any slice done.

## Roadmap (thin slices, Nick QAs each pass)

1. **File browser + read-only details.** ✅ Includes the NAS
   cache/debounce work and the metadata-read adapter layer.
2. **Editing** — ✅ audio tags + epub metadata + rename + album art
   (path entry and iTunes-API fetch, in `artfetch.py`); ✓-mark write
   manifest; the save question (a ConfirmSave modal until 2026-10-26).
3. **Engine actions** — in progress via notes/claude/todo-*.md (the
   active queue) + notes/claude/handoff.md (briefs). Shipped
   2026-07-11: the action-button pattern, book convert/extract-cover/
   create-opf, folderize; later that day the flagship subtitle port
   (subsync.py + get/clean/shift/watch — the shift div is the wizard
   exemplar) and fix-multi-artist (plan previews share one
   apply/cancel pair now). notes/claude/proposals.md holds the
   search + Move designs (both resolved). Shipped 2026-07-15: video
   container + posters (#6), omnibus splitter (#11), Move, the logo;
   session 2 shipped the image slice (#8/#9 rename/convert/resize/
   rotate) and resolved the key-space question — CONTEXTUAL REUSE,
   see QA-TODO and actions.ActionBar.set_visible — the folder slice
   (#10 rename/new/trash — Finder chords ⌘⇧N/⌘⌫, send2trash), and
   standardize-formatting #12 (v1 extractors verbatim; the rebuild
   now keeps metadata + cover), sort #12b (Nick's spec: wrap a
   book's files into "Author Sort - Title/" — the fourth plan-shaped
   action), and video→gif #13 (third wizard div; _nav_items
   generalized). The fuzz harness write-jails its child and keeps pty
   on death; its first real kill (ConfirmSave double-dismiss) is
   fixed (see QA-TODO). Session 3 (2026-08-12, Fable — todo-4/5, log
   in notes/claude/handoff-fable.md): terms-of-art refactor
   (PathInput/DetailsView/Selected/BulkSelected…), the TreeView
   container (path input inside the tree pane), the color theme
   (theme.py — rule 5), ONE state-driven Command Strip (strip.py,
   responsive wrapping), cut/copy/paste as tree commands, the
   Button Refactor (todo-4 words/keys/order; reserved-chord
   substitutions logged in notes/qa/todo-2.md), view-scoped chords,
   and the sub-form focus lockdown. Session 5 (2026-08-22, Opus —
   Nick's four asks, all logged in notes/qa/todo-2.md): the video
   form's field order; "open" (^o) as the universal SECOND button on
   every file kind, generalized from video's old "watch" (which cost
   "write opf" its ^o → ^w); video folderize (videofolder.py — wrap a
   video into a folder named after its filename, sidecars and art
   riding along, no preview, single-epub sort's shape); and the video
   poster shown in the pane like album art, with the poster ladder now
   in posters.find_poster. Same session, two bugs Nick hit: subliminal
   discovery (a Homebrew keg reaches its deps through .pth files —
   site.addsitedir, never sys.path.insert) and path-input navigation
   (LibraryTree.anchor expands a directory cursor). Session 6
   (2026-08-22, Opus — logged in notes/qa/todo-2.md): three shell-outs
   retired ahead of the distributable-binary question. subliminal is a
   pyproject dependency instead of a Homebrew keg spliced in with
   site.addsitedir (import_subliminal survives only as the test seam);
   ffprobe is replaced by container.py (mutagen ©nam for mp4/m4v,
   enzyme EBML for mkv — .avi/.mov unhandled on purpose, 0 of 71
   sampled library files carry a title tag); and details.launch is
   cross-platform. ffmpeg (gif), alass, and Calibre convert remain
   external and are the irreducible three. Session 7 (2026-08-22, Opus —
   logged in notes/qa/todo-2.md): the SMB freeze. Every filesystem probe
   the Path Input made ran on the event loop (`parse_view`'s `is_dir`
   and the suggester's listing, both PER KEYSTROKE), and each keystroke
   re-rooted the tree on top of that — so a spun-down NAS didn't make
   mediasmith slow, it made it stop. Fixed by rule 4's new clause: `fs`
   has an async front door, typing is debounced, matches are CachedPaths
   (free `is_dir`), the suggester sits out when unfocused, and
   `_apply_restore` waits on Textual's load queue under a timeout so an
   orphaned queue degrades instead of wedging the tree's message pump.
   Same session, five more of Nick's asks: ONE TOAST PER JOB
   (progress.py — a running job owns its toast, updates it in place, and
   only `done=True` lets it fade; every long action is converted, and
   one-shot refusals stay plain `notify`), a poster search that scores
   results instead of taking TMDB's first (primary_release_year, title
   grading, the raw filename as a last query — a remake no longer loses
   to the famous original), video chord moves (^folderize, fetch
   s^ubtitles), the poster staging folder renamed to
   ~/Downloads/Mediasmith, and FOLDERIZE FROM THE TREE on ^f — the
   first action reachable from both views, printed on the tree strip
   only while the selection offers one. Session 9 (2026-08-25, Opus —
   logged in notes/qa/todo-2.md): CASE-BLIND FILESYSTEMS. APFS and the
   SMB share fold case, so `The Matrix/` and `the matrix/` are one
   directory with one spelling and `mkdir` hands back whichever is
   already there — which cost a video folderize both the wrapper folder
   and the video (moved into itself), made audio folderize renumber
   files that were already in place, and blocked the action Nick tried
   to run. casing.py is the answer: the plan stays case-SENSITIVE, a
   second folder is made where the volume allows one, and otherwise the
   existing folder is renamed into the wanted spelling through
   ConfirmCaseRename (keep contents / trash them / cancel) — wired into
   all four wrapping actions. Same session: ^DEL takes the TREE's
   cursor instead of the pane's debounced copy of it (a delete within
   150ms of an arrow key hit the previous row, or nothing at all) and
   lands the cursor on the row that slides up into the gap, ^s
   acknowledges its write, and every action button prints a POSITIONAL
   chord beside its letter one (^1…^9, pane bar first — Nick's A/B
   before deciding on a refactor). Measured, don't re-derive:
   ctrl+digit CANNOT cross tmux — only ^1 and ^9 survive, the rest
   collapse into their C0 codes (^3 IS escape, ^7 is the app's ^/, ^8
   is backspace) whatever `extended-keys` says — so ⌥+digit is wired
   up beside it, arriving either as `alt+<digit>` or as the macOS
   Option glyph (¡™£¢∞§¶•ª), which is what Ghostty types and what
   tmux's ESC+digit decodes to. Session 17 (2026-09-16, Opus — logged
   in notes/qa/todo-2.md): IMAGE TRACE, Illustrator's feature on potrace
   (trace.py). Illustrator's control names and scales outside the
   engine, potrace's inside it; every control a ←→ stepper; the fourth
   wizard div, and the first that takes over its panel — pane bar,
   filename, and size rows hide so the picture fills the details view,
   re-traced at full resolution and drawn by potrace's PGM backend at
   the picture's exact pixel size (`images.cell_pixels`). potrace is
   the fourth external tool; the pure-Python port was measured 30–180×
   slower and turned down (todo-binary.md). Session 18 (2026-09-29,
   Opus — logged in notes/qa/todo-2.md): ILLUSTRATOR RESCUE
   (illustrator.py). An .ai saved with PDF compatibility is two
   documents in one container, and Illustrator writes only the ARTBOARD
   into the PDF half — so work parked beside the artboard is invisible
   to every non-Adobe reader, and enlarging the artboard reveals
   nothing. The module reads the other half (`/AIPrivateData`, inflated
   from `%AI12_CompressedData`) and rewrites the whole canvas as a PDF
   or SVG beside the source. Two constructs decide whether the product
   looks like the original, both measured against Illustrator's own PDF
   half: a run of subpaths sharing paint is ONE nonzero fill (that is
   what makes compound holes work), and a gradient object inside a
   group is a CLIP the gradient paints through, not a fill on top of
   it. Miss the second and a gradient logo comes back as a black
   silhouette. New kind: VECTOR (.ai/.eps/.svg/.pdf), the seventh
   panel; the canvas probe is a worker because `read_details` was on the
   event loop and the private data is ½ MB to inflate. Session 20
   (2026-10-26, Opus — logged in notes/qa/todo-2.md): ALWAYS-AVAILABLE
   ACTIONS, the revision above, built in six slices off
   `notes/mockups/always-available-actions-3.txt`. Slices 0–3a are in:
   (0) the read moved off the event loop into `adapters.resolve` +
   a bounded cache invalidated by the writer, which is where the "<1s
   entering details" actually was — a duplicate synchronous read of the
   file already on screen — plus `DetailsView.settled`, the signal the
   rest hangs on; (1) the one pane bar became three (Contextual/File/
   Actions), labels lost their spliced letters and gained capitals, and
   the Actions bar went positional-only; (2) chords fire from the tree,
   targeted at the cursor captured AT THE KEYPRESS and buffered until
   the bar settles, with `^f`-folderize's special case retired and the
   strip re-split; (3a) `→` descends on a file and `↑↓` walk a ROW at a
   time, a bar being one row; (3b) the chrome — no pane borders, six
   `element-*` tokens replacing the idle/focus PAIRS, a field's label as
   its grey/PRIMARY chip (`FieldLabel`), the same chip on every tree row
   (`tree--node-chip`), a labelled filename sharing the panel's column,
   and the `^/`→`ESC` chip inside the path box; (4) the micro-modals —
   both ModalScreens DELETED, a destructive fork is now a QUESTION on
   the Contextual bar (`DetailsView.ask`, cookbook rule 6).
   Then slice 5's CONNECTOR, over three more rounds of Nick's notes
   (todo-6): `Spine` draws the centre line and `LibraryTree` the run out
   of the cursor, and together they show the PATH — the line between the
   selected row and the focused element wears `traversed`, carries only
   its own arms (`╮ ╯ ╰`, never a T or a +), and reverts to `path-fg`
   when nothing in details holds focus. theme.py is now a four-state
   model (`focusable` / `triggerable` / `focused` / `traversed`) with the
   idle-focus PAIRS deleted; buttons are chained with `──` links
   (`BarLink`); the artwork branches off the line (`ArtSpine`) and leads
   down into its own method bar; and a braille spinner stands where a
   value or a still-probing button group will appear. `Spine.restub()`
   exists because the first version walked the DOM per rendered LINE and
   doubled the suite's runtime — a widget that reads the layout must read
   it once per redraw. The tree's own vertical scrollbar is OFF
   (`scrollbar-size-vertical: 0`): its track cells are spaces with a
   background, so they erase the run passing under them.
   What remains of slice 5 is the fixed-pane scroll architecture, which
   is what would give the tree its scrollbar back at the viewport edge,
   plus one deferred bit of chrome: labels beside the cover/poster
   IMAGES (the art has one now — the image sizing inside a labelled row
   rides a fragile `width: 1fr`).
   ⬅ you are here
4. **Batch operations.** Partially done ahead of schedule: shift-range
   and album-folder bulk editing shipped (2026-07-10); space-marking +
   batch bar still to come as a third gesture over the same selection
   set (`LibraryTree._selection_paths` / `DetailsPane.preview_bulk`).
5. **Responsive/mobile** — narrow-width breakpoints for tmux-from-phone;
   tree-first two-step flow on narrow screens.

Session 22 (2026-10-30, Opus — four rounds of notes in
`notes/claude/todo-6.md`, logged in `notes/qa/todo-2.md`): the connector
and the four-state theme above, plus three things that are not chrome.
`prefs.py` keeps the switches that outlive a session (`^.` today) in
`~/.config/mediasmith/prefs.json` — a temp-file-and-rename write, and
defaults whenever the file is unreadable; the test suite and the fuzz
child both get `XDG_CONFIG_HOME` pointed somewhere else, because a test
run must not rewrite Nick's own switches. `update.py` is self-update for
the people Nick hands this to: a copy `uv tool install` owns asks the
remote once a day whether the commit in its `direct_url.json` has moved,
`uv tool upgrade`s itself, and says the new version runs next launch —
following the URL it was installed FROM, so SSH and HTTPS both work, and
refusing to touch anything that is not a uv-installed copy, so a
checkout is never altered. The repo being private is what stands between
that and a one-line install for a friend; that call is Nick's.

Distributable binary: `notes/claude/todo-binary.md` is the STANDING
ANSWER — what a binary buys, the four code blockers, the four external
tools that cannot be bundled (ffmpeg, alass, potrace, Calibre convert), and why
`uv tool install` keeps winning. Read it before re-deriving the question.

Session notes: `notes/qa/todo-2.md` is the ACTIVE QA ledger — what
awaits Nick's manual pass, chord renames, and parked UX decisions.
(`notes/qa/todo-1.md` is the prior session's, mostly cleared.)

## Environment facts

- Nick is a UX designer; expect many UI iteration passes. UX decisions are
  his; surface trade-offs, don't pre-decide aesthetics.
- Terminal: Ghostty (Kitty graphics protocol works). Remote use: tmux from
  phone (images need halfcell fallback there; persistence matters).
- Runtime: `uv` (PEP 723 inline deps or pyproject — pick when scaffolding).
- Media lives on the NAS under `/Volumes/Room of Requirement/AUDIO/…`, 
  `/Volumes/Room of Requirement/BOOKS/…`, and `/Volumes/Room of Requirement/
  VIDEO/…`; test media for the harness should be scratch copies, never the
  library.
- Long-term portfolio goal: browser demo via textual-serve + demo mode —
  keep engines runnable with scripted fake events (`--demo`) from day one.
