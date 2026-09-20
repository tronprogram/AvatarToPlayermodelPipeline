"""Playermodel autorun Lua renderer."""

from pathlib import Path

import pytest

from app.services.playerlua import PlayerLuaService, PlayermodelLua, lua_filename


def _spec(**overrides) -> PlayermodelLua:
    values = dict(
        display_name="My Avatar",
        model_path="models/player/avatar/avatar.mdl",
    )
    values.update(overrides)
    return PlayermodelLua(**values)


def test_write_registers_model_and_lowercase_filename(tmp_path: Path):
    dest = PlayerLuaService(tmp_path).write(_spec())
    assert dest == tmp_path / "my_avatar.lua"
    text = dest.read_text(encoding="utf-8")
    assert (
        'player_manager.AddValidModel("My Avatar", "models/player/avatar/avatar.mdl")'
        in text
    )
    assert (
        'list.Set("PlayerOptionsModel", "My Avatar", "models/player/avatar/avatar.mdl")'
        in text
    )
    assert "AddValidHands" not in text


def test_write_optional_hands(tmp_path: Path):
    text = PlayerLuaService(tmp_path).write(
        _spec(hands_path="models/weapons/c_arms_avatar.mdl")
    ).read_text(encoding="utf-8")
    assert (
        'player_manager.AddValidHands("My Avatar", "models/weapons/c_arms_avatar.mdl", 0, "00000000")'
        in text
    )


def test_normalizes_backslashes(tmp_path: Path):
    text = PlayerLuaService(tmp_path).write(
        _spec(model_path=r"models\player\avatar\avatar.mdl")
    ).read_text(encoding="utf-8")
    assert "models/player/avatar/avatar.mdl" in text
    assert "\\" not in text


def test_rejects_path_without_models_prefix(tmp_path: Path):
    with pytest.raises(ValueError, match="models/"):
        PlayerLuaService(tmp_path).write(_spec(model_path="player/avatar/avatar.mdl"))


def test_lua_filename_requires_alnum():
    assert lua_filename("Cool PM") == "cool_pm.lua"
    with pytest.raises(ValueError, match="letters or digits"):
        lua_filename("***")
