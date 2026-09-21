"""Detect installed tools under the writable data directory."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from app.services.deps.catalog import load_catalog


def is_executable_file(path) -> bool:
    """True if the file looks runnable (unix +x or a Windows .exe)."""
    if not os.path.isfile(path):
        return False
    if path.lower().endswith(".exe"):
        return True
    return os.access(path, os.X_OK)


def named_executable_found(name: str, search_dir: Path) -> bool:
    if shutil.which(name) is not None:
        return True
    if not search_dir.exists():
        return False
    for candidate in (name, f"{name}.exe"):
        if is_executable_file(str(search_dir / candidate)):
            return True
    return False


def any_executable_in_dir(search_dir: Path) -> bool:
    if not search_dir.exists():
        return False
    for root, _dirs, files_in_dir in os.walk(search_dir):
        for fname in files_in_dir:
            if is_executable_file(os.path.join(root, fname)):
                return True
    return False


def gmod_app_installed(search_dir: Path) -> bool:
    """True when SteamCMD has a fully installed Garry's Mod dedicated server."""
    acf = search_dir / "steamapps" / f"appmanifest_{load_catalog().gmod_app_id}.acf"
    if not acf.is_file():
        return False
    text = acf.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'"StateFlags"\s+"(\d+)"', text)
    if not match:
        return False
    flags = int(match.group(1))
    fully_installed = 4
    busy = 32 | 128 | 256 | 1024  # missing, corrupt, update running/started
    return bool(flags & fully_installed) and not (flags & busy)


def gmod_named_tools_present(search_dir: Path) -> bool:
    if not search_dir.exists():
        return False
    found = {name: False for name in load_catalog().gmod_tool_names}
    for _root, _dirs, files in os.walk(search_dir):
        for fname in files:
            key = fname.lower()
            if key in found:
                found[key] = True
        if all(found.values()):
            return True
    return all(found.values())


def gmod_tools_present(search_dir: Path) -> bool:
    """True when 4020 is installed, or gmad.exe and studiomdl.exe were dropped in."""
    if gmod_app_installed(search_dir):
        return True
    return gmod_named_tools_present(search_dir)


def blender_root(data: Path) -> Path:
    return data / load_catalog().directories["blender"].path


def find_blender_bin(data: Path) -> Path | None:
    """Portable Blender first, then a blender on PATH."""
    root = blender_root(data)
    for candidate in (
        root / "Blender.app" / "Contents" / "MacOS" / "Blender",
        root / "blender.exe",
        root / "blender",
    ):
        if is_executable_file(str(candidate)):
            # macOS Blender must run from inside the .app; a helper symlink at
            # data/blender/blender cannot find bundled Python.
            return candidate.resolve()
    found = shutil.which("blender")
    return Path(found) if found else None


def gmod_tools_root(data: Path) -> Path:
    return data / load_catalog().directories["gmod_tools"].path


def blender_user_resources(root: Path) -> Path:
    """Folder passed as ``BLENDER_USER_RESOURCES``. Addons live in ``scripts/addons``."""
    return root / "user"


def source_tools_install_dir(data: Path) -> Path:
    """Directory Blender scans for legacy addons under this portable install."""
    dest = blender_user_resources(blender_root(data)) / "scripts" / "addons"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def find_source_tools(blender: Path) -> Path | None:
    """Return the Blender Source Tools addon folder if it is in the user scripts dir."""
    addons = blender_user_resources(blender) / "scripts" / "addons"
    if not addons.is_dir():
        return None
    for name in load_catalog().source_tools_addon_names:
        package = addons / name
        if package.is_dir() and (package / "__init__.py").is_file():
            return package
        script = addons / f"{name}.py"
        if script.is_file():
            return script
    return None


def blender_launch_env(data: Path) -> dict[str, str]:
    """Environment for a Blender child. User scripts stay inside ``data/blender``."""
    from app.core.process import PYTHON_ENV_KEYS, command_env

    user = blender_user_resources(blender_root(data))
    (user / "scripts" / "addons").mkdir(parents=True, exist_ok=True)
    return command_env({"BLENDER_USER_RESOURCES": str(user)}, drop=PYTHON_ENV_KEYS)


def archive_name_from_url(url: str) -> str | None:
    name = url.rsplit("/", 1)[-1]
    if name in {"download", "download.php"}:
        return None
    return name


