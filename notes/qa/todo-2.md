# QA to-do — todo-4/5 refactor (Fable session, 2026-08-12)

Everything from this refactor that needs Nick's eyes or renames after it
lands. (Named "todo-2.md" per your instruction during the session.)

## Reserved chords: what you asked for vs. what shipped

- [ ] Your Button Refactor spec assigned six reserved chords (^i ^c ^h ^m
      ^j ^z — terminal aliases for tab/interrupt/backspace/enter/newline/
      suspend). Per your call, the nearest safe letter stands in. Each
      line shows the full button text, spec → shipped:

      | kind        | button text          | spec | shipped |
      |-------------|----------------------|------|---------|
      | audio       | **im^port**          | ^i   | **^p**  |
      | video       | **c^lean subs**      | ^c   | **^l**  |
      | video       | **shif^t subs**      | ^h   | **^t**  |
      | epub + mobi | **conver^t to mobi** | ^m   | **^t**  |
      | epub        | **clea^n**           | ^c   | **^n**  |
      | image       | **convert to jp^g**  | ^j   | **^g**  |
      | image       | **r^esize**          | ^z   | **^e** (its old chord) |

      Plus the tree command: **cop^y** = ^y (you specced no key; ^c is
      reserved). Rename any of these — each is one letter in
      `details.PANE_ACTIONS` (or `strip.py`/`browser.py` for copy).

## Button refactor — judgment calls to confirm

- [ ] Chords are VIEW-SCOPED now: a Details button's chord fires only
      while Details view holds focus. Video/folder actions need ⏎ first
      (every kind is enterable via its rename form). The old
      "chords fire from the tree" behavior is gone per your Focus rules.
- [ ] Chords that Input eats (^a azw3, ^e extract, ^u upload cover,
      ^w webp/watch…) now FORWARD from a focused field when a visible
      button claims them — so ^a no longer homes the cursor on a book
      form, it converts to azw3. The macOS word/line nav (⌥-arrows)
      still works.
- [ ] Your per-kind lists order save first; audio's import/fetch stayed
      as the small bar under the album art (the action-method pattern),
      not merged into the bottom bar. Say so if you wanted one row.
- [ ] "sort" on a single epub is now labeled **folderize** (^f) per your
      spec; on a FOLDER it kept the word **sort** (^o) — your folder list
      didn't mention it, and renaming both would put two "folderize"
      buttons on one folder view (the audio folderize also lives there).
- [ ] "standardize" is now **clea^n** everywhere it appears — including
      the folder batch button (your spec renamed it under Epub only).
