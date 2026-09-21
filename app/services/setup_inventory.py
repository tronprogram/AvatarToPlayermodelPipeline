"""User-facing tool inventory for Setup and Convert checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.paths import data_dir
from app.services.deps.catalog import load_catalog
from app.services.deps.detect import (
    blender_root,
    find_blender_bin,
    find_hlmvplusplus,
    find_modified_compiler,
    find_source_tools,
    gmod_tools_present,
    gmod_tools_root,
)
from app.services.deps.steamcmd import find_steamcmd
from app.services.user_settings import load_settings, path_or_none


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

    compiler = find_modified_compiler(data, path_or_none(settings.compiler))
    hlmvpp = find_hlmvplusplus(data, path_or_none(settings.hlmvplusplus))

    catalog = load_catalog()
    return (
        ToolRow(
            "blender",
            f"Blender {catalog.blender_lts} LTS Portable",
            blender is not None,
            _text(blender),
            True,
        ),
        ToolRow(
            "sourcetools",
            "Blender Source Tools",
            source is not None,
            _text(source),
            True,
            hint=catalog.source_tools_url,
        ),
        ToolRow(
            "compiler",
            "Modified Source compiler",
            compiler is not None,
            _text(compiler),
            True,
            hint=catalog.port_template_hint,
        ),
        ToolRow(
            "hlmvplusplus",
            "HLMV++",
            hlmvpp is not None,
            _text(hlmvpp),
            False,
            hint=catalog.hlmvpp_hint,
        ),
        ToolRow("steamcmd", "SteamCMD", steam is not None, _text(steam), True),
        ToolRow(
            "gmod_tools",
            "Garry's Mod dedicated",
            gmod_ok,
            _text(gmod_root) if gmod_ok else None,
            True,
            steam_uri=catalog.gmod_steam_uri,
        ),
    )


def required_ready(rows: tuple[ToolRow, ...] | None = None) -> bool:
    rows = rows or tool_rows()
    return all(row.present for row in rows if row.required)


def blender_without_source_tools(rows: tuple[ToolRow, ...] | None = None) -> bool:
    rows = rows or tool_rows()
    by_id = {row.id: row for row in rows}
    return by_id["blender"].present and not by_id["sourcetools"].present


DEFAULT_SELECTED = (
    "blender",
    "sourcetools",
    "compiler",
    "hlmvplusplus",
    "steamcmd",
    "gmod_tools",
)

def setup_tree() -> tuple[tuple[str, str, str | None], ...]:
    blender = load_catalog().blender_lts
    return (
        ("blender", f"Blender {blender} LTS Portable (required for headless exports)", None),
        ("sourcetools", "Blender Source Tools (required for DMX manipulation)", "blender"),
        ("compiler", "Modified Source compiler (required to compile models)", None),
        ("hlmvplusplus", "HLMV++ (preview the compiled playermodel after Convert)", None),
        ("steamcmd", "SteamCMD (required to download GMod tools)", None),
        (
            "gmod_tools",
            "Garry's Mod Dedicated Server (required for playermodel generation)",
            "steamcmd",
        ),
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


def gmod_tools_needs_step(
    selected: set[str], rows: tuple[ToolRow, ...] | None = None
) -> bool:
    if "gmod_tools" not in selected:
        return False
    rows = rows or tool_rows()
    by_id = {row.id: row for row in rows}
    return not by_id["gmod_tools"].present


def selected_missing(
    selected: set[str], rows: tuple[ToolRow, ...] | None = None
) -> list[ToolRow]:
    rows = rows or tool_rows()
    return [row for row in rows if row.id in selected and not row.present]


def selected_ready(selected: set[str], rows: tuple[ToolRow, ...] | None = None) -> bool:
    return not selected_missing(selected, rows)


def disk_budget_for(selected: set[str]) -> float:
    budget = load_catalog().disk_budget_gib
    return round(sum(budget[key] for key in selected if key in budget), 1)