def _archive_on_disk(dest: Path, *patterns: str) -> str | None:
    for pattern in patterns:
        matches = sorted(
            path for path in dest.glob(pattern) if path.is_file() and path.stat().st_size
        )
        if matches:
            return matches[0].name
    return None


def downloaded_archives(dest: Path, links: dict[str, str]) -> dict[str, str | None]:
    """Filenames already in dest for each fetch target (None if missing)."""
    found: dict[str, str | None] = {}
    for name, url in links.items():
        if name == "compiler":
            found[name] = _archive_on_disk(
                dest, "Gmod-Model-Port-Template*.zip", "main.zip"
            )
            continue
        if name == "hlmvplusplus":
            found[name] = _archive_on_disk(dest, "hammerplusplus_2013mp*.zip")
            continue
        expected = archive_name_from_url(url)
        if expected:
            path = dest / expected
            found[name] = expected if path.is_file() and path.stat().st_size else None
            continue
        found[name] = _archive_on_disk(dest, "blender_source_tools*.zip")
    return found


def install_path(data: Path, archive_key: str) -> Path:
    if archive_key == "sourcetools":
        return source_tools_install_dir(data)
    catalog = load_catalog()
    install_key = catalog.archive_installs[archive_key]
    return data / catalog.directories[install_key].path


def _studiomdl_in(root: Path) -> Path | None:
    for candidate in (
        root / "bin" / "studiomdl.exe",
        root / "bin" / "x64" / "studiomdl.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def steam_library_roots() -> list[Path]:
    """Common Steam library folders that may contain app 243750."""
    roots: list[Path] = []
    guessed = [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path.home() / ".steam" / "steam",
        Path.home() / ".local" / "share" / "Steam",
        Path.home() / "Library" / "Application Support" / "Steam",
    ]
    for root in guessed:
        common = root / "steamapps" / "common"
        if common.is_dir():
            roots.append(root)
    return roots


def modified_compiler_tree(root: Path) -> Path | None:
    """Folder that contains ``bin/studiomdl.exe`` (BobmacU 'Modified Complier')."""
    for name in ("Modified Complier", "Modified Compiler", "compiler"):
        candidate = root / name
        if (candidate / "bin" / "studiomdl.exe").is_file():
            return candidate
    if (root / "bin" / "studiomdl.exe").is_file():
        return root
    return None


def find_hlmvplusplus(data: Path, override: Path | None = None) -> Path | None:
    """ficool2 HLMV++ (no Steam SDK install)."""
    if override is not None:
        exe = (
            override
            if override.suffix.lower() == ".exe"
            else override / "hlmvplusplus.exe"
        )
        if exe.is_file():
            return exe
    for candidate in (
        data / "hlmvplusplus" / "hlmvplusplus.exe",
        data / "compiler" / "bin" / "hlmvplusplus.exe",
        data / "sdk2013mp" / "bin" / "hlmvplusplus.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def find_modified_compiler(data: Path, override: Path | None = None) -> Path | None:
    """BobmacU/SFM ``studiomdl.exe`` used for Convert compile."""
    if override is not None:
        exe = (
            override
            if override.suffix.lower() == ".exe"
            else override / "bin" / "studiomdl.exe"
        )
        if exe.is_file():
            return exe
        tree = modified_compiler_tree(override)
        if tree is not None:
            return tree / "bin" / "studiomdl.exe"
    dest = data / "compiler" / "bin" / "studiomdl.exe"
    if dest.is_file():
        return dest
    tree = modified_compiler_tree(data / "_gmod_port_template")
    if tree is not None:
        return tree / "bin" / "studiomdl.exe"
    return None


def find_sdk2013mp(data: Path, override: Path | None = None) -> Path | None:
    """Source SDK Base 2013 Multiplayer tree (HLMV only; not the compiler)."""
    candidates: list[Path] = []
    if override is not None:
        candidates.append(override)
    candidates.append(data / "sdk2013mp")
    for steam in steam_library_roots():
        candidates.append(
            steam / "steamapps" / "common" / "Source SDK Base 2013 Multiplayer"
        )
    seen: set[Path] = set()
    for root in candidates:
        resolved = root.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        if _studiomdl_in(resolved) is not None or (resolved / "hl2mp" / "gameinfo.txt").is_file():
            return resolved
    return None


def find_studiomdl(data: Path, override: Path | None = None) -> Path | None:
    root = find_sdk2013mp(data, override)
    if root is None:
        return None
    return _studiomdl_in(root)
