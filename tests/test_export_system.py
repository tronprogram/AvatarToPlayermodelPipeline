"""ExportSystemService orchestration and path helpers."""

from pathlib import Path

import pytest

from app.core.process import CommandResult
from app.services.compile import CompiledModel, modelname_from_qc
from app.services.export_system import (
    ExportSystemService,
    PlayermodelIdentity,
    SourceDmxFiles,
    playermodel_identity,
)
from app.services.valvetextures import ValveMaterial


def test_playermodel_identity_paths():
    identity = playermodel_identity("My Avatar")
    assert identity == PlayermodelIdentity(
        display_name="My Avatar",
        slug="my_avatar",
        model_name="player/my_avatar/my_avatar.mdl",
        cdmaterials="models/player/my_avatar",
        model_path="models/player/my_avatar/my_avatar.mdl",
        hands_name="weapons/c_arms_my_avatar.mdl",
        hands_path="models/weapons/c_arms_my_avatar.mdl",
    )


def test_playermodel_identity_rejects_empty():
    with pytest.raises(ValueError, match="letters or digits"):
        playermodel_identity("***")


def test_stage_valve_materials_copies_into_cdmaterials(tmp_path: Path):
    source = tmp_path / "work" / "materials"
    source.mkdir(parents=True)
    (source / "face.vtf").write_bytes(b"VTF")
    (source / "face.vmt").write_text('"VertexLitGeneric" {}\n', encoding="utf-8")
    (source / "notes.txt").write_text("skip\n", encoding="utf-8")
    game = tmp_path / "garrysmod"
    dest = ExportSystemService(tmp_path / "avatar.glb").stage_valve_materials(
        source, "models/player/my_avatar", garrysmod=game
    )
    assert dest == game / "materials" / "models" / "player" / "my_avatar"
    assert (dest / "face.vtf").read_bytes() == b"VTF"
    assert (dest / "face.vmt").is_file()
    assert not (dest / "notes.txt").exists()


def test_stage_valve_materials_requires_vtf_or_vmt(tmp_path: Path):
    source = tmp_path / "empty"
    source.mkdir()
    with pytest.raises(FileNotFoundError, match="No VTF/VMT"):
        ExportSystemService(tmp_path / "avatar.glb").stage_valve_materials(
            source, "models/player/x", garrysmod=tmp_path / "garrysmod"
        )


def test_playermodel_qc_uses_dmx_and_gender(tmp_path: Path):
    dmx = SourceDmxFiles(
        reference=tmp_path / "reference.dmx",
        physics=tmp_path / "physics.dmx",
        ragdoll=tmp_path / "anims" / "ragdoll.dmx",
        proportions=tmp_path / "anims" / "proportions.dmx",
        arms=tmp_path / "arms.dmx",
        aligned_glb=tmp_path / "aligned.glb",
    )
    identity = playermodel_identity("My Avatar")
    spec = ExportSystemService(tmp_path / "avatar.glb").playermodel_qc(
        dmx, identity, gender="female"
    )
    assert spec.model_name == identity.model_name
    assert spec.cdmaterials == identity.cdmaterials
    assert spec.include_anims == "f_anm.mdl"
    assert spec.reference == dmx.reference


def test_carms_qc_uses_arms_and_identity(tmp_path: Path):
    dmx = SourceDmxFiles(
        reference=tmp_path / "reference.dmx",
        physics=tmp_path / "physics.dmx",
        ragdoll=tmp_path / "anims" / "ragdoll.dmx",
        proportions=tmp_path / "anims" / "proportions.dmx",
        arms=tmp_path / "arms.dmx",
        aligned_glb=tmp_path / "aligned.glb",
    )
    identity = playermodel_identity("My Avatar")
    spec = ExportSystemService(tmp_path / "avatar.glb").carms_qc(dmx, identity)
    assert spec.model_name == identity.hands_name
    assert spec.arms == dmx.arms
    assert spec.cdmaterials == identity.cdmaterials


