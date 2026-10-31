Context: ./notes/mockups/always-available-actions-3.txt was recently implemented by you. However, there are a number of details of the implementation which do not match the mockup. Please correct items from the following checklist:

- [x] Please add a blank line between button bars. Currently, I see this:
      ```
      ^s Save
      ^o Open    ^x Cut    ^y Copy    ^DEL Delete
      ^1 Fetch Subtitles    ^2 Download Posters    ^3 Make GIF    ^4 Folderize
      ```
      When there should be a blank line between each group
      ```
      ^s Save

      ^o Open    ^x Cut    ^y Copy    ^DEL Delete
      
      ^1 Fetch Subtitles    ^2 Download Posters    ^3 Make GIF    ^4 Folderize
      ```
      Please see mockup file for examples.

- [x] Only show the `^s Save` button when there are changes to save.

- [x] When the user has focus on an element in a file's details, add the button `ESC Exit` to the contextual button bar. Please see lines 462 to 721 in the mockup file.

- [x] For details fields which are not editable, do not color the background with the focusable color (ie, no bg color) and do not draw a line leading from the beginning of that field to the center line. Only focusable elements should receive the bg color & line treatment. Both of these UI details indicate which options from the list of details are editable and navigable with the arrow keys.

- [x] Please treat the cover image for video files and ebook files the same as album art.

- [x] Please insert a new line between the final metadata field and the the album art/cover field for audio, video, and ebook files.

- [x] Please draw a line from the end of the focused element in the tree to connect with the center line, and do not draw the center line below this point. Also, please color the fg of this line along a path leading from the focused tree node to the focused detail field. Please see examples for all of these details in the mockup file.

- [x] Please updaate the variables used in theme.py to match the new mental model of the UI. I would like to make changes to this file directly, and it no longer matches what the app currently does.
      Color variables to add (beyond refactoring existing variables):
      - [x] Differentiate between "focused," which tracks the current location and movement of the user's ability to edit and manipulate data, and "focus_path," which includes all elements also "selected" en route to the focused element. An example: If the field "filename" is focused, then that field should have the bg color "focused," while the path drawn between this element and the selected file tree node should have the fg color "focus_path," and the selected file tree node should have bg color "focus_path."
      - [x] Remove the state where focusing on a detail field changes colors, and remove any variables which contain colors for that state.
      - [x] Any element which is "focused," including buttons, should follow the same coloring pattern, which is: bg color of "focused" and fg color of "grey_20." This is theoretically configurable by me in an updated theme.py file, but I want to make sure that this button state is achievable under refactored variables.


Please see the mockup below for the following TODO items:

- [x] ¹ This connector isn't quite right at the bottom angle.
      Implemented:
      `📄 Closet Witch - Complete Discography - 05 Solar Lullaby.mp3 ──╰─── `
      Mockup:
      `📄 Closet Witch - Complete Discography - 05 Solar Lullaby.mp3 ──╯ `

- [x] ² The "focused_path" element should not have a bg color when that element is the connecting line. So, in example ² in the mockup below, the connecting line should not have a bg color.
      `📄 Closet Witch - Complete Discography - 05 Solar Lullaby.mp3 ──╯ ` <-- this is the connecting line which should not have a bg color
      
- [x] ³ Please add a two-cell margin between the left column and the center line, as seen in the mockups.
      Implemented:
      ` │ ^/   /Users/nick/Music/Closet Witch - Complete Discography/Closet Wit │╭── filename       Closet Witch - Complete Discography - 05 Solar Lullaby.mp3`
      Mockup:
      ` │ ^/   /Users/nick/Music/Closet Witch - Complete Discography/Closet Wit │  ╭── filename       Closet Witch - Complete Discography - 05 Solar Lullaby.mp3`

- [x] ⁴ Add once cell of padding to the left of detail fields -- the bg color should touch the connecting line.
      Implemented:
      `├── ▒▒▒▒▒▒`
      Mockup:
      `├──▒▒▒▒▒▒▒`

- [x] ⁵ Likewise, remove the space between the connecting line and the first button in a button group.
      Implemented:
      `├── ▒▒▒▒▒▒▒▒▒──▒▒▒▒▒▒▒▒──▒▒▒▒▒▒▒▒▒──▒▒▒▒▒▒▒▒▒▒▒▒▒`
      Mockup:
      `├──▒▒▒▒▒▒▒▒▒──▒▒▒▒▒▒▒▒──▒▒▒▒▒▒▒▒▒──▒▒▒▒▒▒▒▒▒▒▒▒▒`

- [x] ⁶ Also color the horizontal connector extending from the center line to a focused element.
      Implemented:
      `╭   filename` <-- this is the only connecting line character with focused_path color
      Mockup:
      `╭── filename` <-- all three characters here should have the focused_path color
      
- [x] ⁷ When an element above a focusable element is focused, change the connecting line at the junction for each element lower in the list. In this example, consider "filename" to be focused; then, make the following change to each field below it (title, artist, etc). I am going to give you a choice for this one:
      - [x] Option 1: follow the mockup.
            Instead of simply colorizing the `├` character, change it out for the `│` character.
            Implemented:
            `├── title`
            Mockup:
            `│── title`
      - [-] Option 2: overlay a "focused_bg"-colored line with fixed/absolute positioning above the center line, leaving the original center line untouched.
      Additional context for this entire checklist item: coloring the fg of `├` in the string `├──` is weird, because the horizontal piece is not supposed to be colored. If these borders were colored with CSS, I would set the vertical border with a CSS class on one element, and then a horizontal line before the element with a space of 0px between it and the center line. In other words, I consider the horizontal component to be separate from the vertical component, and in a CSS world the character `├` wouldn't exist.

 ╭───────────────────────────────────────────────────────────────────────╮
 │ ^/   /Users/nick/Music/Closet Witch - Complete Discography/Closet Wit │╭── filename ⁶     Closet Witch - Complete Discography - 05 Solar Lullaby.mp3 ³
 ╰───────────────────────────────────────────────────────────────────────╯│
 ├─ 📄 .gitconfig                                                         ├── title ⁷        Solar Lullaby ⁴
 ├─ 📁 .gnupg                                                             ├── artist         Closet Witch
 ├─ 📄 .lesshst                                                           ├── album artist   Closet Witch
 ├─ 📁 .local                                                             ├── album          Complete Discography
 ├─ 📄 .mysql_history                                                     ├── genre          -
 ├─ 📁 .npm                                                               ├── date           2020
 ├─ 📁 .nuget                                                             ├── track no.      5
 ├─ 📁 .pi                                                                ├── disc no.       -
 ├─ 📄 .profile                                                           ├── composer       -
 ├─ 📁 .rustup                                                            │
 ├─ 📁 .ssh                                                               ├── album art      􎻮̅̅᷇􎻮̅̍᷇􎻮̅̎᷇􎻮̅̐᷇􎻮̅̒᷇􎻮̅̽᷇􎻮̅̾᷇􎻮̅̿᷇􎻮̅͆᷇􎻮̅͊᷇􎻮̅͋᷇􎻮̅͌᷇􎻮̅͐᷇􎻮̅͑᷇􎻮̅͒᷇􎻮̅͗᷇􎻮̅͛᷇ 
 ├─ 📁 .stacher                                                           │                  􎻮̍̅᷇􎻮̍̍᷇􎻮̍̎᷇􎻮̍̐᷇􎻮̍̒᷇􎻮̍̽᷇􎻮̍̾᷇􎻮̍̿᷇􎻮̍͆᷇􎻮̍͊᷇􎻮̍͋᷇􎻮̍͌᷇􎻮̍͐᷇􎻮̍͑᷇􎻮̍͒᷇􎻮̍͗᷇􎻮̍͛᷇
 ├─ 📄 .tcshrc                                                            │                  􎻮̎̅᷇􎻮̎̍᷇􎻮̎̎᷇􎻮̎̐᷇􎻮̎̒᷇􎻮̎̽᷇􎻮̎̾᷇􎻮̎̿᷇􎻮̎͆᷇􎻮̎͊᷇􎻮̎͋᷇􎻮̎͌᷇􎻮̎͐᷇􎻮̎͑᷇􎻮̎͒᷇􎻮̎͗᷇􎻮̎͛᷇
 ├─ 📂 .Trash                                                             │                  􎻮̐̅᷇􎻮̐̍᷇􎻮̐̎᷇􎻮̐̐᷇􎻮̐̒᷇􎻮̐̽᷇􎻮̐̾᷇􎻮̐̿᷇􎻮̐͆᷇􎻮̐͊᷇􎻮̐͋᷇􎻮̐͌᷇􎻮̐͐᷇􎻮̐͑᷇􎻮̐͒᷇􎻮̐͗᷇􎻮̐͛᷇
 ├─ 📄 .viminfo                                                           │                  􎻮̒̅᷇􎻮̒̍᷇􎻮̒̎᷇􎻮̒̐᷇􎻮̒̒᷇􎻮̒̽᷇􎻮̒̾᷇􎻮̒̿᷇􎻮̒͆᷇􎻮̒͊᷇􎻮̒͋᷇􎻮̒͌᷇􎻮̒͐᷇􎻮̒͑᷇􎻮̒͒᷇􎻮̒͗᷇􎻮̒͛᷇
 ├─ 📄 .vimrc                                                             │                  􎻮̽̅᷇􎻮̽̍᷇􎻮̽̎᷇􎻮̽̐᷇􎻮̽̒᷇􎻮̽̽᷇􎻮̽̾᷇􎻮̽̿᷇􎻮̽͆᷇􎻮̽͊᷇􎻮̽͋᷇􎻮̽͌᷇􎻮̽͐᷇􎻮̽͑᷇􎻮̽͒᷇􎻮̽͗᷇􎻮̽͛᷇
 ├─ 📄 .zsh_history                                                       │                  􎻮̾̅᷇􎻮̾̍᷇􎻮̾̎᷇􎻮̾̐᷇􎻮̾̒᷇􎻮̾̽᷇􎻮̾̾᷇􎻮̾̿᷇􎻮̾͆᷇􎻮̾͊᷇􎻮̾͋᷇􎻮̾͌᷇􎻮̾͐᷇􎻮̾͑᷇􎻮̾͒᷇􎻮̾͗᷇􎻮̾͛᷇
 ├─ 📁 .zsh_sessions                                                      │                  􎻮̿̅᷇􎻮̿̍᷇􎻮̿̎᷇􎻮̿̐᷇􎻮̿̒᷇􎻮̿̽᷇􎻮̿̾᷇􎻮̿̿᷇􎻮̿͆᷇􎻮̿͊᷇􎻮̿͋᷇􎻮̿͌᷇􎻮̿͐᷇􎻮̿͑᷇􎻮̿͒᷇􎻮̿͗᷇􎻮̿͛᷇
 ├─ 📄 .zshenv                                                            │                  􎻮͆̅᷇􎻮͆̍᷇􎻮͆̎᷇􎻮͆̐᷇􎻮͆̒᷇􎻮͆̽᷇􎻮͆̾᷇􎻮͆̿᷇􎻮͆͆᷇􎻮͆͊᷇􎻮͆͋᷇􎻮͆͌᷇􎻮͆͐᷇􎻮͆͑᷇􎻮͆͒᷇􎻮͆͗᷇􎻮͆͛᷇
 ├─ 📄 .zshrc                                                             │                  􎻮͊̅᷇􎻮͊̍᷇􎻮͊̎᷇􎻮͊̐᷇􎻮͊̒᷇􎻮͊̽᷇􎻮͊̾᷇􎻮͊̿᷇􎻮͊͆᷇􎻮͊͊᷇􎻮͊͋᷇􎻮͊͌᷇􎻮͊͐᷇􎻮͊͑᷇􎻮͊͒᷇􎻮͊͗᷇􎻮͊͛᷇
 ├─ 📁 Applications                                                       │                  􎻮͋̅᷇􎻮͋̍᷇􎻮͋̎᷇􎻮͋̐᷇􎻮͋̒᷇􎻮͋̽᷇􎻮͋̾᷇􎻮͋̿᷇􎻮͋͆᷇􎻮͋͊᷇􎻮͋͋᷇􎻮͋͌᷇􎻮͋͐᷇􎻮͋͑᷇􎻮͋͒᷇􎻮͋͗᷇􎻮͋͛᷇
 ├─ 📁 Books                                                              │                  􎻮͌̅᷇􎻮͌̍᷇􎻮͌̎᷇􎻮͌̐᷇􎻮͌̒᷇􎻮͌̽᷇􎻮͌̾᷇􎻮͌̿᷇􎻮͌͆᷇􎻮͌͊᷇􎻮͌͋᷇􎻮͌͌᷇􎻮͌͐᷇􎻮͌͑᷇􎻮͌͒᷇􎻮͌͗᷇􎻮͌͛᷇
 ├─ 📁 code                                                               │                  􎻮͐̅᷇􎻮͐̍᷇􎻮͐̎᷇􎻮͐̐᷇􎻮͐̒᷇􎻮͐̽᷇􎻮͐̾᷇􎻮͐̿᷇􎻮͐͆᷇􎻮͐͊᷇􎻮͐͋᷇􎻮͐͌᷇􎻮͐͐᷇􎻮͐͑᷇􎻮͐͒᷇􎻮͐͗᷇􎻮͐͛᷇
 ├─ 📁 Desktop                                                            │                  􎻮͑̅᷇􎻮͑̍᷇􎻮͑̎᷇􎻮͑̐᷇􎻮͑̒᷇􎻮͑̽᷇􎻮͑̾᷇􎻮͑̿᷇􎻮͑͆᷇􎻮͑͊᷇􎻮͑͋᷇􎻮͑͌᷇􎻮͑͐᷇􎻮͑͑᷇􎻮͑͒᷇􎻮͑͗᷇􎻮͑͛᷇
 ├─ 📁 Documents                                                          │                  􎻮͒̅᷇􎻮͒̍᷇􎻮͒̎᷇􎻮͒̐᷇􎻮͒̒᷇􎻮͒̽᷇􎻮͒̾᷇􎻮͒̿᷇􎻮͒͆᷇􎻮͒͊᷇􎻮͒͋᷇􎻮͒͌᷇􎻮͒͐᷇􎻮͒͑᷇􎻮͒͒᷇􎻮͒͗᷇􎻮͒͛᷇
 ├─ 📁 Downloads                                                          │                  􎻮͗̅᷇􎻮͗̍᷇􎻮͗̎᷇􎻮͗̐᷇􎻮͗̒᷇􎻮͗̽᷇􎻮͗̾᷇􎻮͗̿᷇􎻮͗͆᷇􎻮͗͊᷇􎻮͗͋᷇􎻮͗͌᷇􎻮͗͐᷇􎻮͗͑᷇􎻮͗͒᷇􎻮͗͗᷇􎻮͗͛᷇
 ├─ 📁 FontBase                                                           │                  700 × 700
 ├─ 📁 go                                                                 │
 ├─ 📁 Library                                                            ├──                 ^p import    ^f fetch
 ├─ 📁 Movies                                                             │
 ├─ 📂 Music                                                              ├──  ESC Exit
 │  ├─ 📄 .DS_Store                                                       │
 │  ├─ 📄 .localized                                                      ├──  ^o Open    ^x Cut    ^y Copy    ^DEL Delete ⁵
 │  ├─ 📁 Art                                                             │   info           mp3 · 320 kbps · 141s · 5.7 MB
 │  ├─ 📂 Closet Witch - Complete Discography                             │
 │  │  ├─ 📄 Closet Witch - Complete Discography - 01 A Happy Kettle.mp3  │
 │  │  ├─ 📄 Closet Witch - Complete Discography - 02 Ace of Cups.mp3     │
 │  │  ├─ 📄 Closet Witch - Complete Discography - 03 Abstinence, but Not.│
 │  │  ├─ 📄 Closet Witch - Complete Discography - 04 The Squash Rotting.m│
 │  │  ├─ 📄 Closet Witch - Complete Discography - 05 Solar Lullaby.mp3 ──╰─── ¹ ²
 │  │  ├─ 📄 Closet Witch - Complete Discography - 06 Arlington Cemetery -
 │  │  ├─ 📄 Closet Witch - Complete Discography - 07 Abstinence, but Not
 │  │  ├─ 📄 Closet Witch - Complete Discography - 08 The Squash Rotting -
 │  │  ├─ 📄 Closet Witch - Complete Discography - 09 Blood Orange.mp3
 │  │  ├─ 📄 Closet Witch - Complete Discography - 10 Moonstomp.mp3
 │  │  ├─ 📄 Closet Witch - Complete Discography - 11 Eyelids of Horus.mp3
 │  │  ├─ 📄 Closet Witch - Complete Discography - 12 Brother.mp3
 ▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂
 ↓↑ navigate · ESC close · ^q quit  
 


