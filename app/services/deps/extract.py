"""Unpack downloaded archives into the install tree."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.archives import extract_archive


def finalize_install(target: Path) -> None:
    if os.name == "nt":
        return
    blender_bin = target / "Blender.app" / "Contents" / "MacOS" / "Blender"
    if blender_bin.is_file():
        blender_bin.chmod(blender_bin.stat().st_mode | 0o111)
        link = target / "blender"
        if not link.exists():
            link.symlink_to(blender_bin)
    unix_bins = (
        "blender",
        "steamcmd.sh",
        "linux32/steamcmd",
        "linuxarm64/steamcmd",
    )
    for name in unix_bins:
        path = target / name
        if path.is_file():
            path.chmod(path.stat().st_mode | 0o111)
    steamcmd_sh = target / "steamcmd.sh"
    steamcmd = target / "steamcmd"
    if steamcmd_sh.is_file() and not steamcmd.exists():
        steamcmd.symlink_to(steamcmd_sh)


def extract_install(archive: Path, target: Path, *, unwrap: bool) -> None:
    extract_archive(archive, target, unwrap=unwrap)
    finalize_install(target)
