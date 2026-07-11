# QA to-do — 2026-07-11 session 2 (subtitles: the flagship port)

Everything below passed pytest + the fuzz harness; human pass pending.
Keys are placeholders as usual: ^k get subs · ^u clean subs · ^v shift
subs · ^w watch — rename at will (avoid `actions.RESERVED_KEYS`).

## get subs (^k, on any single video)

- [ ] Press on a subless video: notifications walk the phases
      (searching OpenSubtitles… → syncing with alass…), then a final
      verdict; the .srt/.ass appears in the tree without ^r and the
      subtitles row updates
- [ ] Press on a video that HAS a sub: it re-fetches and **overwrites**
      the sibling sub — the one deliberate exception to
      refuse-overwrite (an explicit press means "replace this bad
      sub"). Veto this if it feels dangerous.
- [ ] Missing alass/subliminal → an error toast with the brew install
      lines, nothing else happens
- [ ] Verdict severities: "synced (+56ms)" reads as info; "large
      shift, verify" / "couldn't sync" read as warnings — eyeball
      those files (the v1 ground-truth policy is unchanged)
- [ ] * Run it over one real film folder and spot-check playback —
      new environment (v2), same engine; confirm nothing regressed

## clean subs (^u, only when a sibling .srt exists)

- [ ] Strips font/color markup and drops credit cues near the file's
      edges, in place; toast reports what went ("2 credit cues
      removed · markup stripped from 14 cues")
- [ ] Already-clean file → "already clean", no write (mtime unchanged)
- [ ] .ass/.vtt sibling: button absent (SRT-only engine)

## shift subs (^v — the wizard-div pattern debut)

- [ ] ^v opens an inline div under the video rows: shift readout +
      hint line; focus lands on the readout (reverse-video highlight)
- [ ] ←→ ±0.1s · ⇧←→ ±1s · ⇞⇟ ±10s; ✓ appears while the shift is
      unwritten; ^save button joins the bar while the div is open
- [ ] ^s writes (cues shifted, clamped at 0), ✓ clears, div stays
      open for further nudging; every write recomputes from the
      original parse — nudge forward, save, nudge back, save = the
      original file, byte-for-byte timing
- [ ] esc with a pending shift → ConfirmSave (save/discard/keep);
      esc clean closes straight back to the tree
- [ ] ^v again while pending refuses to close (toast); while clean,
      toggles the div away — react-style, per your spec
- [ ] ↓ from the readout walks into the action bar; ↑ walks back
- [ ] KNOWN GAP: browsing to another file while a shift is pending
      silently drops it (same as folderize's preview). Acceptable?
- [ ] The div's look = the template for image-resize and video→gif
      wizards — bless or adjust the visual before those get built

## watch (^w, on any single video)

- [ ] Launches the video in the default player; a get-subs install is
      named exactly like the video, so VLC/IINA auto-load it
- [ ] Wiring the sub file explicitly (--sub-file) needs your player's
      name — tell Claude which app and it becomes `open -a X args`

## Also fixed this session (no QA needed, FYI)

- The folderize probe crashed the app when browsing /dev (DirEntry
  stat raises EBADF there) — fuzz-caught once the new chords
  reshuffled the walks; this was almost certainly the old "seed 7
  died once" ghost. Walker now skips unstattable entries.
- A details-pane worker result landing during app teardown could
  raise NoMatches on #pane-bar (suite flake) — now guarded.

## Parked decisions from this session

- [ ] get subs currently always fetches+syncs (force). Alternatives:
      a second "resync" button, or skip-if-present + a long-press
      semantics. Current pick = simplest.
- [ ] The `safe` engine flag (reject large shifts) is not surfaced in
      the UI — wanted as a toggle somewhere?
- [ ] Shift div arrow steps (0.1s/1s/10s) are v1's — still right?


# QA to-do — 2026-07-11 weekend session (action buttons + book convert)

Everything below passed pytest + the fuzz harness; human pass pending.

## The button pattern (new, app-wide)

- [ ] Button labels: the ^ splices in front of its char when the char is
      in the word (`^save`, `^fetch`, `convert to e^pub`, `convert to
      mo^bi`); otherwise it prefixes (`^o path`, `^y convert to azw3`).
      Wording/keys all revisable — shout at whatever reads wrong.
- [ ] Key char + its ^ render in the accent color, rest of the word plain
- [ ] ↑↓ now walk *through* the buttons (↓ on a button row = move right);
      ←→ still move within a row; ← on the leftmost button ascends
- [ ] Buttons wrap flexbox-style: shrink the window until the book row
      (save · convert to epub · convert to mobi · convert to azw3)
      breaks onto two lines; nothing clips
- [ ] Action chords fire from the tree: highlight a song, press ^o —
      the art path input opens without entering the pane first. Feel OK,
      or should chords require the pane to be focused?

## Book convert (buttons on every ebook)

- [ ] An epub offers: save · convert to mobi (^b) · convert to azw3 (^y);
      a .mobi offers epub/azw3, etc. — own format absent
- [ ] Converting notifies start ("Dune.epub → .mobi…") and completion;
      the new file appears in the tree without ^r, cursor stays put
- [ ] Existing target: refuses with a warning, never overwrites
- [ ] No Calibre → error notification pointing at calibre-ebook.com
- [ ] Convert keys are placeholders (^p/^b/^y) — rename/rebind at will
- [ ] A long conversion over SMB: UI stays live? Start two at once?

## Folderize (button on folders)

- [ ] `fo^lderize` appears on a messy folder shortly after highlight
      (probe fills in late — watch the delay on NAS folders), stays
      absent on organized folders, Books, Empty, Album Art
- [ ] Press: plan preview in the details pane (new Artist/Album tree,
      skips listed with reasons); bar becomes `^apply` / `cancel`
- [ ] ^a applies: files move, "* Skipped/" collects untagged, empty
      dirs pruned, tree refreshes, toast summarizes counts
- [ ] esc backs out of the preview without touching anything
- [ ] Album-like folder (bulk form view) also offers folderize
- [ ] * Probe cost on the real NAS Music Library root: is highlight
      still snappy? (budget is folderize.PROBE_BUDGET = 200 tag reads)

## Book extract-cover + create-opf

- [ ] `ex^tract cover` appears only on epubs that have a cover; writes
      cover.png/.jpg (named for the real format) beside the book
- [ ] `^g create opf` writes a Calibre-style metadata.opf from the
      book's metadata; check it looks right to Calibre if you import
- [ ] Both refuse to overwrite an existing target (warning toast)
- [ ] Both appear on epubs only — .mobi/.azw3 hide them (no reader)

# QA to-do — 2026-07-10 session (editing slice + bulk)

Everything below passed pytest + the fuzz harness; this list is the
human pass: look-and-feel, real library, real terminal. Test in Ghostty
first; repeat the starred items over tmux-from-phone.

## Chrome

- [ ] Scrollbars: thumbs are `▂` (horizontal) / `▌` (vertical), 1 cell
      wide; vertical no longer looks thinner than horizontal
- [ ] Scrollbar track matches the pane background — including while the
      tree is focused (the 5% focus tint was removed to keep them equal;
      confirm you don't miss it — accent border still marks focus)
- [ ] Tree pane has 1 char padding between text and border
- [ ] Command strips: left strip shows with tree/path focus, right strip
      with details focus, each aligned under its column; global strip
      unchanged on the last line
- [ ] * Strip text clipping at phone width — wording is placeholder,
      trim to taste

## Single-file editing (mp3, epub)

- [ ] ⏎ / ⇥ / → on an editable file all enter details, filename focused,
      cursor at end, nothing selected
- [ ] ↑↓ (and ⇥) move between fields; focus never escapes except esc/←
- [ ] ← mid-text moves the cursor; ← at text start = esc
- [ ] opt+arrows word-jump; opt+shift+arrows word-select (* on phone:
      may degrade in tmux — known, report what you see)
- [ ] ✓ appears after an edited field, disappears if you retype the
      original value; save and discard both clear all ✓
- [ ] ^s writes tags; rename via the filename field renames on disk and
      the tree/path bar follow
- [ ] esc with pending edits → Save / Discard / Keep editing modal
      (s / d / esc); esc clean releases straight to the tree
- [ ] epub: title/author/series/publisher/language/date round-trip;
      cover survives the rewrite (file still opens in your reader)

## Album art

- [ ] Art is the last field: label column, image top-aligned with the
      label, left edge on the input column, aspect ratio preserved
- [ ] `path ^o`: input pre-filled with the track's folder; tab completes
      (dirs + images only); ⏎ previews as pending art; esc cancels back
      to the buttons; try dragging an image from Finder into the input
- [ ] `fetch ^f` on a real album: sensible candidate first; ^f again
      cycles; notification names artist — album and position
- [ ] Saved art actually lands in the file (check in Music.app/another
      player); replaces rather than appends
- [ ] Button row reachable: ↓ from art, ←→ between buttons, ⏎ activates,
      ← on leftmost releases

## Refresh + selection

- [ ] ^r on a NAS folder picks up externally added/removed files;
      expansion + cursor survive
- [ ] shift+↓↑ selects (reversed rows), stops at folder boundaries,
      collapses on any plain move
- [ ] Live bulk preview while extending feels right at NAS latency —
      this is the acceptance-critical one; if the "reading N files…"
      flash annoys, say so
- [ ] Album folder (leaf, one kind) shows the bulk form immediately;
      artist folder shows counts; ⏎ on an album folder descends into
      the form; → still just expands the folder
- [ ] cover.jpg in an album folder doesn't block bulk

## Bulk editing

- [ ] "N audio files selected" title; no filename field; focus enters at
      first tag
- [ ] Unanimous fields show the value; divergent show dim `(mixed)`;
      empty-everywhere shows `-`
- [ ] Edit one field, ^s: writes only that field to every file; mixed
      fields you didn't touch keep their per-file values
- [ ] Mixed field: type → ✓; empty it back out → ✓ gone (won't write).
      Known gap: no way to delete a mixed tag from all files, and no
      per-field revert once touched (esc → discard resets the form)
- [ ] Art in bulk: `(mixed)` when covers differ; fetch/path applies one
      cover to the whole album on save
- [ ] Partial failure notice reads OK (lock a file to force one if you
      care)
- [ ] * Bulk read of a real album over SMB: acceptable delay?

## Narrow (phone) mode — 2026-07-10, awaiting first real QA

All starred: test over tmux-from-phone. Breakpoint is `NARROW_COLUMNS = 80`
in app.py — tune to taste (resize Ghostty across 80 cells to flip live).

- [ ] * Launch at phone width: tree only, full width; path bar and
      details hidden
- [ ] * ^/ summons the path bar *above* the tree (shared, not swapped);
      ⏎/esc dismiss it and it disappears again
- [ ] * "View" (read-only kinds): ⏎/→ swaps details in, no accent border,
      ↑↓ still walk the tree underneath with live details, esc swaps back
- [ ] * "Focus" (audio/epub): ⏎/⇥/→ swaps details in *with* the accent
      border and lands on the filename; esc/save-release swaps back
- [ ] * ^/ while viewing or editing details summons the path bar over it
- [ ] * Resize across the breakpoint mid-session (Ghostty window drag,
      tmux pane resize) — layout follows, focus stays put
- [ ] * Strip wording at 60 cells — current strings likely clip
- [ ] Parked: in "view" the left strip still says "⏎ edit" — needs a
      view-specific strip ("↑↓ files · esc back")?
- [ ] Parked: kinds-specific additions to the tree gestures you predicted
      you'd want after first use — collect them here

## Open UX decisions parked in this session

- [ ] save button sits below the art, often below the fold — final home?
- [ ] info row parked below save — final home?
- [ ] strip wording everywhere
- [ ] ✓-click to revert a touched field (worth building?)