For the following checklist items, please reference the mockup below:

 ╭───────────────────────────────────────────────────────────────────────╮
 │ ^/   /Users/nick/Downloads/5179932805744.mp4                          │  ╭── filename         5179932805744.mp4
 ╰───────────────────────────────────────────────────────────────────────╯  │¹
 📂 nick                                                                    │   embedded title  —
 ├─ 📁 Applications                                                         │   container       mp4
 ├─ 📁 Books                                                                │   codec           H.264
 ├─ 📁 code                                                                 │   size            1.8 GB
 ├─ 📁 Desktop                                                              │   subtitles       none
 ├─ 📁 Documents                                                            │   posters         eat-purely.webp
 ├─ 📂 Downloads                                                            │
 │  ├─ 📄 01.1.pdf                                                          ├── poster
 │  ├─ 📄 02.1.pdf                                                          │                    􎻮̅̅⃧􎻮̅̍⃧􎻮̅̎⃧􎻮̅̐⃧􎻮̅̒⃧􎻮̅̽⃧􎻮̅̾⃧􎻮̅̿⃧􎻮̅͆⃧􎻮̅͊⃧􎻮̅͋⃧􎻮̅͌⃧􎻮̅͐⃧􎻮̅͑⃧  ⁶
 │  ├─ 📄 45rpm.afdesign                                                    │                    􎻮̍̅⃧􎻮̍̍⃧􎻮̍̎⃧􎻮̍̐⃧􎻮̍̒⃧􎻮̍̽⃧􎻮̍̾⃧􎻮̍̿⃧􎻮̍͆⃧􎻮̍͊⃧􎻮̍͋⃧􎻮̍͌⃧􎻮̍͐⃧􎻮̍͑⃧
 │  ├─ 📄 2026-08-31---Jonathan-Jalbert---9300111043900015806926.pdf        │                    􎻮̎̅⃧􎻮̎̍⃧􎻮̎̎⃧􎻮̎̐⃧􎻮̎̒⃧􎻮̎̽⃧􎻮̎̾⃧􎻮̎̿⃧􎻮̎͆⃧􎻮̎͊⃧􎻮̎͋⃧􎻮̎͌⃧􎻮̎͐⃧􎻮̎͑⃧
 │  ├─ 📄 5179932805744.mp4 ² ⁷ ────────────────────────────────────────────┤ ³                  􎻮̐̅⃧􎻮̐̍⃧􎻮̐̎⃧􎻮̐̐⃧􎻮̐̒⃧􎻮̐̽⃧􎻮̐̾⃧􎻮̐̿⃧􎻮̐͆⃧􎻮̐͊⃧􎻮̐͋⃧􎻮̐͌⃧􎻮̐͐⃧􎻮̐͑⃧
 │  ├─ 📄 Animal Matching Cards.afphoto                                     │                    􎻮̒̅⃧􎻮̒̍⃧􎻮̒̎⃧􎻮̒̐⃧􎻮̒̒⃧􎻮̒̽⃧􎻮̒̾⃧􎻮̒̿⃧􎻮̒͆⃧􎻮̒͊⃧􎻮̒͋⃧􎻮̒͌⃧􎻮̒͐⃧􎻮̒͑⃧
 │  ├─ 📄 artcraft-launcher-0.3.2-macos-universal.dmg                       │                    􎻮̽̅⃧􎻮̽̍⃧􎻮̽̎⃧􎻮̽̐⃧􎻮̽̒⃧􎻮̽̽⃧􎻮̽̾⃧􎻮̽̿⃧􎻮̽͆⃧􎻮̽͊⃧􎻮̽͋⃧􎻮̽͌⃧􎻮̽͐⃧􎻮̽͑⃧
 │  ├─ 📄 Avantris LLC Professional Services Agreement_encrypted_.pdf       │                    􎻮̾̅⃧􎻮̾̍⃧􎻮̾̎⃧􎻮̾̐⃧􎻮̾̒⃧􎻮̾̽⃧􎻮̾̾⃧􎻮̾̿⃧􎻮̾͆⃧􎻮̾͊⃧􎻮̾͋⃧􎻮̾͌⃧􎻮̾͐⃧􎻮̾͑⃧
 │  ├─ 📁 book-inspiration-from-nick                                        │                    􎻮̿̅⃧􎻮̿̍⃧􎻮̿̎⃧􎻮̿̐⃧􎻮̿̒⃧􎻮̿̽⃧􎻮̿̾⃧􎻮̿̿⃧􎻮̿͆⃧􎻮̿͊⃧􎻮̿͋⃧􎻮̿͌⃧􎻮̿͐⃧􎻮̿͑⃧
 │  ├─ 📄 book-inspiration-from-nick.zip                                    │                    􎻮͆̅⃧􎻮͆̍⃧􎻮͆̎⃧􎻮͆̐⃧􎻮͆̒⃧􎻮͆̽⃧􎻮͆̾⃧􎻮͆̿⃧􎻮͆͆⃧􎻮͆͊⃧􎻮͆͋⃧􎻮͆͌⃧􎻮͆͐⃧􎻮͆͑⃧
 │  ├─ 📁 Books                                                             │                    􎻮͊̅⃧􎻮͊̍⃧􎻮͊̎⃧􎻮͊̐⃧􎻮͊̒⃧􎻮͊̽⃧􎻮͊̾⃧􎻮͊̿⃧􎻮͊͆⃧􎻮͊͊⃧􎻮͊͋⃧􎻮͊͌⃧􎻮͊͐⃧􎻮͊͑⃧
 │  ├─ 📁 character-design                                                  │                    􎻮͋̅⃧􎻮͋̍⃧􎻮͋̎⃧􎻮͋̐⃧􎻮͋̒⃧􎻮͋̽⃧􎻮͋̾⃧􎻮͋̿⃧􎻮͋͆⃧􎻮͋͊⃧􎻮͋͋⃧􎻮͋͌⃧􎻮͋͐⃧􎻮͋͑⃧
 │  ├─ 📁 Childrens                                                         │                    􎻮͌̅⃧􎻮͌̍⃧􎻮͌̎⃧􎻮͌̐⃧􎻮͌̒⃧􎻮͌̽⃧􎻮͌̾⃧􎻮͌̿⃧􎻮͌͆⃧􎻮͌͊⃧􎻮͌͋⃧􎻮͌͌⃧􎻮͌͐⃧􎻮͌͑⃧
 │  ├─ 📁 Comics                                                            │                    􎻮͐̅⃧􎻮͐̍⃧􎻮͐̎⃧􎻮͐̐⃧􎻮͐̒⃧􎻮͐̽⃧􎻮͐̾⃧􎻮͐̿⃧􎻮͐͆⃧􎻮͐͊⃧􎻮͐͋⃧􎻮͐͌⃧􎻮͐͐⃧􎻮͐͑⃧
 │  ├─ 📁 CTR                                                               │                    􎻮͑̅⃧􎻮͑̍⃧􎻮͑̎⃧􎻮͑̐⃧􎻮͑̒⃧􎻮͑̽⃧􎻮͑̾⃧􎻮͑̿⃧􎻮͑͆⃧􎻮͑͊⃧􎻮͑͋⃧􎻮͑͌⃧􎻮͑͐⃧􎻮͑͑⃧
 │  ├─ 📄 deck (1).pdf                                                      │                    􎻮͒̅⃧􎻮͒̍⃧􎻮͒̎⃧􎻮͒̐⃧􎻮͒̒⃧􎻮͒̽⃧􎻮͒̾⃧􎻮͒̿⃧􎻮͒͆⃧􎻮͒͊⃧􎻮͒͋⃧􎻮͒͌⃧􎻮͒͐⃧􎻮͒͑⃧
 │  ├─ 📄 deck (2).pdf                                                      │                    􎻮͗̅⃧􎻮͗̍⃧􎻮͗̎⃧􎻮͗̐⃧􎻮͗̒⃧􎻮͗̽⃧􎻮͗̾⃧􎻮͗̿⃧􎻮͗͆⃧􎻮͗͊⃧􎻮͗͋⃧􎻮͗͌⃧􎻮͗͐⃧􎻮͗͑⃧
 │  ├─ 📄 deck.pdf                                                          │                    1600 × 1200
 │  ├─ 📄 eat-purely.svg                                                    │
 │  ├─ 📄 eat-purely.webp                                                   ├──  ESC Exit
 │  ├─ 📁 Ebay                                                              │
 │  ├─ 📄 HandBrake-1.11.2.dmg                                             ⁸├──  ^o Open ⁴    ^x Cut      ^y Copy      ^DEL Delete ⁵
 │  ├─ 📁 Ideo                                                              │
 │  ├─ 📁 Img - Memories                                                    ╰──  ^1 Fetch Subtitles      ^2 Download Posters      ^3 Make GIF      ^4 Folderize ⁵
 │  ├─ 📄 IPHONE-6-BW-OC-2.svg
 │  ├─ 📄 Logic Pro v12.3 (OS 15.6.x +).dmg
 │  ├─ 📄 Logic_Pro_X_11.0.1.dmg
 │  ├─ 📁 Map Clicker
 │  ├─ 📄 meals.txt
 │  ├─ 📄 Meccia IDES Payment History 1.pdf
 │  ├─ 📁 Slides
 │  ├─ 📁 Transmission
 │  ├─ 📁 Vagabond Screenshots
 │  ├─ 📄 Vagabond v22 090.jpg
 │  ├─ 📄 Vending Machine Letter.jpeg
 │  ├─ 📄 VMware-Fusion-26H1-25388279_universal.dmg
 │  ╰─ 📄 VMware_Fusion_V13.6.2.dmg
 ├─ 📁 FontBase
 ├─ 📁 go
 ├─ 📁 Library
 ├─ 📁 Movies
 ├─ 📁 Music
 ├─ 📁 Pictures
 ╰─ 📁 Public


 ↓↑ navigate · ESC close · ^q quit ⁹                                                                                                                



