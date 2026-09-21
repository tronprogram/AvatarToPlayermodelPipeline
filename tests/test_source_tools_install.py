from pathlib import Path

from app.services.deps.detect import (
    blender_launch_env,
    blender_user_resources,
    find_source_tools,
    source_tools_install_dir,
)


def test_source_tools_install_in_blender_user_scripts(tmp_path: Path):
    dest = source_tools_install_dir(tmp_path)
    assert dest == tmp_path / "blender" / "user" / "scripts" / "addons"
    assert dest.is_dir()
    assert blender_user_resources(tmp_path / "blender") == tmp_path / "blender" / "user"


def test_find_source_tools_only_in_user_scripts(tmp_path: Path):
    wrong = tmp_path / "blender" / "scripts" / "addons" / "io_scene_valvesource"
    wrong.mkdir(parents=True)
    (wrong / "__init__.py").write_text("", encoding="utf-8")
    assert find_source_tools(tmp_path / "blender") is None

    right = source_tools_install_dir(tmp_path) / "io_scene_valvesource"
    right.mkdir()
    (right / "__init__.py").write_text("", encoding="utf-8")
    assert find_source_tools(tmp_path / "blender") == right


def test_blender_launch_env_points_at_user_resources(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/tmp/venv")
    monkeypatch.setattr("app.services.deps.detect.blender_root", lambda _data: tmp_path / "blender")
    env = blender_launch_env(tmp_path)
    assert env["BLENDER_USER_RESOURCES"] == str(tmp_path / "blender" / "user")
    assert "PYTHONPATH" not in env
    assert (tmp_path / "blender" / "user" / "scripts" / "addons").is_dir()
