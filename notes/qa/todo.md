# QA to-do — 2026-07-15/16 session 2 (images · folders · standardize ·
# sort · video→gif — the queue is BUILT OUT)

## Old

- [ ] The "download posters" setup instructions are incorrect.
- [ ] Book edit form now exposes "author sort" (creator opf:file-as) and
      "series no." (calibre:series_index). Confirm ✓-mark/save/clear behave on
      both new fields, and check the book/audio label columns still align at
      phone width (widest is now "albumartist"/"author sort", both 11).
- [ ] "number" field labels renamed to "no." (track no., disc no., series no.)
      — display only; keys unchanged (audio keys are mutagen tag names).
- [ ] Album art and book covers now print their pixel dimensions beneath
      the image ("600 × 600", muted). Shows only when a cover is present
      (hidden on no-cover / (mixed) bulk); images-off still shows the dims.
      Format uses " × " to match the image panel's dimensions field — OK, or
      want plain "600x600"?
- [ ] Action buttons highlight orange on arrow-key focus, with the chord
      recolored to light orange (#ffe6c2) so it stays legible; word goes
      black/bold. QA the contrast on real buttons — the light-orange chord
      vs. a light grey was the open call.

## Rename any file kind (2026-08-11, your ask)

- [ ] EDITABLE_KINDS is now every kind (frozenset(PANELS)) — video and
      "other" (plain files) join audio/book/image/folder. They edit as a
      filename-only form, modeled on the folder panel: the #fname input
      leads, read-only details sit below, and ^s (or the save button)
      writes the rename. No metadata form for these two, so rename IS the
      whole edit.
- [ ] CONSEQUENCE — there is no longer a read-only kind. enter/→/⇥ on a
      video or a plain file now DESCEND into the rename field (before, they
      were a no-op on wide / a focus-less "view" on narrow). The narrow
      "view without focus" path (app.view_details / _details_viewing) now
      only fires for UNREADABLE selections; harmless, left in place.
- [ ] Video's contextual chords are unaffected: ^k/^u/^v/^w/^d/^g still
      fire app-wide from the tree (App.on_key → action_for_key), so the
      default flow (highlight video, press the chord) is unchanged. New:
      the pane's "save" button now leads the video action bar (it's the
      rename write). NB while the #fname field HAS focus, the Input eats
      some of those letters — press esc back to the tree to use them, same
      as the audio/book tag fields already do.
- [ ] Tests updated to the new model: test_other_file_is_editable,
      test_narrow_other_descends_editable, test_details_follow_cursor,
      test_wide_enter_focuses_any_kind (were the old read-only guards).
- [ ] KNOWN EDGE (unfixed, decide if it matters): on a video, a PENDING
      subtitle shift wins ^s — if you nudge a shift AND rename in the same
      descent, ^s writes the shift and the rename is dropped (that leg of
      _start_save returns early). Rare sequence; flagged not fixed.

## Tree: guides + collapse-level (2026-08-08, your two asks)