- [x] ¹ I would like to make a few distinctions between different states and the colors associated with them. Note that these terms of art and states are new to this todo item, but will be folded into the official terms-of-art.md file going forward:

        Terms of art:
        - element: following HTML naming convention, an element is an individual component of the document
          - node: an element which is either a file or directory in the file tree
          - label: an element which identifies an input, value, or image to which it is linked
          - button: a clickable element which corresponds to an action the user can take
        - path: An unbroken line of unicode box-drawing characters which visually connect focusable elements. Note that paths are not elements.

        State: `focusable`
        Description: this state applies to any element which can attain a "focused" state. Note that this state does not include path characters.
        focusable element bg color -> "focusable-bg": GREY_20
        focusable element fg color -> "focusable-fg": GREY_90
        Applies to:
        - nodes
        - labels (though, only labels associated with editable inputs and images)
        - buttons

        State: `triggerable`
        Description: this is a state which modifies the fg color of a keybinding which can be triggered by the user at the current moment in time.
        triggerable bg color -> "triggerable-bg": inherit (`focusable-bg` for buttons, app background (GREY_10) for command strip actions)
        triggerable fg color -> "triggerable-fg": #ffa62b (I want a unique value for this because I would like the ability to change this to a different color than `focused-bg`)
        Notes:
        - Applies to keybindings only
        - Yes, this means that command strip actions need to have the keybinding separated from the action name just like buttons

        State: `focused`
        Description: This state applies to a single element (but not path) in the viewport which the user is currently able to interact with, manipulate, or modify.
        focused element bg color -> "focused-bg": #ffa62b
        focused element fg color -> "focused-fg": GREY_10
        Notes:
        - This state applies to buttons as well--in the current implementation, focused buttons have a bg color of GREY_20 and fg color of FOCUSED; they *should* have a bg color of #ffa62b and fg color of GREY_20 (though, please use the variables `focused-bg` and `focused-fg` as outlined above)

        State: `path`
        Description: This state applies to path characters which have not been traversed, and is the default state of path characters. In the mockup above, let's say "filename" is focused. In this scenario, all path characters below ³ are in this state.
        path bg color -> transparent (or, the canvas background color, GREY_10)
        path fg color -> text color (or, the canvas foreground color, GREY_90)
        Notes:
        - Treat path characters which have not been traversed with default character styling: fg color as the default fg color, and bg color as the default bg color.
        - I don't think this "state" needs its own variables--I articulated this "state" for you as a way to emphasize the rules for path characters. Hopefully this is helpful to you.

        State: `traversed`
        Description: This state applies to both path characters *and* focusable elements which the user traversed in order to arrive at the current "focused" element. I want traversed elements to be a different color than the focused color, so please use the variables below for this state. In the mockup above, let's say `^x Cut` is focused. In this scenario:
        - The node 5179932805744.mp4 has the `traversed` state
        - All path characters to the right of ³ and below ³ have the `traversed` state.
        - The button `^o Open` has the `traversed` state
        - The path characters between `^o Open` and `^x Cut` (marked by ⁴) have the `traversed` state
        - The button `^x Cut` has the `focused` state
        traversed path bg color: transparent (or, the canvas background color. path characters *always* have the app background color and *never* have a different bg color. I do not think path characters need a bg variable to explicitly set this.)
        traversed path fg color -> "traversed-path-fg": #ffa62b (I will change after you implement these changes)
        traversed element bg color -> "traversed-element-bg": #ffa62b (I will change later)
        traversed element fg color -> "traversed-element-fg": GREY_10
        Notes:
        - The color of traversed nodes looks especially wrong in the current implementation; I can't deduce why they are wrong right now because the colors are so off

- [x] ⁹ Though out of order numerically, ¹ relates to ⁹, so I am putting it next in the list. Given the changes in ¹ above, please rename the variables used for the command strip:
        - "triggerable-fg": #ffa62b
           Used for keybindings. Discussed above.
        - "note": GREY_40
           Combines and replaces "keybinding", "keybinding-bullet", and "logo" into a default color for the entirety of the command strip. Renames this default as "note" so that it describes the function of the text, instead of the component this style is currently used with. Having a "note" variable means that this style can be used in other places in the app by a name which makes sense in any context.
        Before implementing, please consult with me about remaining color variables which I have not directly or indirectly addressed which still need to find a home in the current UI.B

- [x] ² When a *node* is focused, but not its *details*, do not add focused fg color to the line extending outward from the focused node.

- [x] ³ When the selected node is higher than the lowest button group *and* a field in details is focused, change the `┤` to `╮` or `╯`.
        In the mockup above:
        When 5179932805744.mp4 node is focused:
        `────────────────────────────────────────────┤`
        When filename or poster are focused:
        `────────────────────────────────────────────╯`
        When a button in any of the three button groups is focused:
        `────────────────────────────────────────────╮`
        Additional context:
        The goal of this todo item is the same as the goal of lines 73-81 above: we want the path connecting the focused detail field to the file tree node to follow an unbroken line with no `┼`, `├`, or `┤` connectors, or any other T- or +-shaped characters.

- [x] ⁸ Though out of order numerically, ⁸ relates to ³, so I am putting it next in the list. When a button in a non-terminal button group is focused, make a similar change to the path characters as in ³ above:
        In the mockup above:
        When no buttons in the following group are focused:
        `├──  ^o Open      ^x Cut      ^y Copy      ^DEL Delete`
        When any button in the following group is focused:
        `╰──  ^o Open      ^x Cut      ^y Copy      ^DEL Delete`
        When no buttons in the following group are focused:
        `├──  ESC Exit`
        When any button in the following group is focused:
        `╰──  ESC Exit`

- [x] ⁴ Remove one character of padding from the left and from the right edges of buttons. Here is a two-layer mockup:
        Implemented:
          FG Layer:
          `  ESC Exit  `
          BG Layer
          `▒▒▒▒▒▒▒▒▒▒▒▒`
        New:
          FG Layer:
          ` ESC Exit `
          BG Layer
          `▒▒▒▒▒▒▒▒▒▒`

      Also, as implemented, when buttons are focused, the leftmost and rightmost cell of padding on buttons receives the focus color. I do not want this. Please only add the focused color to fg text instead of to padding.
        Characters receiving "focused" color:
        Implemented:
        `▒ ESC Exit ▒`
        New:
        ` ESC Exit `

- [x] ⁵ Please use box-drawing characters to connect buttons in button groups, and add focused_path fg color to all path characters to the left of the focused element.
      New:
        No button focused:
          BG Layer, focusable color:
          `▒▒▒▒▒▒▒▒▒  ▒▒▒▒▒▒▒▒  ▒▒▒▒▒▒▒▒▒  ▒▒▒▒▒▒▒▒▒▒▒▒▒`
          FG Layer, text color:
          `         ──        ──         ──             `
        2nd button focused:
          BG Layer, focused color:
          `           ▒▒▒▒▒▒▒▒                          `
          BG Layer, focusable color:
          `▒▒▒▒▒▒▒▒▒            ▒▒▒▒▒▒▒▒▒  ▒▒▒▒▒▒▒▒▒▒▒▒▒`
          FG Layer, focused color:
          `         ──                                  `
          FG Layer, focusable color:
          `                   ──         ──             `

- [x] ⁶ Please remove the border around album art/cover image which appears when this field is focused--adding the focused color the the element label is sufficient to communicate focus, and this border is no longer needed.

- [x] ⁷ Please add one cell of margin after the widest focusable label and/or two cells of margin after the widest non-focusable label and left-align all input fields after the widest label. Please see examples in original mockup file linked to at the top of this document. An additional example:
        Implemented:
        ```
        ╭── filename Animal Matching Cards.afphoto
        │   size  96.7 KB
        │   type  .afphoto
        ```
        New:
        ```
        ╭── filename  Animal Matching Cards.afphoto
        │   size      96.7 KB
        │   type      .afphoto
        ```


For the following todo items, please use the mockup below:
 ╭───────────────────────────────────────────────────────────────────────╮
 │ ^/   /Users/nick/Music/Various - Gymnasium Violence                   │     7 audio files selected
 ╰───────────────────────────────────────────────────────────────────────╯
 📂 Users                                                                   ╭── title         (mixed)
 ├─ 📂 nick                                                                 ├── artist        (mixed)
 │  ├─ 📁 Applications                                                      ├── album artist  Various
 │  ├─ 📁 Books                                                             ├── album         Gymnasium Violence
 │  ├─ 📁 code                                                              ├── genre         -
 │  ├─ 📁 Desktop                                                           ├── date          2019
 │  ├─ 📁 Documents                                                         ├── track no.     (mixed)
 │  ├─ 📁 Downloads                                                         ├── disc no.      -
 │  ├─ 📁 FontBase                                                          ├── composer      -
 │  ├─ 📁 go                                                                │
 │  ├─ 📁 Library                                                           ├── album art ⁴   􎻮̅̅᷄􎻮̅̍᷄􎻮̅̎᷄􎻮̅̐᷄􎻮̅̒᷄􎻮̅̽᷄􎻮̅̾᷄􎻮̅̿᷄􎻮̅͆᷄􎻮̅͊᷄􎻮̅͋᷄􎻮̅͌᷄􎻮̅͐᷄􎻮̅͑᷄􎻮̅͒᷄
 │  ├─ 📁 Movies                                                            │                 􎻮̍̅᷄􎻮̍̍᷄􎻮̍̎᷄􎻮̍̐᷄􎻮̍̒᷄􎻮̍̽᷄􎻮̍̾᷄􎻮̍̿᷄􎻮̍͆᷄􎻮̍͊᷄􎻮̍͋᷄􎻮̍͌᷄􎻮̍͐᷄􎻮̍͑᷄􎻮̍͒᷄
 │  ├─ 📂 Music                                                             │                 􎻮̎̅᷄􎻮̎̍᷄􎻮̎̎᷄􎻮̎̐᷄􎻮̎̒᷄􎻮̎̽᷄􎻮̎̾᷄􎻮̎̿᷄􎻮̎͆᷄􎻮̎͊᷄􎻮̎͋᷄􎻮̎͌᷄􎻮̎͐᷄􎻮̎͑᷄􎻮̎͒᷄
 │  │  ├─ 📁 Art                                                            │                 􎻮̐̅᷄􎻮̐̍᷄􎻮̐̎᷄􎻮̐̐᷄􎻮̐̒᷄􎻮̐̽᷄􎻮̐̾᷄􎻮̐̿᷄􎻮̐͆᷄􎻮̐͊᷄􎻮̐͋᷄􎻮̐͌᷄􎻮̐͐᷄􎻮̐͑᷄􎻮̐͒᷄
 │  │  ├─ 📁 Closet Witch - Complete Discography                            │                 􎻮̒̅᷄􎻮̒̍᷄􎻮̒̎᷄􎻮̒̐᷄􎻮̒̒᷄􎻮̒̽᷄􎻮̒̾᷄􎻮̒̿᷄􎻮̒͆᷄􎻮̒͊᷄􎻮̒͋᷄􎻮̒͌᷄􎻮̒͐᷄􎻮̒͑᷄􎻮̒͒᷄
 │  │  ├─ 📁 Closet Witch - Yeah Yeah Yeah its Closet Witch- Live at Trump  │                 􎻮̽̅᷄􎻮̽̍᷄􎻮̽̎᷄􎻮̽̐᷄􎻮̽̒᷄􎻮̽̽᷄􎻮̽̾᷄􎻮̽̿᷄􎻮̽͆᷄􎻮̽͊᷄􎻮̽͋᷄􎻮̽͌᷄􎻮̽͐᷄􎻮̽͑᷄􎻮̽͒᷄
 │  │  ├─ 📁 Deemix Folders                                                 │                 􎻮̾̅᷄􎻮̾̍᷄􎻮̾̎᷄􎻮̾̐᷄􎻮̾̒᷄􎻮̾̽᷄􎻮̾̾᷄􎻮̾̿᷄􎻮̾͆᷄􎻮̾͊᷄􎻮̾͋᷄􎻮̾͌᷄􎻮̾͐᷄􎻮̾͑᷄􎻮̾͒᷄
 │  │  ├─ 📁 deemix Music                                                   │                 􎻮̿̅᷄􎻮̿̍᷄􎻮̿̎᷄􎻮̿̐᷄􎻮̿̒᷄􎻮̿̽᷄􎻮̿̾᷄􎻮̿̿᷄􎻮̿͆᷄􎻮̿͊᷄􎻮̿͋᷄􎻮̿͌᷄􎻮̿͐᷄􎻮̿͑᷄􎻮̿͒᷄
 │  │  ├─ 📁 Me                                                             │                 􎻮͆̅᷄􎻮͆̍᷄􎻮͆̎᷄􎻮͆̐᷄􎻮͆̒᷄􎻮͆̽᷄􎻮͆̾᷄􎻮͆̿᷄􎻮͆͆᷄􎻮͆͊᷄􎻮͆͋᷄􎻮͆͌᷄􎻮͆͐᷄􎻮͆͑᷄􎻮͆͒᷄
 │  │  ├─ 📁 Music                                                          │                 􎻮͊̅᷄􎻮͊̍᷄􎻮͊̎᷄􎻮͊̐᷄􎻮͊̒᷄􎻮͊̽᷄􎻮͊̾᷄􎻮͊̿᷄􎻮͊͆᷄􎻮͊͊᷄􎻮͊͋᷄􎻮͊͌᷄􎻮͊͐᷄􎻮͊͑᷄􎻮͊͒᷄
 │  │  ├─ 📁 OldPainless-Demo                                               │                 􎻮͋̅᷄􎻮͋̍᷄􎻮͋̎᷄􎻮͋̐᷄􎻮͋̒᷄􎻮͋̽᷄􎻮͋̾᷄􎻮͋̿᷄􎻮͋͆᷄􎻮͋͊᷄􎻮͋͋᷄􎻮͋͌᷄􎻮͋͐᷄􎻮͋͑᷄􎻮͋͒᷄
 │  │  ├─ 📁 Soulseek                                                       │                 􎻮͌̅᷄􎻮͌̍᷄􎻮͌̎᷄􎻮͌̐᷄􎻮͌̒᷄􎻮͌̽᷄􎻮͌̾᷄􎻮͌̿᷄􎻮͌͆᷄􎻮͌͊᷄􎻮͌͋᷄􎻮͌͌᷄􎻮͌͐᷄􎻮͌͑᷄􎻮͌͒᷄
 │  │  ├─ 📁 Sunrise Skater Kids - Friendworld (2026)                       │                 􎻮͐̅᷄􎻮͐̍᷄􎻮͐̎᷄􎻮͐̐᷄􎻮͐̒᷄􎻮͐̽᷄􎻮͐̾᷄􎻮͐̿᷄􎻮͐͆᷄􎻮͐͊᷄􎻮͐͋᷄􎻮͐͌᷄􎻮͐͐᷄􎻮͐͑᷄􎻮͐͒᷄
 │  │  ╰─ 📂 Various - Gymnasium Violence ¹ ────────────────────────────────┤                 􎻮͑̅᷄􎻮͑̍᷄􎻮͑̎᷄􎻮͑̐᷄􎻮͑̒᷄􎻮͑̽᷄􎻮͑̾᷄􎻮͑̿᷄􎻮͑͆᷄􎻮͑͊᷄􎻮͑͋᷄􎻮͑͌᷄􎻮͑͐᷄􎻮͑͑᷄􎻮͑͒᷄
 │  │     ├─ 📄 ANF - Gymnasium Violence - 02 Shut Up.mp3                   │                 􎻮͒̅᷄􎻮͒̍᷄􎻮͒̎᷄􎻮͒̐᷄􎻮͒̒᷄􎻮͒̽᷄􎻮͒̾᷄􎻮͒̿᷄􎻮͒͆᷄􎻮͒͊᷄􎻮͒͋᷄􎻮͒͌᷄􎻮͒͐᷄􎻮͒͑᷄􎻮͒͒᷄
 │  │     ├─ 📄 ArnoxDuebel - Gymnasium Violence - 04 Burdened.mp3          │                 􎻮͗̅᷄􎻮͗̍᷄􎻮͗̎᷄􎻮͗̐᷄􎻮͗̒᷄􎻮͗̽᷄􎻮͗̾᷄􎻮͗̿᷄􎻮͗͆᷄􎻮͗͊᷄􎻮͗͋᷄􎻮͗͌᷄􎻮͗͐᷄􎻮͗͑᷄􎻮͗͒᷄
 │  │     ├─ 📄 cover.jpg                                                   │                 700 × 700
 │  │     ├─ 📄 D.O.E. - Gymnasium Violence - 06 Void II.mp3                │
 │  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  ├── ⁴            ⁴ ^p⁵import ── ^f fetch ── ⁴
 │  │     ├─ 📄 Nothing Clean - Gymnasium Violence - 05 Fetus - Slog.mp3    │
 │  │     ├─ 📄 Sickmark - Gymnasium Violence - 01 Bounded Minds.mp3        ├── ^x Cut ── ^y Copy ── ^DEL Delete
 │  │     ╰─ 📄 Travølta - Gymnasium Violence - 03 Anarcho Toilet Revolut³  │
 │  ├─ 📁 Pictures                                                          ╰── ^1 Folderize ⁶
 │  ╰─ 📁 Public                                                              ² info          mp3 · 320 kbps · 274s · 12.1 MB
 ╰─ 📁 Shared


 ↓↑ navigate · → TAB expand · ← TAB collapse · ^← collapse level · ENT edit · ^r refresh · ^. toggle hidden files · ^n new directory · ^q quit 

