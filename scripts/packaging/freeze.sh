#!/bin/sh
# Freeze the desktop hallway (PyInstaller one-file / macOS .app).
# Usage (from repo root):
#   ./scripts/packaging/freeze.sh
set -e
REPO=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
PYTHON="$REPO/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Missing $PYTHON. Create the project .venv first." >&2
  exit 1
fi
exec "$PYTHON" "$REPO/scripts/packaging/freeze.py"
