"""Unpack downloaded archives into the install tree."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.core.archives import extract_archive
from app.services.deps.detect import modified_compiler_tree


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


def extract_modified_compiler(archive: Path, data: Path) -> None:
    """Unpack BobmacU's template and promote ``Modified Complier`` to ``data/compiler``."""
    template = data / "_gmod_port_template"
    extract_archive(archive, template, unwrap=True)
    source = modified_compiler_tree(template)
    if source is None:
        raise FileNotFoundError(
            f"No Modified Complier/bin/studiomdl.exe in {archive.name}"
        )
    dest = data / "compiler"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def extract_hlmvplusplus(archive: Path, data: Path) -> None:
    """Unpack ficool2's HLMV++ exe/dll. Run it from ``compiler/bin`` so engine DLLs load."""
    staging = data / "_hlmvpp_extract"
    if staging.exists():
        shutil.rmtree(staging)
    extract_archive(archive, staging, unwrap=True)
    try:
        matches = list(staging.rglob("hlmvplusplus.exe"))
        if not matches:
            raise FileNotFoundError(f"No hlmvplusplus.exe in {archive.name}")
        exe = matches[0]
        dest = data / "hlmvplusplus"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe, dest / "hlmvplusplus.exe")
        dll = exe.with_name("hlmvplusplus.dll")
        if dll.is_file():
            shutil.copy2(dll, dest / "hlmvplusplus.dll")
        compiler_bin = data / "compiler" / "bin"
        if compiler_bin.is_dir():
            shutil.copy2(dest / "hlmvplusplus.exe", compiler_bin / "hlmvplusplus.exe")
            bundled = dest / "hlmvplusplus.dll"
            if bundled.is_file():
                shutil.copy2(bundled, compiler_bin / "hlmvplusplus.dll")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def extract_install(archive: Path, target: Path, *, unwrap: bool) -> None:
    extract_archive(archive, target, unwrap=unwrap)
    finalize_install(target)