- [x] ¹ When a file tree node is selected as in ¹, the path characters should have default fg and bg color. Example:
        Implemented:
        ` 📂 Various - Gymnasium Violence ────────────────────────────────┤`
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^                                  <- focused-bg & focused-fg (correct)
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^    <- traversed-fg & focusable-bg (incorrect)
                                                                        ^^^ <- default bg & default fg (correct)
        New:
        ` 📂 Various - Gymnasium Violence ────────────────────────────────┤`
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^                                  <- focused-bg & focused-fg
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ <- default bg & default fg

- [x] ² Please add a newline between the final button bar and info.
        Implemented:
        ```
        ╰── ^1 Folderize
            info          mp3 · 320 kbps · 274s · 12.1 MB
        ```
        New:
        ```
        ╰── ^1 Folderize

            info          mp3 · 320 kbps · 274s · 12.1 MB
        ```

- [x] ³ Please replace the final character of an overflowing line with an ellipsis character (…).
        Implemented:
        ` 📄 Travølta - Gymnasium Violence - 03 Anarcho Toilet Revoluti`
        New:
        ` 📄 Travølta - Gymnasium Violence - 03 Anarcho Toilet Revolut…`

- [x] ⁴ Please change the UI to match both the functionality and the mental model of this section:

State 1: "📂 Various - Gymnasium Violence" is focused

FG Implemented:

 │  ├─ 📁 FontBase                                                          ├── composer      -
 │  ├─ 📁 go                                                                │
 │  ├─ 📁 Library                                                           ├── album art     􎻮̅̅᷄􎻮̅̍᷄􎻮̅̎᷄􎻮̅̐᷄􎻮̅̒᷄􎻮̅̽᷄􎻮̅̾᷄􎻮̅̿᷄􎻮̅͆᷄􎻮̅͊᷄􎻮̅͋᷄􎻮̅͌᷄􎻮̅͐᷄􎻮̅͑᷄􎻮̅͒᷄
 │  ├─ 📁 Movies                                                            │                 􎻮̍̅᷄􎻮̍̍᷄􎻮̍̎᷄􎻮̍̐᷄􎻮̍̒᷄􎻮̍̽᷄􎻮̍̾᷄􎻮̍̿᷄􎻮̍͆᷄􎻮̍͊᷄􎻮̍͋᷄􎻮̍͌᷄􎻮̍͐᷄􎻮̍͑᷄􎻮̍͒᷄
 │  ├─ 📂 Music                                                             │                 􎻮̎̅᷄􎻮̎̍᷄􎻮̎̎᷄􎻮̎̐᷄􎻮̎̒᷄􎻮̎̽᷄􎻮̎̾᷄􎻮̎̿᷄􎻮̎͆᷄􎻮̎͊᷄􎻮̎͋᷄􎻮̎͌᷄􎻮̎͐᷄􎻮̎͑᷄􎻮̎͒᷄
 │  │  ├─ 📁 Art                                                            │                 􎻮̐̅᷄􎻮̐̍᷄􎻮̐̎᷄􎻮̐̐᷄􎻮̐̒᷄􎻮̐̽᷄􎻮̐̾᷄􎻮̐̿᷄􎻮̐͆᷄􎻮̐͊᷄􎻮̐͋᷄􎻮̐͌᷄􎻮̐͐᷄􎻮̐͑᷄􎻮̐͒᷄
 │  │  ├─ 📁 Closet Witch - Complete Discography                            │                 􎻮̒̅᷄􎻮̒̍᷄􎻮̒̎᷄􎻮̒̐᷄􎻮̒̒᷄􎻮̒̽᷄􎻮̒̾᷄􎻮̒̿᷄􎻮̒͆᷄􎻮̒͊᷄􎻮̒͋᷄􎻮̒͌᷄􎻮̒͐᷄􎻮̒͑᷄􎻮̒͒᷄
 │  │  ├─ 📁 Closet Witch - Yeah Yeah Yeah its Closet Witch- Live at Trump  │                 􎻮̽̅᷄􎻮̽̍᷄􎻮̽̎᷄􎻮̽̐᷄􎻮̽̒᷄􎻮̽̽᷄􎻮̽̾᷄􎻮̽̿᷄􎻮̽͆᷄􎻮̽͊᷄􎻮̽͋᷄􎻮̽͌᷄􎻮̽͐᷄􎻮̽͑᷄􎻮̽͒᷄
 │  │  ├─ 📁 Deemix Folders                                                 │                 􎻮̾̅᷄􎻮̾̍᷄􎻮̾̎᷄􎻮̾̐᷄􎻮̾̒᷄􎻮̾̽᷄􎻮̾̾᷄􎻮̾̿᷄􎻮̾͆᷄􎻮̾͊᷄􎻮̾͋᷄􎻮̾͌᷄􎻮̾͐᷄􎻮̾͑᷄􎻮̾͒᷄
 │  │  ├─ 📁 deemix Music                                                   │                 􎻮̿̅᷄􎻮̿̍᷄􎻮̿̎᷄􎻮̿̐᷄􎻮̿̒᷄􎻮̿̽᷄􎻮̿̾᷄􎻮̿̿᷄􎻮̿͆᷄􎻮̿͊᷄􎻮̿͋᷄􎻮̿͌᷄􎻮̿͐᷄􎻮̿͑᷄􎻮̿͒᷄
 │  │  ├─ 📁 Me                                                             │                 􎻮͆̅᷄􎻮͆̍᷄􎻮͆̎᷄􎻮͆̐᷄􎻮͆̒᷄􎻮͆̽᷄􎻮͆̾᷄􎻮͆̿᷄􎻮͆͆᷄􎻮͆͊᷄􎻮͆͋᷄􎻮͆͌᷄􎻮͆͐᷄􎻮͆͑᷄􎻮͆͒᷄
 │  │  ├─ 📁 Music                                                          │                 􎻮͊̅᷄􎻮͊̍᷄􎻮͊̎᷄􎻮͊̐᷄􎻮͊̒᷄􎻮͊̽᷄􎻮͊̾᷄􎻮͊̿᷄􎻮͊͆᷄􎻮͊͊᷄􎻮͊͋᷄􎻮͊͌᷄􎻮͊͐᷄􎻮͊͑᷄􎻮͊͒᷄
 │  │  ├─ 📁 OldPainless-Demo                                               │                 􎻮͋̅᷄􎻮͋̍᷄􎻮͋̎᷄􎻮͋̐᷄􎻮͋̒᷄􎻮͋̽᷄􎻮͋̾᷄􎻮͋̿᷄􎻮͋͆᷄􎻮͋͊᷄􎻮͋͋᷄􎻮͋͌᷄􎻮͋͐᷄􎻮͋͑᷄􎻮͋͒᷄
 │  │  ├─ 📁 Soulseek                                                       │                 􎻮͌̅᷄􎻮͌̍᷄􎻮͌̎᷄􎻮͌̐᷄􎻮͌̒᷄􎻮͌̽᷄􎻮͌̾᷄􎻮͌̿᷄􎻮͌͆᷄􎻮͌͊᷄􎻮͌͋᷄􎻮͌͌᷄􎻮͌͐᷄􎻮͌͑᷄􎻮͌͒᷄
 │  │  ├─ 📁 Sunrise Skater Kids - Friendworld (2026)                       │                 􎻮͐̅᷄􎻮͐̍᷄􎻮͐̎᷄􎻮͐̐᷄􎻮͐̒᷄􎻮͐̽᷄􎻮͐̾᷄􎻮͐̿᷄􎻮͐͆᷄􎻮͐͊᷄􎻮͐͋᷄􎻮͐͌᷄􎻮͐͐᷄􎻮͐͑᷄􎻮͐͒᷄
 │  │  ╰─ 📂 Various - Gymnasium Violence ──────────────────────────────────┤                 􎻮͑̅᷄􎻮͑̍᷄􎻮͑̎᷄􎻮͑̐᷄􎻮͑̒᷄􎻮͑̽᷄􎻮͑̾᷄􎻮͑̿᷄􎻮͑͆᷄􎻮͑͊᷄􎻮͑͋᷄􎻮͑͌᷄􎻮͑͐᷄􎻮͑͑᷄􎻮͑͒᷄
 │  │     ├─ 📄 ANF - Gymnasium Violence - 02 Shut Up.mp3                   │                 􎻮͒̅᷄􎻮͒̍᷄􎻮͒̎᷄􎻮͒̐᷄􎻮͒̒᷄􎻮͒̽᷄􎻮͒̾᷄􎻮͒̿᷄􎻮͒͆᷄􎻮͒͊᷄􎻮͒͋᷄􎻮͒͌᷄􎻮͒͐᷄􎻮͒͑᷄􎻮͒͒᷄
 │  │     ├─ 📄 ArnoxDuebel - Gymnasium Violence - 04 Burdened.mp3          │                 􎻮͗̅᷄􎻮͗̍᷄􎻮͗̎᷄􎻮͗̐᷄􎻮͗̒᷄􎻮͗̽᷄􎻮͗̾᷄􎻮͗̿᷄􎻮͗͆᷄􎻮͗͊᷄􎻮͗͋᷄􎻮͗͌᷄􎻮͗͐᷄􎻮͗͑᷄􎻮͗͒᷄
 │  │     ├─ 📄 cover.jpg                                                   │                 700 × 700
 │  │     ├─ 📄 D.O.E. - Gymnasium Violence - 06 Void II.mp3                │
 │  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  ├──                ^p import ── ^f fetch ──

