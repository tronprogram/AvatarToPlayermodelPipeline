"""Launch SDK HLMV on a compiled playermodel.

Default is the newest ``models/player/*/*.mdl`` under the GMod tools tree.
Pass a slug (``tronprogram``) or a ``.mdl`` path to pick a specific model.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.paths import data_dir
from app.services.hlmv_preview import open_in_hlmv
from app.services.deps.detect import gmod_tools_root


def player_mdl_root() -> Path:
    return gmod_tools_root(data_dir()) / "garrysmod" / "models" / "player"


def mdl_for_slug(slug: str) -> Path | None:
    mdl = player_mdl_root() / slug / f"{slug}.mdl"
    return mdl if mdl.is_file() else None


def newest_player_mdl() -> Path | None:
    found = [path for path in player_mdl_root().glob("*/*.mdl") if path.is_file()]
    if not found:
        return None
    return max(found, key=lambda path: path.stat().st_mtime)


def _looks_like_path(target: str) -> bool:
    path = Path(target)
    return (
        path.suffix.lower() == ".mdl"
        or path.is_file()
        or path.is_absolute()
        or "/" in target
        or "\\" in target
    )


def resolve_mdl(target: str | None = None) -> Path:
    if not target:
        mdl = newest_player_mdl()
        if mdl is None:
            raise FileNotFoundError(
                f"No compiled playermodel MDLs under {player_mdl_root()}"
            )
        return mdl

    if _looks_like_path(target):
        mdl = Path(target).expanduser().resolve()
        if not mdl.is_file():
            raise FileNotFoundError(f"No compiled MDL at {mdl}")
        return mdl

    mdl = mdl_for_slug(target)
    if mdl is None:
        raise FileNotFoundError(
            f"No compiled MDL at {player_mdl_root() / target / f'{target}.mdl'}"
        )
    return mdl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open the last compiled playermodel in HLMV."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Player slug or path to a .mdl (default: newest under models/player)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="Print the MDL path without launching HLMV",
    )
    args = parser.parse_args(argv)
    try:
        mdl = resolve_mdl(args.target)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(mdl)
    if args.print_only:
        return 0
    open_in_hlmv(mdl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
