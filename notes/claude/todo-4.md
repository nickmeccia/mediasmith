**Context for this File** -- The goal for this entire `todo-4.md` file is to standardize, organize, and simplify the mental model through which the user understands the capabilities of this application through the user interface, and to standardize, organize, and simplify the codebase to match this same mental model.


- [ ] Move Path Input Inside Tree View

I would like to reconsider the zones of this app according to the following diagram:

 ┌───────────────┐ ┌─────────────────────┐
 │Tree View      │ │Details View         │
 │┌─────────────┐│ │                     │
 ││Path Input   ││ │                     │
 │└─────────────┘│ │                     │
 │               │ │                     │
 │               │ │                     │
 │               │ │                     │
 │               │ │                     │
 │               │ │                     │
 │               │ │                     │
 └───────────────┘ └─────────────────────┘
 ┌───────────────────────────────────────┐
 │Command Strip                          │
 └───────────────────────────────────────┘
 
Currently, this app considers Path Input to be a zone separate from Tree View and from Details View, and equal in hierarchy. I would like to change the mental model of Path Input to be a subview of Tree View, instead of its own view. Consequences:

- The UI needs to change. Please see ~/code/mediasmith/notes/mockup-path-input.txt for a mockup.
- The command strip needs to change. Please see `Command Strip & Keybinding Refactor` below.
- The code needs to change...potentially. As a UX designer, if I were coding the front end of this app in HTML and CSS, this mental model change would absolutely inspire changes to my code. What that means for you, I don't know, as this codebase was written entirely by Claudes. Please discuss this consequence with me.
- CLAUDE.md needs to be updated to reflect this change.


- [ ] Terms of Art

I created a new "terms of art" file, which CLAUDE.md instructed you to read when I started this session. I want to be able to communicate accurately and efficiently to Future Claudes, and precise diction will help me immensely in crafting clear instructions.

Please refactor the code according to this terms of art file, so that our conversations can align around these specific terms. Note that many terms of art rename existing concepts and commands; please also consider the remainder of this file as context for parsing ambiguity present in the terms of art file alone. If you still encounter ambiguity--or unearth refactoring or UI decisions which need to be made--please discuss with me.


-[ ] Command Strip & Keybinding Refactor

Mediasmith currently has three command strips:

- Global (bottom line, always shows same commands)
- Tree (left-aligned to left pane, shown when Tree view is focused)
- Details (left-aligned to right pane, shown when Details view is focused)

After developing the app to this point and reflecting upon the keybindings needed for each of the three states, it has become clear that three command strips are not needed:

- The Global command strip only needs ^q
- The Details command strip only needs ESC, because the keybindings are represented as buttons instead of in the command strip
- The Tree command strip still needs many keybindings

Please refactor the Mediasmith command strips into one one command strip, which shows different keybindings depending on state.

## State: Tree view focused
├─ ↓↑ navigate (current: ↑↓ ←→ move)
│  Rename this command on the command strip only; no behavior needs to change
├─ → expand (current: ↑↓ ←→ move)
│  Write a new keybinding on the command strip for this command; no behavior needs to change
├─ ← collapse (current: ↑↓ ←→ move)
│  Write a new keybinding on the command strip for this command; no behavior needs to change
├─ ^← collapse level (current: ⇧← collapse)
│  Rename only; no behavior change
├─ (current: → edit)
│  Remove this command from the app. I have decided that I do not want to duplicate the function of "enter"
│  conditionally dependent on context.
├─ (current: type jump)
│  Remove this keybinding from the command strip, but keep the command. I like this functionality, but it's too
│  difficult to communicate this behavior concisely in the command strip.
├─ ENT edit (current: ⏎ edit)
│  Rename only; no behavior change
├─ ^r refresh (current: ^r refresh)
│  No rename or behavior change 👍
├─ ^. toggle hidden files (current: ^. hidden)
│  Rename only; no behavior change
├─ ^n new directory (current: ^e new)
│  Rename only; no behavior change
├─ ^x cut (current: ^n move (in Details view))
│  This command currently lives as the `^n move` button in the Details view; please add this keybinding to the
│  command strip and remove its button from Details view.
├─ ^DEL delete (current: ^del trash)
│  Rename in command strip & Details view (do not remove from Details view)
├─ ^/ path (current: ^/ path)
│  No rename or behavior change. Please note, however, that this keybinding should only appear when
│  the Tree view is focused.
╰─ ^q quit (current: ^q quit)
   No rename or behavior change 👍

