"""What THIS terminal makes of a focused button.

    .venv/bin/python notes/claude/diag-focus.py ~/Downloads

Navigate onto a button, press F9 (or F12, or ^g), then ^q. It writes
notes/claude/diag-focus.txt — including a traceback if it fails, so an
empty result means the key never arrived rather than "nothing to say".
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from textual.binding import Binding

from mediasmith.app import MediasmithApp, start_directory
from mediasmith.actions import ActionButton

OUT = Path(__file__).with_name("diag-focus.txt")


def hx(color) -> str:
    if color is None:
        return "NONE"
    return color.triplet.hex if getattr(color, "triplet", None) else str(color)


class Diag(MediasmithApp):
    BINDINGS = [*MediasmithApp.BINDINGS,
                Binding("f9", "diag", "diag", show=False),
                Binding("f12", "diag", "diag", show=False),
                Binding("ctrl+g", "diag", "diag", show=False)]

    def action_diag(self) -> None:
        lines = ["diag ran"]
        try:
            lines += self._diag_lines()
        except Exception:
            lines += ["", "FAILED:", traceback.format_exc()]
        try:
            OUT.write_text("\n".join(lines) + "\n")
            self.notify(f"wrote {OUT.name}", title="diag")
        except Exception as error:
            self.notify(f"could not write: {error}", title="diag",
                        severity="error")

    def _diag_lines(self) -> list[str]:
        import textual
        out = [f"textual {textual.__version__}",
               f"python {sys.version.split()[0]}",
               f"color system: {getattr(self.console, 'color_system', '?')}",
               f"ansi_color: {getattr(self, 'ansi_color', '?')}",
               f"theme: {self.theme}",
               f"app_focus: {getattr(self, 'app_focus', '?')}",
               f"size: {self.size}",
               f"focused: {self.focused!r}",
               f"screen stack: {[type(s).__name__ for s in self.screen_stack]}",
               ""]
        variables = self.get_css_variables()
        for var in ("focusable-bg", "focused-bg", "focused-fg",
                    "traversed-element-bg", "background", "surface"):
            out.append(f"  ${var} = {variables.get(var)}")
        out.append("")
        for button in self.query(ActionButton):
            if not button.display:
                continue
            style = button.rich_style
            out.append(
                f"  {(button.parent.id or '?'):16} {button.id:22} "
                f"focus={button.has_focus!s:5} "
                f"pseudo={sorted(button.get_pseudo_classes())} "
                f"classes={sorted(button.classes)} "
                f"fg={hx(style.color)} bg={hx(style.bgcolor)}")
        focused = self.focused
        if isinstance(focused, ActionButton):
            out += ["", f"focused button styles: "
                        f"background={focused.styles.background!r} "
                        f"tint={focused.styles.background_tint!r}",
                    "", "the cells on its row:"]
            strips = list(self.screen._compositor.render_strips())
            y = focused.region.y
            if 0 <= y < len(strips):
                for seg in strips[y]:
                    if seg.text.strip():
                        out.append(f"    {seg.text[:24]!r:28} "
                                   f"fg={hx(seg.style.color)} "
                                   f"bg={hx(seg.style.bgcolor)}")
            else:
                out.append(f"    (row {y} is outside the {len(strips)} rendered)")
        return out


if __name__ == "__main__":
    where = sys.argv[1] if len(sys.argv) > 1 else "."
    Diag(start_directory(Path(where))).run()
