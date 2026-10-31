"""PALETTE — the one file that holds every color in the app.

Every color is a hex assigned to a name, exactly once (Nick's spec,
todo-4 "Color Theme Stylesheet"). WHEN each name applies is decided by
CSS pseudo-classes (app.py / actions.py) and by the two renderers that
paint part of a widget (the Spine, and the tree's rows), which may
reference ONLY these names. Do not hardcode a color value anywhere else
— add a name here instead.

Revised 2026-10-29 (todo-6) for the path model: the idle/focus PAIRS are
gone. They answered "which view owns focus", and the app does not ask
that any more — focus is one ELEMENT, the path to it is lit, and nothing
else changes because the cursor moved. See the focus-model block below.

The "$ref" indirections from Nick's template are resolved at Python
level (constants below) so the Theme itself is a literal name→color
map — Textual substitutes variables into CSS textually and does not
reliably chase variable→variable references.
"""

from textual.theme import Theme

BLACK = "#000000"
GREY_10 = "#1b1b1b"
GREY_20 = "#303030"
GREY_30 = "#474747"
GREY_40 = "#5e5e5e"
GREY_50 = "#777777"
GREY_60 = "#919191"
GREY_70 = "#ababab"
GREY_80 = "#c6c6c6"
GREY_90 = "#e2e2e2"
WHITE = "#ffffff"

CHROME = "#1e1e1e"
"""The one value off the grey ramp: it is Textual's derived `$surface`,
kept at its exact value so adopting the token moved nothing on screen.
It backs the path box and the command strip — the chrome AROUND the two
views, which sit on GREY_10. Move it onto the ramp whenever you like;
nothing else reads it (todo-6, rule 5)."""

PRIMARY = "#ffa62b"
TRAVERSED="#bf8028"
SUCCESS = "#4ebf71"
WARNING = "#ffa62b"
ERROR = "#ba3c5b"

MEDIASMITH = Theme(
    name="mediasmith",
    dark=True,

    primary=PRIMARY,
    success=SUCCESS,
    warning=WARNING,
    error=ERROR,
    background=GREY_10,     # = grey-10, the app canvas
    foreground=GREY_90,     # = grey-90, brightest body text

    variables={
        # -- The palette, by name -------------------------------------------
        "black": BLACK,
        "grey-10": GREY_10,
        "grey-20": GREY_20,
        "grey-30": GREY_30,
        "grey-40": GREY_40,
        "grey-50": GREY_50,
        "grey-60": GREY_60,
        "grey-70": GREY_70,
        "grey-80": GREY_80,
        "grey-90": GREY_90,
        "white": WHITE,

        # -- The four states (Nick's model, todo-6 ¹ / ⁹, 2026-10-30)
        #
        # An ELEMENT is a thing in the document: a node (a file or folder
        # row), a label (one that identifies an editable input or an
        # image), or a button. A PATH is an unbroken line of box-drawing
        # characters connecting focusable elements — a path is NOT an
        # element, and it never carries a background.
        #
        #   focusable    it could take focus
        #   triggerable  a keybinding that works right now (foreground
        #                only; the background is whatever it sits on)
        #   focused      the ONE element the user is acting on
        #   traversed    elements AND path characters the user came
        #                through to reach the focused one
        #
        # `focused` and `traversed` share a foreground and differ by
        # background on purpose: Nick tunes them apart from here.
        "focusable-bg": GREY_20,
        "focusable-fg": GREY_90,

        "triggerable-fg": PRIMARY,

        "focused-bg": PRIMARY,
        # a focused button's CHORD takes focused-fg too (Nick's call,
        # 2026-10-30): triggerable orange on a focused orange block is
        # invisible, and a chord needs no marking while it IS the thing
        # you are on
        "focused-fg": GREY_10,

        "traversed-path-fg": TRAVERSED,
        "traversed-element-bg": TRAVERSED,
        "traversed-element-fg": GREY_10,

        # an UNtraversed path character is ordinary text: canvas colors,
        # no state of its own (todo-6 ¹, the `path` state)
        "path-fg": GREY_90,

        # SELECTED: a row the user has shift-marked. It used to be drawn
        # by REVERSING the row's colours, which is not a state at all —
        # it is whatever swap the row happened to produce, and it is the
        # same SGR 7 that hid the focused-button bug above. Explicit
        # values now (Nick, todo-6), including the pair for a row that
        # is marked AND under the cursor.
        "selected-bg": GREY_90,
        "selected-fg": GREY_10,
        "selected-and-focused-bg": PRIMARY,
        "selected-and-focused-fg": GREY_10,

        # -- Secondary text ------------------------------------------------
        # the command strip, end to end: its words, its bullets, the
        # logo. Named for what the text DOES, so it can be used wherever
        # a note belongs (Nick, todo-6 ⁹)
        "note": GREY_40,
        # in-pane secondary text: a read-only field's label, a dot-file's
        # name, a wizard's hint. Separate from `note` so strip chrome and
        # pane chrome can diverge (Nick's call, 2026-10-30)
        "muted": GREY_60,
        "text-fg": GREY_90,

        # the chrome around the views: the path box and the command strip
        "chrome-bg": CHROME,
        # the tree's own guide lines (│ ├─ ╰─). Textual derives a colour
        # for these; this is the ramp value nearest the one it chose, so
        # that every colour on screen comes from here (rule 5)
        "guide-fg": GREY_30,
        # …and the level type-ahead would search, which is marked by
        # brightening those guides (2026-09-03). Two values, because one
        # of them has to read as lit next to the other.
        "guide-level-fg": GREY_50,

        # Textual's own token, and the reason a focused button looked
        # wrong in a REAL terminal while every headless check passed: it
        # defaults to "b reverse", and SGR 7 makes the TERMINAL swap the
        # two colours below — so `focused-fg on focused-bg` reached the
        # screen as orange text on the canvas. A headless segment dump
        # reports `reverse` as a flag beside the colours, not applied to
        # them, which is exactly why it hid (Nick, todo-6 ⁶).
        "button-focus-text-style": "bold",

        "scrollbar-color": GREY_30,
        "scrollbar-track": "transparent",
        "scrollbar-corner": GREY_10,
    },
)
