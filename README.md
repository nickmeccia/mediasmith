# mediasmith

A media-library browser and toolbench for the terminal. One fullscreen
[Textual](https://textual.textualize.io/) app: directory tree on the left,
live details of the highlighted file on the right.

## Run

```bash
uv run mediasmith [start_dir]
uv run mediasmith --images halfcell|unicode|off   # image renderer override
```

## Development

```bash
uv run pytest                 # unit + interaction (Pilot) tests
uv run python tests/fuzz.py   # random-input stress gate (6 seeds × 75s)
```

## Architecture

This is a clean-slate rewrite; the previous suite is frozen at
[`mediasmith-v1`](../mediasmith-v1). Testing policy, slice roadmap, and the
architecture rules (NAS listing cache, compose-once details pane, textual-image
import ordering) are documented in [CLAUDE.md](CLAUDE.md) — read it before
changing structure.

## Status

- [x] Slice 1 — file browser + read-only details (NAS-cached tree,
      per-kind panels, cover art)
- [ ] Slice 2 — editing (audio tags first)
- [ ] Slice 3 — engine actions (subtitles)
- [ ] Slice 4 — batch operations
- [ ] Slice 5 — responsive / mobile layouts