### Notes on this state
- `move ^n` is currently an action that can be performed on a node from a button in Details view. This is not the right mental model for this action. The mental model for this action, even as it is implemented now, is "cut" and "paste". This command should be renamed to "cut", and it should be a command which the user can execute on any node from Tree view *only*.

## State: Path input focused
├─ TAB complete (current: ⇥ complete)
│  Rename only; no behavior change
├─ ENT go (current: ⏎ go)
│  Rename only; no behavior change
├─ ESC cancel (current: esc cancel)
│  Rename only; no behavior change
╰─ ^q quit (current: ^q quit)
   No rename or behavior change 👍

### Notes on this state
- This state can only be achieved by pressing ^/ while the Tree view is focused.

## State: Details view focused
├─ ↓↑ navigate (current: ↑↓ fields)
│  Rename only; no behavior change
├─ (current: ^s save)
│  Remove keybinding from command strip -- this command is better represented by its button in Details vew itself
├─ ESC close (current: esc back)
│  Rename only; no behavior change
╰─ ^q quit (current: ^q quit)
   No rename or behavior change 👍

## State: Node present on clipboard
├─ ^v paste (current: ^n place here)
│  Rename only; no behavior change. Color this keybinding in the primary brand color to emphasize this state.
├─ ESC cancel (current: esc cancel)
│  Rename only; no behavior change. Color this keybinding in the primary brand color to emphasize this state.
├─ ↓↑ navigate (current: ↑↓ ←→ move)
│  Rename this command on the command strip only; no behavior needs to change
├─ → expand (current: ↑↓ ←→ move)
│  Write a new keybinding on the command strip for this command; no behavior needs to change
├─ ← collapse (current: ↑↓ ←→ move)
│  Write a new keybinding on the command strip for this command; no behavior needs to change
├─ ^← collapse level (current: ⇧← collapse)
│  Rename only; no behavior change
├─ ^r refresh (current: ^r refresh)
│  No rename or behavior change 👍
├─ ^. toggle hidden files (current: ^. hidden)
│  Rename only; no behavior change
├─ ^n new directory (current: ^e new)
│  Rename only; no behavior change
├─ ^DEL delete (current: ^del trash)
│  Rename in command strip & Details view (do not remove from Details view)
╰─ ^q quit (current: ^q quit)
   No rename or behavior change 👍

### Notes on this state
- User only has access to the "cut" command when the Tree view is focused
- Therefore this state is only accessible from the Tree view
- So, this command strip is a modification of the Tree view command strip, with certain keybindings removed and certain commands made unavailable.
  - For example, `^ENT edit` does not appear in this list, because the user shouldn't be able to edit a node's details while carrying an item on the clipboard.
  - As another example, `^x cut` also does not appear in this list, because the user shouldn't be able to cut a second node while already carrying a node on the clipboard.

## Additional Notes

- If a keybinding is not shown in a particular state, its associated command should not be available for the user to execute. For example: `^/` should only trigger focus to the path input from the Tree view. Pressing this command in Details view should do nothing.


- [ ] Command Strip Responsive Styles

Now that the command strip is one line which changes on context, please follow these responsive rules:

- Keep the `justify-content: space-between` rule which separates the keybindings from the logo.
- As the viewport narrows, wrap the command strip onto multiple lines.
- Each keybinding should follow a `white-space: nowrap` rule to prevent it from breaking onto multiple lines
- Please note that the following examples do not follow the new command strip keybindings from the previous checklist item

## Example 1 -- Wide Viewport

```
======= viewport width ======================================================================================
↑↓ ←→ move · ⇧← collapse · type jump · ⏎ edit · ^r refresh · ^e new · ^del trash          𜵎𜵎▖𜷇🯦𜷇▌𜵅𜷃𜵈𜷓𜴀𜵎𜵎▖𜵅𜶍▐𜶓
======= viewport width ======================================================================================
```

## Example 2 -- Medium Viewport

```
======= viewport width =========================================
↑↓ ←→ move · ⇧← collapse · type jump · ⏎ edit · ^r refresh ·
^e new · ^del trash                          𜵎𜵎▖𜷇🯦𜷇▌𜵅𜷃𜵈𜷓𜴀𜵎𜵎▖𜵅𜶍▐𜶓
======= viewport width =========================================
```

## Example 3 -- Narrow Viewport

```
======= viewport width ===============
↑↓ ←→ move · ⇧← collapse · type jump ·
⏎ edit · ^r refresh · ^e new ·
^del trash         𜵎𜵎▖𜷇🯦𜷇▌𜵅𜷃𜵈𜷓𜴀𜵎𜵎▖𜵅𜶍▐𜶓
======= viewport width ===============
```


- [ ] New Feature: Copy

