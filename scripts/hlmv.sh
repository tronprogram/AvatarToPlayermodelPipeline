#!/bin/sh
# Launch HLMV on the last compiled playermodel.
# Usage (from repo root):
#   ./scripts/hlmv.sh
#   ./scripts/hlmv.sh tronprogram
#   ./scripts/hlmv.sh path/to/model.mdl
set -e
REPO=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PYTHON="$REPO/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Missing $PYTHON. Create the project .venv first." >&2
  exit 1
fi
cd "$REPO"
exec "$PYTHON" -m app.hlmv "$@"
