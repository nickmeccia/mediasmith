#!/usr/bin/env python3
"""octant — turn an ASCII grid into Unicode octant (2x4) block characters.

Input is read as a grid of lines. Within each line a SPACE (U+0020) is an
unfilled pixel; every other character is a filled pixel. The grid is tiled
into 2-wide x 4-tall cells; each cell becomes one octant character.

    4 input lines  -> 1 output line
    5 input lines  -> 2 output lines (second band padded with empties)

Cell -> bit layout (value = sum of 2^(n-1) over filled cells):

      col0 col1
  r0   1    2
  r1   3    4
  r2   5    6
  r3   7    8

Sources:
  cli> octant art.txt              # read a file
  cli> octant - < art.txt          # read stdin (also: cat art.txt | octant)
  cli> octant -t "$(pbpaste)"      # a pasted multi-line string argument
"""
from __future__ import annotations

import argparse
import sys

# 26 of the 256 patterns predate Unicode 16 and live in older blocks; the
# remaining 230 are the Block Octants, laid out contiguously from U+1CD00 in
# ascending bit-value order (verified against unicodedata). Hardcoding the 26
# keeps this script independent of the runtime's Unicode version.
_BORROWED = {
    0: 0x20, 1: 0x1CEA8, 2: 0x1CEAB, 3: 0x1FB82, 5: 0x2598, 10: 0x259D,
    15: 0x2580, 20: 0x1FBE6, 40: 0x1FBE7, 63: 0x1FB85, 64: 0x1CEA3,
    80: 0x2596, 85: 0x258C, 90: 0x259E, 95: 0x259B, 128: 0x1CEA0,
    160: 0x2597, 165: 0x259A, 170: 0x2590, 175: 0x259C, 192: 0x2582,
    240: 0x2584, 245: 0x2599, 250: 0x259F, 252: 0x2586, 255: 0x2588,
}


def _build_table() -> list[str]:
    table: list[str | None] = [None] * 256
    for value, codepoint in _BORROWED.items():
        table[value] = chr(codepoint)
    nxt = 0x1CD00
    for value in range(256):
        if table[value] is None:
            table[value] = chr(nxt)
            nxt += 1
    return table  # type: ignore[return-value]


_OCTANTS = _build_table()


def convert(text: str, *, trim: bool = False) -> str:
    """Render an ASCII grid string as octant block lines."""
    lines = text.split("\n")
    if lines and lines[-1] == "":  # drop the empty tail of a trailing newline
        lines.pop()
    if not lines:
        return ""

    width = max((len(line) for line in lines), default=0)
    width += width & 1  # round up to an even number of columns

    out: list[str] = []
    for top in range(0, len(lines), 4):
        band = lines[top:top + 4]
        band += [""] * (4 - len(band))                 # pad band to 4 rows
        rows = [line.ljust(width) for line in band]    # pad rows to full width

        cells: list[str] = []
        for col in range(0, width, 2):
            value = 0
            for r in range(4):
                for c in range(2):
                    if rows[r][col + c] != " ":
                        value |= 1 << (2 * r + c)
            cells.append(_OCTANTS[value])

        line = "".join(cells)
        out.append(line.rstrip() if trim else line)
    return "\n".join(out)


def _read_input(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file and args.file != "-":
        with open(args.file, encoding="utf-8") as fh:
            return fh.read()
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="octant",
        description="Convert an ASCII grid (character=on, space=off) into "
                    "Unicode octant block characters.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="A space is the only 'off' pixel; every other character is 'on'.",
    )
    parser.add_argument(
        "file", nargs="?",
        help="input text file; omit or use '-' to read stdin",
    )
    parser.add_argument(
        "-t", "--text", metavar="STRING",
        help="use this literal multi-line string instead of a file",
    )
    parser.add_argument(
        "--trim", action="store_true",
        help="strip trailing empty cells from each output line",
    )
    args = parser.parse_args(argv)

    try:
        text = _read_input(args)
    except OSError as err:
        parser.error(str(err))

    # Ensure octant glyphs survive a non-UTF-8 default stdout encoding.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    print(convert(text, trim=args.trim))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
