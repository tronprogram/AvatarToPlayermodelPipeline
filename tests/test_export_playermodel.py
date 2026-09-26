"""Guards on the headless Blender export script."""

from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "app" / "blender" / "export_playermodel.py"
)


def test_smd_imports_disable_source_tools_bone_vis():
    text = _SCRIPT.read_text(encoding="utf-8")
    assert text.count('boneMode="NONE"') >= 3
    assert "def _discard_bone_vis" in text
    assert "smd_bone_vis" in text
    assert "icosphere" in text


def test_loop_normals_average_by_shared_position():
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "round(x * 100.0)" in text
    assert "at_pos" in text
