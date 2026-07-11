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
           b"\x13", b"\x0f", b"\x06"])   # ^s ^o ^f: action-bar chords

# seeds alternate through these; narrow exercises the phone column swap
SIZES = [(120, 40), (60, 40)]


def attempt(seed: int, seconds: float, media: Path,
            size: tuple[int, int]) -> bool:
    """Returns True if the app died mid-stress."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.environ["PYTHONFAULTHANDLER"] = "1"
        os.environ["MEDIASMITH_OFFLINE"] = "1"   # ^f must not hit the API
        os.execvp(sys.executable, [sys.executable, "-m", "mediasmith", str(media)])

    cols, rows = size
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    os.set_blocking(fd, False)   # a blocking write can hang the gate forever

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
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass
    os.waitpid(pid, 0)
    return dead


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=6)
    parser.add_argument("--seconds", type=float, default=75)
    args = parser.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="mediasmith-fuzz-"))
    media = make_media_tree(scratch / "media")
    deaths = 0
    try:
        for seed in range(7, 7 + args.seeds):
            size = SIZES[seed % len(SIZES)]
            died = attempt(seed, args.seconds, media, size)
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
