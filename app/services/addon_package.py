"""Assemble a legacy GMod addon folder (addon.json + lua + models + materials)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.services.playerlua import PlayerLuaService, PlayermodelLua

ADDON_TYPES = frozenset(
    {
        "gamemode",
        "map",
        "weapon",
        "vehicle",
        "npc",
        "entity",
        "tool",
        "effects",
        "model",
        "servercontent",
    }
)
ADDON_TAGS = frozenset(
    {
        "fun",
        "roleplay",
        "scenic",
        "movie",
        "real",
        "cartoon",
        "water",
        "comic",
        "build",
    }
)


@dataclass(frozen=True, slots=True)
class AddonMetadata:
    """Fields written to ``addon.json`` (gmad + human-readable extras).

    ``addon_type`` must be a gmad type (default ``model``). ``tags`` is at
    most two values from ``ADDON_TAGS``. Empty ``author`` / ``description`` /
    ``ignore`` are still emitted so the JSON shape is stable.
    """

    title: str
    author: str = ""
    description: str = ""
    addon_type: str = "model"
    tags: tuple[str, ...] = ("fun", "roleplay")
    ignore: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AddonSpec:
    """Files and names for one addon directory.

    ``model_path`` / ``hands_path`` are Lua paths starting at ``models/``.
    ``cdmaterials`` is the folder under ``materials/`` (same as QC).
    ``mdl`` / ``hands_mdl`` are compiled files on disk; siblings are copied.
    ``materials`` is the folder of VTF/VMT files to copy under ``cdmaterials``.
    """

    metadata: AddonMetadata
    display_name: str
    model_path: str
    mdl: Path
    materials: Path
    cdmaterials: str
    hands_path: str | None = None
    hands_mdl: Path | None = None


@dataclass(frozen=True, slots=True)
class GmodAddon:
    """Written addon tree ready to drop into ``garrysmod/addons``.

    ``mdl`` / ``hands`` are the copied files under ``root/models/``.
    ``materials`` is ``root/materials/<cdmaterials>``.
    """

    root: Path
    addon_json: Path
    lua: Path
    mdl: Path
    materials: Path
    hands: Path | None


class AddonPackageService:
    """Write one addon folder into ``directory``."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, spec: AddonSpec) -> GmodAddon:
        """Write ``addon.json``, Lua, both MDL families, and materials.

        Returns ``GmodAddon`` whose ``root`` is this service's ``directory``.
        ``hands`` is ``None`` when ``spec.hands_path`` is omitted.
        """
        meta = _validated_metadata(spec.metadata)
        if not spec.mdl.is_file():
            raise FileNotFoundError(f"No compiled MDL at {spec.mdl}")
        if not spec.materials.is_dir():
            raise FileNotFoundError(f"No materials directory at {spec.materials}")
        if spec.hands_path and spec.hands_mdl is None:
            raise ValueError("hands_path requires hands_mdl")
        if spec.hands_mdl is not None and not spec.hands_mdl.is_file():
            raise FileNotFoundError(f"No compiled C-arms MDL at {spec.hands_mdl}")

        self.directory.mkdir(parents=True, exist_ok=True)
        addon_json = self.directory / "addon.json"
        addon_json.write_text(
            json.dumps(_addon_json_payload(meta), indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        lua = PlayerLuaService(self.directory / "lua" / "autorun").write(
            PlayermodelLua(
                display_name=spec.display_name,
                model_path=spec.model_path,
                hands_path=spec.hands_path,
            )
        )

        dest_mdl = self.directory / Path(*_slash(spec.model_path).split("/"))
        dest_mdl.parent.mkdir(parents=True, exist_ok=True)
        _copy_mdl_family(spec.mdl, dest_mdl)

        dest_hands: Path | None = None
        if spec.hands_path and spec.hands_mdl is not None:
            dest_hands = self.directory / Path(*_slash(spec.hands_path).split("/"))
            dest_hands.parent.mkdir(parents=True, exist_ok=True)
            _copy_mdl_family(spec.hands_mdl, dest_hands)

        dest_materials = self.directory / "materials" / Path(*_slash(spec.cdmaterials).split("/"))
        dest_materials.mkdir(parents=True, exist_ok=True)
        for src in spec.materials.iterdir():
            if src.is_file():
                shutil.copy2(src, dest_materials / src.name)

        return GmodAddon(
            root=self.directory,
            addon_json=addon_json,
            lua=lua,
            mdl=dest_mdl,
            materials=dest_materials,
            hands=dest_hands,
        )


def _validated_metadata(meta: AddonMetadata) -> AddonMetadata:
    if not meta.title.strip():
        raise ValueError("title is required")
    addon_type = meta.addon_type.strip().lower()
    if addon_type not in ADDON_TYPES:
        raise ValueError(f"addon_type must be one of {sorted(ADDON_TYPES)}")
    if len(meta.tags) > 2:
        raise ValueError("gmad allows at most two tags")
    tags = tuple(tag.strip().lower() for tag in meta.tags)
    unknown = [tag for tag in tags if tag not in ADDON_TAGS]
    if unknown:
        raise ValueError(f"unknown addon tags: {unknown}")
    return AddonMetadata(
        title=meta.title.strip(),
        author=meta.author.strip(),
        description=meta.description.strip(),
        addon_type=addon_type,
        tags=tags,
        ignore=tuple(item.strip() for item in meta.ignore if item.strip()),
    )


def _addon_json_payload(meta: AddonMetadata) -> dict[str, object]:
    return {
        "title": meta.title,
        "type": meta.addon_type,
        "tags": list(meta.tags),
        "author": meta.author,
        "description": meta.description,
        "ignore": list(meta.ignore),
    }


def _copy_mdl_family(src_mdl: Path, dest_mdl: Path) -> None:
    stem = src_mdl.stem
    for src in src_mdl.parent.iterdir():
        if src.is_file() and src.name.startswith(stem + "."):
            shutil.copy2(src, dest_mdl.parent / src.name)


def _slash(value: str) -> str:
    return value.replace("\\", "/")