FG New:

 │  ├─ 📁 FontBase                                                          ├── composer        -
 │  ├─ 📁 go                                                                │
 │  ├─ 📁 Library                                                           ├── album art ──╮    􎻮̅̅᷄􎻮̅̍᷄􎻮̅̎᷄􎻮̅̐᷄􎻮̅̒᷄􎻮̅̽᷄􎻮̅̾᷄􎻮̅̿᷄􎻮̅͆᷄􎻮̅͊᷄􎻮̅͋᷄􎻮̅͌᷄􎻮̅͐᷄􎻮̅͑᷄􎻮̅͒᷄
 │  ├─ 📁 Movies                                                            │               │   􎻮̍̅᷄􎻮̍̍᷄􎻮̍̎᷄􎻮̍̐᷄􎻮̍̒᷄􎻮̍̽᷄􎻮̍̾᷄􎻮̍̿᷄􎻮̍͆᷄􎻮̍͊᷄􎻮̍͋᷄􎻮̍͌᷄􎻮̍͐᷄􎻮̍͑᷄􎻮̍͒᷄
 │  ├─ 📂 Music                                                             │               │   􎻮̎̅᷄􎻮̎̍᷄􎻮̎̎᷄􎻮̎̐᷄􎻮̎̒᷄􎻮̎̽᷄􎻮̎̾᷄􎻮̎̿᷄􎻮̎͆᷄􎻮̎͊᷄􎻮̎͋᷄􎻮̎͌᷄􎻮̎͐᷄􎻮̎͑᷄􎻮̎͒᷄
 │  │  ├─ 📁 Art                                                            │               │   􎻮̐̅᷄􎻮̐̍᷄􎻮̐̎᷄􎻮̐̐᷄􎻮̐̒᷄􎻮̐̽᷄􎻮̐̾᷄􎻮̐̿᷄􎻮̐͆᷄􎻮̐͊᷄􎻮̐͋᷄􎻮̐͌᷄􎻮̐͐᷄􎻮̐͑᷄􎻮̐͒᷄
 │  │  ├─ 📁 Closet Witch - Complete Discography                            │               │   􎻮̒̅᷄􎻮̒̍᷄􎻮̒̎᷄􎻮̒̐᷄􎻮̒̒᷄􎻮̒̽᷄􎻮̒̾᷄􎻮̒̿᷄􎻮̒͆᷄􎻮̒͊᷄􎻮̒͋᷄􎻮̒͌᷄􎻮̒͐᷄􎻮̒͑᷄􎻮̒͒᷄
 │  │  ├─ 📁 Closet Witch - Yeah Yeah Yeah its Closet Witch- Live at Trump  │               │   􎻮̽̅᷄􎻮̽̍᷄􎻮̽̎᷄􎻮̽̐᷄􎻮̽̒᷄􎻮̽̽᷄􎻮̽̾᷄􎻮̽̿᷄􎻮̽͆᷄􎻮̽͊᷄􎻮̽͋᷄􎻮̽͌᷄􎻮̽͐᷄􎻮̽͑᷄􎻮̽͒᷄
 │  │  ├─ 📁 Deemix Folders                                                 │               │   􎻮̾̅᷄􎻮̾̍᷄􎻮̾̎᷄􎻮̾̐᷄􎻮̾̒᷄􎻮̾̽᷄􎻮̾̾᷄􎻮̾̿᷄􎻮̾͆᷄􎻮̾͊᷄􎻮̾͋᷄􎻮̾͌᷄􎻮̾͐᷄􎻮̾͑᷄􎻮̾͒᷄
 │  │  ├─ 📁 deemix Music                                                   │               │   􎻮̿̅᷄􎻮̿̍᷄􎻮̿̎᷄􎻮̿̐᷄􎻮̿̒᷄􎻮̿̽᷄􎻮̿̾᷄􎻮̿̿᷄􎻮̿͆᷄􎻮̿͊᷄􎻮̿͋᷄􎻮̿͌᷄􎻮̿͐᷄􎻮̿͑᷄􎻮̿͒᷄
 │  │  ├─ 📁 Me                                                             │               │   􎻮͆̅᷄􎻮͆̍᷄􎻮͆̎᷄􎻮͆̐᷄􎻮͆̒᷄􎻮͆̽᷄􎻮͆̾᷄􎻮͆̿᷄􎻮͆͆᷄􎻮͆͊᷄􎻮͆͋᷄􎻮͆͌᷄􎻮͆͐᷄􎻮͆͑᷄􎻮͆͒᷄
 │  │  ├─ 📁 Music                                                          │               │   􎻮͊̅᷄􎻮͊̍᷄􎻮͊̎᷄􎻮͊̐᷄􎻮͊̒᷄􎻮͊̽᷄􎻮͊̾᷄􎻮͊̿᷄􎻮͊͆᷄􎻮͊͊᷄􎻮͊͋᷄􎻮͊͌᷄􎻮͊͐᷄􎻮͊͑᷄􎻮͊͒᷄
 │  │  ├─ 📁 OldPainless-Demo                                               │               │   􎻮͋̅᷄􎻮͋̍᷄􎻮͋̎᷄􎻮͋̐᷄􎻮͋̒᷄􎻮͋̽᷄􎻮͋̾᷄􎻮͋̿᷄􎻮͋͆᷄􎻮͋͊᷄􎻮͋͋᷄􎻮͋͌᷄􎻮͋͐᷄􎻮͋͑᷄􎻮͋͒᷄
 │  │  ├─ 📁 Soulseek                                                       │               │   􎻮͌̅᷄􎻮͌̍᷄􎻮͌̎᷄􎻮͌̐᷄􎻮͌̒᷄􎻮͌̽᷄􎻮͌̾᷄􎻮͌̿᷄􎻮͌͆᷄􎻮͌͊᷄􎻮͌͋᷄􎻮͌͌᷄􎻮͌͐᷄􎻮͌͑᷄􎻮͌͒᷄
 │  │  ├─ 📁 Sunrise Skater Kids - Friendworld (2026)                       │               │   􎻮͐̅᷄􎻮͐̍᷄􎻮͐̎᷄􎻮͐̐᷄􎻮͐̒᷄􎻮͐̽᷄􎻮͐̾᷄􎻮͐̿᷄􎻮͐͆᷄􎻮͐͊᷄􎻮͐͋᷄􎻮͐͌᷄􎻮͐͐᷄􎻮͐͑᷄􎻮͐͒᷄
 │  │  ╰─ 📂 Various - Gymnasium Violence ──────────────────────────────────┤               │   􎻮͑̅᷄􎻮͑̍᷄􎻮͑̎᷄􎻮͑̐᷄􎻮͑̒᷄􎻮͑̽᷄􎻮͑̾᷄􎻮͑̿᷄􎻮͑͆᷄􎻮͑͊᷄􎻮͑͋᷄􎻮͑͌᷄􎻮͑͐᷄􎻮͑͑᷄􎻮͑͒᷄
 │  │     ├─ 📄 ANF - Gymnasium Violence - 02 Shut Up.mp3                   │               │   􎻮͒̅᷄􎻮͒̍᷄􎻮͒̎᷄􎻮͒̐᷄􎻮͒̒᷄􎻮͒̽᷄􎻮͒̾᷄􎻮͒̿᷄􎻮͒͆᷄􎻮͒͊᷄􎻮͒͋᷄􎻮͒͌᷄􎻮͒͐᷄􎻮͒͑᷄􎻮͒͒᷄
 │  │     ├─ 📄 ArnoxDuebel - Gymnasium Violence - 04 Burdened.mp3          │               │   􎻮͗̅᷄􎻮͗̍᷄􎻮͗̎᷄􎻮͗̐᷄􎻮͗̒᷄􎻮͗̽᷄􎻮͗̾᷄􎻮͗̿᷄􎻮͗͆᷄􎻮͗͊᷄􎻮͗͋᷄􎻮͗͌᷄􎻮͗͐᷄􎻮͗͑᷄􎻮͗͒᷄
 │  │     ├─ 📄 cover.jpg                                                   │               │   700 × 700
 │  │     ├─ 📄 D.O.E. - Gymnasium Violence - 06 Void II.mp3                │               │
 │  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  │               ╰── ^p Import ── ^f Fetch

  Notes:
  - Path is drawn through album art label and to the 
  - The "album art" element is not focusable, but it does describe the "Import" and "Fetch" buttons, which are focusable
  - Extra margin cells may need to be applied to all fields to fit these new path characters in
  - Path characters after `^f Fetch` have been removed
  - "Import" and "Fetch" have been capitalized (as should all button names)
  - The unconnected path characters have been removed from the final line in the mockup:
    Implemented:
    `│  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  ├──                ^p import ── ^f fetch ──`
    New
    `│  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  │               ╰── ^p Import ── ^f Fetch`