- [ ] Guide tint no longer bleeds down the subtree. Highlight a folder
      whose subdirectories are ALSO expanded: only the cursor's DIRECT
      children get blue ├─/╰─ connectors; nested grandchildren keep grey
      connectors. The blue │ still runs down the direct-child column
      (that's the boundary of the direct children, kept on purpose).
- [ ] Done by reimplementing DirectoryTree._render_line in browser.py
      with ONE change: the selected guide style is no longer sticky down
      the path (see the flagged line + the per-iteration guide_style
      reset). Fragile vs. Textual upgrades — if guides look wrong after a
      bump, re-diff against textual/widgets/_tree.py::_render_line.
- [ ] NEW CHORD — collapse the whole level: shift+← flattens the cursor's
      folder level — its node, its siblings, and all their offspring —
      back to a plain sibling list; cursor stays put. (← still collapses
      one node.) KEY IS A PLACEHOLDER — rename at will. No conflict with
      the shift-subs wizard's shift+← (that's scoped to its div's focus).
- [ ] shift+← now prints in the tree command strip ("⇧← collapse").

## Tree: expand/collapse no longer strands the view (2026-08-08, your bug)

- [ ] Repro was: expand a node and the view jumps to the top row instead
      of staying on the cursor; or descend + come back + collapse and the
      cursor snaps to the top. Cause: the centered-scroll invariant
      (scroll_y == cursor_line) wasn't re-asserted after a structural
      change — a fit↔overflow flip, or a scroll that landed while the
      layout was mid-reflow (pane height transiently 0), left it stranded.
      node.collapse() also never re-scrolled at all.
- [ ] Fix: on_tree_node_expanded / on_tree_node_collapsed re-center the
      cursor via call_after_refresh (runs AFTER the load-driven scroll, so
      it corrects a bad landing instead of racing it). Verified with an
      A/B: forced desync self-corrects with the fix, stays stranded
      without. Couldn't reproduce the *expand* variant synthetically —
      please re-test that one specifically in your real tree.

## Trash: works on files now + moved to ctrl+del (2026-08-08, your bug)

- [ ] Trash used to no-op on files — it targeted _plan_root() (folders /
      album-bulk only). Now it trashes the highlighted item itself, file
      OR folder (adapters.trash / send2trash handles both). Shift-range
      multi-selections have no single target — left alone (unchanged).
- [ ] Key moved ^t → ctrl+del. This ENDS the ^t collision with extract-
      cover (books): ^t is now extract-cover only; trash is ctrl+del.
- [ ] Which physical key? On a Mac the "delete"-labeled key is really
      backspace, and forward-delete is fn+delete. So the app accepts BOTH
      ctrl+delete and ctrl+backspace for trash — whichever your terminal
      sends. Confirm ctrl+del fires in Ghostty; tell me if only one of
      the two variants works.
- [ ] Guarded: neither variant trashes while a text field is focused (a
      folder's rename form uses ctrl+backspace as word-delete) — the
      button still trashes there.
- [ ] The trash BUTTON still shows only on folder/album views (prints
      "^del trash"); on file panes there's no button but the chord works
      (same as ^e new-folder). Say if you want a visible trash button on
      file panes too.
- [ ] Re: your ⌘⌫ question — it almost certainly never reached the app.
      macOS claims ⌘ (Command) for system/app shortcuts, and terminals
      (Ghostty included) don't forward ⌘+key to the TUI unless you add an
      explicit keybind in config. So BOTH were true: ⌘⌫ didn't arrive AND
      the feature was folder-only. ctrl-based chords do reach Ghostty
      (Kitty keyboard protocol), so ctrl+del is the right home for it.

## Overwrite: second-press escape hatch (2026-08-08, your bug)

- [ ] A produce action that would clobber an existing file now REFUSES
      ONCE ("X already exists — press again to overwrite") and, on the
      same key pressed again on the same file, overwrites. Browsing away
      (or a different action) disarms.
- [ ] Covered: book convert (^p/^b/^y), extract cover (^t), create opf
      (^g), image convert (^p/^g/^b/^f), image resize (^a in the div),
      make gif (^a in the div).
- [ ] NOT covered (deliberately — different UX, flag if you want them):
      · standardize "(clean)" siblings (batch/stream — already-clean
        books are filtered, not refused);
      · plan-based folderize / sort / split-omnibus (they refuse
        PER-FILE inside a preview — overwriting there wants a per-row
        toggle, not one key);
      · rename (overwriting a different file by renaming onto it is a
        clobber of the wrong kind — left refusing);
      · move (proposal M1 — refuses per item).
- [ ] Confirm the wording/gesture feels right; is one confirming press
      enough, or do you want a visible "armed" indicator?

## Keys: ⌘ → ctrl migration (2026-08-08, your bug — ⌘ didn't reach term)

- [ ] new folder: ⌘⇧N → ^e · trash: ⌘⌫ → ^t. Both print on their
      folder buttons now ("n^ew folder" / "^trash") and dispatch like
      every other action. CONTEXTUAL REUSE: ^e is also split-omnibus
      (book) / resize (image), ^t is extract-cover (book) — a visible
      button wins, so on those views the chord does that instead.
- [ ] new-folder still works on ANY selection (a file → its parent),
      via an on_key fallback when no ^e button is showing; trash stays
      folder-only (no-op elsewhere, as before).
- [ ] first/last row: ⌘↑ / ⌘↓ → ^↑ / ^↓ (ctrl+up/down).
- [ ] show-hidden: the ⌘⇧. duplicate is gone; ^. (ctrl+full_stop)
      remains — verify ^. actually toggles hidden in your terminal (it's
      the one chord I didn't touch; tell me if it's also dead).
- [ ] The fuzz gate now exercises new-folder/trash for the first time
      (^e/^t were already in its KEYS) — write-jailed, so its scratch
      tree is where any "untitled folder" lands.

## Book cover: add/replace (^f cover — on every epub, 2026-08-07)

- [ ] Button "cover" in the epub button group (your call: for now it
      lives with the other actions; you want ALL cover tasks moved next
      to the cover art later — parked).
- [ ] Press → a path input opens under the cover, pre-filled by
      priority: (1) a sibling image sharing the book's stem
      (Dune.epub → Dune.jpg/png…), (2) a cover.* image, (3) else the
      book's own directory. Tab-completes the filesystem (image files +
      dirs), like the audio art-path. ⏎ applies (writes), esc cancels.
- [ ] Writes into the epub: replaces the existing cover in place
      (re-encoded to its format — png stays png, jpg stays jpg) or adds
      a cover.jpg + manifest/meta when the book had none. Refresh shows
      the new art. Open in a reader to confirm it took.
- [ ] KEY: ^f is a placeholder — CONTEXTUAL REUSE of art-fetch (audio) /
      convert-tiff (image); neither ever shows on a book. Rename at will.
- [ ] Divergence from audio art (which stays PENDING until ^s): the book
      cover WRITES ON APPLY (it's an action button, not a metadata
      field). Reconcile if you'd rather it join the ✓/save flow.
- [ ] Edge parked: a book whose existing cover is an exotic format
      (gif/webp/svg) is re-encoded png-or-jpeg by href extension — jpg/
      png (the ~universal case) are exact; a gif-declared cover could
      mis-match. Rare; flag if you hit one.
- [ ] NEXT (your stated direction): move cover manipulation (this +
      extract-cover) OUT of the button group to sit beside the cover
      image; richer file-pick (tree browser) later.

## Video → gif (make ^gif — ^g on any video)

- [ ] ^g toggles the div: fps [12] · width [480] · ^apply; ⏎ in a
      field applies too; ^g again (from the tree) closes it
- [ ] Make one from a real film clip: two-pass palette = no dither
      banding; check the file size feels right for 12fps/480px
- [ ] Defaults veto: 12 fps / 480 px — tasty or not?
- [ ] Output Name.gif beside the video, refuse-overwrite; the tree
      picks it up and the div stays open for another size
- [ ] No ffmpeg → error toast with the brew line
- [ ] Whole-video only: start/duration trimming exists in the engine
      but has no fields yet — want them?
- [ ] ↓ walks fps → width → ^apply → the pane bar; ↑ walks back
      (the shift div and gif div can be open together — try it)

## Standardize formatting (stan^dardize — ^d on books/folders)

- [ ] On any epub: writes "Name (clean).epub" beside it; toast names
      the detected style + chapter count; tree follows
- [ ] THE REAL TEST: run it on one Wildbow epub per style (Ward =
      calibre-h1, Worm/Twig = calibre-bold, Pact = calibre-h2, Pale)
      and read a few chapters — the extractors are v1's verbatim, but
      the epub WRITER is a fresh port; confirm output matches what the
      v1 tool produced
- [ ] Metadata carry (new vs v1): series/publisher/date/language and
      the cover survive into the clean copy — check one in Calibre
- [ ] On a folder: button appears only while a direct-child epub
      still lacks its "(clean)" sibling; batch streams a toast per
      book + a summary; direct children only (subfolders untouched)
- [ ] Refuse-overwrite per book; "(clean)" files are never batch
      inputs (no "(clean) (clean)" from folder mode)
- [ ] Naming veto: is " (clean)" the suffix you want?
- [ ] Not offered on mobi/azw3 (convert to epub first) — OK?
- [ ] Parked: v1's --style override isn't surfaced; if detection
      misses on a real book, that becomes a wizard-div option

## Sort (s^ort — MOVED ^t → ^o; now on a single ebook too)

- [ ] KEY MOVED: sort was ^t, now ^o. ^t collided with extract-cover
      once sort landed on a single epub (both show at once). ^o is a
      contextual reuse of rotate (image) / art-path (audio) — neither
      ever shares a book/folder view. Rename the placeholder at will.
- [ ] RENAME NOW ON (you asked): both flows rename every book file to
      the folder name + suffix; sidecars (metadata.opf, cover.*) keep
      their canonical names.
- [ ] SERIES NAMING (2026-08-07): a book with a calibre series + numeric
      index is named "Author Sort - Series - NN - Title" (NN = two-digit,
      e.g. "Jemisin, N. K. - The Broken Earth - 01 - The Fifth Season");
      a fractional index keeps its decimal ("02.5"). No series (or a
      non-numeric index) → "Author Sort - Title". Both file AND folder
      take this name. Verify against a real series dump on the NAS.
- [ ] Folder flow (unchanged shape): button on folders holding a loose
      epub not already in its "Author Sort - Title/" wrapper; absent on
      wrapper folders; preview lists each wrapper + files (formats
      grouped by stem; opf/cover ride along only for a lone book);
      ^a applies, esc cancels; existing folders reused, collisions
      refuse per file.
- [ ] NEW single-ebook flow: navigate to an ebook, ⏎ into details, press
      sort (or the button). It renames + wraps THAT file only (siblings
      left behind), no preview, then re-reveals the book inside its new
      folder — still selected and editable (filename focused). Refuses
      to overwrite an existing file in the wrapper.
- [ ] Single-ebook button is epub-only (mobi/azw3 have no readable
      metadata) and hidden once the book already sits in its earned
      folder — right calls?
- [ ] A mobi/azw3 with no epub sibling is skipped with a reason (folder
      flow) — right call, or should it wrap by stem-as-name?

## ⚠ Fuzz death (2026-08-07): pane ←/→ indexed a hidden button — fixed

Seed 12 died: `ValueError: list.index(x): x not in list` in
`action_pane_left`/`action_pane_right`. A focused ActionButton
(act-new_folder) was hidden by a context change (a probe fill-in or a
debounced re-preview calling `set_visible`) while it still held focus;
the next ←/→ did `row.index(focused)` on the now-visible-only list it
was no longer in. Both handlers now guard `focused in row` first and
fall through (← ascends, → no-ops) — the same defensive shape
`_move_nav` already had. Latent since the action bars existed; the
sort-on-a-book context churn just made it reachable.

## ⚠ Fuzz deaths: solved (ConfirmSave double-dismiss) + gate hardened

Two gate deaths this session (seeds 7 and 10), one root cause, found
via the new kept-on-death pty: **two ConfirmSave keys landing inside
one frame (esc esc) dismissed the modal twice; the second pop hit an
empty screen stack and ScreenStackError is app death.** The modal now
takes only its first answer (regression test:
test_confirm_save_survives_double_dismiss). This bug shipped with the
modal itself (2026-07-10) — folders becoming editable just made
dirty-state + esc vastly more common, which is why it fired now.

The hunt also caught the gate writing outside its sandbox: the walk
used folder-rename on its OWN scratch root and left "untitled folder"
droppings (an exposure that predates #10 — move/folderize could
always write wherever the walk browsed). Harness fixes in fuzz.py:
- macOS seatbelt WRITE-JAIL: the child may only write inside its
  scratch tree (+/dev); a denied write surfaces as an error toast,
  itself now fuzzed
- every seed's pty is captured, kept under a unique name on death
  ("only the pty tail tells" — now enforced, and a re-run can't
  delete the evidence); `--first N` re-runs one seed alone
- known determinism hole: the random scratch dirname is VISIBLE in
  the tree (parent context row), so every run's walk differs even at
  a fixed seed — deaths reproduce statistically, not exactly
Nothing outside /tmp was touched; your repo was verified clean.

## Folder rename (folders joined EDITABLE_KINDS)

- [ ] ⏎ on a plain folder descends into a filename-only form (counts
      row stays); rename on disk, tree and path bar follow
- [ ] Rename an EXPANDED folder: its open subtree stays open, cursor
      stays on it — try a deep NAS artist folder
- [ ] Renaming the context row (the tree's own root line) re-anchors
      cleanly
- [ ] Known gap: album-like folders open as the bulk form, which has
      no filename field — no UI to rename those yet. Want one?
- [ ] Behavior change: ⏎ on folders used to be a no-op on wide (and
      "view" on narrow) — now it descends with focus everywhere

## New folder (⌘⇧N — Finder's chord — or the button on folder views)

- [ ] Creates "untitled folder" in the highlighted folder (highlighted
      file → its parent), cursor lands on it, focus drops straight
      into the rename field — Finder's whole flow
- [ ] Name collisions get " 2", " 3", …
- [ ] ⌘⇧N needs the kitty protocol: works in Ghostty; CHECK
      tmux-from-phone — if super doesn't arrive there, the button on
      folder views is the fallback (chord ideas welcome)
- [ ] Strip now reads "… · ⌘⇧n new · ⌘⌫ trash" — wording/clipping at
      phone width is yours to trim

## Trash (⌘⌫, or the trash button on folder views)

- [ ] Sends the folder to the macOS Trash (send2trash dep) with NO
      confirm — the Trash is the undo. Veto if that feels too hot.
- [ ] Tree re-lists, cursor moves to the parent; trashing the context
      row climbs out cleanly
- [ ] Try one NAS folder: network volumes keep their own .Trashes —
      confirm the file surfaces in Finder's Trash (send2trash may
      error on volumes without one; the toast will say so)
- [ ] Folders only for now (your note scoped it) — files are a
      one-line change
- [ ] Buttons print no chord (⌘-chords don't fit the ^x label scheme) —
      naming/label ideas yours

## Image rename (images joined EDITABLE_KINDS)

- [ ] ⏎/⇥/→ on an image descends into a filename-only form; rename on
      disk works; esc releases (ConfirmSave when the name is edited)
- [ ] New "dimensions" row (e.g. "1920 × 1080") under size — instant,
      read from the bytes already in memory; "—" for unparseable files
- [ ] Narrow-mode change to eyeball: images used to "view" (tree kept
      focus); now they descend WITH focus like audio/books, because
      rename made them editable. If browsing photos on the phone feels
      worse now, say so — a view-first hybrid is possible
- [ ] .tiff/.tif are now image kinds (they convert, so they must view)

## ⚠ Contextual key reuse is live (your pick, this session)

The ctrl-letter pool was empty, so image actions REUSE letters whose
other owner is a book/audio-only button — no two same-key buttons can
ever be visible together, and ActionBar.set_visible asserts it (the
app would crash-log rather than fire an ambiguous chord):
- ^p convert to jpg (books: convert to epub)
- ^g convert to png (books: create opf)
- ^b convert to webp (books: convert to mobi)
- ^f convert to tiff (audio: fetch art)
- ^e resize (books: split omnibus)
- ^o rotate (audio: art path)
- ^a apply, in the resize div (plan previews: apply)
Same Input caveat as ^e/split-omnibus: while the filename field is
focused, ^e/^a are Input editing chords — the image chords fire from
the tree, the buttons always work.

## Convert (buttons on every image, own format hidden)

- [ ] photo.png offers jpg/webp/tiff (no png); .jpeg hides jpg (alias)
- [ ] Converted file lands beside the source, tree follows, cursor
      stays; refuse-overwrite with a warning toast
- [ ] RGBA→jpg flattens instead of erroring; EXIF survives where the
      format allows (engine-tested; spot-check a real photo)

## Resize (^e — the second wizard div; shift-subs is the first)

- [ ] ^e opens an inline div: W × H inputs prefilled with the true
      dimensions, a "link" checkbox (checked), an ^apply button
- [ ] Linked: editing either field recomputes the other from the
      TRUE aspect (no drift from repeated edits); unlinked: distort
- [ ] ⏎ in either field applies, ^a applies, esc releases to the tree
      (div stays open — no pending state, nothing to confirm)
- [ ] ^e again from the tree toggles it closed, react-style
- [ ] Output is "name (WxH).ext" beside the source (pixels are
      precious — resize never edits in place), refuse-overwrite
- [ ] The div's look should match the shift div — flag any mismatch

## Rotate (^o, 90° clockwise per press)

- [ ] The one in-place image edit; the pane's image and dimensions
      row refresh after each press
- [ ] On a JPEG the toast appends "(JPEG re-encoded)" (quality 95 —
      a lossless-jpeg dep was not added unasked; say the word)

## Also changed (FYI)

- Book convert (^p/^b/^y) now refuses under MEDIASMITH_OFFLINE — that
  guard is what let the convert chords join the fuzz gate's KEYS
  (real ebook-convert spawns are too heavy for it). Normal use is
  unaffected unless you export that env var yourself.
- Fuzz KEYS grew ^a ^p ^b ^y ^t ^g — every seed's walk re-dealt.
- Bulk-selecting images/videos now says "N images/files" instead of
  mislabeling them "books" (still read-only — no bulk image form).

# QA to-do — 2026-07-15 session (logo · video: container + posters ·
# split omnibus)

## Mediasmith logo (global strip)

- [ ] The wordmark sits flush right on the global strip; eyeball it in
      Ghostty (the octant glyphs need a font with Unicode 16 blocks —
      if you see tofu, that's the font, not the app)
- [ ] Shrink the window: at 50 cells the logo vanishes (collision
      rule), reappears at 51; check it survives a phone-width tmux
- [ ] Color: it inherits the strip's muted gray — want it accented?

## Video: container row

- [ ] Every video shows a "container" row (suffix name: mkv/mp4/…)
      above the embedded title; instant, no probe delay
- [ ] Parked: editable container = a remux — if you want it, it should
      be convert-to-mp4/mkv buttons (book-convert shape), not a field

## Download posters (^d, on any single video)

- [ ] Press on a local video: toasts walk the phases (identifying →
      searching → fingerprinting → downloading, every 5th file), then
      a summary; posters land in a "Film (Year)" folder BESIDE the
      video and the tree shows it without ^r
- [ ] Press on a NAS video (under /Volumes): posters stage to
      ~/Downloads/Videosmith/<Film (Year)>/ instead — the
      local/network heuristic is literally "path starts /Volumes";
      veto if that's wrong for your mounts
- [ ] No TMDB key → a toast with the two setup lines (env var or
      ~/.config/mediasmith/tmdb_api_key)
- [ ] Near-duplicate posters are collapsed (keeps the hi-res copy);
      re-running refuses to overwrite what's already there
- [ ] A film TMDB can't match → "no TheMovieDB match" warning, no
      folder created

## Split omnibus (^e, on epubs that hold ≥2 books)

- [ ] The button appears on a real omnibus shortly after highlight
      (zip-read probe fills in late), never on single books
- [ ] Press: preview lists each detected book, chapter counts, and
      the output filenames; ^a writes them beside the source, esc
      backs out untouched
- [ ] SERIES NOW SET (2026-08-07, you asked): an omnibus IS a series,
      so each split is tagged calibre:series = the omnibus's own title
      and series_index = its 1-based position, and named to match —
      "Author Sort - <Omnibus Title> - NN - <Book>.epub". A split book
      is therefore born correctly named + tagged; sorting it later is a
      no-op.
- [ ] EDITABLE SPLIT FORM (2026-08-07, your feedback): pressing split no
      longer drops straight to a read-only preview with no focus. It now
      opens an EDITABLE form in the details pane (pane focused, lands on
      the author field), following the single-ebook edit layout:
        · shared fields: author, author sort, series
        · per book: title, series no.
      All pre-filled from the NCX/OPF guesses; the user corrects them
      (e.g. title "Book01 The Fifth Season" → "The Fifth Season", series
      cruft "…(book 1-3)" → "The Broken Earth") BEFORE anything writes.
      ^a (=^apply, works while a field is focused) writes; esc cancels
      and ascends to the tree. This SUPERSEDES the verbatim-series cruft
      worry — you fix it inline now.
- [ ] Scope calls to sanity-check: (a) an omnibus with >20 books falls
      back to the OLD read-only preview (no inline edit) — pool cap, fine?
      (b) series no. is a plain integer field; fractional inserts (2.5)
      aren't offered in the form (engine still supports them). (c) the
      form never touches publisher/language/date/pubdate — inherited
      from the omnibus. Want any of those editable too?
- [ ] Outputs open in your reader: front matter present, only the
      book's own chapters, TOC has chapters at the root (the omnibus
      book-title level is dropped)
- [ ] Re-apply refuses to overwrite existing outputs (per book)
- [ ] Known scope cut: a FLAT-TOC omnibus (chapters at top level, no
      book containers) gets no button — v1 solved it with an
      interactive conversation; v2 would need a wizard div. Do you
      own any? If yes it gets built.

## ⚠ Key space: two letters recovered (your veto)

The ^d and ^e chords come from auditing RESERVED_KEYS (option 1 from
the session-3 note, executed): against Textual 8's real bindings,
^d and ^e are only Input *editing* chords (delete-right / end) — the
same class as a/k/u/v/w/x, which video/folder actions already use
safely because no Input is focusable in those contexts. c/q (app),
h/i/j/m (terminal aliases), z (suspend) stay reserved. So:
- ^d → download posters (shipped)
- ^e → split omnibus (shipped); on book views a focused tag field
  eats ^e (end-of-line) — the chord fires from the tree, the button
  itself always works. Same caveat will apply to any future letter
  on editable kinds.
The pool is exhausted again; #10 New/Delete still needs the
ctrl+shift-layer (or contextual-reuse) decision from the session-3
note. Veto any of this by renaming keys; the reserve list is
actions.RESERVED_KEYS.

# QA to-do — 2026-07-11 session 3 (multi-artist · Move)

## fix multi-artist — see its section under session 2 below

## Move (^n — proposal M1, approved)

- [ ] `^n move` on any file/folder/selection lifts it; strip reads
      "moving N · ^n place here · esc cancel"; the button relabels
- [ ] Browse anywhere (including a ^/ path jump — the lift survives),
      `^n` again places into the highlighted folder (a highlighted
      file means its folder; an album-like bulk view means that
      folder)
- [ ] Same folder → "already here" toast, lift kept; folder into its
      own subtree → refused; existing name at target → that file
      refused, others move (refuse-overwrite per file)
- [ ] esc cancels the lift (after plan previews, before narrow view
      close — check the esc chain feels right on the phone)
- [ ] Cross-volume move (NAS↔local): copy+delete under the hood —
      try one biggish file; UI should stay live, toast on finish
- [ ] Lifting an album-like folder lifts the FOLDER (not its files);
      lifting a shift-selection lifts the files. Right call?

## ⚠ Key space is exhausted — needs your decision

^n was the last unclaimed ctrl-letter (a–z minus RESERVED_KEYS are
all assigned). New/Delete (#10), sort (#12), and gif (#13) will need
chords. Options to weigh, roughly in my preference order:
1. Audit RESERVED_KEYS (c d e h i j m q z) — some may be safely
   bindable in this app's contexts; even 2–3 recovered letters buys
   a year.
2. A ctrl+shift layer (kitty protocol carries it; Ghostty yes,
   tmux-from-phone needs testing) for rarer actions.
3. Contextual reuse with a precedence rule (same chord, different
   meaning per kind) — cheapest, but invisible modality; I'd avoid.

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

## fix multi-artist (^x, folder action — folderize's twin)

- [ ] `fi^x multi-artist` appears on folders (and album bulk views)
      whose subtree has slash-tangled artist/albumartist tags; absent
      on clean libraries (same late-probe fill as folderize)
- [ ] Press: preview lists each album as "Album → Main Artist" with
      the tangled files' old values; ^a applies, esc/cancel backs out
- [ ] AC/DC guard: an album under an artist folder literally named
      "AC-DC" (sanitized slash) must NOT be offered — the slash is
      the band's name. Try it on real AC/DC rips if you have them.
- [ ] v1's per-album include/exclude checkboxes are gone by design:
      scope by invoking on a smaller folder. Veto if you miss them.
- [ ] Note: folderize's apply/cancel buttons are now shared with this
      feature (`^apply`/`cancel` label unchanged) — regression-check
      folderize preview still applies/cancels correctly

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
