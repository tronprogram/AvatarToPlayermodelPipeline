"""HLMV++ Wine helpers."""

import hashlib
import struct
from pathlib import Path

from app.services.hlmv_preview import (
    ensure_hl2mp_game_searchpath,
    ensure_hlmv_include_anims,
    ensure_hlmv_scripts,
    find_qc,
    pack_hlmv_custom_vpk,
    stage_hlmv_assets,
    write_hlmv_gameinfo,
    write_hlmv_material_vpk,
)
from app.services.windows_tools import windows_path


def test_windows_path_uses_z_drive(tmp_path: Path):
    target = tmp_path / "export_test" / "myavatar.qc"
    target.parent.mkdir()
    target.write_text("$modelname x\n", encoding="utf-8")
    converted = windows_path(target)
    assert converted.startswith("Z:")
    assert "\\" in converted
    assert converted.endswith("myavatar.qc")
    assert "/" not in converted[2:]


def test_find_qc_prefers_myavatar(tmp_path: Path):
    (tmp_path / "other.qc").write_text("a\n", encoding="utf-8")
    named = tmp_path / "myavatar.qc"
    named.write_text("b\n", encoding="utf-8")
    assert find_qc(tmp_path) == named


def test_write_hlmv_gameinfo_mounts_garrysmod(tmp_path: Path):
    game_dir = tmp_path / "pipeline"
    garrysmod = tmp_path / "garrysmod"
    garrysmod.mkdir()
    dest = write_hlmv_gameinfo(game_dir, garrysmod)
    text = dest.read_text(encoding="utf-8")
    assert dest == game_dir / "gameinfo.txt"
    assert "Pipeline HLMV" in text
    assert "4000" in text
    assert "243750" not in text
    assert windows_path(garrysmod).replace("\\", "/") in text
    assert windows_path(game_dir).replace("\\", "/") in text
    assert (game_dir / "scripts" / "game_sounds_manifest.txt").is_file()


def test_stage_hlmv_assets_copies_mdl_and_materials(tmp_path: Path):
    garrysmod = tmp_path / "garrysmod"
    mdl_dir = garrysmod / "models" / "player" / "myavatar"
    mat_dir = garrysmod / "materials" / "models" / "player" / "myavatar"
    mdl_dir.mkdir(parents=True)
    mat_dir.mkdir(parents=True)
    mdl = mdl_dir / "myavatar.mdl"
    mdl.write_bytes(b"IDST")
    (mdl_dir / "myavatar.vvd").write_bytes(b"VVD")
    (mat_dir / "face.vtf").write_bytes(b"VTF")
    (mat_dir / "face.vmt").write_text('"VertexLitGeneric"\n{\n}\n', encoding="utf-8")
    game_dir = tmp_path / "pipeline"
    extra = tmp_path / "hl2"
    rel = stage_hlmv_assets(
        game_dir, mdl, garrysmod, extra_material_roots=[extra]
    )
    assert rel == "models/player/myavatar/myavatar.mdl"
    assert (game_dir / "models" / "player" / "myavatar" / "myavatar.vvd").read_bytes() == b"VVD"
    assert (game_dir / "materials" / "models" / "player" / "myavatar" / "face.vtf").read_bytes() == b"VTF"
    assert (extra / "materials" / "models" / "player" / "myavatar" / "face.vmt").is_file()


def test_stage_hlmv_assets_rewrites_cdmaterials_slashes(tmp_path: Path):
    garrysmod = tmp_path / "garrysmod"
    mdl_dir = garrysmod / "models" / "player" / "myavatar"
    mdl_dir.mkdir(parents=True)
    mdl = mdl_dir / "myavatar.mdl"
    mdl.write_bytes(b"IDST\x00models\\player\\myavatar\\\x00face\x00")
    game_dir = tmp_path / "pipeline"
    stage_hlmv_assets(game_dir, mdl, garrysmod)
    staged = game_dir / "models" / "player" / "myavatar" / "myavatar.mdl"
    payload = staged.read_bytes()
    assert b"models/player/myavatar/" in payload
    assert b"models\\player\\" not in payload


def test_write_hlmv_material_vpk_contains_vmt(tmp_path: Path):
    materials = tmp_path / "myavatar"
    materials.mkdir()
    (materials / "face.vmt").write_text('"VertexLitGeneric"\n{\n}\n', encoding="utf-8")
    dest = tmp_path / "pipeline_dir.vpk"
    write_hlmv_material_vpk(
        materials, dest, prefix="materials/models/player/myavatar"
    )
    assert dest.is_file()
    from srctools.vpk import VPK

    pak = VPK(str(dest), mode="r")
    info = pak["materials/models/player/myavatar/face.vmt"]
    assert b"VertexLitGeneric" in info.read()


