"""Unpack zip, tar.gz/tar.xz, and dmg archives into a target directory."""

from __future__ import annotations

import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from app.core.process import run_command

_DMG_SKIP = {".DS_Store", "Applications", ".background", ".VolumeIcon.icns"}


def extract_archive(archive: Path, target: Path, *, unwrap: bool = True) -> None:
    """Unpack one archive into target.

    zip, tar/tgz/tar.gz/tar.xz, and dmg are supported. A single top-level
    folder is flattened unless it is a .app bundle or unwrap is False.
    """
    suffixes = "".join(archive.suffixes).lower()
    with tempfile.TemporaryDirectory(prefix="extract-") as tmp:
        staging = Path(tmp)
        if suffixes.endswith(".zip"):
            _extract_zip(archive, staging)
        elif suffixes.endswith(".dmg"):
            _extract_dmg(archive, staging)
        elif ".tar" in suffixes or suffixes.endswith(".tgz"):
            _extract_tar(archive, staging)
        else:
            raise ValueError(f"Unknown archive type: {archive.name}")
        if unwrap:
            _unwrap_single_root(staging)
        target.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            dest = target / item.name
            if dest.exists():
                if dest.is_dir() and not dest.is_symlink():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))


def _unwrap_single_root(staging: Path) -> None:
    macosx = staging / "__MACOSX"
    if macosx.is_dir():
        shutil.rmtree(macosx)
    children = [path for path in staging.iterdir() if not path.name.startswith(".")]
    if len(children) != 1 or not children[0].is_dir():
        return
    inner = children[0]
    if inner.suffix == ".app":
        return
    for item in inner.iterdir():
        shutil.move(str(item), str(staging / item.name))
    inner.rmdir()


def _assert_inside(dest: Path, member_name: str) -> None:
    dest = dest.resolve()
    target = (dest / member_name).resolve()
    if not target.is_relative_to(dest):
        raise ValueError(f"Unsafe archive path: {member_name!r}")


def _extract_zip(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            _assert_inside(dest, info.filename)
        zf.extractall(dest)


def _extract_tar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive) as tf:
        tf.extractall(dest, filter="data")


def _extract_dmg(archive: Path, dest: Path) -> None:
    mount = Path(tempfile.mkdtemp(prefix="dmg-"))
    try:
        run_command(
            [
                "hdiutil",
                "attach",
                "-nobrowse",
                "-readonly",
                "-mountpoint",
                str(mount),
                str(archive),
            ]
        )
        apps = [path for path in mount.iterdir() if path.suffix == ".app" and path.is_dir()]
        if apps:
            for app in apps:
                shutil.copytree(app, dest / app.name, symlinks=True)
            return
        for item in mount.iterdir():
            if item.name in _DMG_SKIP or item.name.startswith("."):
                continue
            target = dest / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True, symlinks=True)
            else:
                shutil.copy2(item, target)
    finally:
        run_command(["hdiutil", "detach", str(mount)], check=False)
        shutil.rmtree(mount, ignore_errors=True)
