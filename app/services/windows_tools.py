"""Launch Windows Source/Crowbar .exe files on this OS.

Windows: run the binary natively with OS paths.
macOS: Whisky ``wine64``, then PATH wine; prefix from ``WINEPREFIX``, a
Whisky bottle, ``data/wineprefix``, or ``~/.wine``.
Linux: PATH ``wine64``/``wine`` only (never Whisky); prefix from
``WINEPREFIX``, ``data/wineprefix``, or ``~/.wine``.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.paths import data_dir
from app.core.process import PYTHON_ENV_KEYS, command_env

HostKind = Literal["native", "wine"]

_WHISKY_SUPPORT = (
    Path.home() / "Library" / "Application Support" / "com.isaacmarovitz.Whisky"
)
_WHISKY_BOTTLE_ROOTS = (
    Path.home() / "Library" / "Containers" / "com.isaacmarovitz.Whisky" / "Bottles",
    _WHISKY_SUPPORT / "Bottles",
)


@dataclass(frozen=True, slots=True)
class WineSession:
    """Wine binary + prefix. Only set on macOS/Linux hosts."""

    wine: Path
    prefix: Path


@dataclass(frozen=True, slots=True)
class WindowsToolHost:
    """How a Windows .exe should be invoked on this machine."""

    kind: HostKind
    wine: Path | None = None
    prefix: Path | None = None

    @property
    def uses_wine(self) -> bool:
        return self.kind == "wine"

    def tool_path(self, path: Path) -> str:
        """Path as the Windows process will see it."""
        resolved = path.resolve()
        if self.kind == "native":
            return str(resolved)
        return wine_z_path(resolved)

    def gameinfo_path(self, path: Path) -> str:
        """Quoted path for Source ``gameinfo.txt`` SearchPaths."""
        return '"' + self.tool_path(path).replace("\\", "/") + '"'

    def argv(self, exe: Path, *args: Path | str) -> list[str]:
        """``[exe, …]`` on Windows, ``[wine, exe, …]`` on Unix."""
        converted = [
            self.tool_path(arg) if isinstance(arg, Path) else arg for arg in args
        ]
        if self.kind == "native":
            return [str(exe), *converted]
        if self.wine is None:
            raise FileNotFoundError("Wine is required to run Windows tools on this OS.")
        return [str(self.wine), str(exe), *converted]

    def env(self) -> dict[str, str]:
        if self.kind == "wine" and self.wine is not None and self.prefix is not None:
            extra = {
                "WINEPREFIX": str(self.prefix),
                "WINEARCH": "win64",
                "WINEDEBUG": "-all",
                "PATH": f"{self.wine.parent}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            return command_env(extra=extra, drop=PYTHON_ENV_KEYS)
        return command_env(drop=(*PYTHON_ENV_KEYS, "WINEPREFIX", "WINEARCH", "WINEDEBUG"))

    def as_wine_session(self) -> WineSession:
        if self.kind != "wine" or self.wine is None or self.prefix is None:
            raise FileNotFoundError("Wine is only used on macOS and Linux.")
        return WineSession(self.wine, self.prefix)


def wine_z_path(path: Path) -> str:
    """Wine default Z: drive maps to the Unix root."""
    return "Z:" + str(path.resolve()).replace("/", "\\")


# Crowbar tests and older callers still import this name.
windows_path = wine_z_path


def windows_gameinfo_path(path: Path) -> str:
    """Quoted Wine Z: path with forward slashes for ``gameinfo.txt``."""
    return '"' + wine_z_path(path).replace("\\", "/") + '"'


def is_windows() -> bool:
    return sys.platform == "win32"


def try_detect_windows_tool_host() -> WindowsToolHost | None:
    """Return a host when this machine can run Windows Source tools."""
    if is_windows():
        return WindowsToolHost(kind="native")
    wine = find_wine()
    prefix = find_wine_prefix()
    if wine is None or prefix is None:
        return None
    return WindowsToolHost(kind="wine", wine=wine, prefix=prefix)


def detect_windows_tool_host() -> WindowsToolHost:
    """Native on Windows; Wine + prefix on macOS/Linux. Raises if missing."""
    host = try_detect_windows_tool_host()
    if host is None:
        raise FileNotFoundError(_missing_host_message())
    return host


def find_wine() -> Path | None:
    """Wine launcher, or None on Windows / when Wine is missing."""
    if is_windows():
        return None
    if sys.platform == "darwin":
        whisky = whisky_wine()
        if whisky is not None:
            return whisky
    return path_wine()


def find_wine_prefix() -> Path | None:
    """Writable Wine prefix for this OS, or None on Windows / when missing."""
    if is_windows():
        return None
    env_prefix = os.environ.get("WINEPREFIX")
    if env_prefix:
        prefix = Path(env_prefix).expanduser()
        if (prefix / "drive_c").is_dir():
            return prefix
    if sys.platform == "darwin":
        bottle = whisky_bottle()
        if bottle is not None:
            return bottle
    bundled = data_dir() / "wineprefix"
    if _looks_like_prefix(bundled):
        return bundled
    home = Path.home() / ".wine"
    if _looks_like_prefix(home):
        return home
    return None


def path_wine() -> Path | None:
    for name in ("wine64", "wine"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def whisky_wine() -> Path | None:
    """Whisky ships Wine.app; only relevant on macOS."""
    for candidate in (
        _WHISKY_SUPPORT / "Libraries" / "Wine" / "bin" / "wine64",
        _WHISKY_SUPPORT / "Libraries" / "Wine" / "bin" / "wine",
    ):
        if _is_executable(candidate):
            return candidate
    return None


def whisky_bottle() -> Path | None:
    """First Whisky bottle with ``drive_c``, preferring one that already has Crowbar settings."""
    bottles: list[Path] = []
    for root in _WHISKY_BOTTLE_ROOTS:
        if not root.is_dir():
            continue
        bottles.extend(
            sorted(path for path in root.iterdir() if _looks_like_prefix(path))
        )
    if not bottles:
        return None
    for bottle in bottles:
        users = bottle / "drive_c" / "users"
        if users.is_dir() and any(
            users.glob("*/AppData/Roaming/ZeqMacaw/Crowbar 0.74")
        ):
            return bottle
    return bottles[0]


def crowbar_settings_file(host: WindowsToolHost) -> Path:
    """Crowbar 0.74 settings.xml for this host."""
    if host.kind == "native":
        appdata = os.environ.get("APPDATA")
        root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return root / "ZeqMacaw" / "Crowbar 0.74" / "Crowbar Settings.xml"
    return wine_crowbar_settings_hint(host.as_wine_session().prefix)


def wine_crowbar_settings_hint(prefix: Path) -> Path:
    """Fallback Crowbar settings path when no user folder exists yet."""
    return (
        prefix
        / "drive_c"
        / "users"
        / "crossover"
        / "AppData"
        / "Roaming"
        / "ZeqMacaw"
        / "Crowbar 0.74"
        / "Crowbar Settings.xml"
    )


def _looks_like_prefix(path: Path) -> bool:
    return (path / "drive_c").is_dir()


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _missing_host_message() -> str:
    if sys.platform == "darwin":
        return (
            "Wine is not available. Install Whisky or put wine64 on PATH, "
            "and set WINEPREFIX or use a Whisky bottle."
        )
    if sys.platform.startswith("linux"):
        return (
            "Wine is not available. Install wine or wine64 and set WINEPREFIX "
            "(or use ~/.wine / data/wineprefix)."
        )
    return "Windows Source tools cannot be launched on this platform."
