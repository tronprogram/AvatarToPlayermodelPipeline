"""Load the Setup install catalog.

The copy shipped with the app is the default. The file Setup actually reads
is ``data/catalog.json``, which the user can edit. A missing user file is
filled from the default. Download URLs are templates; version fields are
substituted when the links are requested.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from app.core.paths import data_dir, resource_root


class InstallDirectory(NamedTuple):
    """Executable name, path under ``data/``, and whether that exe must exist."""

    executable: str
    path: str
    check_executable: bool


@dataclass(frozen=True)
class Catalog:
    """One reading of the install catalog."""

    directories: dict[str, InstallDirectory]
    archive_installs: dict[str, str]
    manual_installs: tuple[str, ...]
    source_tools_addon_names: tuple[str, ...]
    source_tools_url: str
    port_template_url: str
    port_template_hint: str
    blender_cdn: str
    blender_lts: str
    blender_intel_mac_lts: str
    hlmvpp_build: str
    hlmvpp_url: str
    hlmvpp_hint: str
    gmod_app_id: str
    gmod_steam_uri: str
    gmod_tool_names: tuple[str, ...]
    disk_budget_gib: dict[str, float]
    link_templates: dict


_override: Path | None = None
_cache: tuple[Path, int, Catalog] | None = None


def bundled_catalog_path() -> Path:
    """Default catalog packed with the program."""
    return resource_root() / "app" / "services" / "deps" / "catalog.json"


def user_catalog_path() -> Path:
    """Catalog the user can edit. Lives next to the other writable data."""
    return data_dir() / "catalog.json"


def ensure_user_catalog() -> Path:
    """Copy the bundled default into ``data/catalog.json`` when the user has none."""
    dest = user_catalog_path()
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            bundled_catalog_path().read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    return dest


def set_catalog_path(path: Path | None) -> None:
    """Read ``path`` instead of the user file. ``None`` restores the user file."""
    global _override, _cache
    _override = path
    _cache = None


def _series(version: str) -> str:
    """``5.2.2`` → ``5.2``. Blender's CDN folder is the minor series."""
    major, minor, *_rest = version.split(".")
    return f"{major}.{minor}"


def _build(raw: dict) -> Catalog:
    gmod_app_id = str(raw["gmod_app_id"])
    return Catalog(
        directories={
            key: InstallDirectory(
                executable=row["executable"],
                path=row["path"],
                check_executable=row["check_executable"],
            )
            for key, row in raw["directories"].items()
        },
        archive_installs=dict(raw["archive_installs"]),
        manual_installs=tuple(raw["manual_installs"]),
        source_tools_addon_names=tuple(raw["source_tools_addon_names"]),
        source_tools_url=raw["source_tools_url"],
        port_template_url=raw["port_template_url"],
        port_template_hint=raw["port_template_hint"],
        blender_cdn=raw["blender_cdn"],
        blender_lts=str(raw["blender_lts"]),
        blender_intel_mac_lts=str(raw["blender_intel_mac_lts"]),
        hlmvpp_build=str(raw["hlmvpp_build"]),
        hlmvpp_url=raw["hlmvpp_url"],
        hlmvpp_hint=raw["hlmvpp_hint"],
        gmod_app_id=gmod_app_id,
        gmod_steam_uri=f"steam://install/{gmod_app_id}",
        gmod_tool_names=tuple(raw["gmod_tool_names"]),
        disk_budget_gib={
            key: float(value) for key, value in raw["disk_budget_gib"].items()
        },
        link_templates=raw["dependency_links"],
    )


def _read(path: Path) -> Catalog:
    return _build(json.loads(path.read_text(encoding="utf-8")))


def load_catalog() -> Catalog:
    """Return the user catalog, or the bundled default if that file is unreadable."""
    path = _override if _override is not None else ensure_user_catalog()
    mtime = path.stat().st_mtime_ns
    global _cache
    if _cache is not None and _cache[0] == path and _cache[1] == mtime:
        return _cache[2]
    try:
        catalog = _read(path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        if path == bundled_catalog_path():
            raise
        catalog = _read(bundled_catalog_path())
    _cache = (path, mtime, catalog)
    return catalog


def _names(catalog: Catalog) -> dict[str, str]:
    return {
        "blender_cdn": catalog.blender_cdn,
        "blender_lts": catalog.blender_lts,
        "blender_series": _series(catalog.blender_lts),
        "blender_intel_mac_lts": catalog.blender_intel_mac_lts,
        "blender_intel_mac_series": _series(catalog.blender_intel_mac_lts),
        "hlmvpp_build": catalog.hlmvpp_build,
        "hlmvpp_url": catalog.hlmvpp_url,
        "source_tools_url": catalog.source_tools_url,
        "port_template_url": catalog.port_template_url,
    }


def _expand(value: str, names: dict[str, str]) -> str:
    current = value
    for _ in range(4):
        filled = current.format_map(names)
        if filled == current:
            return current
        current = filled
    return current


def dependency_links(system_type: str, system_arch: str) -> dict[str, str]:
    catalog = load_catalog()
    links = catalog.link_templates
    names = _names(catalog)
    match system_type:
        case "windows" | "linux":
            chosen = links[system_type]
        case "darwin":
            chosen = links["darwin"][system_arch]
        case _:
            raise ValueError(f"Unknown system type {system_type}!")
    return {key: _expand(url, names) for key, url in chosen.items()}
