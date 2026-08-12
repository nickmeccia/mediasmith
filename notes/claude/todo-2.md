
-[x] Directory tree focus while scrolling
  - When nodes overflow the scroll container, keep the selected item on the center terminal cell line.
    - Example 1:
      - Scroll container can hold 11 lines
      - List has 20 nodes
      - user has selected node #7
      - scroll container shows nodes 2-12, with #7 selected
    When the scroll container can hold an even number of lines, the focused line should be int(lines/2) (ie, round down). There should be one extra node after the selected line than before the line.
    - Example 2
      - scroll container can hold 10 lines
      - list has 20 nodes
      - user has selected node #7
      - scroll container shows nodes 3-13, with #7 selected
    Pad the beginning and end of the list with empty space so that focus can stay in the center of the scroll container.
    - Example 3
      - scroll container can hold 11 lines
      - list has 20 nodes
      - user has selected node #19
      - scroll container shows nodes 14-20, plus 4 blank lines

  -[ ] Bug: When the user presses left arrow to move focus from current node to the parent directory node, the scroll container does not redraw itself and the focused node exists outside of the scroll container, instead of at the center line.

-- do not execute below this line --

  -[ ] Folder-collapsing behavior
    - Current behavior: 
      Consider the following flow:

      Initial state:

    When the user is focused on a node of depth 2 (see screenshot below), pressing 


-[ ] change focus on final node behavior (remove padding)

-[ ] Directory tree focus on folder open

-[ ] Folderize command on the book itself


