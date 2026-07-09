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
import os
import pty
import random
import select
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mediafactory import make_media_tree  # noqa: E402

KEYS = ([b"\x1b[B"] * 5 + [b"\x1b[A"] * 3
        + [b"\x1b[C", b"\x1b[D", b" ", b"\t", b"\r", b"c"])


def attempt(seed: int, seconds: float, media: Path) -> bool:
    """Returns True if the app died mid-stress."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.environ["PYTHONFAULTHANDLER"] = "1"
        os.execvp(sys.executable, [sys.executable, "-m", "mediasmith", str(media)])

    random.seed(seed)
    start = time.time()
    dead = False
    while time.time() - start < seconds:
        readable, _, _ = select.select([fd], [], [], 0.02)
        if readable:
            try:
                chunk = os.read(fd, 65536)
                if not chunk:
                    dead = True
                    break
            except OSError:
                dead = True
                break
        try:
            os.write(fd, random.choice(KEYS))
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
            died = attempt(seed, args.seconds, media)
            deaths += died
            print(f"seed {seed}: {'DIED' if died else f'survived {args.seconds:.0f}s'}",
                  flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    print(f"{deaths} deaths / {args.seeds} seeds")
    return 1 if deaths else 0


if __name__ == "__main__":
    sys.exit(main())