BG Implemented (Partial):

 │  ├─ 📁 FontBase                                                          ├── composer      -
 │  ├─ 📁 go                                                                │
 │  ├─ 📁 Library                                                           ├──▒▒▒▒▒▒▒▒▒▒▒    􎻮̅̅᷄􎻮̅̍᷄􎻮̅̎᷄􎻮̅̐᷄􎻮̅̒᷄􎻮̅̽᷄􎻮̅̾᷄􎻮̅̿᷄􎻮̅͆᷄􎻮̅͊᷄􎻮̅͋᷄􎻮̅͌᷄􎻮̅͐᷄􎻮̅͑᷄􎻮̅͒᷄
 │  ├─ 📁 Movies                                                            │                 􎻮̍̅᷄􎻮̍̍᷄􎻮̍̎᷄􎻮̍̐᷄􎻮̍̒᷄􎻮̍̽᷄􎻮̍̾᷄􎻮̍̿᷄􎻮̍͆᷄􎻮̍͊᷄􎻮̍͋᷄􎻮̍͌᷄􎻮̍͐᷄􎻮̍͑᷄􎻮̍͒᷄
 │  ├─ 📂 Music                                                             │                 􎻮̎̅᷄􎻮̎̍᷄􎻮̎̎᷄􎻮̎̐᷄􎻮̎̒᷄􎻮̎̽᷄􎻮̎̾᷄􎻮̎̿᷄􎻮̎͆᷄􎻮̎͊᷄􎻮̎͋᷄􎻮̎͌᷄􎻮̎͐᷄􎻮̎͑᷄􎻮̎͒᷄
 │  │  ├─ 📁 Art                                                            │                 􎻮̐̅᷄􎻮̐̍᷄􎻮̐̎᷄􎻮̐̐᷄􎻮̐̒᷄􎻮̐̽᷄􎻮̐̾᷄􎻮̐̿᷄􎻮̐͆᷄􎻮̐͊᷄􎻮̐͋᷄􎻮̐͌᷄􎻮̐͐᷄􎻮̐͑᷄􎻮̐͒᷄
 │  │  ├─ 📁 Closet Witch - Complete Discography                            │                 􎻮̒̅᷄􎻮̒̍᷄􎻮̒̎᷄􎻮̒̐᷄􎻮̒̒᷄􎻮̒̽᷄􎻮̒̾᷄􎻮̒̿᷄􎻮̒͆᷄􎻮̒͊᷄􎻮̒͋᷄􎻮̒͌᷄􎻮̒͐᷄􎻮̒͑᷄􎻮̒͒᷄
 │  │  ├─ 📁 Closet Witch - Yeah Yeah Yeah its Closet Witch- Live at Trump  │                 􎻮̽̅᷄􎻮̽̍᷄􎻮̽̎᷄􎻮̽̐᷄􎻮̽̒᷄􎻮̽̽᷄􎻮̽̾᷄􎻮̽̿᷄􎻮̽͆᷄􎻮̽͊᷄􎻮̽͋᷄􎻮̽͌᷄􎻮̽͐᷄􎻮̽͑᷄􎻮̽͒᷄
 │  │  ├─ 📁 Deemix Folders                                                 │                 􎻮̾̅᷄􎻮̾̍᷄􎻮̾̎᷄􎻮̾̐᷄􎻮̾̒᷄􎻮̾̽᷄􎻮̾̾᷄􎻮̾̿᷄􎻮̾͆᷄􎻮̾͊᷄􎻮̾͋᷄􎻮̾͌᷄􎻮̾͐᷄􎻮̾͑᷄􎻮̾͒᷄
 │  │  ├─ 📁 deemix Music                                                   │                 􎻮̿̅᷄􎻮̿̍᷄􎻮̿̎᷄􎻮̿̐᷄􎻮̿̒᷄􎻮̿̽᷄􎻮̿̾᷄􎻮̿̿᷄􎻮̿͆᷄􎻮̿͊᷄􎻮̿͋᷄􎻮̿͌᷄􎻮̿͐᷄􎻮̿͑᷄􎻮̿͒᷄
 │  │  ├─ 📁 Me                                                             │                 􎻮͆̅᷄􎻮͆̍᷄􎻮͆̎᷄􎻮͆̐᷄􎻮͆̒᷄􎻮͆̽᷄􎻮͆̾᷄􎻮͆̿᷄􎻮͆͆᷄􎻮͆͊᷄􎻮͆͋᷄􎻮͆͌᷄􎻮͆͐᷄􎻮͆͑᷄􎻮͆͒᷄
 │  │  ├─ 📁 Music                                                          │                 􎻮͊̅᷄􎻮͊̍᷄􎻮͊̎᷄􎻮͊̐᷄􎻮͊̒᷄􎻮͊̽᷄􎻮͊̾᷄􎻮͊̿᷄􎻮͊͆᷄􎻮͊͊᷄􎻮͊͋᷄􎻮͊͌᷄􎻮͊͐᷄􎻮͊͑᷄􎻮͊͒᷄
 │  │  ├─ 📁 OldPainless-Demo                                               │                 􎻮͋̅᷄􎻮͋̍᷄􎻮͋̎᷄􎻮͋̐᷄􎻮͋̒᷄􎻮͋̽᷄􎻮͋̾᷄􎻮͋̿᷄􎻮͋͆᷄􎻮͋͊᷄􎻮͋͋᷄􎻮͋͌᷄􎻮͋͐᷄􎻮͋͑᷄􎻮͋͒᷄
 │  │  ├─ 📁 Soulseek                                                       │                 􎻮͌̅᷄􎻮͌̍᷄􎻮͌̎᷄􎻮͌̐᷄􎻮͌̒᷄􎻮͌̽᷄􎻮͌̾᷄􎻮͌̿᷄􎻮͌͆᷄􎻮͌͊᷄􎻮͌͋᷄􎻮͌͌᷄􎻮͌͐᷄􎻮͌͑᷄􎻮͌͒᷄
 │  │  ├─ 📁 Sunrise Skater Kids - Friendworld (2026)                       │                 􎻮͐̅᷄􎻮͐̍᷄􎻮͐̎᷄􎻮͐̐᷄􎻮͐̒᷄􎻮͐̽᷄􎻮͐̾᷄􎻮͐̿᷄􎻮͐͆᷄􎻮͐͊᷄􎻮͐͋᷄􎻮͐͌᷄􎻮͐͐᷄􎻮͐͑᷄􎻮͐͒᷄
 │  │  ╰─█████████████████████████████████──────────────────────────────────┤                 􎻮͑̅᷄􎻮͑̍᷄􎻮͑̎᷄􎻮͑̐᷄􎻮͑̒᷄􎻮͑̽᷄􎻮͑̾᷄􎻮͑̿᷄􎻮͑͆᷄􎻮͑͊᷄􎻮͑͋᷄􎻮͑͌᷄􎻮͑͐᷄􎻮͑͑᷄􎻮͑͒᷄
 │  │     ├─ 📄 ANF - Gymnasium Violence - 02 Shut Up.mp3                   │                 􎻮͒̅᷄􎻮͒̍᷄􎻮͒̎᷄􎻮͒̐᷄􎻮͒̒᷄􎻮͒̽᷄􎻮͒̾᷄􎻮͒̿᷄􎻮͒͆᷄􎻮͒͊᷄􎻮͒͋᷄􎻮͒͌᷄􎻮͒͐᷄􎻮͒͑᷄􎻮͒͒᷄
 │  │     ├─ 📄 ArnoxDuebel - Gymnasium Violence - 04 Burdened.mp3          │                 􎻮͗̅᷄􎻮͗̍᷄􎻮͗̎᷄􎻮͗̐᷄􎻮͗̒᷄􎻮͗̽᷄􎻮͗̾᷄􎻮͗̿᷄􎻮͗͆᷄􎻮͗͊᷄􎻮͗͋᷄􎻮͗͌᷄􎻮͗͐᷄􎻮͗͑᷄􎻮͗͒᷄
 │  │     ├─ 📄 cover.jpg                                                   │                 700 × 700
 │  │     ├─ 📄 D.O.E. - Gymnasium Violence - 06 Void II.mp3                │
 │  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  ├──                ^p import ── ^f fetch ──

BG New (Partial):

 │  ├─ 📁 FontBase                                                          ├── composer        -
 │  ├─ 📁 go                                                                │
 │  ├─ 📁 Library                                                           ├── album art ──╮    􎻮̅̅᷄􎻮̅̍᷄􎻮̅̎᷄􎻮̅̐᷄􎻮̅̒᷄􎻮̅̽᷄􎻮̅̾᷄􎻮̅̿᷄􎻮̅͆᷄􎻮̅͊᷄􎻮̅͋᷄􎻮̅͌᷄􎻮̅͐᷄􎻮̅͑᷄􎻮̅͒᷄
 │  ├─ 📁 Movies                                                            │               │   􎻮̍̅᷄􎻮̍̍᷄􎻮̍̎᷄􎻮̍̐᷄􎻮̍̒᷄􎻮̍̽᷄􎻮̍̾᷄􎻮̍̿᷄􎻮̍͆᷄􎻮̍͊᷄􎻮̍͋᷄􎻮̍͌᷄􎻮̍͐᷄􎻮̍͑᷄􎻮̍͒᷄
 │  ├─ 📂 Music                                                             │               │   􎻮̎̅᷄􎻮̎̍᷄􎻮̎̎᷄􎻮̎̐᷄􎻮̎̒᷄􎻮̎̽᷄􎻮̎̾᷄􎻮̎̿᷄􎻮̎͆᷄􎻮̎͊᷄􎻮̎͋᷄􎻮̎͌᷄􎻮̎͐᷄􎻮̎͑᷄􎻮̎͒᷄
 │  │  ├─ 📁 Art                                                            │               │   􎻮̐̅᷄􎻮̐̍᷄􎻮̐̎᷄􎻮̐̐᷄􎻮̐̒᷄􎻮̐̽᷄􎻮̐̾᷄􎻮̐̿᷄􎻮̐͆᷄􎻮̐͊᷄􎻮̐͋᷄􎻮̐͌᷄􎻮̐͐᷄􎻮̐͑᷄􎻮̐͒᷄
 │  │  ├─ 📁 Closet Witch - Complete Discography                            │               │   􎻮̒̅᷄􎻮̒̍᷄􎻮̒̎᷄􎻮̒̐᷄􎻮̒̒᷄􎻮̒̽᷄􎻮̒̾᷄􎻮̒̿᷄􎻮̒͆᷄􎻮̒͊᷄􎻮̒͋᷄􎻮̒͌᷄􎻮̒͐᷄􎻮̒͑᷄􎻮̒͒᷄
 │  │  ├─ 📁 Closet Witch - Yeah Yeah Yeah its Closet Witch- Live at Trump  │               │   􎻮̽̅᷄􎻮̽̍᷄􎻮̽̎᷄􎻮̽̐᷄􎻮̽̒᷄􎻮̽̽᷄􎻮̽̾᷄􎻮̽̿᷄􎻮̽͆᷄􎻮̽͊᷄􎻮̽͋᷄􎻮̽͌᷄􎻮̽͐᷄􎻮̽͑᷄􎻮̽͒᷄
 │  │  ├─ 📁 Deemix Folders                                                 │               │   􎻮̾̅᷄􎻮̾̍᷄􎻮̾̎᷄􎻮̾̐᷄􎻮̾̒᷄􎻮̾̽᷄􎻮̾̾᷄􎻮̾̿᷄􎻮̾͆᷄􎻮̾͊᷄􎻮̾͋᷄􎻮̾͌᷄􎻮̾͐᷄􎻮̾͑᷄􎻮̾͒᷄
 │  │  ├─ 📁 deemix Music                                                   │               │   􎻮̿̅᷄􎻮̿̍᷄􎻮̿̎᷄􎻮̿̐᷄􎻮̿̒᷄􎻮̿̽᷄􎻮̿̾᷄􎻮̿̿᷄􎻮̿͆᷄􎻮̿͊᷄􎻮̿͋᷄􎻮̿͌᷄􎻮̿͐᷄􎻮̿͑᷄􎻮̿͒᷄
 │  │  ├─ 📁 Me                                                             │               │   􎻮͆̅᷄􎻮͆̍᷄􎻮͆̎᷄􎻮͆̐᷄􎻮͆̒᷄􎻮͆̽᷄􎻮͆̾᷄􎻮͆̿᷄􎻮͆͆᷄􎻮͆͊᷄􎻮͆͋᷄􎻮͆͌᷄􎻮͆͐᷄􎻮͆͑᷄􎻮͆͒᷄
 │  │  ├─ 📁 Music                                                          │               │   􎻮͊̅᷄􎻮͊̍᷄􎻮͊̎᷄􎻮͊̐᷄􎻮͊̒᷄􎻮͊̽᷄􎻮͊̾᷄􎻮͊̿᷄􎻮͊͆᷄􎻮͊͊᷄􎻮͊͋᷄􎻮͊͌᷄􎻮͊͐᷄􎻮͊͑᷄􎻮͊͒᷄
 │  │  ├─ 📁 OldPainless-Demo                                               │               │   􎻮͋̅᷄􎻮͋̍᷄􎻮͋̎᷄􎻮͋̐᷄􎻮͋̒᷄􎻮͋̽᷄􎻮͋̾᷄􎻮͋̿᷄􎻮͋͆᷄􎻮͋͊᷄􎻮͋͋᷄􎻮͋͌᷄􎻮͋͐᷄􎻮͋͑᷄􎻮͋͒᷄
 │  │  ├─ 📁 Soulseek                                                       │               │   􎻮͌̅᷄􎻮͌̍᷄􎻮͌̎᷄􎻮͌̐᷄􎻮͌̒᷄􎻮͌̽᷄􎻮͌̾᷄􎻮͌̿᷄􎻮͌͆᷄􎻮͌͊᷄􎻮͌͋᷄􎻮͌͌᷄􎻮͌͐᷄􎻮͌͑᷄􎻮͌͒᷄
 │  │  ├─ 📁 Sunrise Skater Kids - Friendworld (2026)                       │               │   􎻮͐̅᷄􎻮͐̍᷄􎻮͐̎᷄􎻮͐̐᷄􎻮͐̒᷄􎻮͐̽᷄􎻮͐̾᷄􎻮͐̿᷄􎻮͐͆᷄􎻮͐͊᷄􎻮͐͋᷄􎻮͐͌᷄􎻮͐͐᷄􎻮͐͑᷄􎻮͐͒᷄
 │  │  ╰─█████████████████████████████████──────────────────────────────────┤               │   􎻮͑̅᷄􎻮͑̍᷄􎻮͑̎᷄􎻮͑̐᷄􎻮͑̒᷄􎻮͑̽᷄􎻮͑̾᷄􎻮͑̿᷄􎻮͑͆᷄􎻮͑͊᷄􎻮͑͋᷄􎻮͑͌᷄􎻮͑͐᷄􎻮͑͑᷄􎻮͑͒᷄
 │  │     ├─ 📄 ANF - Gymnasium Violence - 02 Shut Up.mp3                   │               │   􎻮͒̅᷄􎻮͒̍᷄􎻮͒̎᷄􎻮͒̐᷄􎻮͒̒᷄􎻮͒̽᷄􎻮͒̾᷄􎻮͒̿᷄􎻮͒͆᷄􎻮͒͊᷄􎻮͒͋᷄􎻮͒͌᷄􎻮͒͐᷄􎻮͒͑᷄􎻮͒͒᷄
 │  │     ├─ 📄 ArnoxDuebel - Gymnasium Violence - 04 Burdened.mp3          │               │   􎻮͗̅᷄􎻮͗̍᷄􎻮͗̎᷄􎻮͗̐᷄􎻮͗̒᷄􎻮͗̽᷄􎻮͗̾᷄􎻮͗̿᷄􎻮͗͆᷄􎻮͗͊᷄􎻮͗͋᷄􎻮͗͌᷄􎻮͗͐᷄􎻮͗͑᷄􎻮͗͒᷄
 │  │     ├─ 📄 cover.jpg                                                   │               │   700 × 700
 │  │     ├─ 📄 D.O.E. - Gymnasium Violence - 06 Void II.mp3                │               │
 │  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  │               ╰── ^p Import ── ^f Fetch

  Notes:
  - "album art" is currently a focusable label; however, this label does not actually become focused--the buttons do. So, please remove the "focusable" background color
  - All other nodes and the "composer" label should also have the "focusable" background, but that's a lot of work for me to make, so hopefully this line of text will help you imagine that this is true.
  
