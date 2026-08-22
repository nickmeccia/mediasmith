# QA to-do — todo-4/5 refactor (Fable session, 2026-08-12)

Everything from this refactor that needs Nick's eyes or renames after it
lands. (Named "todo-2.md" per your instruction during the session.)

## Reserved chords: what you asked for vs. what shipped

- [ ] Your Button Refactor spec assigned six reserved chords (^i ^c ^h ^m
      ^j ^z — terminal aliases for tab/interrupt/backspace/enter/newline/
      suspend). Per your call, the nearest safe letter stands in. Each
      line shows the full button text, spec → shipped:

      | kind        | button text          | spec | shipped |
      |-------------|----------------------|------|---------|
      | audio       | **im^port**          | ^i   | **^p**  |
      | video       | **c^lean subs**      | ^c   | **^l**  |
      | video       | **shif^t subs**      | ^h   | **^t**  |
      | epub + mobi | **conver^t to mobi** | ^m   | **^t**  |
      | epub        | **clea^n**           | ^c   | **^n**  |
      | image       | **convert to jp^g**  | ^j   | **^g**  |
      | image       | **r^esize**          | ^z   | **^e** (its old chord) |

      Plus the tree command: **cop^y** = ^y (you specced no key; ^c is
      reserved). Rename any of these — each is one letter in
      `details.PANE_ACTIONS` (or `strip.py`/`browser.py` for copy).

## Button refactor — judgment calls to confirm

- [ ] Chords are VIEW-SCOPED now: a Details button's chord fires only
      while Details view holds focus. Video/folder actions need ⏎ first
      (every kind is enterable via its rename form). The old
      "chords fire from the tree" behavior is gone per your Focus rules.
- [ ] Chords that Input eats (^a azw3, ^e extract, ^u upload cover,
      ^w webp/watch…) now FORWARD from a focused field when a visible
      button claims them — so ^a no longer homes the cursor on a book
      form, it converts to azw3. The macOS word/line nav (⌥-arrows)
      still works.
- [ ] Your per-kind lists order save first; audio's import/fetch stayed
      as the small bar under the album art (the action-method pattern),
      not merged into the bottom bar. Say so if you wanted one row.
- [ ] "sort" on a single epub is now labeled **folderize** (^f) per your
      spec; on a FOLDER it kept the word **sort** (^o) — your folder list
      didn't mention it, and renaming both would put two "folderize"
      buttons on one folder view (the audio folderize also lives there).
- [ ] "standardize" is now **clea^n** everywhere it appears — including
      the folder batch button (your spec renamed it under Epub only).
