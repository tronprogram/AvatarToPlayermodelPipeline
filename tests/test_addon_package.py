"""GMod addon folder layout."""

import json
from pathlib import Path

import pytest

from app.services.addon_package import AddonMetadata, AddonPackageService, AddonSpec


def _compiled_tree(tmp_path: Path):
    compiled = tmp_path / "compiled"
    mdl_dir = compiled / "models" / "player" / "avatar"
    hands_dir = compiled / "models" / "weapons"
    mat_dir = compiled / "materials" / "models" / "player" / "avatar"
    mdl_dir.mkdir(parents=True)
    hands_dir.mkdir(parents=True)
    mat_dir.mkdir(parents=True)
    mdl = mdl_dir / "avatar.mdl"
    mdl.write_bytes(b"IDST")
    (mdl_dir / "avatar.dx90.vtx").write_bytes(b"VTX")
    (mdl_dir / "avatar.vvd").write_bytes(b"VVD")
    hands = hands_dir / "c_arms_avatar.mdl"
    hands.write_bytes(b"HAND")
    (hands_dir / "c_arms_avatar.vvd").write_bytes(b"HVVD")
    (mat_dir / "face.vmt").write_text('"VertexLitGeneric" {}\n', encoding="utf-8")
    (mat_dir / "face.vtf").write_bytes(b"VTF")
    return mdl, hands, mat_dir


def test_write_copies_models_materials_lua_and_metadata(tmp_path: Path):
    mdl, hands, mat_dir = _compiled_tree(tmp_path)
    dest = tmp_path / "addons" / "my_avatar"
    addon = AddonPackageService(dest).write(
        AddonSpec(
            metadata=AddonMetadata(
                title="My Avatar",
                author="pipeline",
                description="Converted avatar playermodel",
            ),
            display_name="My Avatar",
            model_path="models/player/avatar/avatar.mdl",
            mdl=mdl,
            materials=mat_dir,
            cdmaterials="models/player/avatar",
            hands_path="models/weapons/c_arms_avatar.mdl",
            hands_mdl=hands,
        )
    )

    payload = json.loads(addon.addon_json.read_text(encoding="utf-8"))
    assert payload == {
        "title": "My Avatar",
        "type": "model",
        "tags": ["fun", "roleplay"],
        "author": "pipeline",
        "description": "Converted avatar playermodel",
        "ignore": [],
    }
    assert addon.lua == dest / "lua" / "autorun" / "my_avatar.lua"
    lua = addon.lua.read_text(encoding="utf-8")
    assert "AddValidModel" in lua
    assert "PlayerOptionsModel" in lua
    assert (
        'player_manager.AddValidHands("My Avatar", "models/weapons/c_arms_avatar.mdl", 0, "00000000")'
        in lua
    )
    assert addon.mdl.read_bytes() == b"IDST"
    assert (dest / "models" / "player" / "avatar" / "avatar.dx90.vtx").read_bytes() == b"VTX"
    assert addon.hands is not None
    assert addon.hands.read_bytes() == b"HAND"
    assert (dest / "models" / "weapons" / "c_arms_avatar.vvd").read_bytes() == b"HVVD"
    assert (addon.materials / "face.vtf").read_bytes() == b"VTF"
    assert addon.materials == dest / "materials" / "models" / "player" / "avatar"


def test_rejects_more_than_two_tags(tmp_path: Path):
    mdl, _, mat_dir = _compiled_tree(tmp_path)
    with pytest.raises(ValueError, match="at most two tags"):
        AddonPackageService(tmp_path / "addon").write(
            AddonSpec(
                metadata=AddonMetadata(title="X", tags=("fun", "roleplay", "real")),
                display_name="X",
                model_path="models/player/x/x.mdl",
                mdl=mdl,
                materials=mat_dir,
                cdmaterials="models/player/x",
            )
        )


def test_rejects_unknown_addon_type(tmp_path: Path):
    mdl, _, mat_dir = _compiled_tree(tmp_path)
    with pytest.raises(ValueError, match="addon_type"):
        AddonPackageService(tmp_path / "addon").write(
            AddonSpec(
                metadata=AddonMetadata(title="X", addon_type="playermodel"),
                display_name="X",
                model_path="models/player/x/x.mdl",
                mdl=mdl,
                materials=mat_dir,
                cdmaterials="models/player/x",
            )
        )


def test_hands_path_requires_compiled_mdl(tmp_path: Path):
    mdl, _, mat_dir = _compiled_tree(tmp_path)
    with pytest.raises(ValueError, match="hands_mdl"):
        AddonPackageService(tmp_path / "addon").write(
            AddonSpec(
                metadata=AddonMetadata(title="X"),
                display_name="X",
                model_path="models/player/x/x.mdl",
                mdl=mdl,
                materials=mat_dir,
                cdmaterials="models/player/x",
                hands_path="models/weapons/c_arms_x.mdl",
            )
        )