def test_pack_hlmv_custom_vpk_writes_version_two(tmp_path: Path):
    folder = tmp_path / "pipeline"
    materials = folder / "materials" / "models" / "player" / "myavatar"
    materials.mkdir(parents=True)
    (materials / "face.vmt").write_text('"VertexLitGeneric"\n{\n}\n', encoding="utf-8")
    (materials / "face.vtf").write_bytes(b"VTF\x00payload")
    dest = pack_hlmv_custom_vpk(folder)
    assert dest == tmp_path / "pipeline.vpk"
    raw = dest.read_bytes()
    signature, version, tree, embed, chunk, other, signature_size = struct.unpack_from(
        "<IIIIIII", raw, 0
    )
    assert signature == 0x55AA1234
    assert version == 2
    assert embed > 0
    assert chunk == 0
    assert other == 48
    assert signature_size == 0
    other_at = 28 + tree + embed
    assert hashlib.md5(raw[28 : 28 + tree]).digest() == raw[other_at : other_at + 16]
    assert hashlib.md5(b"").digest() == raw[other_at + 16 : other_at + 32]
    assert hashlib.md5(raw[: other_at + 32]).digest() == raw[other_at + 32 : other_at + 48]
    from srctools.vpk import VPK

    pak = VPK(str(dest), mode="r")
    assert pak.version == 2
    assert b"VertexLitGeneric" in pak["materials/models/player/myavatar/face.vmt"].read()
    assert pak["materials/models/player/myavatar/face.vtf"].read() == b"VTF\x00payload"


def test_pack_hlmv_custom_vpk_skips_an_empty_folder(tmp_path: Path):
    folder = tmp_path / "pipeline"
    folder.mkdir()
    assert pack_hlmv_custom_vpk(folder) is None
    assert not (tmp_path / "pipeline.vpk").exists()


def test_ensure_hl2mp_game_searchpath_adds_game_mount(tmp_path: Path):
    gameinfo = tmp_path / "gameinfo.txt"
    gameinfo.write_text(
        "\t\t\tmod+mod_write+default_write_path\t\t|gameinfo_path|.\n"
        "\t\t\tgame+game_write\t\thl2mp\n",
        encoding="utf-8",
    )
    ensure_hl2mp_game_searchpath(gameinfo)
    text = gameinfo.read_text(encoding="utf-8")
    assert "game\t\t\t\t|gameinfo_path|." in text
    ensure_hl2mp_game_searchpath(gameinfo)
    assert gameinfo.read_text(encoding="utf-8").count("game\t\t\t\t|gameinfo_path|.") == 1


def test_ensure_hlmv_include_anims_copies_into_game_models(tmp_path: Path, monkeypatch):
    cache = tmp_path / "sdk2013mp" / "models"
    cache.mkdir(parents=True)
    (cache / "m_anm.mdl").write_bytes(b"MDL")
    (cache / "m_anm.ani").write_bytes(b"ANI")
    (cache / "f_anm.mdl").write_bytes(b"FMD")
    (cache / "f_anm.ani").write_bytes(b"FAN")
    monkeypatch.setattr("app.services.hlmv_preview.data_dir", lambda: tmp_path)
    dest = tmp_path / "hl2mp"
    written = ensure_hlmv_include_anims(dest)
    assert (dest / "models" / "m_anm.mdl").read_bytes() == b"MDL"
    assert (dest / "models" / "m_anm.ani").read_bytes() == b"ANI"
    assert dest / "models" / "m_anm.mdl" in written
    again = ensure_hlmv_include_anims(dest)
    assert dest / "models" / "m_anm.mdl" in again


def test_ensure_hlmv_scripts_writes_stub_manifest(tmp_path: Path):
    game_dir = tmp_path / "garrysmod"
    game_dir.mkdir()
    dest = ensure_hlmv_scripts(game_dir)
    assert dest == game_dir / "scripts" / "game_sounds_manifest.txt"
    text = dest.read_text(encoding="utf-8")
    assert "game_sounds_manifest" in text
    again = ensure_hlmv_scripts(game_dir)
    assert again.read_text(encoding="utf-8") == text