def test_export_playermodel_chains_daughters(monkeypatch, tmp_path: Path):
    work = tmp_path / "work"
    game = tmp_path / "garrysmod"
    (game / "gameinfo.txt").parent.mkdir(parents=True)
    (game / "gameinfo.txt").write_text("GameInfo {}\n", encoding="utf-8")
    glb = tmp_path / "avatar.glb"
    glb.write_bytes(b"glb")
    service = ExportSystemService(glb)

    dmx = SourceDmxFiles(
        reference=work / "reference.dmx",
        physics=work / "physics.dmx",
        ragdoll=work / "anims" / "ragdoll.dmx",
        proportions=work / "anims" / "proportions.dmx",
        arms=work / "arms.dmx",
        aligned_glb=work / "aligned.glb",
    )

    def fake_dmx(out_dir: Path, gltf=None, *, gender="male"):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "anims").mkdir(exist_ok=True)
        for path in (
            dmx.reference,
            dmx.physics,
            dmx.ragdoll,
            dmx.proportions,
            dmx.arms,
            dmx.aligned_glb,
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"dmx")
        return dmx

    def fake_textures(directory: Path, textures=None, *, cdmaterials=""):
        directory.mkdir(parents=True, exist_ok=True)
        vtf = directory / "face.vtf"
        vmt = directory / "face.vmt"
        vtf.write_bytes(b"VTF")
        vmt.write_text('"VertexLitGeneric" {}\n', encoding="utf-8")
        return [
            ValveMaterial(
                vtf=vtf,
                vmt=vmt,
                has_alpha=False,
                source_name="face",
                original_name="face",
            )
        ]

    def fake_compile(qc: Path):
        model_name = modelname_from_qc(qc)
        compiled = game / "models" / Path(*model_name.split("/"))
        compiled.parent.mkdir(parents=True, exist_ok=True)
        compiled.write_bytes(b"IDST")
        (compiled.with_suffix(".vvd")).write_bytes(b"VVD")
        return CompiledModel(
            mdl=compiled,
            log=CommandResult(argv=["studiomdl"], returncode=0, stdout="ok", stderr=""),
            model_name=model_name,
            vtx=None,
            vvd=compiled.with_suffix(".vvd"),
            phy=None,
        )

    monkeypatch.setattr(service, "export_source_dmx", fake_dmx)
    monkeypatch.setattr(service, "export_valve_textures", fake_textures)
    monkeypatch.setattr(service, "compile_qc", fake_compile)

    addon_dir = tmp_path / "addons" / "my_avatar"
    build = service.export_playermodel(
        work,
        display_name="My Avatar",
        gender="male",
        addon_dir=addon_dir,
        garrysmod=game,
        author="pipeline",
        description="Test avatar",
    )

    assert build.identity.slug == "my_avatar"
    assert build.qc == work / "my_avatar.qc"
    assert '$modelname "player/my_avatar/my_avatar.mdl"' in build.qc.read_text(encoding="utf-8")
    assert build.carms_qc == work / "c_arms_my_avatar.qc"
    assert '$modelname "weapons/c_arms_my_avatar.mdl"' in build.carms_qc.read_text(
        encoding="utf-8"
    )
    assert '$model "arms" "arms.dmx"' in build.carms_qc.read_text(encoding="utf-8")
    assert build.staged_materials == game / "materials" / "models" / "player" / "my_avatar"
    assert (build.staged_materials / "face.vtf").is_file()
    assert build.compiled.mdl == game / "models" / "player" / "my_avatar" / "my_avatar.mdl"
    assert build.carms.mdl == game / "models" / "weapons" / "c_arms_my_avatar.mdl"
    assert build.addon.root == addon_dir
    lua = (addon_dir / "lua" / "autorun" / "my_avatar.lua").read_text(encoding="utf-8")
    assert "AddValidHands" in lua
    assert (addon_dir / "models" / "player" / "my_avatar" / "my_avatar.mdl").read_bytes() == b"IDST"
    assert (addon_dir / "models" / "weapons" / "c_arms_my_avatar.mdl").read_bytes() == b"IDST"
    assert (addon_dir / "materials" / "models" / "player" / "my_avatar" / "face.vmt").is_file()
    assert '"author": "pipeline"' in (addon_dir / "addon.json").read_text(encoding="utf-8")
