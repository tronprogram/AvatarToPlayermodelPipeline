"""Zip a packaged addon so it extracts into garrysmod/addons/<slug>."""

from __future__ import annotations

import zipfile
from pathlib import Path


def zip_addon(addon_root: Path, dest: Path) -> Path:
    """Write ``dest`` containing ``<addon_root.name>/...``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    root = addon_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"No addon folder at {root}")
    prefix = root.name
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                zf.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
    return dest
