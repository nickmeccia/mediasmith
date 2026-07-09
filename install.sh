#!/bin/sh
# Symlink the launcher into your PATH. Safe to re-run.
#   ./install.sh                    # installs to ~/.local/bin
#   BINDIR=/usr/local/bin ./install.sh
set -e

BINDIR="${BINDIR:-$HOME/.local/bin}"
REPO="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$BINDIR"
ln -sf "$REPO/bin/mediasmith" "$BINDIR/mediasmith"
echo "Installed: $BINDIR/mediasmith -> $REPO/bin/mediasmith"

command -v uv >/dev/null 2>&1 || echo "WARNING: uv not found on PATH (required)"
case ":$PATH:" in
  *":$BINDIR:"*) ;;
  *) echo "WARNING: $BINDIR is not on your PATH" ;;
esac
