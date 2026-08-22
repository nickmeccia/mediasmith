#!/usr/bin/env python3
"""Random-keypress stress harness — the anti-crash release gate.

Runs the real app in a real pty and mashes keys. Both v1 prototype crashes
were input races that only this kind of test caught; run it before
declaring any slice done.

    uv run python tests/fuzz.py                    # 6 seeds × 75s
    uv run python tests/fuzz.py --seeds 2 --seconds 20   # quick pass

Exit code 0 = no deaths.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import pty
import random
import shutil
import struct
import sys
import tempfile
import termios
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mediafactory import make_media_tree  # noqa: E402

KEYS = ([b"\x1b[B"] * 5 + [b"\x1b[A"] * 3
        + [b"\x1b[C", b"\x1b[D", b" ", b"\t", b"\r", b"c",
           b"\x1b[1;2B", b"\x1b[1;2A",   # shift+↓/↑: selection stress
           b"\x1b", b"\x1b", b"\x1f",    # esc (narrow view close), ctrl+/
           b"\x13", b"\x0f", b"\x06",    # ^s ^o ^f: save, open, fetch subs
           b"\x0b", b"\x15", b"\x16", b"\x17",   # ^k ^u ^v ^w: upload
                                         # cover, paste, write opf
           b"\x18",                      # ^x: cut / strip multi-artist
           b"\x0e",                      # ^n: new directory
           b"\x16",                      # ^v: paste
           b"\x1b[1;5D",                 # ctrl+←: collapse level
           b"\x04",                      # ^d: folderize a video
           b"\x05",                      # ^e: split omnibus / resize div
           b"\x01",                      # ^a: plan apply / resize apply
           b"\x10", b"\x02", b"\x19",    # ^p ^b ^y: converts (books are
                                         # OFFLINE-guarded; images run)
           b"\x14", b"\x07",             # ^t ^g: extract cover, make gif
           b"\x1b[3;5~",                 # ctrl+del: trash (OFFLINE-guarded)
           b"\x1b[1;2C", b"\x1b[1;2D",   # shift+→/←: shift-div nudges /
                                         # shift+←: collapse the tree level
           b"\x1b[5~", b"\x1b[6~"])      # pgup/pgdn: ±10s nudges

# seeds alternate through these; narrow exercises the phone column swap
SIZES = [(120, 40), (60, 40)]


def _jail_argv(argv: list[str], scratch: Path) -> list[str]:
    """Confine the child's file WRITES to its scratch tree (macOS
    seatbelt). The walk can browse anywhere — it has climbed to /dev,
    and once RENAMED ITS OWN SCRATCH DIR out from under the app
    (2026-07-15, seed 7) — so with rename/move/new-folder live, an
    unjailed walk can mutate real directories. Reads stay open; only
    writes outside the scratch (plus tty devices) are denied, and a
    denied write surfaces as an error toast — an error path worth
    fuzzing in itself."""
    if sys.platform != "darwin" or not shutil.which("sandbox-exec"):
        return argv
    profile = ("(version 1)(allow default)(deny file-write*)"
               f'(allow file-write* (subpath "{scratch}") (subpath "/dev"))')
    return ["sandbox-exec", "-p", profile, *argv]


def attempt(seed: int, seconds: float, scratch: Path, media: Path,
            size: tuple[int, int]) -> bool:
    """Returns True if the app died mid-stress. The pty output is kept
    at /tmp/fuzz-seed<N>.pty on death — only that tail can tell a
    worker crash from a swallowed CancelledError (standing lesson)."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.environ["PYTHONFAULTHANDLER"] = "1"
        os.environ["MEDIASMITH_OFFLINE"] = "1"   # ^f must not hit the API
        argv = _jail_argv([sys.executable, "-m", "mediasmith", str(media)],
                          scratch)
        os.execvp(argv[0], argv)

    cols, rows = size
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    os.set_blocking(fd, False)   # a blocking write can hang the gate forever
    pty_log = Path(f"/tmp/fuzz-seed{seed}.pty")
    pty_out = pty_log.open("wb")

    def drain() -> bool:
        """Read everything buffered; False when the child hung up. A lazy
        drain builds output backpressure that can deadlock the app's writer
        thread against our own (formerly blocking) key writes."""
        while True:
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                return True
            except OSError:
                return False
            if not chunk:
                return False
            pty_out.write(chunk)

    random.seed(seed)
    start = time.time()
    dead = False
    stalled: float | None = None
    while time.time() - start < seconds:
        if not drain():
            dead = True
            break
        try:
            os.write(fd, random.choice(KEYS))
            stalled = None
        except BlockingIOError:
            # input buffer full: the app stopped reading stdin. A wedged
            # app is as dead as a crashed one — fail the seed, don't hang.
            if stalled is None:
                stalled = time.time()
            elif time.time() - stalled > 5:
                print(f"seed {seed}: app stopped reading stdin (wedged)",
                      flush=True)
                dead = True
                break
        except OSError:
            dead = True
            break
        time.sleep(random.uniform(0.03, 0.12))

    if not dead:
        try:
            os.write(fd, b"\x11")   # ctrl+q — plain q now type-searches
        except OSError:
            pass
        time.sleep(1)
        drain()
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass
    os.waitpid(pid, 0)
    pty_out.close()
    if dead:
        # unique name: a surviving re-run of the same seed must never
        # delete the evidence of an earlier death
        kept = pty_log.with_name(f"fuzz-seed{seed}-{int(time.time())}.pty")
        pty_log.rename(kept)
        tail = kept.read_bytes()[-2000:]
        print(f"seed {seed}: pty kept at {kept}; tail:\n"
              f"{tail.decode('utf-8', errors='replace')}", flush=True)
    else:
        pty_log.unlink(missing_ok=True)
    return dead


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=6)
    parser.add_argument("--seconds", type=float, default=75)
    parser.add_argument("--first", type=int, default=7,
                        help="first seed (re-run a dying seed alone)")
    args = parser.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="mediasmith-fuzz-"))
    media = make_media_tree(scratch / "media")
    deaths = 0
    try:
        for seed in range(args.first, args.first + args.seeds):
            size = SIZES[seed % len(SIZES)]
            died = attempt(seed, args.seconds, scratch, media, size)
            deaths += died
            print(f"seed {seed} @ {size[0]}x{size[1]}: "
                  f"{'DIED' if died else f'survived {args.seconds:.0f}s'}",
                  flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    print(f"{deaths} deaths / {args.seeds} seeds")
    return 1 if deaths else 0


if __name__ == "__main__":
    sys.exit(main())
