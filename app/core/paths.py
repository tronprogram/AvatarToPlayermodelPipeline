"""Filesystem roots for a PyInstaller one-file (portable) binary.

Two different directories:

- resource_root(): bundled, read-only files (templates, static, VERSION).
  Frozen, this is PyInstaller's temp extract (`sys._MEIPASS`).
- writable_root(): folder next to the .exe, for logs.
  Frozen, never `_MEIPASS` — that directory is deleted when the process exits.

In a source checkout both resolve to the repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running from a PyInstaller binary."""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Directory of files packed into the binary."""
    meipass = getattr(sys, "_MEIPASS", None)
    if is_frozen() and meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[2]


def writable_root() -> Path:
    """Directory that travels with the .exe (or the repo root in development)."""
    if is_frozen():
        return _frozen_writable_root(Path(sys.executable).resolve())
    return Path(__file__).resolve().parents[2]


def _frozen_writable_root(executable: Path) -> Path:
    """Folder next to the binary, or next to the .app on macOS."""
    here = executable.parent
    if sys.platform == "darwin" and here.name == "MacOS":
        contents = here.parent
        bundle = contents.parent
        if contents.name == "Contents" and bundle.suffix == ".app":
            return bundle.parent
    return here


def data_dir() -> Path:
    """Writable data directory next to the binary."""
    path = writable_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    """Writable log directory next to the binary."""
    path = writable_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
