# QA to-do — 2026-07-15 session 2 (images: rename · convert · resize ·
# rotate)

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
