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
