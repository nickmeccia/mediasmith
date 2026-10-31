
# TERMS OF ART

```
Term of Art
noun
"A word or phrase that has a precise, specialized meaning within a particular subject or activity."
```


## Global

- **Mediasmith** -- The name of this application.

### State

- **State** -- A snapshot of specific circumstances or configuration at a specific moment in time.

- **Focus** -- A state where the user's actions are restricted to affecting only a specific zone of the user interface, usually a specific view.

- **Gain Focus** -- A change in state where an area of the UI becomes focused through a specific event.

- **Release Focus** -- A change in state where an area of the UI becomes unfocused through a specific event.

- **Selected** -- A state representing a user's choice in a UI element which usually affects the state of a second UI element. For example, _selecting_ an audio file node in Tree View displays metadata and actions pertaining the that media type in the Details View.

- **Navigate** — A command which moves the selected state along a one- or two-dimensional track of options, depending on the context of the UI.

#### Element States

The four states an element can be in, named by Nick in todo-6 and kept
as the only colour vocabulary in `theme.py`. They are states of an
ELEMENT, not of a view.

- **Focusable** -- An element the user can move focus to, and therefore
  one whose value can be changed. It is marked by a background, which is
  what tells a focusable field apart from a read-only one -- a read-only
  value gets no background and no line out to the Path.

- **Triggerable** -- A keybinding printed on an element that works right
  now. Only the keybinding takes the colour, never the words beside it,
  so a glance at a bar or the Command Strip reads as "these keys fire."

- **Focused** -- The ONE element the user is on. Background and
  foreground both change, and its keybinding stops being coloured as
  triggerable: a chord needs no marking while it IS the thing you are
  on.

- **Traversed** -- Everything the focus moved THROUGH to reach the
  focused element: the selected tree node, the Path, and the buttons to
  the left of a focused button, with their links. An element traversed
  gets the focused colours; the Path gets the foreground only, because a
  line with a background is a bar, not a line.

- **Path** -- The line drawn from the selected tree node to the focused
  element, through the centre line between the two views. It shows only
  its own arms -- it turns toward what it reaches and stops there.


## Views

- **View** -- A self-contained component which visualizes one complete concept. In web application terms, a view could be an entire page, or a reusable subset of that page. Generic example views include modals, navigation, and any part of a page which can be recontextualized on a different page.

### Tree View

- **Tree View** -- This view displays a directory tree of the user's local filesystem, which can be navigated by pressing keybindings to trigger a suite of navigation and editing commands

#### Sub-Views

- **Path Input** -- This view is a text input which, at all times, displays the path to the current node in the tree. When focused, this input can be manipulated to change the selected node of the tree.

#### States

- **Default** -- The filesystem tree is navigable and manipulatable by most commands.

- **Clipboard Active** -- User has triggered either the "cut" or "copy" command and a node exists on the clipboard.

- **Path Input Focused** -- When the Path Input is focused, the user can only manipulate the Path Input, and no other part of Tree View.

#### Commands

- **Navigate** -- Move the selected state between adjacent nodes of the tree

- **Expand** -- Reveal the contents of the selected node as a subtree.

- **Collapse** -- Hide the contents of the selected node as a subtree.

- **Collapse Level** -- Collapse selected node and all sibling nodes.

- **Edit** -- Shift focus to Details View for selected node.

- **Refresh** -- Update Tree View with current state of filesystem.

- **Toggle Hidden Files** -- Show/hide hidden files in Tree View (files beginning with `.`),

- **New Directory** -- Create a new folder as a child of selected directory, or a new folder as a sibling of selected file.

- **Cut**, **Paste** -- Cut adds selected node to clipboard. The clipboard can only hold one selection at a time. When the user pastes, the node is moved to the new location.

- **Copy**, **Paste** -- Copy adds selected node to clipboard. The clipboard can only hold one selection at a time. When the user pastes, the node is duplicated at the new location.

