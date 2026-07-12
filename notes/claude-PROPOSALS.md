# Proposals — unified search & folder Move

Written by Fable 5 (2026-07-11, session 2) per claude-TODO #15 and the
handoff brief. Constraints honored throughout: no modals, the pane
hierarchy stays intact, phone width must work.

**DECIDED (Nick, 2026-07-11 evening):**

- **Search: none of the below.** Nick's reframe: "unified search" is
  really *download tools*, and they only fit mediasmith if downloads
  land at the browser's location — which Anna's Archive (link-only
  without a paid API) can't honor. Download tools move to
  ~/code/downloader (Claude-in-the-loop pipeline; deemix can target a
  directory, Anna produces verified links via manifest). The
  mediasmith seam is the filesystem: downloader stages files,
  mediasmith tags/folderizes/moves them. See
  ~/code/downloader/anna-search-audit.md for the v1 strategy audit
  that came out of this. Options S1–S3 below are kept for the
  record only.
- **Move: M1 approved** (cut/paste with strip-visible pending state).
  Nick also confirmed M2's insight from the user side: cut → ^/ →
  type path → ⏎ → paste IS the type-a-destination flow, composed
  from existing parts — which requires the lift to survive path-bar
  jumps. Built same day; see the commit and QA-TODO.


## Unified search (Deezer · Anna's Archive · future serial scraping)

The reframe that makes this fit the app: **search results are just
details of a query** — so they belong in the details column, which
already knows how to swap content in and out (folderize preview,
narrow "view").

### Option S1 — a search panel in the details column  ← recommended

- A global chord (say `^g`, placeholder) swaps the details column to
  a search panel: query input on top, result list under it.
- **Kind-aware by browser context**: invoked while an audio file or
  album folder is highlighted → Deezer; while a book/Books folder →
  Anna's Archive; ambiguous → whichever was used last, with a
  provider button row (the app's standard buttons) to switch.
- The pane hierarchy holds: the query input controls the result
  list (live, like the path bar controls the tree); ↓/⏎ descends
  into the list; ⏎ on a result acts (download); esc ascends list →
  input → panel closes, browser restored.
- **Downloads land in the folder the browser is sitting in.** That's
  the payoff of putting search inside the browser instead of over
  it: where you are is where it goes. Refuse-overwrite +
  `FileCreated` as usual.
- Narrow mode: identical to the existing `-details-open` swap; no
  new layout work.
- Serial scraping later = one more provider whose "results" are
  chapters/books; same panel, same list.

### Option S2 — search as a path-bar mode

Typing a sigil (`?query`) or a chord flips the path bar into a query
field and the **tree** shows results as nodes. Elegant on paper
(results get marking/details for free), but tree nodes are Paths
everywhere (`node.data.path`, the adapters, the cache); teaching the
tree about remote non-path entries touches every layer. High churn,
and mixing remote results into the filesystem surface muddies "the
tree is the truth about your disk". Not worth it.

### Option S3 — a pushed full Screen (a separate "page")

Not technically a modal, but it abandons the one-surface model, needs
its own narrow-mode work, and the browser context (where downloads
land) is lost. The k9s/lazygit pattern suits apps without a spatial
home base; this app has one. Pass.

**Recommendation: S1.** Smallest new surface, reuses the swap
machinery that already exists twice, and it gives search a spatial
meaning (results drop where you stand) instead of being a detached
utility. Open questions for Nick: the chord; whether the result list
should offer per-result buttons (preview/download variants) or just
⏎-to-download; whether `dzr-srt`-style tooling is still the Deezer
transport.


## Folder Move

Your instinct ("easy operation, heavy UI") is right if Move gets its
own surface. It shouldn't. The pattern hiding in plain sight is
**cut → navigate → paste**, which every single-pane file manager
converged on (ranger `dd`/`pp`, Finder ⌘C/⌘⌥V, mc F6): the *browser
itself* is the destination picker — you already built the hard part.

### Option M1 — cut/paste with strip-visible pending state  ← recommended

- `^x` (placeholder) on the highlighted file/folder — or the current
  shift-selection, later the space-marks — lifts it: the strip gains
  a persistent segment: `moving 3 files · ^v place here · esc cancel`.
- Browse anywhere, exactly as normal (that's the whole UI).
- `^v` moves into the highlighted folder (or the highlighted file's
  parent). Worker + notify; cross-volume (NAS↔local) is copy+delete
  and can take a while — notify start/end like conversions.
- Guards: refuse-overwrite per file; placing into the source folder
  = no-op toast; placing a folder into its own subtree = refused.
- esc cancels the lift (before any other esc meaning fires).
- Optional garnish, not required for v1: while a lift is pending,
  the details pane's folder view adds a line "^v moves 3 files
  here". The strip already carries the state; this just localizes it.
- Phone width: free — no second pane, no new column.

### Option M2 — a "move to path" wizard div on the details pane

A `move` button opens the shift-div-style inline row with a
tab-completing path input (ArtPathInput's machinery). Works, and the
parts exist — but typing paths is the weakest input on the phone,
and it duplicates the browser's one job (going places) in a text
field. Keep as a possible *addition* for power use, not the primary.

### Option M3 — dual-pane mode

The mc/Norton answer. It's the biggest layout change the app could
make, exists only to serve Move, and dies at phone width. Pass.

**Recommendation: M1**, with New/Delete (#10) landing first so the
full CRUD story arrives together. Open questions for Nick: chords
(^x/^v collide with Input cut/paste — fine while the tree has focus,
which is the only place lifting makes sense, but say if you want
different keys); should a lift survive a path-bar jump (I say yes —
that's the point); does Move belong on the strip permanently or only
once something is lifted (I say only while lifted — zero chrome
otherwise).
