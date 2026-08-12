# Fable → Opus handoff — todo-4 + todo-5 execution (2026-08-12)

Claude Fable 5 is executing `notes/claude/todo-4.md` + `todo-5.md` under a
fixed usage-credit budget. **If you are Opus 5 picking this up: read
CLAUDE.md, `notes/claude/terms-of-art.md`, and todo-4.md first**, then
continue from the first unchecked item below. One commit per item; each
commit message names its item. Update this file as you go.

## Decisions already made with Nick (do not re-ask)

1. **Reserved-key conflicts in the Button Refactor** (^i import, ^c clean ×2,
   ^h shift subs, ^m mobi ×2, ^j jpg, ^z resize are reserved/terminal
   aliases): substitute the nearest safe letter for those six, implement the
   rest exactly per spec, and **log each substitution in `notes/qa/todo-2.md`**
   (the empty QA ledger — Nick called it "todo-2.md"), quoting the full
   button text with the from→to chords. Anything else from this refactor
   needing Nick's post-hoc attention also goes in that file.
2. **Path Input inside Tree View**: real structural change — a new
   `TreeView` container widget owns `PathInput` + `LibraryTree`; border,
   focus state, and tree-level state (clipboard) live on the container.
3. **Collapse level**: rebind to ctrl+left; keep shift+left as a hidden
   alias. Strip prints `^← collapse level`.
4. **^/ stays available while the clipboard is active** (add `^/ path` to
   the clipboard-state strip) so cut → ^/ → destination → paste survives.
5. **Strict focus scoping** (consequence Nick approved by silence, stated
   explicitly before starting): chords no longer fire from the tree for
   Details-view actions. Video/folder actions require ⏎ into Details view.
   Every kind is enterable (rename form), so nothing is unreachable.
6. **^DEL lines read sequentially**: strip refactor renames the trash
   button → "delete"; the later Button Refactor removes the button from
   every kind. End state: delete is a Tree-view command (^DEL) only.
7. The stray `*` on "^upload cover *" in todo-4 is treated as a typo.

## Terms-of-art rename map (applied in item 2)

- `DetailsPane` → `DetailsView`; handler prefix `details_pane_` → `details_view_`
- `PathBar` → `PathInput`
- `LibraryTree.Focused` → `LibraryTree.Selected` (cursor highlight);
  old `LibraryTree.Selected` (multi) → `LibraryTree.BulkSelected`
- actions: `fold_open`→`expand`, `fold_close`→`collapse`,
  `to_details`→`edit`, `new_folder`→`new_directory`, `trash`→`delete`,
  `fix_multi_artist`→`strip_multi_artist` (labels updated to match)
- "wizard" is a term of art (Inline Input Wizard) — kept.
- `LibraryTree` keeps its name (the tree widget inside the TreeView container).

## Queue (Nick-approved order; commit per item)

- [x] 1. todo-5 bulk-save focus bug — commit 62913ca; regression test
      `test_bulk_save_keeps_focus`.
- [x] 2. Terms-of-art refactor (rename map above) — sed across
      mediasmith/ + tests/; `action_markup` also fixed to never splice a
      multi-char key_label ("^DEL delete", not "^delete").
- [ ] 3. **TreeView container** (todo-4 "Move Path Input Inside Tree View").
      New `TreeView` (Vertical container) in browser.py owning
      PathInput + LibraryTree; mockup `notes/mockups/path-input.txt`:
      the input is a bordered box INSIDE the tree's border. Move the
      `#left`/border/focus CSS onto TreeView (`:focus-within` lights the
      container); app.py composes `TreeView` and stops talking to two
      siblings. Keep narrow-breakpoint behavior (-path-open etc.).
- [ ] 4. **Color theme stylesheet** (todo-4 last item). New
      `mediasmith/theme.py` holding Nick's `Theme` verbatim (name→hex map;
      resolve "$ref" values in Python before constructing Theme —
      Textual variables can't reference each other reliably).
      `register_theme` + `self.theme = "mediasmith"` in App.
      Replace ALL hardcoded colors ($accent, orange, #ffe6c2, etc.)
      with his tokens; implement the idle/focus dimming his variable
      pairs describe (border/text/cursor/scrollbar/label/button swap on
      view focus; details uses :focus-within). Chord colors inside
      button labels are markup, not CSS — relabel on pane focus change
      (watch screen.focused; app.py `_sync_strips` shows the pattern).
      Hidden-file dimming (`node-hidden-fg-*`) is new: stylize dotfile
      labels in `LibraryTree.render_label`. Never hardcode colors again.
- [ ] 5. **Command strip & keybinding refactor** (todo-4). ONE strip
      (delete `#ctxrow`), state-driven: Tree / PathInput / Details /
      Clipboard states exactly per todo-4 spec (+ `^/ path` in clipboard
      state per decision 4; `^v paste`+`esc cancel` in primary color).
      Key changes: ^e new → **^n new directory**; move (^n) becomes
      **^x cut** (tree-only command, button removed from Details);
      **^v paste**; ^del → **^DEL delete**; **^← collapse level**
      (⇧← hidden alias); type-jump stays but leaves the strip;
      "→ edit" duplicate removed (⏎ only); ^/ only from Tree view.
      Enforce "not shown → not available" per state.
- [ ] 6. **Copy** (todo-4). ^c is reserved — pick a safe chord and log it
      in notes/qa/todo-2.md. Copy follows cut's pattern (clipboard holds
      one selection; paste duplicates instead of moving; shutil.copy2/
      copytree in a worker, refuse-overwrite per file).
- [ ] 7. **Responsive strip styles** (todo-4): one strip, wraps at narrow
      widths (FlowLayout in actions.py is the wrapping row primitive),
      keybindings nowrap, logo right-aligned (space-between), logo yields
      before collision (LOGO_MIN_WIDTH logic exists).
- [ ] 8. **Button refactor** (todo-4): per-kind renames/order per spec +
      safe substitutes for the six reserved chords (log in qa/todo-2.md).
      Remove move/new-folder/trash buttons from Details view. Nested
      (indented) entries are conditional visibility. "(when …)" =
      existing show/hide rules. Chord dispatch becomes view-scoped
      (decision 5) — remove the fire-from-tree path in App.on_key.
- [ ] 9. **Focus lockdown** (todo-4): while a sub-form/wizard or plan
      preview is focused, keys must not reach Details view or the tree
      (e.g. pending subtitle shift must not shadow a rename ^s).
      Sub-views per terms-of-art: Import Album Art, Import Cover, Shift
      Subtitles, Resize Image, Make GIF, Split Omnibus; plan previews.
- [ ] 10. **CLAUDE.md update**: pane-hierarchy diagram gains PathInput
      inside TreeView; terms-of-art names; new strip model; note
      notes/qa/todo-2.md as the active QA ledger.

## Working rules

- Test per item (`pytest tests/ -q`, full suite ~10+ min — background it);
  fuzz gate (snapshot copy! see CLAUDE.md) at milestones 5 and 9.
- New chords → tests/fuzz.py KEYS.
- Nick QAs visuals; don't over-iterate look-and-feel, land the spec.
