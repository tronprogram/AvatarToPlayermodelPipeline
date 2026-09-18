"""Crowbar Wine helpers."""

from pathlib import Path

from app.services.crowbar import (
    ensure_hl2mp_game_searchpath,
    ensure_hlmv_scripts,
    find_qc,
    stage_hlmv_assets,
    windows_path,
    write_crowbar_settings,
    write_hlmv_gameinfo,
    write_hlmv_material_vpk,
)


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


def test_write_crowbar_settings_points_at_qc(tmp_path: Path):
    prefix = tmp_path / "prefix"
    user = prefix / "drive_c" / "users" / "crossover"
    user.mkdir(parents=True)
    qc = tmp_path / "myavatar.qc"
    qc.write_text("$modelname x\n", encoding="utf-8")
    compiler = tmp_path / "studiomdl.exe"
    compiler.write_bytes(b"")
    gameinfo = tmp_path / "gameinfo.txt"
    gameinfo.write_text("GameInfo {}\n", encoding="utf-8")
    dest = write_crowbar_settings(prefix, qc, compiler, gameinfo)
    text = dest.read_text(encoding="utf-8")
    assert "Garry's Mod (pipeline)" in text
    assert "CompileQcPathFileName" in text
    assert "myavatar.qc" in text
    assert "OptionsAutoOpenQcFileIsChecked>true" in text
    assert "ViewGameSetupSelectedIndex" in text


def test_write_hlmv_gameinfo_mounts_garrysmod(tmp_path: Path):
    game_dir = tmp_path / "pipeline"
    garrysmod = tmp_path / "garrysmod"
    garrysmod.mkdir()
    dest = write_hlmv_gameinfo(game_dir, garrysmod)
    text = dest.read_text(encoding="utf-8")
    assert dest == game_dir / "gameinfo.txt"
    assert "Pipeline HLMV" in text
    assert "243750" in text
    assert "|all_source_engine_paths|hl2/pipeline.vpk" in text
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


def test_ensure_hlmv_scripts_writes_stub_manifest(tmp_path: Path):
    game_dir = tmp_path / "garrysmod"
    game_dir.mkdir()
    dest = ensure_hlmv_scripts(game_dir)
    assert dest == game_dir / "scripts" / "game_sounds_manifest.txt"
    text = dest.read_text(encoding="utf-8")
    assert "game_sounds_manifest" in text
    again = ensure_hlmv_scripts(game_dir)
    assert again.read_text(encoding="utf-8") == text
