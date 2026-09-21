"""Discover and validate Wine prefixes (Whisky, CrossOver, Bottles, Wine).

Windows never needs this. Darwin/Linux always do: compilers are Windows
``.exe`` files. The user should see a bottle name, not a UUID path.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

from app.core.paths import data_dir
from app.services.user_settings import load_settings, path_or_none, save_settings
from app.services.windows_tools import (
    _WHISKY_BOTTLE_ROOTS,
    _looks_like_prefix,
    find_wine,
    is_windows,
    whisky_wine,
)

WineKind = Literal["whisky", "crossover", "bottles", "wine"]

_CROSSOVER_BOTTLES = (
    Path.home() / "Library" / "Application Support" / "CrossOver" / "Bottles"
)
_BOTTLES_ROOTS = (
    Path.home() / ".local" / "share" / "bottles" / "bottles",
    Path.home()
    / ".var"
    / "app"
    / "com.usebottles.bottles"
    / "data"
    / "bottles"
    / "bottles",
)
_CROSSOVER_WINE = (
    Path("/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wineloader"),
    Path("/opt/cxoffice/bin/wineloader"),
)


@dataclass(frozen=True, slots=True)
class WineCandidate:
    """One usable prefix + the Wine that should launch it."""

    kind: WineKind
    name: str
    version: str
    prefix: Path
    wine: Path | None

    @property
    def location(self) -> str:
        return str(self.prefix)

    @property
    def label(self) -> str:
        """One-line description: ``Whisky 7.7, Bottle test - /path``."""
        kind = {
            "whisky": "Whisky",
            "crossover": "CrossOver",
            "bottles": "Bottles",
            "wine": "Wine",
        }[self.kind]
        head = f"{kind} {self.version}".strip() if self.version else kind
        if self.kind == "wine":
            return f"{head} - {self.location}"
        if self.name:
            return f"{head}, Bottle {self.name} - {self.location}"
        return f"{head} - {self.location}"


def host_id() -> str:
    """``darwin-arm64``, ``linux-x86_64``, …"""
    system = platform.system().lower()
    arch = platform.machine().lower()
    if arch in {"amd64", "x86_64"}:
        arch = "x86_64"
    elif arch in {"aarch64", "arm64"}:
        arch = "arm64"
    return f"{system}-{arch}"


def wine_is_required() -> bool:
    """Windows tools need Wine off native Windows."""
    return not is_windows()


def list_candidates() -> tuple[WineCandidate, ...]:
    """Prefixes we can name, with ``drive_c`` and a Wine binary."""
    if is_windows():
        return ()
    wine = find_wine()
    found: list[WineCandidate] = []
    seen: set[Path] = set()

    def add(
        kind: WineKind,
        prefix: Path,
        launcher: Path | None,
        *,
        name: str = "",
        version: str = "",
    ) -> None:
        resolved = prefix.expanduser().resolve()
        if resolved in seen or not _looks_like_prefix(resolved):
            return
        if launcher is None:
            return
        seen.add(resolved)
        found.append(
            WineCandidate(
                kind=kind,
                name=name,
                version=version or _launcher_version(launcher),
                prefix=resolved,
                wine=launcher,
            )
        )

    whisky = whisky_wine()
    if sys_darwin():
        for root in _WHISKY_BOTTLE_ROOTS:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                name, version = _whisky_identity(child)
                add("whisky", child, whisky, name=name, version=version)
        cx_wine = _crossover_wine()
        if _CROSSOVER_BOTTLES.is_dir():
            for child in sorted(_CROSSOVER_BOTTLES.iterdir()):
                add(
                    "crossover",
                    child,
                    cx_wine or wine,
                    name=_crossover_name(child) or child.name,
                    version=_crossover_version(cx_wine or wine),
                )

    if not sys_darwin():
        for root in _BOTTLES_ROOTS:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                add(
                    "bottles",
                    child,
                    wine,
                    name=_bottles_name(child) or child.name,
                    version=_bottles_version(child) or _launcher_version(wine),
                )

    env = os.environ.get("WINEPREFIX")
    if env:
        add("wine", Path(env), wine)
    add("wine", Path.home() / ".wine", wine)
    add("wine", data_dir() / "wineprefix", wine)

    override = path_or_none(load_settings().wine_prefix)
    if override is not None:
        add("wine", override, wine)

    return tuple(found)


def chosen_candidate() -> WineCandidate | None:
    """The bottle Convert will use, or None if the assistant must ask."""
    if not wine_is_required():
        return None
    candidates = list_candidates()
    override = path_or_none(load_settings().wine_prefix)
    if override is not None:
        resolved = override.expanduser().resolve()
        for item in candidates:
            if item.prefix == resolved:
                return item
        if _looks_like_prefix(resolved) and find_wine() is not None:
            return WineCandidate(
                kind="wine",
                name="",
                version=_launcher_version(find_wine()),
                prefix=resolved,
                wine=find_wine(),
            )
        return None
    if len(candidates) == 1:
        return candidates[0]
    return None


def wine_ready() -> bool:
    if not wine_is_required():
        return True
    return chosen_candidate() is not None


def select_prefix(path: Path) -> str | None:
    """Persist a prefix. Returns an error string, or None on success."""
    resolved = path.expanduser()
    if not _looks_like_prefix(resolved):
        return "That folder is not a Wine prefix (it has no drive_c)."
    if find_wine() is None and whisky_wine() is None and _crossover_wine() is None:
        return "Wine is not installed. Install Whisky, CrossOver, Bottles, or Wine."
    settings = load_settings()
    settings.wine_prefix = str(resolved.resolve())
    save_settings(settings)
    return None


def sys_darwin() -> bool:
    return sys.platform == "darwin"


def _crossover_wine() -> Path | None:
    for candidate in _CROSSOVER_WINE:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _whisky_identity(prefix: Path) -> tuple[str, str]:
    meta = prefix / "Metadata.plist"
    name = prefix.name
    version = ""
    if not meta.is_file():
        return name, version
    data = _load_plist(meta)
    if data is None:
        return name, version
    info = data.get("info")
    if isinstance(info, dict):
        raw = info.get("name")
        if isinstance(raw, str) and raw.strip():
            name = raw.strip()
    wine_cfg = data.get("wineConfig")
    if isinstance(wine_cfg, dict):
        ver = wine_cfg.get("wineVersion")
        if isinstance(ver, dict):
            parts = [ver.get("major"), ver.get("minor"), ver.get("patch")]
            nums = [str(part) for part in parts if part not in (None, "")]
            if len(nums) == 3 and nums[2] == "0":
                nums = nums[:2]
            version = ".".join(nums)
    return name, version


def _whisky_name(prefix: Path) -> str | None:
    name, _version = _whisky_identity(prefix)
    return name or None


def _crossover_name(prefix: Path) -> str | None:
    conf = prefix / "cxbottle.conf"
    if not conf.is_file():
        conf = prefix / "CXBottle.conf"
    if not conf.is_file():
        return None
    try:
        text = conf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.lower().startswith("name"):
            _, _, value = line.partition("=")
            name = value.strip().strip('"')
            if name:
                return name
    return None


def _bottles_name(prefix: Path) -> str | None:
    yml = prefix / "bottle.yml"
    if not yml.is_file():
        return None
    try:
        text = yml.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.lower().startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"').strip("'")
            if name:
                return name
    return None


@cache
def _launcher_version(launcher: Path | None) -> str:
    if launcher is None or not launcher.is_file():
        return ""
    try:
        result = subprocess.run(
            [str(launcher), "--version"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = (result.stdout or result.stderr or "").strip().splitlines()
    if not text:
        return ""
    return text[0].replace("wine-", "").strip()


def _crossover_version(launcher: Path | None) -> str:
    info = Path("/Applications/CrossOver.app/Contents/Info.plist")
    if info.is_file():
        data = _load_plist(info)
        if data is not None:
            short = data.get("CFBundleShortVersionString")
            if isinstance(short, str) and short.strip():
                return short.strip()
    return _launcher_version(launcher)


def _load_plist(path: Path) -> dict | None:
    """Read a .plist. ``plistlib`` is CPython stdlib, not a macOS binding."""
    try:
        import plistlib
    except ImportError:
        return None
    try:
        data = plistlib.loads(path.read_bytes())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _bottles_version(prefix: Path) -> str:
    yml = prefix / "bottle.yml"
    if not yml.is_file():
        return ""
    try:
        text = yml.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for key in ("Runner:", "runner:", "Version:", "version:"):
        for line in text.splitlines():
            if line.startswith(key):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    return ""
