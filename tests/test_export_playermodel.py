"""Guards for headless export orchestration (behavior covered in regressions)."""

import ast
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "app/blender/export_playermodel.py"


def test_smd_imports_disable_bone_display_geometry():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and ast.unparse(n.func) == "bpy.ops.import_scene.smd"]
    assert len(imports) == 3
    for call in imports:
        assert any(k.arg == "boneMode" and isinstance(k.value, ast.Constant)
                   and k.value.value == "NONE" for k in call.keywords)


def test_glb_is_normalized_before_skeleton_alignment():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = sorted((n.lineno, ast.unparse(n.func)) for n in ast.walk(main)
                   if isinstance(n, ast.Call))
    names = [name for _, name in calls]
    assert names.index("bpy.ops.import_scene.gltf") < names.index("_prepare_source_space")
    assert names.index("_prepare_source_space") < names.index("_align_citizen_to_avatar")


def test_carms_skeleton_is_isolated_and_rooted_at_spine4():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [ast.unparse(n.func) for n in ast.walk(main) if isinstance(n, ast.Call)]
    assert "_finalize_carms_skeleton" in calls
    finalize = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_finalize_carms_skeleton")
    source = ast.get_source_segment(SCRIPT.read_text(encoding="utf-8"), finalize)
    assert '"ValveBiped.Bip01_Spine4"' in source
    assert "spine4.parent = None" in source
    assert "armature.copy()" in source
    assert source.index("_remap_carms_root_weights(arms)") < source.index("bones.remove(bone)")


def test_animation_capture_preserves_pose_across_frame_evaluation():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    capture = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == "_capture_action")
    body = ast.get_source_segment(source, capture)
    assert body.index("matrix_basis.copy()") < body.index("frame_set(1)")
    assert body.index("frame_set(1)") < body.index("matrix_basis =")
