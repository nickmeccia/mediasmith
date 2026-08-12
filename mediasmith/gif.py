"""Video → GIF: ffmpeg's two-pass palette pipeline.

Pass one distills an optimal 256-color palette from the (scaled,
resampled) clip; pass two renders the GIF through it — the difference
between a dithered mess and a GIF worth sending. Defaults are the
treat the brief asked for: 12 fps reads smooth without ballooning the
file, 480 px wide fits chat windows, lanczos scaling keeps text
legible.

House rules: output lands beside the source, never overwrites; ffmpeg
presence is checked calibre-style; the ``runner`` seam exists so tests
never spawn a real ffmpeg.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_FPS = 12
DEFAULT_WIDTH = 480

FFMPEG_TIMEOUT = 600    # a long clip on the NAS is minutes, not forever


def check_requirements() -> list[str]:
    if shutil.which("ffmpeg") is None:
        return ["ffmpeg not found — brew install ffmpeg"]
    return []


def gif_target(video: Path) -> Path:
    return video.with_suffix(".gif")


def _run_ffmpeg(argv: list[str]) -> None:
    result = subprocess.run(argv, capture_output=True, text=True,
                            timeout=FFMPEG_TIMEOUT)
    if result.returncode != 0:
        lines = (result.stderr or "").strip().splitlines()
        raise RuntimeError(lines[-1] if lines else "ffmpeg failed")


def make_gif(video: Path, fps: int = DEFAULT_FPS,
             width: int = DEFAULT_WIDTH,
             start: float | None = None, duration: float | None = None,
             runner=None, overwrite: bool = False) -> Path:
    """Render ``video`` to a sibling GIF. Raises on bad options, ffmpeg
    failures, and (unless ``overwrite``) an existing target."""
    if fps < 1 or width < 1:
        raise ValueError("fps and width must be positive")
    target = gif_target(video)
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target.name} already exists")
    run = runner or _run_ffmpeg
    clip: list[str] = []
    if start is not None:
        clip += ["-ss", str(start)]
    if duration is not None:
        clip += ["-t", str(duration)]
    filters = f"fps={fps},scale={width}:-1:flags=lanczos"
    with tempfile.TemporaryDirectory(prefix="mediasmith-gif-") as tmp:
        palette = Path(tmp) / "palette.png"
        run(["ffmpeg", "-v", "error", *clip, "-i", str(video),
             "-vf", f"{filters},palettegen", "-y", str(palette)])
        # -y/-n belt-and-braces: the exists() check above races nothing in
        # the UI (one worker), but ffmpeg must never prompt on stdin
        run(["ffmpeg", "-v", "error", "-y" if overwrite else "-n",
             *clip, "-i", str(video),
             "-i", str(palette),
             "-filter_complex", f"{filters} [x]; [x][1:v] paletteuse",
             str(target)])
    return target