- [ ] The gif and resize wizards' apply buttons are **^save** per spec.
      While a wizard is open, ^s means the wizard's write, not the
      rename-form save (the wizard's bar wins the chord).
- [ ] Plan previews (folderize/sort/strip multi-artist/split omnibus)
      now take focus when they open — chords are view-scoped, so the
      preview lands focus on its apply button; esc cancels from there.

## Command strip & clipboard (todo-4)

- [ ] **Copy's chord is ^y, not ^c** — ^c is reserved (terminal interrupt /
      Textual's app-owned copy). ^y splices into "cop^y" on the strip.
      Rename if you prefer another letter (free letters in tree state:
      anything outside r . n x v / q).
- [ ] Paste CLEARS the clipboard, for copy as well as cut. Finder pastes a
      copy repeatedly; if you want that, say so and paste will keep a
      copy-clipboard alive.
- [ ] Copy-paste into the SAME folder is refused ("already here") like
      cut. Finder would make "notes copy.txt" — tell me if you want that.
- [ ] ⇥ still descends into Details (an ENT alias) even though the strip
      only lists ENT edit — kept as a hidden alias like ⇧← collapse
      level. Say the word and both aliases die.
- [ ] Narrow-mode flow change: ^/ no longer summons the path input while
      Details is focused/viewed (tree-only per your spec) — on the phone
      it's now esc, then ^/.

## Color theme (todo-4 "Color Theme Stylesheet")

- [ ] All colors now live in `mediasmith/theme.py` (your palette,
      verbatim); CSS holds only state (which token applies when). Nothing
      else in the app may name a hex — future Claudes included.
- [ ] Eyeball the scrollbar tracks: your spec says `transparent`; the old
      design matched them to each pane's background because a transparent
      track didn't always blend. If a track renders black, the fix is one
      token pair in theme.py (`scrollbar-track-*`).
- [ ] Idle-view dimming is now real: unfocused panes drop to grey-40 text
      / grey-30 borders per your palette. Verify readability on the NAS
      browse (SMB latency means you'll stare at idle panes plenty).
- [ ] Hidden files (dotfiles) now dim to the `node-hidden-fg-*` pair —
      this styling is NEW (they used to render like any file).
- [ ] Buttons: chord glyphs dim with the pane (grey-40), light to primary
      when Details view holds focus, flip to grey-90 on the selected
      (arrow-highlighted) button. The old focused-button look (orange bg,
      black text) is now primary bg / grey-90 text per your palette.

## Session 4 (Opus, 2026-08-13) — three fixes + one they turned up

- [ ] **Tree scrollbar inset.** The 1-cell gutter moved from the children
      (`PathInput` margin / `LibraryTree` padding) onto the `TreeView`
      pane as `padding: 0 1`. A child's horizontal margin costs EVERY
      sibling that width — Textual's vertical layout resolves `1fr`
      against the widest margin in the box — which is why the tree ran 2
      cells narrow and its scrollbar sat 3 cells off the border. Now 1
      cell each side; nothing else moved.
- [ ] **New color tokens** (theme.py): `node-hidden-selected-fg-focus`,
      `node-hidden-selected-fg-idle`, `node-selected-fg-idle` (all
      grey-10) and the scrollbar corner pair `scrollbar-corner-focus` /
      `scrollbar-corner-idle` (grey-10 — Textual calls that cell the
      ScrollBarCorner; its rule is `scrollbar-corner-color`).
      Two things to eyeball:
      · grey-10 fg on `node-selected-bg-idle` (grey-20) is a very dark
        row — that is what the spec asked for; say the word for a
        lighter token.
      · a hidden row is DIMMED by DirectoryTree's own component class,
        which fades any token toward the row behind it (grey-10 came out
        #684a20). The selected pair drops dim so the token lands exactly;
        unselected hidden rows still dim as before.
- [ ] **Arrow-key direction bug: it was a repaint, not a move.** Focus
      always moved correctly; `ActionButton.watch_has_focus` overrode
      Widget's without calling it, and Widget's version is what applies
      the `:focus` CSS — so the highlight only caught up on the NEXT
      keypress, which reads exactly like "the first press after a
      reversal keeps going the old way". Confirmed against a real pty
      (Pilot never saw it: it asserts focus, not pixels).
- [ ] **Fallout of that fix, needs your eye:** with the highlight now
      live, the selected button was rendering in the plain focused-pane
      pair, never the selected one — `DetailsView:focus-within
      ActionButton` (two type names) outranked a bare
      `ActionButton:focus`. The selected pair (primary bg / grey-90 text,
      per the palette) now applies. If you preferred the quieter look,
      that is one selector in app.py.

## Session 5 (Opus, 2026-08-22) — Nick's four requests

All four landed; each item below is what needs your eye.

- [ ] **Video form field order** is now embedded title / container /
      size / subtitles / posters, per your list (`details.py`,
      `panel-video`). Nothing else moved.
- [ ] **"open" is the new universal second button** (`^o`, every file
      kind: audio, video, book, image, and plain files). It is video's
      old **watch** button, renamed and generalized — same
      `details.launch` seam, same `MEDIASMITH_OFFLINE` guard so the fuzz
      gate doesn't spawn 100 players. A FOLDER does not get it: its ^o
      is the **sort** button, and one context may never show two
      buttons on one chord (`ActionBar.set_visible` asserts this).
      Say the word if you want folders to open in Finder — then sort
      needs a new letter.
- [ ] **^o cost two chords their letter** (both logged like the reserved
      substitutions above):

      | kind  | button text        | was | now     |
      |-------|--------------------|-----|---------|
      | epub  | **^write opf**     | ^o  | **^w**  |
      | video | **fol^derize**     | —   | **^d**  |

      Video folderize wanted ^o (your "open" took it), ^f/^l/^t are the
      subtitle suite, so "fol^derize" took ^d. ^d is an Input editing
      chord (delete-right); the button forwards it, as with the others.
- [ ] **Video folderize** wraps the video into a folder named after the
      filename minus its extension, exactly like a single epub's
      folderize: no plan preview, one move, then the video is revealed
      inside its new folder still editable. The button hides when the
      video already sits in a folder named after it.
- [ ] **What rides along with the video** (your call in-session:
      sidecars, not the video alone — a subtitle is only ever found as
      `<video stem>.srt` beside its video):
      · anything sharing the video's stem — `.srt`, `.en.srt`, `.nfo`,
        a poster folder named after the file;
      · when it is the folder's ONLY video, its art too: loose images
        and image-only subfolders (that is `posters.run`'s folder, which
        it names after TMDB's title, not after the file).
      Everything else stays put — in a folder of many videos a stray
      image belongs to no one in particular. `videofolder.py` docstring
      states the rule; change it there.
- [ ] **The poster now shows in the video pane** with its pixel
      dimensions under it, the album-art/book-cover treatment. Finding
      it moved into `posters.find_poster` (same ladder as above:
      `<stem>.jpg` → poster folder → loose art), so what the pane shows
      is exactly what folderize would move. The posters ROW prints a
      folder-relative name now (`Alien (1979)/a.png`) when the poster
      lives one level down.

### …and two more you turned up mid-session

- [ ] **"fetch subtitles" said subliminal wasn't installed when it was.**
      Homebrew's subliminal 2.7.1 keg reaches its dependencies through a
      `.pth` file (`homebrew_deps.pth` → the certifi keg), and only
      `site.addsitedir` executes those — `subsync.import_subliminal` was
      doing a bare `sys.path.insert`, so subliminal imported and then
      died on `certifi`. Every ImportError read as "not installed", which
      is why reinstalling and relaunching never helped. Fixed
      (`site.addsitedir`, added once per process). The message now names
      the real failure when the keg IS on disk — reinstall advice only
      when nothing was found.
- [ ] **Path input → tree now expands where it lands.** Committing a
      filtered path put the cursor on the folder but left it closed
      (`LibraryTree.anchor` expanded the CONTAINING directory only). A
      cursor that is itself a directory is expanded too now. Unfiltered
      Enter already behaved this way, which is why it looked
      inconsistent.


## Session 6 (2026-08-22, Opus) — three shell-outs retired

Context: Nick asked whether mediasmith could ship as a distributable
binary. It can, but a binary only removes the *Python* dependency, not
the *toolchain* one — so the prior question is how many external
commands can stop being external. These three could; ffmpeg (gif),
alass, and Calibre (convert) still cannot. See the session transcript
for the full triage.

- [ ] **subliminal is a real dependency now** (`pyproject.toml`), not a
      Homebrew keg spliced in at runtime. The whole discovery apparatus
      is gone — `find_subliminal_pythonpath`, `site.addsitedir`,
      `_SITE_ADDED`, `SUBLIMINAL_PYTHONPATH`. `import_subliminal()`
      survives ONLY as the test seam. This retires this morning's `.pth`
      fix and its two tests: the keg indirection they described no
      longer exists, so they were deleted with the machinery rather
      than left describing a dead path.
      **To verify manually:** fetch subtitles for a video that needs
      them, over the network. That path is monkeypatched in every test,
      so the suite cannot prove it. Provider discovery (stevedore entry
      points) resolves 12 providers here and `opensubtitles` loads.
- [ ] **ffprobe is gone** — replaced by `mediasmith/container.py`
      (`read_title`): mutagen's `©nam` atom for mp4/m4v, enzyme's EBML
      header for mkv. `adapters.probe_video_title` and
      `subsync.read_release_name` both delegate to it and are no longer
      slow — the worker thread around the first is now politeness, not
      necessity (10–50 ms over SMB vs ~1 s to spawn ffprobe).
      `.avi` and `.mov` are DELIBERATELY unhandled: measured against the
      library, 0/40 sampled .avi and 0/31 .mov carry a title tag at all,
      so ffprobe answered None for them too. Don't "fix" this without
      re-measuring; the docstring says so.
      **To verify manually:** the video pane's title row on a few mkv
      and mp4 files, and that subtitle matching still finds release
      names (the `ReleaseFound` event).
- [ ] **`open` is cross-platform** — `details.launch` branches
      darwin → `open`, win32 → `os.startfile`, else `xdg-open`, with
      child output to DEVNULL. It hardcoded `open` before, which was a
      latent bug for the tmux-from-phone/Linux case in roadmap 5. This
      stays a subprocess on purpose: every package that wraps it is a
      platform check plus a Popen, which is not worth a dependency.

Test additions: `tests/test_container.py` (7) and two `launch` platform
tests in `test_app.py`. `tests/fixtures/` holds four tiny synthetic
containers (~2 KB each), committed as files so the suite never needs
ffmpeg to *build* a fixture for the module whose point is not needing
ffmpeg to *read* one.


## Session 7 (2026-08-22, Opus) — the SMB freeze

Nick's report: navigating the Path Input straight to
`/Volumes/Room of Requirement/VIDEO/Sort/` **always** made him wait, and
once wedged the app hard enough that quitting was the only exit. Finder
makes him wait for the same disks to spin up — the difference is that
Finder is still a running program while it waits.

**What was wrong.** Every filesystem call the Path Input made ran on the
event loop, and each one is a network round trip that a sleeping SMB disk
answers in seconds rather than milliseconds:

| where | called | cost when the disks are asleep |
|---|---|---|
| `parse_view` (via `on_input_changed`) | `is_dir()`, once **per keystroke** | one stat |
| `PathSuggester.get_suggestion` | `fs.list_dir`, once **per keystroke** | stat + scandir |
| `on_input_submitted` | `is_dir()` then `is_file()` | two stats |
| `LibraryTree.anchor` | `cursor.is_dir()` | one stat |
| `ArtPathInput` / `CoverPathInput` `action_complete` | `fs.cached_children` | stat + scandir |

The cache did not save it: a HIT still pays the mtime `stat` that proves
the listing fresh, and that stat is the call that hangs. Worse, each
keystroke also *re-rooted the tree* — a whole `DirectoryTree` reload —
so typing a 40-character path queued 40 of them back to back with no way
to interrupt. And `PathSuggester` fires on every value write, not just
typed ones, so the tree's own path sync ran a listing **per arrow key**.

**What changed.**

- `fs` grew an async front door — `alist_dir`, `acached_children`,
  `ais_dir`, `anode_type` — and a third module rule: nothing in `fs` is
  safe to call from the event loop. Every widget goes through the
  `a`-prefixed wrappers; the plain functions are for thread workers.
- Typing is debounced (`DEBOUNCE_SECONDS`, the same 0.15 s the details
  pane uses): one re-root per pause, not one per character. The parse
  runs in a worker (`_show_typed`) and re-checks that the value has not
  moved on before it touches the tree.
- `PathInput._matches` returns `CachedPath`s, so every `is_dir()`
  downstream of a match is free.
- The suggester returns `None` when the input is unfocused — the ghost
  only renders with focus, so the listing was pure cost.
- `on_input_submitted` asks `fs.anode_type` once instead of `is_dir()`
  then `is_file()`: one stat, not two.
- `_apply_restore` waits on Textual's load queue under `LOAD_TIMEOUT`
  (30 s). A re-root arriving mid-drain can orphan the queue the restore
  joined to, and that join never returns — which is the hard wedge Nick
  hit. Timing out costs a cursor placement, not the session.

**What you'll see.** A `reading…` marker on the Path Input's border
while a read is in flight (`browser.READING`, right-aligned, in the
label token). It is the one aesthetic decision in this change and it is
yours to keep, restyle, or drop — the fix works without it.

**To verify manually** (do this with the NAS asleep, which is the only
state that reproduces it):
- [ ] Type a long `/Volumes/Room of Requirement/…` path into the Path
      Input. The app should stay alive the whole time — cursor moves,
      the strip redraws, esc works — and the tree should catch up once.
- [ ] Press esc mid-wait. It should return you to the tree, not queue
      behind the read.
- [ ] Arrow through a NAS folder. No listing should fire per row now.
- [ ] Confirm the `reading…` marker reads right to you, or say what it
      should be instead.


## Session 7, part two (2026-08-22, Opus) — five asks

### 1. One toast per job, held until the job ends

You ran `fetch subtitles` and `download posters` and thought both were
broken: nothing visible for ~5 s, because each message raised its OWN
toast and every toast had faded before the next one arrived.

`mediasmith/progress.py` is the mechanism. A **job** owns one toast for
its whole life: the first report raises it, every later report replaces
the text in place, and only `done=True` releases it to fade (8 s by
default). `DetailsView.job(key, title, message, …)` is the call site
shape; `key` is the title where a job cannot overlap itself
("folderize", "sort", "paste") and title+path where it can — subtitle
fetches, conversions, and gif renders run side by side on purpose and
each keeps its own toast.

Converted, top to bottom: get subs · download posters · convert · book
cover · standardize · paste/move · folderize (audio) · strip
multi-artist · split omnibus · sort · video folderize · every
produce-a-sibling action (gif, extract cover, write opf, image
convert/resize). One-shot messages — refusals, guards, "offline",
validation errors — stay ordinary `notify` calls: they are not jobs.

Textual 8.2.8 has no public "update a notification" API, so this reaches
into `Notification`/`Toast`/`ToastRack`. Every reach is guarded: with no
toast to update (a dismissed one, or `run_test`, which disables
notifications by default) it falls back to raising a fresh one and
nothing breaks. `tests/test_progress.py` pins the behaviour, not the
internals.

- [ ] **To verify manually:** fetch subtitles on a video that needs them
      and watch ONE toast walk through its phases. Same for download
      posters. Two fetches at once should be two toasts.
- [ ] The finished toast lingers 8 s (`progress.FINAL_TIMEOUT`) — say if
      that is too long or too short.

### 2. Poster search: the remake vs. the classic

`2017 — Ghost In The Shell.mp4` fetched the 1995 anime. Reproduced
against the live API, and it was three bugs stacked:

1. **TMDB's `year` matches ANY release date a film carries.** The 1995
   anime had a 2017 re-release, so it comes back for `year=2017` — and
   ranks FIRST, being marginally more popular. `primary_release_year`
   is the original release and returns the 2017 film alone. It is now
   the first query, with the broad `year` and then no year as fallbacks.
2. **`results[0]` was popularity order.** Results are scored now:
   title match (exact > containing > unrelated), then a matching year,
   then popularity.
3. **The narrowest query is not always the best one.** "2001 A Space
   Odyssey" parses as title "A Space Odyssey" + year 2001, and
   `primary_release_year=2001` answers with three NASA documentaries —
   the wrong film, but not an empty result, so the old "first non-empty
   wins" rule would have taken it. Every attempt now scores into one
   pool, and the raw filename is added as a last query.

Two parser fixes came with it:

- your `<year> — <title>` naming left the em dash welded to the title
  ("— Ghost In The Shell"); stranded edge dashes are trimmed now, and a
  title's own punctuation ("Airplane!", "WALL·E") is left alone;
- guessit is pinned to `type="movie"`, without which a numeric title
  suffix parses as season/episode ("Blade Runner 2049" → S20E49,
  "Ocean's 11" → episode 11) and the title comes back truncated.

Measured A/B over 13 filenames against the live API: the change fixes
Ghost in the Shell (2017) and The Thing (2011) — the same remake-loses-
to-the-classic shape — and regresses nothing. The common case still
costs ONE request; only a genuinely ambiguous name pays for the rest.

- [ ] Known miss, both before and after: `Ocean's 11 (2001)` finds an
      obscure 2019 film, because TMDB spells the Soderbergh one
      "Ocean's Eleven" and numeral-vs-word is a different problem.
      `2001 — Ocean's Eleven.mkv` resolves correctly. Say if that is
      worth chasing.

### 3. Video chords

- **`fol^derize` → `^folderize`** (was ^d).
- **`^fetch subtitles` → `fetch s^ubtitles`** (was ^f, now ^u).

- [ ] The audio-folder folderize button still reads `fo^lderize` (^l) —
      you asked about video files only, so I left it. It is now the one
      folderize not on ^f, which also makes the tree's ^f (below) read
      oddly there. Say the word and it moves; nothing collides in the
      folder context.

### 4. Posters stage to `~/Downloads/Mediasmith/`

Was `Videosmith` (the v1 tool's name). One constant,
`posters.STAGING_DIR`. Existing files under `~/Downloads/Videosmith/`
are NOT migrated — move or delete them yourself.

### 5. Folderize from Tree View, on ^f

`^f` with the tree focused fires whichever folderize the selection is
showing — a video's, a single epub's, or an audio folder's. It reads
the composed pane bar rather than re-deriving the rules
(`DetailsView.folderize_action`, matched on the button's WORD), so the
tree can never offer a folderize the details pane would not.

The strip prints `^f folderize` in the tree state only while one is on
offer, which keeps the todo-4 contract intact — a key on the strip
works, a key off it does not. That made the tree strip dynamic:
`strip.tree_state(folderize=…)`, resynced from `_sync_pane_bar` so a
late probe result reaches the strip too.

- [ ] It sits after `⏎ edit` on the strip — both act on the node the
      cursor is on. Move it if you want it grouped elsewhere.
- [ ] This is the first action reachable from both views. Chords are
      otherwise view-scoped (todo-4); if you want more of them mirrored
      into the tree, the shape is `App.on_key` + a `*_action()` lookup
      on DetailsView, and each one has to earn its strip entry.

### Session 7 gates

Full suite **425 passed**; fuzz gate **0 deaths / 6 seeds** (from a
snapshot, per CLAUDE.md). No new chords for `tests/fuzz.py` KEYS — ^f
and ^u were already in the press pool, which is why the tree's ^f and
the moved subtitle chord were exercised by the gate as they landed.

New test files: `tests/test_progress.py` (7 — one toast, updated,
released, two jobs at once, a dismissed toast, a severity change).
Additions: `tests/test_posters.py` (+9: the search ladder and the
parser fixes), `tests/test_app.py` (+9: the NAS liveness ticker, the
debounce, the `reading…` marker, tree folderize + its strip entry, and
one toast end-to-end through download posters), `tests/test_fs.py`
(+5: the async front door).


## Session 8 (2026-08-22, Opus)

### 6. ← collapses the whole subtree

`←` on an expanded folder now calls `TreeNode.collapse_all()` instead
of `collapse()` (`LibraryTree.action_collapse`). Pressing `←` then `→`
on the same folder is a reset: the children come back as a plain list,
never in whatever shape they happened to be in before.

- [ ] `^←`/`⇧← collapse level` is unchanged — it still flattens the
      cursor's whole SIBLING level, where `←` only touches the cursor's
      own subtree. If `←` now covers enough of that ground for you, the
      level chord is a candidate for retirement.

Regression: `tests/test_app.py::test_collapse_resets_child_expansion`.

### 7. The selected node wears a pad cell on each side

Buttons print one cell of padding around their label; the tree cursor
now does the same. No text moves — both pads are cells that were
already on the row, restyled:

- the LEFT pad is the space the last guide column ends with (the cell
  adjacent to the rightmost box character): `render_line` appends
  `guide[:-1]` in the guide style and `guide[-1:]` in the label style;
- the space between the icon and the name takes the label style too
  (`render_label` restyles the icon prefix's last cell);
- the RIGHT pad is a space appended past the name — it lands where only
  row background was, so nothing shifts there either.

The ICON is inside the run as of 2026-09-01 (it shipped outside it, and
the emoji cells read as a black gap mid-highlight — that was our styling,
not a limit of emoji: a terminal paints the cell background from the SGR
attributes and draws the glyph on top). `render_label` now stylizes the
prefix from cell 0, so the block is continuous: pad · icon · name · pad.
A shift-marked row reverses its left pad with the label so its block
starts in the same column.

Regression: `tests/test_app.py::test_selected_row_wears_a_pad_cell_on_each_side`.


## Session 9 (2026-08-25, Opus) — your four asks

### 8. `^DEL` sometimes didn't delete (found, fixed)

Reproduced, no steps needed: **the pane's copy of the highlight is
150ms stale.** Details view learns the cursor through the preview
debounce (`DetailsView._queue_preview`), and `^del` read its target from
`DetailsView.path` — so a `^del` pressed within 150ms of an arrow key
acted on the row you just LEFT. Two faces, both of them "it didn't
delete this file":

- the previous row still existed → it was trashed instead, and the tree
  jumped to the parent, so the file you meant sat there untouched;
- the previous row was already gone (you deleted it a moment ago, or
  renamed it) → `path.exists()` was False, `_delete_target` returned
  None, and the keypress died in silence.

Fixed at the source: `^del` now takes the TREE's highlight
(`LibraryTree.cursor_path()`, passed in by `App.on_key`) — the tree is
what the strip's `^DEL` belongs to, so its cursor is the target. The
`exists()` stat moved off the event loop into the delete worker (rule 4),
where a missing file reports "already gone" instead of nothing.

**Where the cursor lands after a delete** (your follow-up): Finder's
rule — the sibling that slid up into the dead row's place, or the one
above it when the dead row was last, or the parent when it was an only
child (`LibraryTree.cursor_to_gap`). It used to climb to the parent
every time, which is what made a second `^DEL` mean the whole folder.
Details follows the new cursor, so the pane shows the next file.

- [ ] A shift-range selection still has no single target, so `^DEL`
      leaves it alone — but it now SAYS so ("nothing to delete —
      highlight one file or folder") instead of swallowing the key.
      If you want a range delete, that is batch work (roadmap 4) and a
      different confirmation question.
- [ ] A second, older reason a `^DEL` can do nothing, and this one is
      by design: it is a TREE command, so it is inert while Details view
      holds focus (after `⏎`). The strip is honest about it — `^DEL
      delete` prints in the tree state only — but if your muscle memory
      says delete works from the pane too, that is a decision to make,
      not a bug to fix. Mirroring it is the same shape as the tree's
      `^f` (an `App.on_key` case plus a `STATE_DETAILS` entry).

Regressions: `test_trash_takes_the_row_the_tree_highlights`,
`test_trash_says_so_when_there_is_no_single_target`, and the three
cursor-landing cases (`..._takes_the_dead_row_s_place`,
`..._falls_back_to_the_one_above`, `..._falls_back_to_the_parent`).

### 9. Folderize is case-sensitive, and asks before respelling

Your report was the visible half of something worse. On APFS (and the
SMB share) `The Matrix/` and `the matrix/` are ONE directory with one
spelling, and `mkdir` silently hands back whichever spelling is already
there. Three bugs came out of that, all fixed:

1. **Data loss (video folderize).** Wrapping `The Matrix.mkv` beside an
   existing `the matrix/` folder saw that folder as a companion (rule 1
   matches on the lowered stem), and moved it into itself. On a case-
   insensitive volume that orphans the folder AND the video that had
   just been moved into it — I reproduced an empty directory with both
   files gone. `videofolder.companions` now compares with
   `casing.same_dir` (samefile), so the wrapper is never its own cargo.
2. **Endless renumbering (audio folderize).** A file already sitting in
   `the beatles/abbey road/` collided with ITSELF at the tagged casing,
   so `_free_name` renamed it `01 Song (1).mp3` — and folderize stayed
   on offer, adding another number every run. A candidate that IS the
   source file is no longer a collision.
3. **The refusal you hit.** Nothing could ever create the second
   folder, so the action either half-failed or silently used the old
   spelling.

The rules now, per your spec: the plan stays case-SENSITIVE (a folder
spelled differently is not the folder your tags/filename ask for, so
the button is offered); a second folder is made wherever the filesystem
allows one (case-sensitive volumes never see the modal); otherwise the
existing folder is RENAMED into your casing, gated by the modal you
asked for — **Rename, keep contents** (`k`) / **Rename, delete
contents** (`d`) / **Cancel** (`esc`).

Wired into all four wrapping actions: audio folderize, video folderize,
folder sort, and a single epub's folderize. The engine is
`mediasmith/casing.py` (clash detection, the two answers, an SMB-proof
case-only rename that verifies itself through a temp name).

- [ ] "Delete contents" sends them to the **Trash**, not to oblivion —
      Trash is the undo, same as `^DEL`. Say if you meant permanent.
- [ ] The modal is the app's SECOND modal; the cookbook said ConfirmSave
      would be the only one. Your call overrides it — but note the rule
      it does not break: options BEFORE an action are still inline divs.
      This is a destructive fork mid-write, which is ConfirmSave's own
      shape.
- [ ] An audio folderize can clash on several folders at once (artist
      AND album, or many artists). One modal covers them all — it names
      the first and says "(and N more)", and your answer applies to
      every one. Say if you want them one at a time.
- [ ] Cancel drops the plan preview you had just applied; folderize has
      to be re-run. Cheap to change if it annoys you.
- [ ] One case-sensitive consequence I did NOT smooth over, because it
      is a UX call: a video already sitting in a folder spelled
      differently from its filename (`the matrix/The Matrix.mkv`) still
      counts as "not in place", so folderize is offered and it NESTS —
      `the matrix/The Matrix/The Matrix.mkv`. The alternative reading is
      that the parent is the wrapper wearing the wrong spelling, and
      folderize should offer to respell IT (the same modal, no move).
      Say which you want.

### 10. `^s` acknowledges the save

A single-file save wrote in total silence — the ✓ marks just cleared,
which looks the same as a keypress that did nothing. It now raises the
same notification toast the converts use ("`<name>` saved", title
"save"), per your note. Bulk saves and the subtitle shift already
reported; this makes it the rule.

### 11. Positional chords: `^1 ^save`, `^2 ^open`, …

Both keybindings are live at once, as you asked — the letter chord and
the number fire the same action, and the number is printed in the
keybinding color in front of the word.

Two judgment calls to confirm:

- [ ] **The pane bar is numbered first.** Your example (`[^1] [^s]ave`)
      only holds if "save" is always ^1, so the bottom bar takes ^1…^n
      and any sub-bar on show takes the tail — in an audio pane that is
      `^1 ^save`, `^2 ^open`, then `^3 im^port`, `^4 ^fetch` up in the
      art row. Reading order (top to bottom) would number the art row
      ^1/^2 instead and push save to ^3. Say which you want to test.
- [ ] **Numbers are positional, so they move** as context shows and
      hides buttons — that is the thing being tested, but it means a
      number is not muscle memory the way a letter is.
- [ ] The strip doesn't print them, matching its existing rule that the
      save button carries its own chord (`STATE_DETAILS` has no ^s).
- [ ] Buttons past the ninth get no number (`actions.ORDINAL_LIMIT`).
      The book pane is the one that comes close.

### 11b. ⌥+digit, because ctrl+digit cannot survive tmux

You asked whether a different modifier gets numbers through tmux. I
measured it end to end — a pty pretending to be Ghostty, tmux 3.7 in
the middle, a raw-stdin dump as the app — rather than guess. What
reaches the inner app when the outer terminal sends ctrl+1…ctrl+9:

      | key | tmux default | `extended-keys always` | as Textual reads it |
      |-----|--------------|------------------------|---------------------|
      | ^1  | `1`          | `CSI 27;5;49~`         | **ctrl+1** ✓        |
      | ^2  | `NUL`        | `NUL`                  | ctrl+@              |
      | ^3  | `ESC`        | `ESC`                  | **escape**          |
      | ^4  | `0x1C`       | `0x1C`                 | ctrl+backslash      |
      | ^5  | `0x1D`       | `0x1D`                 | ctrl+]              |
      | ^6  | `0x1E`       | `0x1E`                 | ctrl+^              |
      | ^7  | `0x1F`       | `0x1F`                 | **the app's ^/**    |
      | ^8  | `0x7F`       | `0x7F`                 | **backspace**       |
      | ^9  | `9`          | `CSI 27;5;57~`         | **ctrl+9** ✓        |

Only ^1 and ^9 cross intact, and no tmux setting changes that: tmux
prefers each digit's legacy C0 code over the extended form. Three of
those codes already mean something in this app — ^3 IS escape, ^7 is
the path chord, ^8 is backspace — so aliasing our way out would arm
three keys that cancel, jump, and edit instead of pressing a button.

**⌥+digit crosses tmux untouched, in every configuration, with no tmux
config at all** (`ESC 1`…`ESC 9`). So it is wired up beside the ctrl
spelling — ⌥2 and ^2 both press button two. It arrives under two
spellings, both handled: `alt+<digit>` where modifiers are reported
properly, and the macOS Option GLYPH (`¡™£¢∞§¶•ª`) everywhere else —
which is also exactly what Ghostty types today with
`macos-option-as-alt` off, so it works at your desk unchanged.

- [ ] **Cost of the glyph spelling:** those nine characters are
      printable, so `FieldInput` now intercepts them — you cannot type
      `¡` or `§` into a filename or tag while the number chords live.
      Say the word if that matters and I will scope them to the pane
      (buttons reachable, fields left alone).
- [ ] **ESC ambiguity:** ⌥1 reaches tmux as `ESC 1`, which is also
      "esc, then 1" typed fast. Inside Details view esc ascends to the
      tree, so a slow-hand version of that lands the digit in the
      tree's type-to-select. `set -sg escape-time 10` in tmux narrows
      the window if you ever see it.
- [ ] The buttons print `^N`, not `⌥N` — your spec's label. The Option
      spelling is an unprinted alias, like ⇥ for ⏎ and ⇧← for ^←. If
      the A/B ends with numbers staying, the label should probably say
      whichever one you actually press.
- [ ] If you want the ctrl spelling to work in tmux for the two digits
      that can (^1, ^9), tmux needs `set -s extended-keys always` plus
      `set -as terminal-features ',xterm-ghostty:extkeys'`. You have no
      tmux.conf at all right now, so out of the box ^1 is a bare `1`.

### Session 9 gates

New: `tests/test_casing.py` (13). Additions: `tests/test_actions.py`
(+5 — the ordinal markup, the key parser, per-bar numbering) and
`tests/test_app.py` (+10 —
the modal's three answers, the two delete regressions, the save
acknowledgment, and three for the positional chords).
`tests/fuzz.py` KEYS grew the five CSI-u sequences for ^1…^5 and three
ESC+digit ones for the ⌥ spelling.

Full suite **463 passed**; fuzz gate **0 deaths / 6 seeds** (seeds 7–12, from a
snapshot per CLAUDE.md).


## Session 10 (2026-09-01, Opus) — the tree's highlight

### 12. The icon joined the selection block

The `📁`/`📄` cells rendered on the pane background mid-highlight
because `DirectoryTree` styles its icon prefix with `base_style` (the
row's style), not the cursor's — nothing to do with emoji, which take a
background like any other cell. `render_label` now applies the label
style from cell 0, so a selected row is one continuous block: pad ·
icon · name · pad. Item 7 above is amended.

### 13. The guide tint marks the cursor's OWN level

It used to light up the guide column of the cursor's CHILDREN — the
rows beneath it. Per your sketch it now lights up the column its own
connector is drawn in: the spine of its sibling group, running the full
height of that group and on through the subtrees hanging off it.

The rule is one line — a guide column belongs to that node's parent's
child list, so it tints when `node.parent is cursor.parent`
(`LibraryTree._tint_level`, used by both the render and the line cache
key).

- [ ] ~~**The root row has no siblings, so selecting it tints nothing.**~~
      Answered by session 14 below: the root is an expanded folder, so it
      tints its children again — no special case needed.
- [ ] The tint still only shows while the TREE holds focus (unchanged);
      an idle tree draws every guide in the idle grey.
- [ ] Colors are Textual's defaults here — `tree--guides-selected` has
      no rule in `app.py`, so the tint is a built-in variable, not a
      theme.py token. It is the one color in the tree that rule 5 does
      not yet cover; worth a token if you want to pick it.

Repaint scope had to grow with it: upstream refreshes only the lines
containing the old and new cursor nodes, which left a sibling's guide
stale when the cursor changed levels. `watch_cursor_line` now refreshes
both parents' subtrees, and the tinted level is part of the line cache
key.

Regression: `tests/test_app.py::test_guides_tint_the_cursors_own_sibling_level`
(includes the cross-level move, which is what the stale-cache bug looked
like).


## Session 11 (2026-09-02, Opus) — audio info + a fatal cover

### 14. The audio info line carries type and bitrate

`info` under the save row read `238s · 9.2 MB`; it now reads
`mp3 · 320 kbps · 238s · 9.2 MB`. `AudioDetails` gained `filetype` (the
suffix, spelled like `VideoDetails.container`) and `bitrate`; mutagen
reports one for every format it parses, and a format that doesn't gets
the average its own bytes imply (`size * 8 / length`).

- [ ] **A selection shows the RANGE, not an average**: a VBR album is
      `mp3 · 192–320 kbps · …`, and a mixed-format folder prints both
      suffixes (`flac/mp3`). Say the word if a single averaged number
      reads better to you.
- [ ] Nothing prints a dash — a part no file reported drops out of the
      line entirely (`details.audio_info_label`).

### 15. A truncated album cover killed the app (found, fixed)

`I See Stars/Renegades Forever` — all eleven tracks carry the same 746 KB
JPEG that ends 3 bytes early. PIL decodes LAZILY: `Image.open` reads only
the header, so `_set_cover`'s try/except saw a perfectly good image and
the actual decode happened later, inside the widget's `render()` — on
Textual's render path, where an OSError is fatal.

`images.decode` now pulls the pixels at assignment time, where the
caller can catch it. A file that ends mid-scan still decodes as far as it
got, so the art shows rather than vanishing; PIL's truncation escape is
global state, so it is set only around the salvage and put straight back
(the write paths — imageops, epub — keep refusing damaged input).

- [ ] **A salvaged cover says `1500 × 1500 · damaged` under it**, so a
      cover with a gray strip at the bottom reads as the file's fault,
      not the pane's. Drop the word if you find it noisy.
- [ ] Art too far gone to decode still hides the widget, as before.
- [ ] The same path serves book covers, video posters, and the image
      panel — all four go through `_set_cover`.

### Session 11 gates

New: `tests/test_images.py` (5 — intact, salvaged, unsalvageable,
non-image, and that the global flag comes back). Additions:
`tests/test_adapters.py` (+3 — filetype/bitrate, the label's three
shapes, the bulk range) and `tests/test_app.py` (+2 — the damaged cover
renders and is labelled; the unreadable one hides). `mediafactory` grew
`make_truncated_jpeg`. No new chords, so `tests/fuzz.py` KEYS is
unchanged.

Full suite **474 passed**; fuzz gate **0 deaths / 6 seeds** (seeds 7–12,
from a snapshot per CLAUDE.md).


## Session 12 (2026-09-02, Opus) — type-ahead descends

- [ ] **Typing on an EXPANDED folder now searches its CHILDREN**, not its
      siblings — so selecting a folder, expanding it, and typing no longer
      needs a ↓ first (your ask: the hand stays on the home row). The
      folder itself is not a candidate, so its own letter reaches a child
      (or the nearest-before fallback within the children).
- [ ] A COLLAPSED folder is unchanged: typing still walks its siblings.
- [ ] The scope is PINNED when the buffer starts (`_search_scope`, cleared
      by the same timer/navigation that clears the buffer). Without it,
      "01…" typed as `0` then `1` would descend again on the second key if
      the first landed on an expanded child.
- [ ] A folder expanded but still LOADING (children not in yet) falls back
      to the sibling scope rather than searching an empty list.

### Session 12 gates

`browser.LibraryTree._scope_node` is the new seam; `_jump_to` reads the
pinned scope instead of recomputing the cursor's parent. Tests:
`tests/test_app.py` +2 (descends into an expanded folder and keeps the
scope across keystrokes; stays on siblings when collapsed). No new
chords, so `tests/fuzz.py` KEYS is unchanged. Full suite **476 passed**.

Fuzz gate **0 deaths / 6 seeds** (seeds 7–12, from a snapshot per
CLAUDE.md).


## Session 13 (2026-09-03, Opus) — a case-only rename is not a collision

- [ ] **`1-09 All Things Yet to be.mp3` → `…Yet to Be.mp3` saves now.**
      Your report (2026-09-02): save failed with "already exists". The
      refuse-overwrite guard in `adapters.rename` asked
      `target.exists()`, and on a case-blind volume (APFS, the SMB share)
      the target IS the file you are renaming — so every capitalization
      fix was refused. The guard now allows the one case where the target
      is the same file, and only for a case-only pair: two DIFFERENT names
      sharing an inode are hardlinks, and clobbering one is a real loss.
- [ ] The respell itself goes through `casing.rename` — the halfway-name
      dance the folder actions already needed, because SMB can treat a
      case-only rename as a no-op and silently keep the old spelling. Try
      one on the NAS and confirm the tree shows the new casing.
- [ ] Renaming ONTO another file (`02 Song Two.mp3` when it exists) still
      refuses, as before.

### Session 13 gates

`tests/test_adapters.py` +1 (`test_rename_changing_only_case`, verified
red before the fix). No new chords, so `tests/fuzz.py` KEYS is unchanged.
Full suite **477 passed**.


## Session 14 (2026-09-03, Opus) — the tint follows type-ahead

- [ ] **An EXPANDED folder under the cursor tints its CHILDREN's guide
      column** again, not its siblings' — the partial revert you asked
      for. Anything else (a file, a collapsed folder) still tints its own
      sibling level, which is what session 10 changed.
- [ ] The rule is now the SAME rule type-ahead uses, in one place
      (`LibraryTree._is_open_folder`, read by both `_scope_node` and
      `_tint_level`): the level the tint marks is the level typing
      searches. A folder expanded but still LOADING falls back to
      siblings in both, so the tint never marks an empty list.
- [ ] Consequence, and it closes session 10's open question: the ROOT row
      tints its children again, since the root is an expanded folder.
- [ ] Unchanged: tint only while the TREE holds focus; colors are still
      Textual's `tree--guides-selected` default, not a theme.py token.

### Session 14 gates

`tests/test_app.py::test_guides_tint_the_level_type_ahead_searches`
(rewritten from `…_the_cursors_own_sibling_level`) — expanded folder
drops the tint a level, the leaf below keeps it, a collapsed sibling
lifts it back, and the cross-level move repaints the stale rows. No new
chords, so `tests/fuzz.py` KEYS is unchanged. Full suite **477 passed**.


## Session 15 (2026-09-03, Opus) — todo-5: fold, focus, folders, codec

### TAB folds the directory under the cursor

- [ ] **TAB no longer descends into the details view.** It expands a
      closed folder and collapses an open one — →/← under one key. ⏎ is
      the only key that descends now; it always was the one edit key on
      the strip, and TAB was an unadvertised duplicate of it.
- [ ] Collapsing goes through `collapse_all`, exactly as ← does: re-open
      a folder and you get a plain child list, never the shape it
      happened to have last time.
- [ ] On a FILE, TAB does nothing — the same silence → gives. It still
      shadows Textual's focus cycling, so the tree stays home base.
- [ ] **The strip prints `→ TAB expand · ← TAB collapse`** — the key
      rides BOTH entries rather than taking a third of its own. The strip
      lists keys per command ("↓↑ navigate"), not commands per key, and a
      standalone `TAB expand/collapse` entry was 8 columns wider: enough
      to push the tree state (with `^f folderize` on show) onto a second
      line at 220 columns. It wants 222 for one line as it stands; your
      mockups run ~245, so this only bites a narrower window.
- [ ] It shows in the clipboard state too: folding is navigation, and
      carrying a cut file never stopped you navigating.

### The path input is the only lit box while you type in it

- [ ] **Focusing the Path Input drops the Tree View's border back to
      idle**, so the input's own box is the only lit thing. Leaving it
      (⏎, esc, or clicking into the tree) puts the pane border back.
- [ ] `PathInput.on_focus` toggles `-path-editing` on the container,
      beside the `-editing` class it already puts on the tree; the CSS
      rule sits next to `TreeView:focus-within` in app.py. Narrow mode is
      untouched — the details-open rule still wins there.

### Folders say how many files they hold and how much they weigh

- [ ] **Two rows under `contains`: `files` and `size`**, both RECURSIVE —
      the whole subtree, not the top level. (`contains` still counts the
      top level only, which is why Movies reads `1 folder` and `3`.)
- [ ] They fill in late, starting as `…`: a size total costs one stat per
      file — the thing rule 1 avoids everywhere else, and unavoidable
      here — so the walk runs in a worker (`fs.tree_totals`).
- [ ] **A walk still going after 8 seconds reports what it has, with a
      `+`** (`1,204+ files · 8.7 GB+`), rather than grinding for minutes
      on a library root. Say the word if you would rather it always
      finished, however long a whole volume takes.
- [ ] Dot entries are skipped (matching the `contains` counts); a locked
      subfolder costs accuracy, not the number; a symlinked folder counts
      once and is never descended.
- [ ] Cached against the folder's OWN mtime, so revisits are free and the
      app's own actions (which change the folder) re-count. A change
      buried levels down goes unnoticed until `^r` drops the cache.
- [ ] Empty reads `0` / `0 B`; unreadable reads `—`, never a stuck `…`.
- [ ] Album-like folders are unaffected: they still descend into the bulk
      form, whose info line already totals length and size.

### Video files show their codec

- [ ] **A `codec` row sits under `container`**, filled in late by the
      same worker that reads the embedded title — one header, two reads.
- [ ] It prints the STANDARD's name — `H.264`, `H.265`, `AV1`, `VP9`,
      `ProRes` — not the encoder's. x265 is one program that writes HEVC,
      and the container records the format, never the tool; a file
      encoded by something else would be mislabelled `x265`. If you want
      the row to read that way anyway, it is one dict in container.py
      (`_MP4_CODECS` / `_MKV_CODECS`).
- [ ] Still no ffprobe. `.mkv` reads through enzyme's video track;
      `.mp4` / `.m4v` / `.mov` through a box walk down to the sample
      description. mutagen is no help here — its MP4 parser reads the
      first AUDIO track, so `info.codec` is empty on a video file.
- [ ] `.mov` answers for the codec even though it has no title tag: the
      two reads no longer cover the same suffixes. `.avi` stays
      unhandled — its codec lives in a RIFF stream header, a third
      parser for one suffix.
- [ ] A codec nothing here has a name for prints raw (`zzzz`); an
      unparsable file prints `—`.

### Session 15 gates

New seams: `LibraryTree.action_toggle_fold`, `fs.tree_totals` (+ `Totals`,
`TOTALS_BUDGET_SECONDS`), `container.read_video_codec` (+ the ISO box
walk), `adapters.probe_video_codec`, `DetailsView._probe_totals`, and
`_probe_title` widened into `_probe_container`.

Tests: `tests/test_fs.py` +9 (subtree, dot entries, the cache and its
documented blind spot, the budget floor, an abandoned walk, a locked
subfolder, a missing folder, a symlink loop); `tests/test_container.py`
+9 cases (both fixtures, HEVC/AV1 re-typed in a copy, an unknown fourcc,
.mov, .avi, junk); `tests/test_app.py` +7 (TAB folds, TAB on a file is
inert, path focus lights one box, folder totals fill in and count what is
nested, the codec row and its dash); `tests/test_adapters.py` +1.
Rewritten: the two TAB-descend tests now press ⏎, and the two strip
width tests moved 220 → 240 columns.

No new chords (TAB is already in `tests/fuzz.py` KEYS). Fuzz gate
**0 deaths / 6 seeds** (seeds 7–12, from a snapshot per CLAUDE.md).

Full suite **503 passed**. One flake surfaced while the fuzz gate ran on
the same machine: `test_opt_up_down_at_top_level` died with a
`textual.worker` error and passed alone and in its neighborhood
afterwards. The exposure is real, though — a totals walk can outlive the
pane by seconds where every other probe returns in milliseconds, and a
`call_from_thread` into a closed app raises inside the worker — so
`_probe_totals` now drops its result rather than reporting into an app
that has gone.


## Session 16 (2026-09-10, Opus) — where the app opens, "album artist"

### `albumartist` prints as two words

- [ ] The audio form's third field reads **album artist** now
      (`adapters.FIELD_LABELS`). Display only — the tag key stays
      `albumartist`, which is what mutagen writes and what every
      adapter/test still keys on.
- [ ] It is the widest audio label, so the label column grew one cell
      (12 + gutter). The form measures itself, but the parked `info` row
      under save carries that width BY HAND and was pinned at 11; it
      moved to 12. Check on a track with art that `info`, `album art`,
      and the fields still share one left edge.

### Where the app opens

- [ ] Your report: launched from `/Volumes/Room of Requirement/AUDIO/
      Music Library`, the app opened on `~/code`. I could not reproduce
      it. From that directory `mediasmith` roots the tree on `AUDIO`
      with `Music Library` expanded and the cursor on it — checked twice
      through the real launcher in a pty, once on the NAS itself.
      `uv run --project` does not move the working directory (measured),
      and `Path.resolve()` can only walk symlinks OUT of a path — it
      cannot invent `~/code`. `~/code` is exactly what parent-context
      rooting shows when the shell's cwd is `~/code/mediasmith`. Two ways
      that happens without your noticing: an unquoted
      `cd /Volumes/Room of Requirement/...` (zsh reads the spaces as
      extra words, refuses the cd, and leaves you where you were), and
      `t1`…`t9` attaching to a tmux session whose pane never left the
      repo. If it happens again, `pwd` in that pane before launching —
      that answers it in one line.
- [ ] Hardened regardless: `bin/mediasmith` passes `$PWD` explicitly
      instead of letting the app resolve a `"."` later, so nothing
      between the shell and Python can move the directory out from under
      it. An explicit `mediasmith <dir>` still wins.
- [ ] New `app.start_directory`: a start path that is not a listable
      directory climbs to the nearest one that is (a file → its folder; a
      cwd whose volume went away → the nearest live parent), and a path
      with nothing above it lands at home rather than at `/`. Before, the
      tree was handed a root it could not list.

### Session 16 gates

`tests/test_app.py` +1 (`test_start_directory_is_where_the_app_was_launched`).
No new chords and no new interactive surface, so `tests/fuzz.py` KEYS is
unchanged and the fuzz gate was NOT re-run this session. Full suite
**504 passed** (223 app + 38 adapters + 243 everything else).


## Session 17 (2026-09-16, Opus) — Image Trace

Illustrator's Image Trace on an image file: **tr^ace** (^a) on the image
bar, after resize. Engine in `mediasmith/trace.py`; the pane side is the
"image trace" section of `details.py`.

### Your decisions, as built

- [ ] Controls, with Illustrator's names and scales: **threshold** 0–255,
      **paths** 0–100%, **corners** 0–100%, **noise** 1–100 px, **invert**,
      **ignore white**, plus the **format** picker (svg → eps → pdf). No
      presets, no color or grayscale modes.
- [ ] Every control is a stepper: ←→ ±1, ⇧←→ ±10; switches flip and the
      format cycles on either arrow. ↑↓ walk the rows, then the buttons.
- [ ] While trace is open, the image fills the Details view. The pane
      bar, the filename row, and the size/dimensions rows hide, and the
      picture takes every row from under the controls to the pane's
      floor, scaled to fit without cropping or stretching. It refits
      when the window resizes.
- [ ] **^view source / ^view tracing** (^v) is Illustrator's View menu
      as one key. Changing a setting while the source is shown switches
      back to the tracing, so the change is visible.
- [ ] **^save** writes `photo.svg` (or .eps/.pdf) beside the image and
      keeps trace open, so a second format costs one keypress. It
      refuses to overwrite, and pressing it again overwrites — the same
      second-press escape as convert and resize.
- [ ] Tracer: Homebrew `potrace`. Without it, ^a says
      `brew install potrace`.

### Judgment calls to confirm

- [ ] **Default values** are potrace's own defaults on Illustrator's
      scales (threshold 128, paths 80%, corners 25%, noise 2 px), NOT
      Illustrator's defaults (paths 50%, corners 75%, noise 25 px).
      The mapping between the two scales is mine, so Illustrator's
      numbers wouldn't reproduce Illustrator's look anyway, and potrace's
      defaults give its best first result. Mapping:
      corners 0→100% = alphamax 4/3→0; paths 0→100% = opttolerance 1→0;
      noise = turdsize.
- [ ] **Settings carry over** from one image to the next for the whole
      session (Illustrator remembers its last trace). They reset when
      the app restarts.
- [ ] **esc closes trace entirely** and returns to the tree, like shift
      subs. Resize, by contrast, stays open when focus leaves it. ← on
      the leftmost button also closes it (← with no other job = esc).
- [ ] **"ignore white" doesn't show in the preview**: turning it off
      adds white fills to the saved file, and white on the white preview
      is invisible. Check the saved file to see it.
- [ ] **Stepper look**: values print as `◂ 128 ▸`, reversed when
      focused (the shift-subs control's focus style). The title line
      reads `photo.png · tracing…` while a preview renders.
- [ ] **Chords**: ^a trace (^t is taken by convert to tiff on the same
      bar), ^v view. Both are placeholders for your rename pass.

### Try these by hand

- [ ] A large photo (8+ MP): a preview takes about a second, and holding
      an arrow re-traces once when you let go, not once per repeat.
- [ ] A transparent PNG logo: transparency is laid over white, so the
      logo traces rather than a black box.
- [ ] Open the saved EPS and PDF in Illustrator.
- [ ] Narrow width (tmux column swap): trace fills the details column.

### Session 17 gates

`tests/test_trace.py` new (16 engine tests: mapping, bitmap prep,
preview size, each format, refuse-overwrite, missing potrace);
`tests/test_app.py` +8 trace pilots, including a check that the picture
runs to the pane's floor without spilling past it. The image bar test
now expects "trace" after "resize". No new fuzz KEYS: ^a and ^v were
already pressed.
Full suite **528 passed**. Fuzz gate **0 deaths / 6 seeds** (seeds 7–12,
from a snapshot). Measured by hand: a 12 MP photo loads in 0.14s and
previews at a 1400×1050 box in about 0.5s.

## Session 18 (2026-09-29, Opus) — Illustrator rescue

An .ai file saved with "Create PDF Compatible File" is two documents in
one container: the PDF half (which every non-Adobe reader opens, and
which Illustrator fills with the ARTBOARD ONLY) and `/AIPrivateData`,
Illustrator's own art stream, which carries the whole canvas. So work
parked beside the artboard survives the save and is invisible to
Affinity, Preview and Inkscape — enlarging the artboard reveals nothing,
because the paths are not in the half that got enlarged.

Found on your own `Consider The Ravens/Image/Identity/Final/logo.ai`:
862 pt of artwork (a second, all-black version of the logo) sitting off
the right edge of a 936 × 936 artboard. Engine in
`mediasmith/illustrator.py`; the pane side is `_fill_vector` /
`_probe_canvas` / `_rescue` in `details.py`.

### Your decisions, as built

- [ ] **A new VECTOR kind** (`kinds.VECTOR`), claiming `.ai .eps .svg
      .pdf`. Only `.ai` has an action behind it today; the others share
      the kind so the vocabulary is honest and the panel has somewhere
      to grow. They used to be OTHER.
- [ ] **The pane reports the canvas**: size, artboard, artwork, and a
      `hidden` line — `862 pt past the right edge`, or `nothing outside
      the artboard`. The three canvas rows fill in LATE (see below).
- [ ] **Two buttons, one per product**, the `convert_*` way:
      **rescue to ^pdf** (^p) and **rescue to s^vg** (^v). PDF keeps the
      CMYK numbers and carries the document's embedded ICC profile
      verbatim; SVG is RGB, resolved through that same profile by
      littleCMS (Pillow), so it matches rather than approximates.
- [ ] **The buttons appear only when work is hidden** — a probe worker
      reads the canvas and flips them on, so the button showing up IS
      the finding. On a clean .ai there is no button.

### Judgment calls to confirm

- [ ] **Chords ^p and ^v.** On the vector bar ^s is save and ^o is open,
      so the chords sit on the format word rather than on "rescue".
      Both letters are already in the fuzz gate's KEYS.
- [ ] **The probe is a worker, not part of `read_details`.** Reading the
      canvas inflates the .ai's private data (½ MB on your logo) and
      `adapters.read_details` runs on the event loop — on the NAS that
      is the 2026-08-22 freeze all over again. Cost: the canvas rows and
      the buttons arrive a beat after the filename.
- [ ] **The product is flattened artwork.** Paths, fills, strokes,
      compound holes, clipping groups, linear gradients and the colour
      profile survive; layer and group NAMES do not. Placed rasters,
      live text, mesh/radial gradients and patterns are reported in
      `Recovery.skipped` rather than dropped silently.
- [ ] **Coordinates are the document's own**, so on-artboard work lands
      exactly where it was and the rescued work sits off to whichever
      side it was parked. The page box is the artwork's bounds plus a
      24 pt margin — it is NOT the old artboard.
- [ ] **Verification, if you want to re-run it**: the recovered PDF,
      cropped back to the original 936 × 936 artboard and rendered at
      150 dpi, differs from Illustrator's own rendering by a mean of
      0.004/255, with 11 pixels of 3.8 M over a 32/255 threshold and
      zero contiguous mismatched regions — every differing pixel is on
      an anti-aliased edge.
- [ ] **`.pdf` is a VECTOR now.** If you keep PDFs you think of as
      documents rather than artwork, say so and I will narrow
      `VECTOR_EXTENSIONS`.

## Session 19 (2026-10-11, Opus) — rescue on Illustrator 2020+ files

Nick's `Traces.ai` (Character Logos/06 Final Vector) showed no rescue
buttons. Two bugs, both fixed in illustrator.py:

- [ ] **Zstandard private data.** Illustrator 2020+ (AI24) compresses
      `/AIPrivateData` behind `%AI24_ZStandard_Data`, not zlib's
      `%AI12_CompressedData`. `read_canvas` read nothing → no buttons.
      Decoded with stdlib `compression.zstd` (3.14+), `backports.zstd`
      below that (new pyproject dependency, 3.12–3.13 only).
- [ ] **Negative canvas coordinates.** The page box was anchored at 0,0,
      cropping everything parked left of or below the origin — on
      Traces.ai, half the canvas. The box now reaches the artwork's
      negative edge; the PDF keeps its page at 0,0 and shifts the art
      with one `cm`, because Preview/Quick Look draw a negative-origin
      MediaBox as blank.
- [ ] Re-run rescue to pdf/svg on Traces.ai and check the whole canvas
      (≈16,180 pt square) is there. Acrobat caps pages at 14,400 pt, so
      this one may open clipped or refused there; Preview renders it.