By renaming `^n move` to `^x cut` and moving the command from Details view to Tree view, I have introduced the idea of a clipboard to Tree view. However, if users are able to cut & paste files, it follows that they should be able to copy files, too.

Please add a feature to copy nodes in Tree view, following the patterns of "cut".


- [ ] Button Refactor

I would like to refactor the names, order, and presence of all the buttons available in Details view.

Please apply the following CSS to this checklist item:

```
.primary {
  color: #FFA500;
}
```

Also, yes, this section follows a different format from the command strip section:

`name of command & keybinding --> new name & keybinding with color`

Please consider the order of the buttons in each respective list to be the order in which I would like the buttons arranged.

## Audio
- save ^s --> <span class="primary">^s<span>ave
- path ^o --> <span class="primary">^i<span>mport
- fetch ^f --> <span class="primary">^f<span>etch
- move ^n --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)

## Video
- get subs ^k --> <span class="primary">^f<span>etch subtitles
  - clean subs ^u --> <span class="primary">^c<span>lean subs (when .srt present)
  - shift subs ^v --> s<span class="primary">^h<span>ift subs (when .srt present)
    - save ^s --> <span class="primary">^s<span>ave (while shift wizard open)
- watch ^w --> <span class="primary">^w<span>atch
- download posters ^d --> download <span class="primary">^p<span>osters
- make gif ^g --> make <span class="primary">^g<span>if
  - apply ^a --> <span class="primary">^s<span>ave (while gif editor open)
- move ^n --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)

## Epub
- save ^s --> <span class="primary">^s<span>ave
  - split omnibus ^e --> split omni<span class="primary">^b<span>us (when omnibus)
- convert to mobi ^b --> convert to <span class="primary">^m<span>obi
- convert to azw3 ^y --> convert to <span class="primary">^a<span>zw3
- create opf ^g --> write <span class="primary">^o<span>pf
- standardize ^d --> <span class="primary">^c<span>lean
- cover ^f --> <span class="primary">^u<span>pload cover *
  - extract cover ^t --> <span class="primary">^e<span>xtract cover (when cover present)
- sort ^o --> <span class="primary">^f<span>olderize
- move ^n --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)

## Mobi / AZW3
- save ^s --> <span class="primary">^s<span>ave
- convert to epub ^e --> convert to <span class="primary">^e<span>pub
- convert to mobi ^b --> convert to <span class="primary">^m<span>obi
- convert to azw3 ^y --> convert to <span class="primary">^a<span>zw3
- move ^n --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)

## Image
- save ^s --> <span class="primary">^s<span>ave
- rotate ^o --> <span class="primary">^r<span>otate
- resize ^e --> resi<span class="primary">^z<span>e
  - apply ^a --> <span class="primary">^s<span>ave
- convert to jpg ^p --> convert to <span class="primary">^j<span>pg
- convert to png ^g --> convert to <span class="primary">^p<span>ng
- convert to tiff ^f --> convert to <span class="primary">^t<span>iff
- convert to webp ^b --> convert to <span class="primary">^w<span>ebp
- move ^n --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)

## Folder
- save ^s --> <span class="primary">^s<span>ave
- new folder ^e --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)
- trash ^del --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)
- move ^n --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)

## Other (Unknown Extension)
- save ^s --> <span class="primary">^s<span>ave
- move ^n --> Please remove this button and disable this command from Details view (see "Command Strip & Keybinding Refactor" above)


- [ ] Focus

A Previous Claude casually wrote this message while making changes:

“Let me note one edge case (a pending subtitle shift takes save precedence over a simultaneous rename)”

According to the new `terms-of-art.md` (above), the user should not be able to affect any view outside of the currently-focused view. Thereform, if the user has the "shift subtitles" sub-form focused, commands to the Details View for that node should not be transmittable--the user can only interact with the "shift subtitles" command.

For this checklist item, would you please lock down this behavior between all views and sub-views?


- [ ] Color Theme Stylesheet

I would like to collect all colors defined in this app in a single file, like a stylesheet, where each color is a hex code assigned to a variable name. Please refactor all existing colors, and in the future do not hardcode color values anywhere in the app -- only use variables from this stylesheet instead.

A Previous Claude gave me the following template for communicating my stylesheet idea to you; please use fresh judgment when implementing and do not take its formatting as an instruction. The color names and hex codes are, however, the content I want you to implement.

```
The example below is in two blocks, because focus is a
STATE, not a color, and a `Theme` is only a name→color map:

  · PALETTE (`Theme`) — every hex, named once. The idle/focus PAIRS live
    here too: the palette names both looks, but can't apply either.
  · STATE (CSS) — references those names by pseudo-class to decide WHEN
    each look applies. No hex, no color choice — only selectors + states.
    This is what makes "swap primary→grey on blur" and "dim the rest"
    happen; both are the same `:focus` flip on different properties.
```

