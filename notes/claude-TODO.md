> (Claude, 2026-07-11: Fable's credits ran out mid-queue. For whoever
> continues: **read CLAUDE.md's "action pattern cookbook", then
> notes/claude-HANDOFF.md** — per-feature briefs with locked
> decisions. The engines for multi-artist (#5), subtitles clean/shift
> (#7), and image convert/resize/rotate (#9) are already built and
> tested in mediasmith/{multiartist,srt,imageops}.py — those features
> need UI wiring only.)

### Preliminary notes:

- Button pattern
  - horizontally-inlined
  - navigable with up/down arrows (moves left/right)
  - are executable with a keybinding
  - contain the keybinding in the printed button text
  - make the keybinding a different color in the button text
  - ideally, the keybinding is a character in the word; if so, just add a `^`  in front of the word; color will distinguish it from the word
  - example: ^save <-- `^s` is a different color from `ave`
  - if the keybinding can't be a character in the word, just choose any character, make a keybinding somehow, and I'll revise the language & keybinding later
  - can you make buttons wrap, like flexbox? That would be weet 
    (Claude, 2026-07-11: yes — Textual has no wrap layout built in, so
    mediasmith/actions.py adds a small FlowLayout (a custom Layout
    registered with Textual's factory) and every ActionBar uses it.
    Buttons wrap at the pane edge and restart at the left, flexbox
    style. One nuance on "navigable with up/down": ↑↓ now walk straight
    through every field *and* button — on a button row ↓ means "next
    button to the right". ←→ also move within a row, ← on the leftmost
    button still ascends, per the pane hierarchy.)

- Please evaluate mediasmith-v1 instead of blindly porting features. If a feature was written well enough in v1 that you can port it unchanged, great! Just, don't assume. Remember, you are Fable 5, and lesser models wrote v1.

- I recommend building one feature at a time, so that you can ask me focused questions about one topic at a time. This is not a rule, just a suggestion to make communication clear on complicated tasks.

- Work on the features marked with a * last (reading their description will explain more).


## Features to add from mediasmith-v1:

**Audiosmith**

-[x] Deezer lookup
     I don't think I need this.

-[x] Deezer search*
     This is a really useful tool, but I'm not sure how to fit it in. The best idea I have right now is a global keybinding to open a modal, but I would like to hear any ideas you have, too. Also, I understand that the `dzr-srt` command doesn't work on my computer right now; just implement assuming it does and I will fix later.
     (Claude, 2026-07-11: resolved OUT of mediasmith by Nick's call —
     download tools move to ~/code/downloader (Claude-in-the-loop
     pipeline). Rationale recorded in notes/claude-PROPOSALS.md;
     deemix can target a directory via flag, so the downloader can
     still land files where mediasmith expects them.)

-[x] Folderize
     Aha, an action which the user can perform on a folder! If you put a button for "folderize audio files" on every folder I wouldn't hate it; however, it would be cool if the button only appeared when this action was possible. This button should appear on folders no matter how high up in the tree the action is possible (barring technical limitations, of course). So, for example, this button would appear on /Users/nick/Music and all subfolders (except for /Users/nick/Music/Album Art).
     (Claude, 2026-07-11: shipped, the cool way — the `fo^lderize`
     button appears only when a background probe finds a file that
     would actually move (budgeted at ~200 tag reads so a huge NAS tree
     can't melt; past the budget it assumes organized — the one
     "technical limitation"). Pressing it shows the planned
     Artist/Album structure in the details pane; ^a applies, esc or
     cancel backs out. Files with missing tags go to "* Skipped/",
     empty folders get pruned. Differences from v1 worth knowing:
     [1] v1 would rebuild an already-organized library into
     "Artist (1)/" — v2 reuses existing folders and treats a file
     already at Artist/Album (per its own tags) as in place, anywhere
     in the tree, so folderizing an album folder is a no-op instead of
     a nesting accident; [2] v1's "rename to NN Title.ext" toggle isn't
     ported yet — say the word; [3] the button also appears on
     album-like folders that open as a bulk-edit form, next to save.)

-[x] Fix multi-artist
     Even with visual editing, this would still be a cool feature to have. It would be initiated in the same way as folderize above: button present on folders.
     (Claude, 2026-07-11: shipped — `fi^x multi-artist`, folderize's
     exact shape: probe-gated button on folders (and album bulk
     views), plan preview per album ("Split EP → Jax Jones" + each
     file's old tangled values), ^a applies, esc cancels. The engine's
     AC/DC guard means a slash-joined artist matching its own artist
     folder is a band name, not a tangle. v1's per-album checkboxes
     are replaced by scoping — invoke on a smaller folder to exclude.
     Architectural note: apply/cancel are now ONE shared pair
     (`plan_apply`/`plan_cancel`) owned by whichever plan preview is
     open — folderize was reworked onto it, so the next plan-shaped
     action costs nothing new.)


**Booksmith**

-[x] Anna search*
     Like Deezer search, this is a really useful tool, and I'm not sure how to fit it in. The best idea I have right now is a global keybinding to open a modal, but I would like to hear any ideas you have, too.
     (Claude, 2026-07-11: out of mediasmith, same call as Deezer
     search. Also audited the v1 tool's strategy at Nick's request —
     ~/code/downloader/anna-search-audit.md: the parser fails open,
     the grouping key can't see un-numbered curator batches, and
     ranking puts coverage fourth. Verdict: don't port; rebuild in
     the downloader as agent-judged link manifests.)

-[x] Convert
     Add buttons to the bottom of ebook views from this palette of buttons:
     save, convert to epub, convert to mobi, convert to azw3
     Whichever file format the ebook is, remove that button from the list. So, if viewing an epub, buttons should read:
     save, convert to mobi, convert to azw3
     (Claude, 2026-07-11: shipped. Exactly this palette, own format
     hidden. Decisions you may want to revise: [1] the converted file
     lands *next to the source* — edit-in-place pattern, no output-dir
     question, the tree refreshes itself; [2] existing target = refuse
     with a warning, never overwrite; [3] conversions run in threads,
     several can run at once; [4] keys are ^p/^b/^y until you pick
     better ones. Not done: bulk convert of a folder (v1 supported it) —
     say the word if you want it on folder views too.)

-[ ] Fix series metadata
     I'm not sure what this does. :(
     (Claude, 2026-07-11: mystery solved — it's a one-shot repair tool,
     not a feature. An old version of standardize-metadata wrote
     `calibre:series content=""` + `series_index="0"` into non-series
     books; this scans a library and strips that signature from epubs
     and metadata.opf files. Recommend: don't port it. If you like, run
     the v1 tool once over BOOKS with --dry-run to confirm nothing
     still carries the bug, then retire it. mediasmith's own epub
     writer already removes the series meta when the field is emptied,
     so the app can't reintroduce the problem.)

-[x] Metadata editor
     Ebook metadata should be editable in the details pane, just like mp3 tags. I haven't tested it yet; check this off if it exists.
     (Claude, 2026-07-11: exists — shipped in the editing slice.
     title/author/series/publisher/language/date round-trip; rename and
     cover survive the epub rewrite. Covered by test_book_panel_is_editable;
     your manual pass is still listed in QA-TODO.)

-[x] Omnibus splitter
     Add a "split omnibus" button following the app's button pattern. Based on the logic for how this works, if I remember correctly it should do nothing on books that are not omnibuses
     (Claude, 2026-07-15: shipped — `split omnibus ^e` appears on an
     epub only when a cheap zip-read probe finds ≥2 books in its NCX
     (your "does nothing on non-omnibuses", done as "isn't offered").
     It's the third plan-shaped action: press → preview lists each
     book + the epub it will write → ^a applies, esc cancels. Output
     is v1's convention ("Author Sort - Title.epub", beside the
     source, refuse-overwrite per book; front matter duplicated into
     each; chapters promoted to TOC roots). One scope cut: v1's
     interactive flows (renaming detected titles, drawing boundaries
     in a FLAT table of contents) needed a conversation the plan
     preview can't hold — so flat-TOC omnibuses simply don't get the
     button. If you own one, say so and it becomes a wizard div.)

-[x] Scrape serial*
     I'm not sure I need this anymore -- this was a tool used for downloading Wildbow's serials off of Wordpress, but now that I have them in ebook format, I don't know what else I will do with this. Well, now I'm thinking, what about Wildbow's future stories? Perhaps this should be folded into a "search" feature, which can collect this, anna search, and deezer search.
     (Claude, 2026-07-11: your instinct held — it folds into the
     download family, which now lives in ~/code/downloader, not
     here. Nothing to build in mediasmith.)

-[ ] Standardize formatting
     This tool is cool. If I remember how it works correctly, it can be used on a single book or on a folder. Add buttons!

-[ ] Standardize metadata
     This tool does too many things at once, which, ironically, was exactly what I needed from the standard, non-TUI-style of CLI app -- I need to perform a bunch of actions to standardize any given book, but even in the svelte UI of mediasmith-v1 there was a lot of tedium involved in navigating to files.
     
     **Already Covered Elsewhere**
     - Normalize ebook metadata: camelcase strings handled through my manual typing, just like I do with mp3 tags. If anything, there could be a button for "make metadata camelcase" but that seems like a silly level of automation. Skip.
     - Add covers: handled by the cover editing tools, copied from mp3 tag editor functionality
     - Convert: handled by buttons discussed above
     - Folderize: the old tool assumed that converting preserved the old file; so, I wanted the new files to be organized all in the same flow so that I didn't have to go back and forth between terminal and finder (that's the reason why this tool did so many things). Now with edit-in-place as the pattern, I think that a feature like this would be confusing, instantaneous magic that would confuse the user unless they knew in advance what it would do.

     **Ideas to Implement**
     -[x] Create opf file: I wouldn't mind a button to do this
          (Claude, 2026-07-11: shipped — `create opf ^g` on epub views
          writes a Calibre-style metadata.opf beside the book from its
          embedded metadata. Refuses to overwrite an existing one.
          epub-only: mobi/azw3 have no metadata reader yet.)
     -[x] Extract cover: There is a silly feature of the old tool that I would use: a button to eject the cover and save it as "cover.jpg" in the same directory.
          (Claude, 2026-07-11: shipped — `extract cover ^t`, and the
          button only appears when the book has a cover. One liberty
          taken: a PNG cover saves as cover.png, not cover.jpg with png
          bytes inside — flag me if you want literal cover.jpg always.)
     -[ ] "Sort" folders: "normalize metadata" and "add my converted ebook to a new folder" are two features which are silly to make buttons for on a single book view. However, at this point in the long list of features, having buttons on folders to sort their contents sounds increasingly appealing. A "sort" feature which standardizes folders would be as useful for books as it is for mp3s--let's start with this
     -[ ] Normalize metadata as an action on a folder: I'm on the fence, currently thinking "no," but...I'm leaving this item for myself to read later (or you to weigh in on now)

**Videosmith**

-[x] Download posters
     This should be a button on a video file, and should detect if the file is on a network volume or not. If it's on a local volume, download posters to the file's folder. If it's on a network volume, create a local folder per the current tool's process.
     (Claude, 2026-07-15: shipped — `^download posters` on every single
     video. The v1 engine is ported to mediasmith/posters.py with its
     tuned parts intact (title ladder: container tag → filename →
     folder; dhash near-duplicate collapse keeping the hi-res copy).
     Decisions to review: [1] "on a network volume" = path under
     /Volumes — crude but honest, flag if your setup disagrees;
     [2] local videos get posters in a subfolder named "Film (Year)"
     beside the video, not loose in the folder (loose files would
     hijack the details pane's poster row and clutter the film dir) —
     network videos stage to ~/Downloads/Videosmith/ as before;
     [3] refuse-overwrite per poster file; [4] progress = a toast per
     phase + every 5th download. The ^d chord came from a RESERVED_KEYS
     audit — see QA-TODO "key space", you have veto.)

-[x] Subtitle clean SRT
     This should be a button on the video file.
     (Claude, 2026-07-11: shipped — `clean subs ^u`, visible only when
     a sibling .srt exists. Cleans in place (v1 regexes verbatim, in
     mediasmith/srt.py); the toast itemizes what was stripped;
     already-clean files aren't rewritten. .ass/.vtt get no button —
     the clean engine is SRT-only.)

-[x] Subtitle DL sync
     This should also be a button on the video file. Bonus if you also add a button to launch the video file with the subtitles so that I can check the alignment.
     (Claude, 2026-07-11: shipped — `get subs ^k` on every single
     video, plus the bonus `watch ^w`. The v1 engine is ported intact
     to mediasmith/subsync.py — hash-match skips alass, ≤2s
     corrections apply silently, larger ones apply-and-flag; its
     ground-truth policy suite now lives in tests/test_subsync.py so
     nobody can drift it unnoticed. One decision to veto: pressing it
     on a video that already has a sub RE-FETCHES over it (explicit
     press = "replace this bad sub") — the one exception to
     refuse-overwrite. watch uses plain `open`; the sub auto-loads
     because it's named like the video — name your player if you want
     --sub-file wiring.)

-[x] Subtitle shift SRT
     Man, I am so excited for this one. My initial instinct is that this feature should be toggleable with a button, react-style. So, the div is not on the page, but pressing a button toggles it on; however, if changes are pending it can't be toggled off until the changes are saved or discarded.
     (Claude, 2026-07-11: shipped exactly react-style — `shift subs
     ^v` toggles an inline div (readout + hint) under the video rows;
     pending changes pin it open (toast tells you so), esc routes
     through ConfirmSave. ←→ ±0.1s, ⇧←→ ±1s, ⇞⇟ ±10s; ^s writes and
     the ✓ clears but the div stays for more nudging. Every write
     recomputes from the ORIGINAL parse (v1's nudge model) so
     back-and-forth can never lose cues or accumulate drift. This div
     is the wizard-pattern exemplar the image-resize/gif features
     should copy — QA its look before those get built.)



## New features

**Command Strip**
-[x] Mediasmith logo
     Can you add this logo to the bottom-most, global command strip, right-aligned with the edge of the viewport?
     𜵎𜵎▖𜷇🯦𜷇▌𜵅𜷃𜵈𜷓𜴀𜵎𜵎▖𜵅𜶍▐𜶓
     Responsive rules: if the viewport would shrink such that this logo would collide with the commands in the command strip, set it to `display: none;` Looking at mediasmith on my phone, it looks like it can still fit. :)
     (Claude, 2026-07-15: shipped — the strip is now commands (1fr) +
     logo (auto), so the wordmark sits flush with the viewport's right
     edge. Every glyph measures cell-width 1 under Rich, so the
     responsive rule is exact math: below 51 cells (1 padding + 30
     commands + 1 gap + 19 logo = LOGO_MIN_WIDTH in app.py) it goes
     display-none, and re-appears on resize. Phone width (60+) keeps
     it, per your check. It inherits the strip's $text-muted — say the
     word if you want it in the accent color.)

**Videosmith**
-[x] Container
     Can you show the container name as a field? Can you make it editable? (I would be satisfied if it was merely viewable)
     (Claude, 2026-07-15: viewable — a "container" row on the video
     panel showing the suffix name ("mkv"), instant, no ffprobe.
     Editable was deliberately left out: changing a container is a
     remux (an ffmpeg conversion), not a metadata write, so it belongs
     with the convert-button pattern (books/images have it) rather
     than an editable field. Say the word and "convert to mp4/mkv"
     buttons follow the book-convert shape.)


**Imagesmith** (I know that these names aren't preserved in the new design, but I thought this was a cute header for this section)

-[ ] View/edit name
     Mediasmith already shows images, but images are media, too, and I want to be able to edit them! Let's start with editing the name.

-[ ] Convert
     Converting images is a task that I perform regularly, and I always have to open up Photoshop (and then the image file, too) to do it. It would be really neat to be able to convert an image using mediasmith into the following formats:
     - jpg
     - png
     - webp
     - tiff
     - Claude's suggestions
     Converting will require choosing options beforehand; this pattern exists in a lot of these features, and I need to come up with a standard solution. However, I want your Fable-sized intelligence to get the functionality into the app before you leave me and it is super late and I can't think of the answer right now. Since you read everything all at once, hopefully you can apply this note found at the end to all "wizard"-style actions, choosing a pattern and using the same pattern. (Modal? I hate modals, but it's easy to conceive of this style of solution in a modal.)

-[ ] Resize
     For this one, I think a button should toggle a div with dimensional controls. I am imagining Photoshop's two numerical inputs separated by a link icon. With the link icon enabled, resizing preserves aspect ratio; with it disabled, resizing distorts the image. I don't need a link icon, but...can you do a checkbox?

-[ ] Rotate
     I don't know how often I will use this feature, but it seems easy to implement. Add a button for it. This one is lower priority than video to gif, I have decided

-[ ] Video to gif
     At a previous job I needed to do this frequently, so I downloaded a CLI tool for it. This one is low priority, but it would be really fun. :)


**Foldersmith**

-[ ] Edit folder names
     This would really help with organization. Follow the same pattern as the other editable files (edit name in details view)

-[ ] New/Delete
     Adding functionality for the final two CRUD operations would take the folder organization to another level. I think there should be keybindings for these operations visible on the command strip, and the "delete" action should have a button on the folder detail view

-[x] Move(???)
     This feature probably has the biggest difference between how easy the operation is to perform vs how much UI support it needs. This feature probably needs my full attention to solve...unless there's a common pattern hiding in plain sight among other, similar programs.
     (Claude, 2026-07-11: shipped as approved M1 (cut/paste; the
     browser IS the destination picker). One change from the
     proposal: a single stateful chord — `^n move` lifts, the button
     relabels to `^n place here`, esc cancels — because ^x/^v turned
     out to collide with fix-multi-artist and shift-subs (tree
     bindings would starve their app-wide chords). The strip shows
     "moving N · ^n place here · esc cancel" while lifted; lifts
     survive path-bar jumps (your cut → ^/ → type → ⏎ → paste flow
     works); refuse-overwrite per file; folder-into-itself refused;
     same-folder place is a no-op that KEEPS the lift. Heads-up: ^n
     was the last free ctrl-letter — see QA-TODO "key space" before
     queueing New/Delete.)

