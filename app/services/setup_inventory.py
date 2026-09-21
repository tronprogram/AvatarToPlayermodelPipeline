"""User-facing tool inventory for Setup and Convert checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.paths import data_dir
from app.services.deps.catalog import (
    CROWBAR_RELEASE,
    DISK_BUDGET_GIB,
    GMOD_STEAM_URI,
    SDK2013_STEAM_URI,
    SOURCE_TOOLS_URL,
)
from app.services.deps.detect import (
    blender_root,
    find_blender_bin,
    find_crowbar,
    find_sdk2013mp,
    find_source_tools,
    find_studiomdl,
    gmod_tools_present,
    gmod_tools_root,
)
from app.services.deps.steamcmd import find_steamcmd
from app.services.user_settings import load_settings, path_or_none, wine_is_required
from app.services.windows_tools import _looks_like_prefix


@dataclass(frozen=True, slots=True)
class ToolRow:
    id: str
    label: str
    present: bool
    path: str | None
    required: bool
    steam_uri: str | None = None
    hint: str = ""


def _text(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def _blender_tree(blender: Path | None, data: Path) -> Path:
    if blender is None:
        return blender_root(data)
    root = blender.parent
    if root.name == "MacOS":
        return root.parents[2]
    return root


def tool_rows() -> tuple[ToolRow, ...]:
    settings = load_settings()
    data = data_dir()

    blender = find_blender_bin(data)
    if settings.blender:
        extra = path_or_none(settings.blender)
        if extra is not None and extra.exists():
            blender = extra if extra.is_file() else find_blender_bin(extra) or extra

    source = find_source_tools(_blender_tree(blender, data))
    if settings.sourcetools:
        extra = path_or_none(settings.sourcetools)
        if extra is not None and extra.exists():
            source = extra

    steam = find_steamcmd(data / "steamcmd")
    if settings.steamcmd:
        extra = path_or_none(settings.steamcmd)
        if extra is not None and extra.exists():
            steam = extra

    gmod_root = gmod_tools_root(data)
    if settings.gmod_tools:
        extra = path_or_none(settings.gmod_tools)
        if extra is not None:
            gmod_root = extra
    gmod_ok = gmod_tools_present(gmod_root)

    sdk = find_sdk2013mp(data, path_or_none(settings.sdk2013))
    studiomdl = find_studiomdl(data, path_or_none(settings.sdk2013))
    crowbar = find_crowbar(data, path_or_none(settings.crowbar))

    return (
        ToolRow("blender", "Blender 5.2 LTS Portable", blender is not None, _text(blender), True),
        ToolRow(
            "sourcetools",
            "Blender Source Tools",
            source is not None,
            _text(source),
            True,
            hint=SOURCE_TOOLS_URL,
        ),
        ToolRow("steamcmd", "SteamCMD", steam is not None, _text(steam), True),
        ToolRow(
            "gmod_tools",
            "Garry's Mod dedicated",
            gmod_ok,
            _text(gmod_root) if gmod_ok else None,
            True,
            steam_uri=GMOD_STEAM_URI,
        ),
        ToolRow(
            "sdk2013",
            "Source SDK 2013 Multiplayer",
            sdk is not None and studiomdl is not None,
            _text(sdk),
            True,
            steam_uri=SDK2013_STEAM_URI,
        ),
        ToolRow(
            "crowbar",
            "Crowbar Editor",
            crowbar is not None,
            _text(crowbar),
            False,
            hint=CROWBAR_RELEASE,
        ),
    )


def required_ready(rows: tuple[ToolRow, ...] | None = None) -> bool:
    rows = rows or tool_rows()
    return all(row.present for row in rows if row.required)


def blender_without_source_tools(rows: tuple[ToolRow, ...] | None = None) -> bool:
    rows = rows or tool_rows()
    by_id = {row.id: row for row in rows}
    return by_id["blender"].present and not by_id["sourcetools"].present


DEFAULT_SELECTED = ("blender", "sourcetools", "steamcmd", "gmod_tools", "sdk2013")

SETUP_TREE = (
    ("blender", "Blender 5.2 LTS Portable (required for headless exports)", None),
    ("sourcetools", "Blender Source Tools (required for DMX manipulation)", "blender"),
    ("steamcmd", "SteamCMD (required to download GMod tools)", None),
    ("gmod_tools", "Garry's Mod Dedicated Server (required for playermodel generation)", "steamcmd"),
    ("sdk2013", "Source SDK 2013 Multiplayer (required for model compile)", "steamcmd"),
    ("crowbar", "Crowbar Editor (used for model visualization)", None),
)


def source_tools_needs_warning(
    selected: set[str], rows: tuple[ToolRow, ...] | None = None
) -> bool:
    """Warn when Source Tools is selected and missing, even if Blender is unset."""
    if "sourcetools" not in selected:
        return False
    rows = rows or tool_rows()
    by_id = {row.id: row for row in rows}
    return not by_id["sourcetools"].present


def sdk2013_needs_steam(
    selected: set[str], rows: tuple[ToolRow, ...] | None = None
) -> bool:
    if "sdk2013" not in selected:
        return False
    rows = rows or tool_rows()
    by_id = {row.id: row for row in rows}
    return not by_id["sdk2013"].present


def selected_missing(
    selected: set[str], rows: tuple[ToolRow, ...] | None = None
) -> list[ToolRow]:
    rows = rows or tool_rows()
    return [row for row in rows if row.id in selected and not row.present]


def selected_ready(selected: set[str], rows: tuple[ToolRow, ...] | None = None) -> bool:
    return not selected_missing(selected, rows)


def disk_budget_for(selected: set[str]) -> float:
    return round(sum(DISK_BUDGET_GIB[key] for key in selected if key in DISK_BUDGET_GIB), 1)


def disk_budget_gib() -> float:
    return round(sum(DISK_BUDGET_GIB.values()), 1)


def wine_ready() -> bool:
    settings = load_settings()
    if not wine_is_required(settings):
        return True
    prefix = path_or_none(settings.wine_prefix)
    return prefix is not None and _looks_like_prefix(prefix)