- **Delete** -- Move selected node to the trash.

- **Quit** -- Closes the app.

### Details View

- **Details View** -- This view displays select data (usually metadata) about the selected node as an editable form culminating in a list of buttons which can perform advanced actions.

#### Sub-Views

##### Sub-Forms

- **Import Album Art** -- A form to add an album art image to an audio file from a local path.

- **Import Cover** -- A form to add a cover image to an ebook from a local path.

- **Shift Subtitles** -- A form to change the timestamps of a subtitle file.

- **Resize Image** -- A form to change the dimensions of an image.

- **Make GIF** -- A form to generate a GIF image from a video.

- **Image Trace** -- A form to turn an image into a black-and-white vector file (SVG, EPS, or PDF), modeled on Illustrator's Image Trace. While it is open, the image fills the rest of Details View and redraws as the tracing after each change; a key flips between the tracing and the source image.

- **Split Omnibus** -- A form to extract individual books from an omnibus ebook.

##### Plan Previews

- **Folderize** -- Wrap audio files or ebook files in folders according to a format-dependent algorithm. On a single ebook or a single video the wrap is one file's, so it runs immediately and has no preview: a video wraps into a folder named after its filename, taking its subtitles and art with it.

- **Strip Multi-Artist** -- Rewrite all `artist` and `album artist` tags as the first artist listed.

- **Split Omnibus Preview** -- A read-only preview of the omnibus flow.

#### States

- **Default** -- The node's form and buttons are navigable and eidtable.

- **Inline Input Wizard Focused** -- The user can only manipulate the controls of the inline input wizard, and must either save or cancel changes in order to return focus to Details View or to transfer focus to Tree View.

- **Plan Preview Focused** -- The user can only manipulate the controls of the inline input wizard, and must either save or cancel changes in order to return focus to Details View or to transfer focus to Tree View.

#### Commands

- **Navigate** -- Move the selected state between adjacent text inputs and/or buttons.

- **Open** -- Hand the selected file to the operating system's default application for its type. Offered on every file, always the second button after Save.

- **Button-Specific Commands** -- Most unique commands are presented as labeled buttons which the user can trigger with keybindings or by selecting and pressing enter.



## Command Strip

- **Command Strip** -- A line of text below the Details View and/or Tree View which pairs keybindings with the commands they execute as a reference to the user.

- **Command** -- An instruction transmitted from the user to the application.

- **Keybinding** -- A key or chord of keys which triggers a command.


---------------------

TODO:

- 19, 21, 23 — Focus / Gain / Release: focus becomes one element, not a zone, and actions are no longer restricted to the focused zone.
- 25 — Selected: needs the new wrinkle that a tree node stays Selected while focus sits elsewhere along the path, shown only by the connector.
- 40, 48 — Path Input: gains the ^/→ESC chip, loses the spinner, and "the user can only manipulate the Path Input" needs a ruling on whether file actions fire while it holds focus.
- 60 — Edit: "shift focus to Details View" → move focus to the filename field; Details View stops being a focus target as a whole.
- 68, 70, 72 — Cut / Copy / Paste / Delete: now File-bar buttons as well as tree commands, and Paste has no button in the mockup.
- 78 — Details View: "culminating in a list of buttons" → three named bars, and it is no longer a view you enter.
- 110, 112 — the lockdown states must say that lockdown also suppresses the always-available actions, or ^1 fires while the trace div owns the panel. Separately, 112's text is a copy of 110's (pre-existing).
- 116, 118, 120 — Navigate becomes bar-granular vertically; Open is no longer "second after Save" (Save moves to Contextual); Button-Specific Commands are positional now.
- 126 — Command Strip: it carries tree navigation only, so the "strip is the contract" doctrine needs restating.

- New terms needed — Button Bar plus the three kinds, and Positional
  Keybinding. (Path and the four element states are defined above now,
  from todo-6 ¹.)