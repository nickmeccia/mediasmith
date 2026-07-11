# mediasmith — architecture handoff

Context for Future Claude (and future Nick). This repo is a clean-slate
rewrite; everything before it is R&D, frozen at `~/code/mediasmith-v1`
(also on GitHub). Read this before writing any code.

## What this app is

One fullscreen Textual TUI with a **file-browser model** — not v1's
menu-of-tools model. The UX was prototyped and user-approved in
`~/code/mediasmith-v1/mediasmith-ux/app.py`; that file is the reference
implementation to consult, not code to import.

```
┌──────────────────────┬───────────────────────────────┐
│ path input (prefix-  │ details of highlighted file   │
│ match, tab-complete) │  · metadata per file kind     │
├──────────────────────┤  · cover / poster image       │
│ directory tree       │  · contextual action buttons  │
│  ↑↓ move, ←→ fold    │    (shortcut chars accented)  │
│  space mark files    │  · batch bar when marks exist │
├──────────────────────┴───────────────────────────────┤
│ command strip — reference only, no buttons           │
└──────────────────────────────────────────────────────┘
```

- Details pane **follows the tree highlight** (debounced), no Enter needed.
- Marking files (`space`) grows a batch bar; batch actions apply only when
  all marked files share one kind.
- Actions are contextual per kind: video → download subtitles/posters,
  audio → editable tag form, book → Calibre-backed metadata, folder →
  whole-folder actions.
- `^S`-style shortcuts are contextual (save tags / download subs / batch
  apply — batch wins when marks exist).

## Interaction model: the pane hierarchy

Nick's core mental model — every navigation or focus decision must stay
consistent with it. The views form a chain of command; **each view
controls the view beneath it**, and the details view controls the file
itself. Focus only ever moves one link at a time: descending is always
deliberate, ascending is always esc-shaped.

```
        ┌──────────────┐
        │  path input  │   what it controls: which directory/filter
        └──────┬───────┘   the browser shows (live while typing)
   descend: ⏎ / esc (commit / cancel — the input never keeps focus)
   ascend:  ^/ from anywhere
        ┌──────▼───────┐
        │ file browser │   what it controls: which file (or selection)
        └──────┬───────┘   the details view shows — HOME BASE: never
   descend: ⏎ ⇥ →          gives up focus implicitly, ↑ at top stays put
     · only when the shown selection is editable (EDITABLE_KINDS)
     · → doubles as fold-open on folders; ⏎ never toggles folds
   ascend:  esc · ← when ← has no other job (text cursor at start,
            leftmost method button, pane itself focused)
        ┌──────▼───────┐
        │ details view │   what it controls: the file's name, tags,
        └──────┬───────┘   and art — all edits PENDING until saved
   descend: nothing to focus below — the "descent" is the write:
     · ^s (or the save button) commits; esc with pending edits asks
       (ConfirmSave modal: save / discard / keep editing)
     · ✓ after a field = the write manifest: exactly what ^s will touch
        ┌──────▼───────┐
        │   the file   │
        └──────────────┘
```

Consequences that follow from the model (don't break them):

- Within details: filename field first, ↑↓/⇥ move between fields, inputs
  are immediately editable on focus (cursor at end, nothing selected).
- Action methods (album art today, more later): compact buttons under
  the target, left→right, each printing its shortcut ("path  ^o"); ↓
  from the field above reaches them, ←→ moves within the row, ⏎ or the
  shortcut activates. Their results feed the same pending/✓/save flow.
- Bulk editing rides the same chain: the browser's *selection* (shift
  range, or an album-like leaf folder ≡ its writable children) is what
  descends into details; the bulk form writes only ✓-marked fields, to
  every file. Divergent values show a `(mixed)` placeholder; a mixed
  field emptied back out returns to "leave every file alone."

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
   - debounce highlight-driven file reads (~150ms);
   - anything slower than a tag read (ffprobe, network) runs in a thread
     worker and fills in late; verify the selection hasn't moved before
     applying the result.

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
   manifest; ConfirmSave modal.
3. **Engine actions** — subtitles first (port the v1 engine). ⬅ next
4. **Batch operations.** Partially done ahead of schedule: shift-range
   and album-folder bulk editing shipped (2026-07-10); space-marking +
   batch bar still to come as a third gesture over the same selection
   set (`LibraryTree._selection_paths` / `DetailsPane.preview_bulk`).
5. **Responsive/mobile** — narrow-width breakpoints for tmux-from-phone;
   tree-first two-step flow on narrow screens.

Session notes: `notes/QA-TODO.md` tracks what awaits Nick's manual QA
pass, plus small parked UX decisions (save-button/info-row placement,
strip wording, per-field ✓ revert).

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
