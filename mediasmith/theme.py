"""PALETTE — the one file that holds every color in the app.

Every color is a hex assigned to a name, exactly once (Nick's spec,
todo-4 "Color Theme Stylesheet"). Focus is a STATE, not a color: the
idle/focus PAIRS are named here, but WHEN each look applies is decided
by CSS pseudo-classes (app.py / actions.py), which may reference ONLY
these tokens. Do not hardcode a color value anywhere else in the app —
add a name here instead.

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

PRIMARY = "#ffa62b"
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


        # Focused View

        "border-fg-focus": PRIMARY,
        "text-fg-focus": GREY_90,

        "node-hidden-fg-focus": GREY_60,
        "node-selected-bg-focus": PRIMARY,
        "scrollbar-color-focus": GREY_90,
        "scrollbar-color-hover-focus": PRIMARY,
        "scrollbar-color-active-focus": PRIMARY,
        "scrollbar-track-focus": "transparent",

        "label-fg-focus": GREY_60,
        "button-bg-focus": GREY_30,
        "button-fg-focus": GREY_90,
        "button-keybinding-fg-focus": PRIMARY,
        "button-selected-bg-focus": PRIMARY,
        "button-selected-fg-focus": GREY_90,
        "button-selected-keybinding-fg-focus": GREY_90,


        # Idle View

        "border-fg-idle": GREY_30,
        "text-fg-idle": GREY_40,

        "node-hidden-fg-idle": GREY_30,
        "node-selected-bg-idle": GREY_20,
        "scrollbar-color-idle": GREY_30,
        "scrollbar-color-hover-idle": GREY_30,
        "scrollbar-color-active-idle": GREY_30,
        "scrollbar-track-idle": "transparent",

        "label-fg-idle": GREY_30,
        "button-bg-idle": GREY_20,
        "button-fg-idle": GREY_40,
        "button-keybinding-fg-idle": GREY_40,
        "button-selected-bg-idle": GREY_20,
        "button-selected-fg-idle": GREY_40,
        "button-selected-keybinding-fg-idle": GREY_40,


        # Command Strip

        "keybinding": GREY_60,
        "keybinding-bullet": GREY_30,
        "logo": GREY_60,
    },
)