```python
from textual.theme import Theme

# ── PALETTE ─ the one file that holds every hex ─────────────────
# Only Textual's fixed semantic slots (primary, success, background…)
# sit at the top level. The grey ramp and every app token live in
# `variables`, where a name is a literal hex OR a "$ref" to another.
MEDIASMITH = Theme(
    name="mediasmith",
    dark=True,

    primary="#ffa62b",
    success="#4ebf71",
    warning="#ffa62b",
    error="#ba3c5b",
    background="#1b1b1b",   # = grey-10, the app canvas
    foreground="#e2e2e2",   # = grey-90, brightest body text

    variables={
        "black":   "#000000",
        "grey-10": "#1b1b1b",
        "grey-20": "#303030",
        "grey-30": "#474747",
        "grey-40": "#5e5e5e",
        "grey-50": "#777777",
        "grey-60": "#919191",
        "grey-70": "#ababab",
        "grey-80": "#c6c6c6",
        "grey-90": "#e2e2e2",
        "white":   "#ffffff",


        # Focused View
        
        "border-fg-focus": "$primary",
        "text-fg-focus": "$grey-90",

        "node-hidden-fg-focus": "$grey-60",
        "node-selected-bg-focus": "$primary",
        "scrollbar-color-focus": "$grey-90",
        "scrollbar-color-hover-focus": "$primary",
        "scrollbar-color-active-focus": "$primary",
        "scrollbar-track-focus": "transparent",

        "label-fg-focus": "$grey-60",
        "button-bg-focus": "$grey-30",
        "button-fg-focus": "$grey-90",
        "button-keybinding-fg-focus": "$primary",
        "button-selected-bg-focus": "$primary",
        "button-selected-fg-focus": "$grey-90",
        "button-selected-keybinding-fg-focus": "$grey-90",


        # Idle View

        "border-fg-idle":  "$grey-30",
        "text-fg-idle": "$grey-40",

        "node-hidden-fg-idle": "$grey-30",
        "node-selected-bg-idle": "$grey-20",
        "scrollbar-color-idle": "$grey-30",
        "scrollbar-color-hover-idle": "$grey-30",
        "scrollbar-color-active-idle": "$grey-30",
        "scrollbar-track-idle": "transparent",

        "label-fg-idle": "$grey-30",
        "button-bg-idle": "$grey-20",
        "button-fg-idle": "$grey-40",
        "button-keybinding-fg-idle": "$grey-40",
        "button-selected-bg-idle": "$grey-20",
        "button-selected-fg-idle": "$grey-40",
        "button-selected-keybinding-fg-idle": "$grey-40",


        # Command Strip

        "keybinding": "$grey-60",
        "keybinding-bullet": "$grey-30",
        "logo": "$grey-60"

    },
)
```

Note from Nick: the following block of code no longer maps to exact variables. Consider it an example from Previous Claude, written before I finished writing my color variables.

```css
/* ── STATE ─ WHEN each look applies. Rule of the pane hierarchy: a view
   is "focused" when it owns focus — details uses :focus-within, so a
   focused child field counts as the pane. Rest = the dim/grey look;
   :focus lights the accents back up. Every value is a $token. */

/* 1 — border swap */
PathBar, LibraryTree, DetailsPane      { border: round $border-idle; }
PathBar:focus,
LibraryTree:focus,
DetailsPane:focus-within               { border: round $border-focus; }

/* 2 — selected node (the tree cursor) swap */
LibraryTree > .tree--cursor {
    background: $node-selected-idle-bg;
    color:      $node-selected-idle-fg;
}
LibraryTree:focus > .tree--cursor {
    background: $node-selected-focus-bg;
    color:      $node-selected-focus-fg;
}

/* 3 — dim the rest: text + scrollbar ride the same idle/focus flip */
LibraryTree              { color: $text-idle;
                           scrollbar-color: $scrollbar-thumb-idle;
                           scrollbar-background: $scrollbar-track; }
LibraryTree:focus        { color: $text-focus;
                           scrollbar-color: $scrollbar-thumb-focus; }
DetailsPane              { color: $text-idle; }
DetailsPane:focus-within { color: $text-focus; }

/* 4 — button swap (arrow-key focus landing on a button highlights it) */
ActionButton        { background: $button-idle-bg;  color: $button-idle-fg; }
ActionButton:focus  { background: $button-focus-bg; color: $button-focus-fg; }
```