State 2: `^p Import` is focused

BG Implemented (Partial):

 │  ├─ 📁 FontBase                                                          ├── composer      -
 │  ├─ 📁 go                                                                │
 │  ├─ 📁 Library                                                           ├──▒▒▒▒▒▒▒▒▒▒▒    􎻮̅̅᷄􎻮̅̍᷄􎻮̅̎᷄􎻮̅̐᷄􎻮̅̒᷄􎻮̅̽᷄􎻮̅̾᷄􎻮̅̿᷄􎻮̅͆᷄􎻮̅͊᷄􎻮̅͋᷄􎻮̅͌᷄􎻮̅͐᷄􎻮̅͑᷄􎻮̅͒᷄
 │  ├─ 📁 Movies                                                            │                 􎻮̍̅᷄􎻮̍̍᷄􎻮̍̎᷄􎻮̍̐᷄􎻮̍̒᷄􎻮̍̽᷄􎻮̍̾᷄􎻮̍̿᷄􎻮̍͆᷄􎻮̍͊᷄􎻮̍͋᷄􎻮̍͌᷄􎻮̍͐᷄􎻮̍͑᷄􎻮̍͒᷄
 │  ├─ 📂 Music                                                             │                 􎻮̎̅᷄􎻮̎̍᷄􎻮̎̎᷄􎻮̎̐᷄􎻮̎̒᷄􎻮̎̽᷄􎻮̎̾᷄􎻮̎̿᷄􎻮̎͆᷄􎻮̎͊᷄􎻮̎͋᷄􎻮̎͌᷄􎻮̎͐᷄􎻮̎͑᷄􎻮̎͒᷄
 │  │  ├─ 📁 Art                                                            │                 􎻮̐̅᷄􎻮̐̍᷄􎻮̐̎᷄􎻮̐̐᷄􎻮̐̒᷄􎻮̐̽᷄􎻮̐̾᷄􎻮̐̿᷄􎻮̐͆᷄􎻮̐͊᷄􎻮̐͋᷄􎻮̐͌᷄􎻮̐͐᷄􎻮̐͑᷄􎻮̐͒᷄
 │  │  ├─ 📁 Closet Witch - Complete Discography                            │                 􎻮̒̅᷄􎻮̒̍᷄􎻮̒̎᷄􎻮̒̐᷄􎻮̒̒᷄􎻮̒̽᷄􎻮̒̾᷄􎻮̒̿᷄􎻮̒͆᷄􎻮̒͊᷄􎻮̒͋᷄􎻮̒͌᷄􎻮̒͐᷄􎻮̒͑᷄􎻮̒͒᷄
 │  │  ├─ 📁 Closet Witch - Yeah Yeah Yeah its Closet Witch- Live at Trump  │                 􎻮̽̅᷄􎻮̽̍᷄􎻮̽̎᷄􎻮̽̐᷄􎻮̽̒᷄􎻮̽̽᷄􎻮̽̾᷄􎻮̽̿᷄􎻮̽͆᷄􎻮̽͊᷄􎻮̽͋᷄􎻮̽͌᷄􎻮̽͐᷄􎻮̽͑᷄􎻮̽͒᷄
 │  │  ├─ 📁 Deemix Folders                                                 │                 􎻮̾̅᷄􎻮̾̍᷄􎻮̾̎᷄􎻮̾̐᷄􎻮̾̒᷄􎻮̾̽᷄􎻮̾̾᷄􎻮̾̿᷄􎻮̾͆᷄􎻮̾͊᷄􎻮̾͋᷄􎻮̾͌᷄􎻮̾͐᷄􎻮̾͑᷄􎻮̾͒᷄
 │  │  ├─ 📁 deemix Music                                                   │                 􎻮̿̅᷄􎻮̿̍᷄􎻮̿̎᷄􎻮̿̐᷄􎻮̿̒᷄􎻮̿̽᷄􎻮̿̾᷄􎻮̿̿᷄􎻮̿͆᷄􎻮̿͊᷄􎻮̿͋᷄􎻮̿͌᷄􎻮̿͐᷄􎻮̿͑᷄􎻮̿͒᷄
 │  │  ├─ 📁 Me                                                             │                 􎻮͆̅᷄􎻮͆̍᷄􎻮͆̎᷄􎻮͆̐᷄􎻮͆̒᷄􎻮͆̽᷄􎻮͆̾᷄􎻮͆̿᷄􎻮͆͆᷄􎻮͆͊᷄􎻮͆͋᷄􎻮͆͌᷄􎻮͆͐᷄􎻮͆͑᷄􎻮͆͒᷄
 │  │  ├─ 📁 Music                                                          │                 􎻮͊̅᷄􎻮͊̍᷄􎻮͊̎᷄􎻮͊̐᷄􎻮͊̒᷄􎻮͊̽᷄􎻮͊̾᷄􎻮͊̿᷄􎻮͊͆᷄􎻮͊͊᷄􎻮͊͋᷄􎻮͊͌᷄􎻮͊͐᷄􎻮͊͑᷄􎻮͊͒᷄
 │  │  ├─ 📁 OldPainless-Demo                                               │                 􎻮͋̅᷄􎻮͋̍᷄􎻮͋̎᷄􎻮͋̐᷄􎻮͋̒᷄􎻮͋̽᷄􎻮͋̾᷄􎻮͋̿᷄􎻮͋͆᷄􎻮͋͊᷄􎻮͋͋᷄􎻮͋͌᷄􎻮͋͐᷄􎻮͋͑᷄􎻮͋͒᷄
 │  │  ├─ 📁 Soulseek                                                       │                 􎻮͌̅᷄􎻮͌̍᷄􎻮͌̎᷄􎻮͌̐᷄􎻮͌̒᷄􎻮͌̽᷄􎻮͌̾᷄􎻮͌̿᷄􎻮͌͆᷄􎻮͌͊᷄􎻮͌͋᷄􎻮͌͌᷄􎻮͌͐᷄􎻮͌͑᷄􎻮͌͒᷄
 │  │  ├─ 📁 Sunrise Skater Kids - Friendworld (2026)                       │                 􎻮͐̅᷄􎻮͐̍᷄􎻮͐̎᷄􎻮͐̐᷄􎻮͐̒᷄􎻮͐̽᷄􎻮͐̾᷄􎻮͐̿᷄􎻮͐͆᷄􎻮͐͊᷄􎻮͐͋᷄􎻮͐͌᷄􎻮͐͐᷄􎻮͐͑᷄􎻮͐͒᷄
 │  │  ╰─░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░──────────────────────────────────┤                 􎻮͑̅᷄􎻮͑̍᷄􎻮͑̎᷄􎻮͑̐᷄􎻮͑̒᷄􎻮͑̽᷄􎻮͑̾᷄􎻮͑̿᷄􎻮͑͆᷄􎻮͑͊᷄􎻮͑͋᷄􎻮͑͌᷄􎻮͑͐᷄􎻮͑͑᷄􎻮͑͒᷄
 │  │     ├─ 📄 ANF - Gymnasium Violence - 02 Shut Up.mp3                   │                 􎻮͒̅᷄􎻮͒̍᷄􎻮͒̎᷄􎻮͒̐᷄􎻮͒̒᷄􎻮͒̽᷄􎻮͒̾᷄􎻮͒̿᷄􎻮͒͆᷄􎻮͒͊᷄􎻮͒͋᷄􎻮͒͌᷄􎻮͒͐᷄􎻮͒͑᷄􎻮͒͒᷄
 │  │     ├─ 📄 ArnoxDuebel - Gymnasium Violence - 04 Burdened.mp3          │                 􎻮͗̅᷄􎻮͗̍᷄􎻮͗̎᷄􎻮͗̐᷄􎻮͗̒᷄􎻮͗̽᷄􎻮͗̾᷄􎻮͗̿᷄􎻮͗͆᷄􎻮͗͊᷄􎻮͗͋᷄􎻮͗͌᷄􎻮͗͐᷄􎻮͗͑᷄􎻮͗͒᷄
 │  │     ├─ 📄 cover.jpg                                                   │                 700 × 700
 │  │     ├─ 📄 D.O.E. - Gymnasium Violence - 06 Void II.mp3                │
 │  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  ├──               ░░░░░░░░░░░──██████████──

BG New (Partial):

 │  ├─ 📁 FontBase                                                          ├── composer        -
 │  ├─ 📁 go                                                                │
 │  ├─ 📁 Library                                                           ╭──░░░░░░░░░░░──╮    􎻮̅̅᷄􎻮̅̍᷄􎻮̅̎᷄􎻮̅̐᷄􎻮̅̒᷄􎻮̅̽᷄􎻮̅̾᷄􎻮̅̿᷄􎻮̅͆᷄􎻮̅͊᷄􎻮̅͋᷄􎻮̅͌᷄􎻮̅͐᷄􎻮̅͑᷄􎻮̅͒᷄
 │  ├─ 📁 Movies                                                            │               │   􎻮̍̅᷄􎻮̍̍᷄􎻮̍̎᷄􎻮̍̐᷄􎻮̍̒᷄􎻮̍̽᷄􎻮̍̾᷄􎻮̍̿᷄􎻮̍͆᷄􎻮̍͊᷄􎻮̍͋᷄􎻮̍͌᷄􎻮̍͐᷄􎻮̍͑᷄􎻮̍͒᷄
 │  ├─ 📂 Music                                                             │               │   􎻮̎̅᷄􎻮̎̍᷄􎻮̎̎᷄􎻮̎̐᷄􎻮̎̒᷄􎻮̎̽᷄􎻮̎̾᷄􎻮̎̿᷄􎻮̎͆᷄􎻮̎͊᷄􎻮̎͋᷄􎻮̎͌᷄􎻮̎͐᷄􎻮̎͑᷄􎻮̎͒᷄
 │  │  ├─ 📁 Art                                                            │               │   􎻮̐̅᷄􎻮̐̍᷄􎻮̐̎᷄􎻮̐̐᷄􎻮̐̒᷄􎻮̐̽᷄􎻮̐̾᷄􎻮̐̿᷄􎻮̐͆᷄􎻮̐͊᷄􎻮̐͋᷄􎻮̐͌᷄􎻮̐͐᷄􎻮̐͑᷄􎻮̐͒᷄
 │  │  ├─ 📁 Closet Witch - Complete Discography                            │               │   􎻮̒̅᷄􎻮̒̍᷄􎻮̒̎᷄􎻮̒̐᷄􎻮̒̒᷄􎻮̒̽᷄􎻮̒̾᷄􎻮̒̿᷄􎻮̒͆᷄􎻮̒͊᷄􎻮̒͋᷄􎻮̒͌᷄􎻮̒͐᷄􎻮̒͑᷄􎻮̒͒᷄
 │  │  ├─ 📁 Closet Witch - Yeah Yeah Yeah its Closet Witch- Live at Trump  │               │   􎻮̽̅᷄􎻮̽̍᷄􎻮̽̎᷄􎻮̽̐᷄􎻮̽̒᷄􎻮̽̽᷄􎻮̽̾᷄􎻮̽̿᷄􎻮̽͆᷄􎻮̽͊᷄􎻮̽͋᷄􎻮̽͌᷄􎻮̽͐᷄􎻮̽͑᷄􎻮̽͒᷄
 │  │  ├─ 📁 Deemix Folders                                                 │               │   􎻮̾̅᷄􎻮̾̍᷄􎻮̾̎᷄􎻮̾̐᷄􎻮̾̒᷄􎻮̾̽᷄􎻮̾̾᷄􎻮̾̿᷄􎻮̾͆᷄􎻮̾͊᷄􎻮̾͋᷄􎻮̾͌᷄􎻮̾͐᷄􎻮̾͑᷄􎻮̾͒᷄
 │  │  ├─ 📁 deemix Music                                                   │               │   􎻮̿̅᷄􎻮̿̍᷄􎻮̿̎᷄􎻮̿̐᷄􎻮̿̒᷄􎻮̿̽᷄􎻮̿̾᷄􎻮̿̿᷄􎻮̿͆᷄􎻮̿͊᷄􎻮̿͋᷄􎻮̿͌᷄􎻮̿͐᷄􎻮̿͑᷄􎻮̿͒᷄
 │  │  ├─ 📁 Me                                                             │               │   􎻮͆̅᷄􎻮͆̍᷄􎻮͆̎᷄􎻮͆̐᷄􎻮͆̒᷄􎻮͆̽᷄􎻮͆̾᷄􎻮͆̿᷄􎻮͆͆᷄􎻮͆͊᷄􎻮͆͋᷄􎻮͆͌᷄􎻮͆͐᷄􎻮͆͑᷄􎻮͆͒᷄
 │  │  ├─ 📁 Music                                                          │               │   􎻮͊̅᷄􎻮͊̍᷄􎻮͊̎᷄􎻮͊̐᷄􎻮͊̒᷄􎻮͊̽᷄􎻮͊̾᷄􎻮͊̿᷄􎻮͊͆᷄􎻮͊͊᷄􎻮͊͋᷄􎻮͊͌᷄􎻮͊͐᷄􎻮͊͑᷄􎻮͊͒᷄
 │  │  ├─ 📁 OldPainless-Demo                                               │               │   􎻮͋̅᷄􎻮͋̍᷄􎻮͋̎᷄􎻮͋̐᷄􎻮͋̒᷄􎻮͋̽᷄􎻮͋̾᷄􎻮͋̿᷄􎻮͋͆᷄􎻮͋͊᷄􎻮͋͋᷄􎻮͋͌᷄􎻮͋͐᷄􎻮͋͑᷄􎻮͋͒᷄
 │  │  ├─ 📁 Soulseek                                                       │               │   􎻮͌̅᷄􎻮͌̍᷄􎻮͌̎᷄􎻮͌̐᷄􎻮͌̒᷄􎻮͌̽᷄􎻮͌̾᷄􎻮͌̿᷄􎻮͌͆᷄􎻮͌͊᷄􎻮͌͋᷄􎻮͌͌᷄􎻮͌͐᷄􎻮͌͑᷄􎻮͌͒᷄
 │  │  ├─ 📁 Sunrise Skater Kids - Friendworld (2026)                       │               │   􎻮͐̅᷄􎻮͐̍᷄􎻮͐̎᷄􎻮͐̐᷄􎻮͐̒᷄􎻮͐̽᷄􎻮͐̾᷄􎻮͐̿᷄􎻮͐͆᷄􎻮͐͊᷄􎻮͐͋᷄􎻮͐͌᷄􎻮͐͐᷄􎻮͐͑᷄􎻮͐͒᷄
 │  │  ╰─░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ──────────────────────────────────╯               │   􎻮͑̅᷄􎻮͑̍᷄􎻮͑̎᷄􎻮͑̐᷄􎻮͑̒᷄􎻮͑̽᷄􎻮͑̾᷄􎻮͑̿᷄􎻮͑͆᷄􎻮͑͊᷄􎻮͑͋᷄􎻮͑͌᷄􎻮͑͐᷄􎻮͑͑᷄􎻮͑͒᷄
 │  │     ├─ 📄 ANF - Gymnasium Violence - 02 Shut Up.mp3                   │               │   􎻮͒̅᷄􎻮͒̍᷄􎻮͒̎᷄􎻮͒̐᷄􎻮͒̒᷄􎻮͒̽᷄􎻮͒̾᷄􎻮͒̿᷄􎻮͒͆᷄􎻮͒͊᷄􎻮͒͋᷄􎻮͒͌᷄􎻮͒͐᷄􎻮͒͑᷄􎻮͒͒᷄
 │  │     ├─ 📄 ArnoxDuebel - Gymnasium Violence - 04 Burdened.mp3          │               │   􎻮͗̅᷄􎻮͗̍᷄􎻮͗̎᷄􎻮͗̐᷄􎻮͗̒᷄􎻮͗̽᷄􎻮͗̾᷄􎻮͗̿᷄􎻮͗͆᷄􎻮͗͊᷄􎻮͗͋᷄􎻮͗͌᷄􎻮͗͐᷄􎻮͗͑᷄􎻮͗͒᷄
 │  │     ├─ 📄 cover.jpg                                                   │               │   700 × 700
 │  │     ├─ 📄 D.O.E. - Gymnasium Violence - 06 Void II.mp3                │               │
 │  │     ├─ 📄 Ghettö - Gymnasium Violence - 07 Helped Self Slaughter.mp3  │               ╰──░░░░░░░░░░░──██████████

  Notes:
  - ▒ = focusable bg color
  - ░ = traversed bg color
  - █ = focused bg color


