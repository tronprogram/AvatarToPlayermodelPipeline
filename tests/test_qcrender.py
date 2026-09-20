"""Playermodel QC renderer."""

from pathlib import Path

import pytest

from app.services.qcrender import CarmsQc, PlayermodelQc, QCRenderService


def _spec(**overrides) -> PlayermodelQc:
    values = dict(
        model_name="player/avatar/avatar.mdl",
        reference="reference.dmx",
        physics="physics.dmx",
        ragdoll="anims/ragdoll.dmx",
        proportions="anims/proportions.dmx",
        size_reference="anims/size_reference.dmx",
        cdmaterials="models/player/avatar",
        include_anims="m_anm.mdl",
    )
    values.update(overrides)
    return PlayermodelQc(**values)


def test_write_uses_model_stem_and_relative_paths(tmp_path: Path):
    dest = QCRenderService(tmp_path).write(_spec())
    assert dest == tmp_path / "avatar.qc"
    text = dest.read_text(encoding="utf-8")
    assert '$modelname "player/avatar/avatar.mdl"' in text
    assert '$model "body" "reference.dmx"' in text
    assert '$collisionjoints "physics.dmx"' in text
    assert '$sequence ragdoll "anims/ragdoll.dmx" ACT_DIERAGDOLL 1' in text
    assert "$unlockdefinebones" in text
    assert '$sequence reference "anims/size_reference.dmx" fps 1' in text
    assert (
        '$animation a_proportions "anims/proportions.dmx" subtract reference 0'
    ) in text
    assert "$sequence proportions a_proportions delta autoplay hidden" in text
    assert '$cdmaterials "models/player/avatar"' in text
    assert '$definebone "ValveBiped.Bip01_Pelvis"' in text


def test_write_makes_absolute_paths_relative(tmp_path: Path):
    dest = QCRenderService(tmp_path).write(
        _spec(
            reference=tmp_path / "reference.dmx",
            physics=tmp_path / "physics.dmx",
            ragdoll=tmp_path / "anims" / "ragdoll.dmx",
            proportions=tmp_path / "anims" / "proportions.dmx",
            size_reference=tmp_path / "anims" / "size_reference.dmx",
        )
    )
    text = dest.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert '$model "body" "reference.dmx"' in text
    assert '$sequence ragdoll "anims/ragdoll.dmx" ACT_DIERAGDOLL 1' in text


def test_male_include_excludes_female(tmp_path: Path):
    text = QCRenderService(tmp_path).write(_spec(include_anims="m_anm.mdl")).read_text()
    assert '$includemodel "m_anm.mdl"' in text
    assert "f_anm.mdl" not in text


def test_female_include_excludes_male(tmp_path: Path):
    text = QCRenderService(tmp_path).write(_spec(include_anims="f_anm.mdl")).read_text()
    assert '$includemodel "f_anm.mdl"' in text
    assert "m_anm.mdl" not in text
    assert "$definebone \"ValveBiped.Bip01_Pelvis\" \"\" -0.000005 -0.788460" in text


def test_rejects_invalid_include_anims(tmp_path: Path):
    with pytest.raises(ValueError, match="include_anims"):
        QCRenderService(tmp_path).write(_spec(include_anims="both.mdl"))  # type: ignore[arg-type]


def test_rejects_absolute_path_outside_directory(tmp_path: Path, tmp_path_factory):
    other = tmp_path_factory.mktemp("elsewhere") / "reference.dmx"
    with pytest.raises(ValueError, match="not under the QC directory"):
        QCRenderService(tmp_path).write(_spec(reference=other))


def test_compile_flags_attachments_ik_and_collision(tmp_path: Path):
    text = QCRenderService(tmp_path).write(_spec()).read_text(encoding="utf-8")
    for flag in (
        "$ambientboost",
        "$mostlyopaque",
        '$surfaceprop "flesh"',
        '$contents "solid"',
        "$bbox -40 -40 0 40 40 72",
    ):
        assert flag in text
    assert "$bonemerge ValveBiped.forward" in text
    assert "$bonemerge ValveBiped.Anim_Attachment_RH" in text
    assert "$bonemerge ValveBiped.Anim_Attachment_LH" in text
    assert '$attachment "eyes" "ValveBiped.Bip01_Head1"' in text
    assert '$attachment "anim_attachment_RH" "ValveBiped.Anim_Attachment_RH"' in text
    assert '$ikchain "rfoot" "ValveBiped.Bip01_R_Foot"' in text
    assert '$ikautoplaylock "lfoot"' in text
    assert ' $rootbone "ValveBiped.Bip01_Pelvis"' in text
    assert "$jointconstrain" in text
    assert '$sequence ragdoll "anims/ragdoll.dmx" ACT_DIERAGDOLL 1' in text
    assert "$unlockdefinebones" in text
    assert '$sequence reference "anims/size_reference.dmx" fps 1' in text
    assert (
        '$animation a_proportions "anims/proportions.dmx" subtract reference 0'
    ) in text
    assert "$sequence proportions a_proportions delta autoplay hidden" in text
    assert '$definebone "ValveBiped.Bip01_Pelvis"' in text
    assert "$maxverts 65536 65536" in text
    assert "$bodygroup" not in text
    assert "$jigglebone" not in text


def test_optional_overrides(tmp_path: Path):
    text = (
        QCRenderService(tmp_path)
        .write(
            _spec(
                surfaceprop="alienflesh",
                mass=72.5,
                illumposition=(1.0, 2.0, 3.0),
            )
        )
        .read_text(encoding="utf-8")
    )
    assert '$surfaceprop "alienflesh"' in text
    assert " $mass 72.5" in text
    assert "$illumposition 1 2 3" in text


def test_rename_materials_emits_renamematerial(tmp_path: Path):
    text = (
        QCRenderService(tmp_path)
        .write(
            _spec(
                rename_materials=(
                    ("hair: Teased spikes_3", "hair"),
                    ("face", "face"),
                )
            )
        )
        .read_text(encoding="utf-8")
    )
    assert '$renamematerial "hair: Teased spikes_3" "hair"' in text
    assert '$renamematerial "face" "face"' not in text


def test_write_carms_uses_model_stem_and_arm_flags(tmp_path: Path):
    dest = QCRenderService(tmp_path).write_carms(
        CarmsQc(
            model_name="weapons/c_arms_avatar.mdl",
            arms=tmp_path / "arms.dmx",
            cdmaterials="models/player/avatar",
        )
    )
    assert dest == tmp_path / "c_arms_avatar.qc"
    text = dest.read_text(encoding="utf-8")
    assert '$modelname "weapons/c_arms_avatar.mdl"' in text
    assert '$model "arms" "arms.dmx"' in text
    assert '$cdmaterials "models/player/avatar"' in text
    assert "$unlockdefinebones" in text
    assert '$includemodel "weapons/c_arms_animations.mdl"' in text
    assert '$sequence idle "arms.dmx" fps 1' in text
    assert "$bonemerge ValveBiped.Bip01_Spine4" in text
    assert "$bonemerge ValveBiped.Anim_Attachment_RH" in text
    assert "$definebone" not in text
