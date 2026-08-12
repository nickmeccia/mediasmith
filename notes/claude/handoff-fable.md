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
- [x] 3. **TreeView container** — commit e220130 (with item 2).
- [x] 4. **Color theme stylesheet** — commit db8e2db. theme.py is the
      palette; CSS is state; hidden-file dimming + chord-markup relabel
      (`DetailsView._sync_button_chrome`) included.
- [x] 5. **Command strip & keybinding refactor** — strip.py (states +
      wrapping renderer); tree commands ^x/^v/^n/^DEL/^← (⇧← alias);
      "→ edit" retired; ^/ tree-gated; clipboard state locks out ⏎ edit
      and second cut.
- [x] 6. **Copy** — ^y (cop^y; ^c reserved, logged). Paste duplicates
      (copy2/copytree), clears the clipboard either way.
- [x] 7. **Responsive strip** — CommandStrip wraps greedily, trailing ·
      on the line end, logo right-aligned on the last line.
- [x] 8. **Button refactor** — PANE_ACTIONS reworked to todo-4 words/
      keys/order; six reserved-chord substitutions logged in
      notes/qa/todo-2.md; move/new-directory/delete buttons removed;
      chords view-scoped (App.on_key); FieldInput forwards Input-eaten
      chords to visible buttons; plan previews take focus (apply btn).
- [x] 9. **Focus lockdown** — `DetailsView._focus_scope()` +
      scoped `_nav_items`: a focused sub-form (art path, cover path,
      shift, resize, gif, omnibus form) confines chords and ↑↓ to its
      own controls; each wizard's scope includes its toggle + write.
- [x] 10. **CLAUDE.md updated** (diagram, hierarchy, rules 5, cookbook,
      roadmap session-3 entry, QA-ledger pointer).

## Done — verification record

- Full pytest suite: 361 passed, 0 failed (2026-08-12, post-item-9).
- Fuzz gate (snapshot copy, new chords in KEYS): **0 deaths / 6 seeds**.
- Queue complete: todo-4 (all 8 items) + todo-5 executed and committed
  (62913ca → fc7e165). Nothing left to hand off except Nick's QA pass:
  **notes/qa/todo-2.md** holds every rename and judgment call awaiting
  him, and the visual pass (theme dimming, strip wrapping, path input
  inside the tree pane) is his by design.

## Working rules

- Test per item (`pytest tests/ -q`, full suite ~10+ min — background it);
  fuzz gate (snapshot copy! see CLAUDE.md) at milestones 5 and 9.
- New chords → tests/fuzz.py KEYS.
- Nick QAs visuals; don't over-iterate look-and-feel, land the spec.
