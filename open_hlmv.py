"""Open the latest compiled playermodel in SDK HLMV.

    .venv\\Scripts\\python.exe open_hlmv.py
    .venv\\Scripts\\python.exe open_hlmv.py path\\to\\model.mdl
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.core.paths import data_dir
from app.services.crowbar import open_in_hlmv
from app.services.deps.detect import gmod_tools_root


def latest_player_mdl() -> Path:
    root = gmod_tools_root(data_dir()) / "garrysmod" / "models" / "player"
    mdls = [path for path in root.rglob("*.mdl") if path.is_file()]
    if not mdls:
        raise FileNotFoundError(f"No compiled playermodel under {root}")
    return max(mdls, key=lambda path: path.stat().st_mtime)


def main(argv: list[str] | None = None) -> Path:
    args = sys.argv[1:] if argv is None else argv
    if args:
        mdl = Path(args[0])
        if not mdl.is_file():
            raise FileNotFoundError(f"No compiled MDL at {mdl}")
    else:
        mdl = latest_player_mdl()
    viewer = open_in_hlmv(mdl)
    print(mdl)
    print(viewer)
    return viewer


if __name__ == "__main__":
    main()