- [x] ⁵ Please change the chord for "import to be `^i Import`

- [x] ⁶ Focusable buttons look great. However, the coloring for focused and traversable buttons are both incorrect. 

      - [x] Focused buttons:
            The following values, taken from theme.py, are correct for focused buttons:

            "focused-bg": PRIMARY,
            # a focused button's CHORD takes focused-fg too (Nick's call,
            # 2026-10-30): triggerable orange on a focused orange block is
            # invisible, and a chord needs no marking while it IS the thing
            # you are on
            "focused-fg": GREY_10,
            
            My suspicion: other styles are overriding these styles for buttons.

      - [x] Traversed buttons:
            The following values, taken from theme.py, are correct for traversed buttons:
            
            "traversed-element-bg": PRIMARY,
            "traversed-element-fg": GREY_10,
            
            My suspicion: `"triggerable-fg": PRIMARY,` is overriding `"traversed-element-fg": GREY_10,` for this state.



- [x] I can't trigger `^/` while focused on any non-node element. I should always be able to trigger ^/ from any non-dirty state.

- [x] Use braille spinners whenever the user is waiting on content to load at the place where the content will appear. Examples:
      ```
      ╭── filename  Users
      │
      │   contains  2 folders
      │   files     ⣴
      │   size      ⣴
      ```
      ```
      ╭── filename  AUDIO
      │
      │   contains  3 folders
      │   files     652+
      │   size      6.4 GB+
      │
      ├── ^x Cut ── ^y Copy ── ^DEL Delete
      │
      ├── ⣴
      ```
      If a probe resolves to find no actions in a button group, simply remove that button group, like so:
      ```
      ╭── filename  AUDIO
      │
      │   contains  3 folders
      │   files     652+
      │   size      6.4 GB+
      │
      ├── ^x Cut ── ^y Copy ── ^DEL Delete
      │
      │
      ```
      This is a good time for me to report a bug. As implemented, when the second button group materializes after the probe, it initially appears with no blank line between the two button groups, like so:
      ```
      ╭── filename  AUDIO
      │
      │   contains  3 folders
      │   files     652+
      │   size      6.4 GB+
      │
      ├── ^x Cut ── ^y Copy ── ^DEL Delete
      ├── ^1 Folderize ── ^2 Strip Multi-Artist
      ```
      Whereas, it *should* appear like this:
      ```
      ╭── filename  AUDIO
      │
      │   contains  3 folders
      │   files     652+
      │   size      6.4 GB+
      │
      ├── ^x Cut ── ^y Copy ── ^DEL Delete
      │
      ├── ^1 Folderize ── ^2 Strip Multi-Artist
      ```

- [x] Please save the state of `^. toggle hidden files` after the user quits mediasmith, so that the user's decision for this state is saved between sessions.

- [x] Related to the item above, when hidden files are toggled off, they appear as typeahead text in the path input. Please determine whether to offer typeahead suggestions basedd on the current state of hidden files:
      - Hidden files shown: typeahead includes hidden files
      - Hidden files hidden: typeahead does not include hidden files

- [x] When the probe for `^f Folderize` returns "false" and that button bar isn't drawn, a static braille character remains in place of the spinner and is not removed.
      Implemented:
      ```
      ╭── filename  Applications
      │
      │   contains  1 folder
      │   files     2
      ┤   size      851 B
      │
      ╰── ^x Cut ── ^y Copy ── ^DEL Delete

         ⣽
      ```
      New:
      ```
      ╭── filename  Applications
      │
      │   contains  1 folder
      │   files     2
      ┤   size      851 B
      │
      ╰── ^x Cut ── ^y Copy ── ^DEL Delete

      
      ```

- [x] Add an empty cell between the button bar braille spinner and the path characters.
      Implemented:
      ```
      ╭── filename  Applications
      │
      │   contains  1 folder
      │   files     2
      ┤   size      851 B
      │
      ├── ^x Cut ── ^y Copy ── ^DEL Delete
      │
      ╰──⣽
      ```
      New:
      ```
      ╭── filename  Applications
      │
      │   contains  1 folder
      │   files     2
      ┤   size      851 B
      │
      ├── ^x Cut ── ^y Copy ── ^DEL Delete
      │
      ╰── ⣽
      ```
      
- [x] When a too-narrow viewport forces a button bar to wrap onto a new line (ie, "wrap into a new button bar"), put a blank line in between these button bars as with all other button bars.
      Implemented:
      ```
      │
      ├── ^o Open ── ^x Cut ── ^y Copy ── ^DEL Delete
      │
      ├── ^1 Rotate ── ^2 Resize ── ^3 Trace ── ^4 Convert to PNG ── ^5 Convert to TIFF ──
      ├── ^6 Convert to WEBP
      ```
      New:
      ```
      │
      ├── ^o Open ── ^x Cut ── ^y Copy ── ^DEL Delete
      │
      ├── ^1 Rotate ── ^2 Resize ── ^3 Trace ── ^4 Convert to PNG ── ^5 Convert to TIFF ──
      │
      ├── ^6 Convert to WEBP
      ```

- [x] Previous Claudes have recommended I keep this app as a Python/Textual app instead of porting it to Go and releasing it as a binary, with the main reason being several libraries currently in use would need to be rewritten from scratch to make it into a Go project, and also there is a convention in projects released through Github to be released as source code instead of as a binary. However, a couple of friends are interested in using this app even though it's not 100% polished, and I would like for them to receive updates automatically when they run the app. Is this possible? If so, can you make it happen? And if not, please discuss.

- [x] After using the app, I would like to change my mind on an earlier decision.
      From earlier in the conversation:
      ```
      ├── ^1 Rotate ── ^2 Resize ── ^3 Trace ──
      │
      ├── ^4 Convert to JPG ── ^5 Convert to TIFF ──
      │
      ╰── ^6 Convert to WEBP
      Your earlier note about the dangling ── is answered by your own mockup — it keeps it, so I left it.
      ```
      I have decided I don't like the "dangling" path character. Please remove them from the final button in any group, like so:
      ```
      ├── ^1 Rotate ── ^2 Resize ── ^3 Trace
      │
      ├── ^4 Convert to JPG ── ^5 Convert to TIFF
      │
      ╰── ^6 Convert to WEBP
      ```
      Furthermore, the controls for wrapped button bars no longer match what the UI is showing. Consider this mockup:
      ```
 │  ├─ 📁 Childrens              │
 │  ├─ 📁 Comics                 │── ESC Exit
 │  ├─ 📁 CTR                    │
 │  ├─ 📄 deck (1).pdf           │── ^o Open ── ^x Cut ── ^y Copy ── ^DEL Delete
 │  ├─ 📄 deck.pdf               │
 │  ├─ 📄 eat-purely.svg         ╰── ^1 Fetch Subtitles ── ^2 Download Posters ──
 │  ├─ 📄 eat-purely.webp        │
 │  ├─ 📁 Ebay                   ╰── ^3 Make GIF ── ^4 Folderize
      ```
      When the user has `^1 Fetch Subtitles` focused, it appears as if they have three options:
      - Press up arrow to move to `^o Open`
      - Press right arrow to move to `^2 Download Posters`
      - Press down arrow to move to `^3 Make GIF` (the same pattern as pressing up arrow to move to `^o Open`)
      However, only the first two options are valid inputs; pressing down arrow does *not* move focus to `^3 Make GIF`
      I think that a better mental model for the code to adopt is the mental model of what the user observes: instead of *wrapping* an overflowing button bar, a *new* button bar should be appended to the list of button bars and populated with any buttons which overflow a longer button bar directly above. If the overflowed buttons appear in a separate bar, that also simplifies the styling you've had to do to make the overflowed buttons "look like" a new button bar. And, of course, it would unify the navigation controls with all other button bars.
      
- [x] You had a question for me: "Should ^., ^r and ^n work from anywhere, the way ^/ now does?" My answer is, yes, all commands printed in the command strip should work from any non-dirty state.

- [x] Another issue raised by you: "A shift-marked tree row is drawn by reversing its colours — the same mechanism that just bit us, still in browser.py by intent. Under the four-state model it has no token behind it."
      Explicit values should be set in theme.py for selected states:
      ```
      "selected-bg": GREY_90
      "selected-fg": GREY_10
      "selected-and-focused-bg": PRIMARY
      "selected-and-focused-fg": GREY_10
      ```

- [x] New feature: cropping an image. I would like to use this process: see what you come up with, use it, then provide you with mockups for changes. Are you able to implement a cropping feature, or would you like me to design one first?

- [x] I would like your help in creating a new feature to reduce the size of digital comics. Please check out ~/Documents/Comics for a few examples.
      The size of digital comics has risen drastically in a short time period: only a couple of years ago, a single issue was somewhere in the range of 30-60 MB for 25-30 images. Included in this folder are some of the most egregious examples from recent months, all over 150 MB, and a record high of 279 MB for 33 images. I don't think this is a reasonable amount of space for these image files to take up, and I would like a feature in Mediasmith to resize/downsample/convert both a single focused image as well as a folder of focused images.
      However, I don't have perfect parameters for you off the top of my head, and I am hoping that you can help me with this. Here are a few constraints from me:
      - I typically read comics on a 2019 iPad Pro -- you probably know the resolution of this
      - However, I would like to future-proof the image size for 2026 iPad resolutions and beyond
      - I use Synology's DS File iOS app to read comics directly from my NAS, and it doesn't appear to support viewing the WEBP format. Even though this is my report, please look into this anyway.
      - I am open to using a different iOS app to read comics from my NAS, but I prefer to keep the folders unzipped so that I can reference specific pages in Finder on my laptop, or even just read an issue from Finder or from Preview