- [ ] The gif and resize wizards' apply buttons are **^save** per spec.
      While a wizard is open, ^s means the wizard's write, not the
      rename-form save (the wizard's bar wins the chord).
- [ ] Plan previews (folderize/sort/strip multi-artist/split omnibus)
      now take focus when they open — chords are view-scoped, so the
      preview lands focus on its apply button; esc cancels from there.

## Command strip & clipboard (todo-4)

- [ ] **Copy's chord is ^y, not ^c** — ^c is reserved (terminal interrupt /
      Textual's app-owned copy). ^y splices into "cop^y" on the strip.
      Rename if you prefer another letter (free letters in tree state:
      anything outside r . n x v / q).
- [ ] Paste CLEARS the clipboard, for copy as well as cut. Finder pastes a
      copy repeatedly; if you want that, say so and paste will keep a
      copy-clipboard alive.
- [ ] Copy-paste into the SAME folder is refused ("already here") like
      cut. Finder would make "notes copy.txt" — tell me if you want that.
- [ ] ⇥ still descends into Details (an ENT alias) even though the strip
      only lists ENT edit — kept as a hidden alias like ⇧← collapse
      level. Say the word and both aliases die.
- [ ] Narrow-mode flow change: ^/ no longer summons the path input while
      Details is focused/viewed (tree-only per your spec) — on the phone
      it's now esc, then ^/.

## Color theme (todo-4 "Color Theme Stylesheet")

- [ ] All colors now live in `mediasmith/theme.py` (your palette,
      verbatim); CSS holds only state (which token applies when). Nothing
      else in the app may name a hex — future Claudes included.
- [ ] Eyeball the scrollbar tracks: your spec says `transparent`; the old
      design matched them to each pane's background because a transparent
      track didn't always blend. If a track renders black, the fix is one
      token pair in theme.py (`scrollbar-track-*`).
- [ ] Idle-view dimming is now real: unfocused panes drop to grey-40 text
      / grey-30 borders per your palette. Verify readability on the NAS
      browse (SMB latency means you'll stare at idle panes plenty).
- [ ] Hidden files (dotfiles) now dim to the `node-hidden-fg-*` pair —
      this styling is NEW (they used to render like any file).
- [ ] Buttons: chord glyphs dim with the pane (grey-40), light to primary
      when Details view holds focus, flip to grey-90 on the selected
      (arrow-highlighted) button. The old focused-button look (orange bg,
      black text) is now primary bg / grey-90 text per your palette.

## Session 4 (Opus, 2026-08-13) — three fixes + one they turned up

- [ ] **Tree scrollbar inset.** The 1-cell gutter moved from the children
      (`PathInput` margin / `LibraryTree` padding) onto the `TreeView`
      pane as `padding: 0 1`. A child's horizontal margin costs EVERY
      sibling that width — Textual's vertical layout resolves `1fr`
      against the widest margin in the box — which is why the tree ran 2
      cells narrow and its scrollbar sat 3 cells off the border. Now 1
      cell each side; nothing else moved.
- [ ] **New color tokens** (theme.py): `node-hidden-selected-fg-focus`,
      `node-hidden-selected-fg-idle`, `node-selected-fg-idle` (all
      grey-10) and the scrollbar corner pair `scrollbar-corner-focus` /
      `scrollbar-corner-idle` (grey-10 — Textual calls that cell the
      ScrollBarCorner; its rule is `scrollbar-corner-color`).
      Two things to eyeball:
      · grey-10 fg on `node-selected-bg-idle` (grey-20) is a very dark
        row — that is what the spec asked for; say the word for a
        lighter token.
      · a hidden row is DIMMED by DirectoryTree's own component class,
        which fades any token toward the row behind it (grey-10 came out
        #684a20). The selected pair drops dim so the token lands exactly;
        unselected hidden rows still dim as before.
- [ ] **Arrow-key direction bug: it was a repaint, not a move.** Focus
      always moved correctly; `ActionButton.watch_has_focus` overrode
      Widget's without calling it, and Widget's version is what applies
      the `:focus` CSS — so the highlight only caught up on the NEXT
      keypress, which reads exactly like "the first press after a
      reversal keeps going the old way". Confirmed against a real pty
      (Pilot never saw it: it asserts focus, not pixels).
- [ ] **Fallout of that fix, needs your eye:** with the highlight now
      live, the selected button was rendering in the plain focused-pane
      pair, never the selected one — `DetailsView:focus-within
      ActionButton` (two type names) outranked a bare
      `ActionButton:focus`. The selected pair (primary bg / grey-90 text,
      per the palette) now applies. If you preferred the quieter look,
      that is one selector in app.py.

## Session 5 (Opus, 2026-08-22) — Nick's four requests

All four landed; each item below is what needs your eye.

- [ ] **Video form field order** is now embedded title / container /
      size / subtitles / posters, per your list (`details.py`,
      `panel-video`). Nothing else moved.
- [ ] **"open" is the new universal second button** (`^o`, every file
      kind: audio, video, book, image, and plain files). It is video's
      old **watch** button, renamed and generalized — same
      `details.launch` seam, same `MEDIASMITH_OFFLINE` guard so the fuzz
      gate doesn't spawn 100 players. A FOLDER does not get it: its ^o
      is the **sort** button, and one context may never show two
      buttons on one chord (`ActionBar.set_visible` asserts this).
      Say the word if you want folders to open in Finder — then sort
      needs a new letter.
- [ ] **^o cost two chords their letter** (both logged like the reserved
      substitutions above):

      | kind  | button text        | was | now     |
      |-------|--------------------|-----|---------|
      | epub  | **^write opf**     | ^o  | **^w**  |
      | video | **fol^derize**     | —   | **^d**  |

      Video folderize wanted ^o (your "open" took it), ^f/^l/^t are the
      subtitle suite, so "fol^derize" took ^d. ^d is an Input editing
      chord (delete-right); the button forwards it, as with the others.
- [ ] **Video folderize** wraps the video into a folder named after the
      filename minus its extension, exactly like a single epub's
      folderize: no plan preview, one move, then the video is revealed
      inside its new folder still editable. The button hides when the
      video already sits in a folder named after it.
- [ ] **What rides along with the video** (your call in-session:
      sidecars, not the video alone — a subtitle is only ever found as
      `<video stem>.srt` beside its video):
      · anything sharing the video's stem — `.srt`, `.en.srt`, `.nfo`,
        a poster folder named after the file;
      · when it is the folder's ONLY video, its art too: loose images
        and image-only subfolders (that is `posters.run`'s folder, which
        it names after TMDB's title, not after the file).
      Everything else stays put — in a folder of many videos a stray
      image belongs to no one in particular. `videofolder.py` docstring
      states the rule; change it there.
- [ ] **The poster now shows in the video pane** with its pixel
      dimensions under it, the album-art/book-cover treatment. Finding
      it moved into `posters.find_poster` (same ladder as above:
      `<stem>.jpg` → poster folder → loose art), so what the pane shows
      is exactly what folderize would move. The posters ROW prints a
      folder-relative name now (`Alien (1979)/a.png`) when the poster
      lives one level down.

### …and two more you turned up mid-session

- [ ] **"fetch subtitles" said subliminal wasn't installed when it was.**
      Homebrew's subliminal 2.7.1 keg reaches its dependencies through a
      `.pth` file (`homebrew_deps.pth` → the certifi keg), and only
      `site.addsitedir` executes those — `subsync.import_subliminal` was
      doing a bare `sys.path.insert`, so subliminal imported and then
      died on `certifi`. Every ImportError read as "not installed", which
      is why reinstalling and relaunching never helped. Fixed
      (`site.addsitedir`, added once per process). The message now names
      the real failure when the keg IS on disk — reinstall advice only
      when nothing was found.
- [ ] **Path input → tree now expands where it lands.** Committing a
      filtered path put the cursor on the folder but left it closed
      (`LibraryTree.anchor` expanded the CONTAINING directory only). A
      cursor that is itself a directory is expanded too now. Unfiltered
      Enter already behaved this way, which is why it looked
      inconsistent.


## Session 6 (2026-08-22, Opus) — three shell-outs retired

Context: Nick asked whether mediasmith could ship as a distributable
binary. It can, but a binary only removes the *Python* dependency, not
the *toolchain* one — so the prior question is how many external
commands can stop being external. These three could; ffmpeg (gif),
alass, and Calibre (convert) still cannot. See the session transcript
for the full triage.

- [ ] **subliminal is a real dependency now** (`pyproject.toml`), not a
      Homebrew keg spliced in at runtime. The whole discovery apparatus
      is gone — `find_subliminal_pythonpath`, `site.addsitedir`,
      `_SITE_ADDED`, `SUBLIMINAL_PYTHONPATH`. `import_subliminal()`
      survives ONLY as the test seam. This retires this morning's `.pth`
      fix and its two tests: the keg indirection they described no
      longer exists, so they were deleted with the machinery rather
      than left describing a dead path.
      **To verify manually:** fetch subtitles for a video that needs
      them, over the network. That path is monkeypatched in every test,
      so the suite cannot prove it. Provider discovery (stevedore entry
      points) resolves 12 providers here and `opensubtitles` loads.
- [ ] **ffprobe is gone** — replaced by `mediasmith/container.py`
      (`read_title`): mutagen's `©nam` atom for mp4/m4v, enzyme's EBML
      header for mkv. `adapters.probe_video_title` and
      `subsync.read_release_name` both delegate to it and are no longer
      slow — the worker thread around the first is now politeness, not
      necessity (10–50 ms over SMB vs ~1 s to spawn ffprobe).
      `.avi` and `.mov` are DELIBERATELY unhandled: measured against the
      library, 0/40 sampled .avi and 0/31 .mov carry a title tag at all,
      so ffprobe answered None for them too. Don't "fix" this without
      re-measuring; the docstring says so.
      **To verify manually:** the video pane's title row on a few mkv
      and mp4 files, and that subtitle matching still finds release
      names (the `ReleaseFound` event).
- [ ] **`open` is cross-platform** — `details.launch` branches
      darwin → `open`, win32 → `os.startfile`, else `xdg-open`, with
      child output to DEVNULL. It hardcoded `open` before, which was a
      latent bug for the tmux-from-phone/Linux case in roadmap 5. This
      stays a subprocess on purpose: every package that wraps it is a
      platform check plus a Popen, which is not worth a dependency.

Test additions: `tests/test_container.py` (7) and two `launch` platform
tests in `test_app.py`. `tests/fixtures/` holds four tiny synthetic
containers (~2 KB each), committed as files so the suite never needs
ffmpeg to *build* a fixture for the module whose point is not needing
ffmpeg to *read* one.
