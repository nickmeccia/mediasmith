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

- Please evaluate mediasmith-v1 instead of blindly porting features. If a feature was written well enough in v1 that you can port it unchanged, great! Just, don't assume. Remember, you are Fable 5, and lesser models wrote v1.

- I recommend building one feature at a time, so that you can ask me focused questions about one topic at a time. This is not a rule, just a suggestion to make communication clear on complicated tasks.

- Work on the features marked with a * last (reading their description will explain more).


## Features to add from mediasmith-v1:

**Audiosmith**

-[x] Deezer lookup
     I don't think I need this.

-[ ] Deezer search*
     This is a really useful tool, but I'm not sure how to fit it in. The best idea I have right now is a global keybinding to open a modal, but I would like to hear any ideas you have, too. Also, I understand that the `dzr-srt` command doesn't work on my computer right now; just implement assuming it does and I will fix later.

-[ ] Folderize
     Aha, an action which the user can perform on a folder! If you put a button for "folderize audio files" on every folder I wouldn't hate it; however, it would be cool if the button only appeared when this action was possible. This button should appear on folders no matter how high up in the tree the action is possible (barring technical limitations, of course). So, for example, this button would appear on /Users/nick/Music and all subfolders (except for /Users/nick/Music/Album Art).

-[ ] Fix multi-artist
     Even with visual editing, this would still be a cool feature to have. It would be initiated in the same way as folderize above: button present on folders.


**Booksmith**

-[ ] Anna search*
     Like Deezer search, this is a really useful tool, and I'm not sure how to fit it in. The best idea I have right now is a global keybinding to open a modal, but I would like to hear any ideas you have, too.

-[ ] Convert
     Add buttons to the bottom of ebook views from this palette of buttons:
     save, convert to epub, convert to mobi, convert to azw3
     Whichever file format the ebook is, remove that button from the list. So, if viewing an epub, buttons should read:
     save, convert to mobi, convert to azw3

-[ ] Fix series metadata
     I'm not sure what this does. :(

-[x] Metadata editor
     Ebook metadata should be editable in the details pane, just like mp3 tags. I haven't tested it yet; check this off if it exists.
     (Claude, 2026-07-11: exists — shipped in the editing slice.
     title/author/series/publisher/language/date round-trip; rename and
     cover survive the epub rewrite. Covered by test_book_panel_is_editable;
     your manual pass is still listed in QA-TODO.)

-[ ] Omnibus splitter
     Add a "split omnibus" button following the app's button pattern. Based on the logic for how this works, if I remember correctly it should do nothing on books that are not omnibuses

-[ ] Scrape serial*
     I'm not sure I need this anymore -- this was a tool used for downloading Wildbow's serials off of Wordpress, but now that I have them in ebook format, I don't know what else I will do with this. Well, now I'm thinking, what about Wildbow's future stories? Perhaps this should be folded into a "search" feature, which can collect this, anna search, and deezer search.

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
     -[ ] Create opf file: I wouldn't mind a button to do this
     -[ ] Extract cover: There is a silly feature of the old tool that I would use: a button to eject the cover and save it as "cover.jpg" in the same directory.
     -[ ] "Sort" folders: "normalize metadata" and "add my converted ebook to a new folder" are two features which are silly to make buttons for on a single book view. However, at this point in the long list of features, having buttons on folders to sort their contents sounds increasingly appealing. A "sort" feature which standardizes folders would be as useful for books as it is for mp3s--let's start with this
     -[ ] Normalize metadata as an action on a folder: I'm on the fence, currently thinking "no," but...I'm leaving this item for myself to read later (or you to weigh in on now)

**Videosmith**

-[ ] Download posters
     This should be a button on a video file, and should detect if the file is on a network volume or not. If it's on a local volume, download posters to the file's folder. If it's on a network volume, create a local folder per the current tool's process.

-[ ] Subtitle clean SRT
     This should be a button on the video file.

-[ ] Subtitle DL sync
     This should also be a button on the video file. Bonus if you also add a button to launch the video file with the subtitles so that I can check the alignment.

-[ ] Subtitle shift SRT
     Man, I am so excited for this one. My initial instinct is that this feature should be toggleable with a button, react-style. So, the div is not on the page, but pressing a button toggles it on; however, if changes are pending it can't be toggled off until the changes are saved or discarded.



## New features

**Videosmith**
-[ ] Container
     Can you show the container name as a field? Can you make it editable? (I would be satisfied if it was merely viewable)


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

-[ ] Move(???)
     This feature probably has the biggest difference between how easy the operation is to perform vs how much UI support it needs. This feature probably needs my full attention to solve...unless there's a common pattern hiding in plain sight among other, similar programs.

