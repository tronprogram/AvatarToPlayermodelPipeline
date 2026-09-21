"""Freeze run_desktop.py with PyInstaller.

Windows/Linux: one-file ``dist/AvatarToPlayermodel[.exe]``.
macOS: onedir ``dist/AvatarToPlayermodel.app`` (one-file .app is rejected
by Gatekeeper / PyInstaller 7).

From the repo root:

    .venv/bin/python scripts/packaging/freeze.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().parent / "desktop.spec"
DIST = REPO / "dist"
WORK = REPO / "build" / "pyinstaller"


def _venv_python() -> Path:
    if os.name == "nt":
        return REPO / ".venv" / "Scripts" / "python.exe"
    return REPO / ".venv" / "bin" / "python"


def _clear_previous_binary() -> None:
    if not DIST.is_dir():
        return
    for leftover in DIST.glob("AvatarToPlayermodel*"):
        if leftover.is_dir():
            shutil.rmtree(leftover)
        else:
            leftover.unlink()


def main() -> int:
    python = _venv_python()
    if not python.is_file():
        print(f"Missing {python}. Create the project .venv first.", file=sys.stderr)
        return 1
    if not SPEC.is_file():
        print(f"Missing spec {SPEC}", file=sys.stderr)
        return 1
    DIST.mkdir(parents=True, exist_ok=True)
    _clear_previous_binary()
    cmd = [
        str(python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--distpath={DIST}",
        f"--workpath={WORK}",
        str(SPEC),
    ]
    print(" ".join(cmd), flush=True)
    code = subprocess.call(cmd, cwd=str(REPO))
    if code == 0:
        _drop_unpackaged_macos_collect()
    return code


def _drop_unpackaged_macos_collect() -> None:
    """BUNDLE copies COLLECT into the .app; the extra folder is leftover."""
    leftover = DIST / "AvatarToPlayermodel"
    bundled = DIST / "AvatarToPlayermodel.app"
    if leftover.is_dir() and bundled.is_dir():
        shutil.rmtree(leftover)


if __name__ == "__main__":
    raise SystemExit(main())
