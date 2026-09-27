"""Executable regressions for helper geometry, smoothing and glTF alpha."""

import ast
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pygltflib import GLTF2, BufferView, Image as GltfImage, Material, PbrMetallicRoughness, Texture, TextureInfo

from app.services.valvetextures import plan_materials, ValveTextureService

SCRIPT = Path(__file__).resolve().parents[1] / "app/blender/export_playermodel.py"


def blender_function(name, **namespace):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SCRIPT), "exec"), namespace)
    return namespace[name]


def test_normals_smooth_duplicate_positions_without_cancelling_backfaces():
    positions = [(0, 0, 0), (1, 0, 0), (0, 1, 0),
                 (0, 0, 0), (0, 1, 0), (-1, 0, 1),
                 (0, 0, 0), (0, 1, 0), (1, 0, 0)]
    normals = blender_function("_hemisphere_loop_normals")(
        positions, list(range(9)), SimpleNamespace(Vector3=tuple))
    assert normals[0] == pytest.approx(normals[3])
    assert normals[0][0] > 0.3
    assert normals[0][2] > 0.9
    assert normals[6] == pytest.approx((0, 0, -1))


def test_discard_only_referenced_bone_shapes_not_named_avatar_meshes():
    helper = SimpleNamespace(name="Icosphere", type="MESH", data=SimpleNamespace(users=1))
    legitimate = SimpleNamespace(name="Icosphere.001", type="MESH")
    bone = SimpleNamespace(custom_shape=helper)
    arm = SimpleNamespace(type="ARMATURE", pose=SimpleNamespace(bones=[bone]))
    class Objects(list):
        def remove(self, obj, do_unlink=False):
            super().remove(obj)
    objects = Objects([helper, legitimate, arm])
    fake = SimpleNamespace(data=SimpleNamespace(objects=objects))
    blender_function("_discard_bone_vis", bpy=fake)()
    assert helper not in objects
    assert legitimate in objects
    assert bone.custom_shape is None


def test_cleanup_precedes_normalization():
    calls = []
    fake = SimpleNamespace(context=SimpleNamespace())
    def discard():
        calls.append("discard")
        raise RuntimeError("stop before scene access")
    with pytest.raises(RuntimeError, match="stop before scene access"):
        blender_function("_prepare_source_space", bpy=fake, _discard_bone_vis=discard)()
    assert calls == ["discard"]


def material_fixture(mode="BLEND", factor=(1, 1, 1, 0.1), alpha=255, cutoff=0.5):
    buf = BytesIO()
    Image.new("RGBA", (8, 8), (100, 150, 200, alpha)).save(buf, "PNG")
    data = buf.getvalue()
    material = Material(name="glasses", alphaMode=mode, alphaCutoff=cutoff,
                        pbrMetallicRoughness=PbrMetallicRoughness(
                            baseColorTexture=TextureInfo(index=0), baseColorFactor=list(factor)))
    gltf = GLTF2(bufferViews=[BufferView(byteLength=len(data))],
                 images=[GltfImage(bufferView=0, mimeType="image/png")],
                 textures=[Texture(source=0)], materials=[material])
    return gltf, data


def test_blend_bakes_factor_into_texture_and_uses_translucent_vmt(tmp_path):
    gltf, data = material_fixture()
    specs = plan_materials(gltf, data)
    with Image.open(BytesIO(specs[0].data)) as image:
        assert image.getpixel((0, 0))[3] == 26
    result = ValveTextureService(tmp_path).convert(specs)[0]
    assert result.has_alpha
    text = result.vmt.read_text()
    assert '"$translucent" "1"' in text
    assert "$alphatest" not in text


def test_opaque_ignores_both_texture_and_factor_alpha(tmp_path):
    gltf, data = material_fixture(mode="OPAQUE", alpha=128)
    result = ValveTextureService(tmp_path).convert(plan_materials(gltf, data))[0]
    assert not result.has_alpha
    assert "$translucent" not in result.vmt.read_text()
    assert "$alphatest" not in result.vmt.read_text()


def test_mask_keeps_cutout_and_cutoff(tmp_path):
    gltf, data = material_fixture(mode="MASK", cutoff=0.25)
    result = ValveTextureService(tmp_path).convert(plan_materials(gltf, data))[0]
    text = result.vmt.read_text()
    assert '"$alphatest" "1"' in text
    assert '"$alphatestreference" "0.25"' in text
    assert "$translucent" not in text


def test_shared_image_distinct_factors_get_distinct_material_names():
    gltf, data = material_fixture()
    import copy
    second = copy.deepcopy(gltf.materials[0])
    second.name = "glasses.001"
    second.pbrMetallicRoughness.baseColorFactor[3] = 0.6
    gltf.materials.append(second)
    assert [s.source_name for s in plan_materials(gltf, data)] == ["glasses", "glasses_2"]


def test_staged_blender_material_names_match_planned_vmt_names():
    from app.services.export_system import _stage_material_names
    import copy
    gltf, data = material_fixture()
    second = copy.deepcopy(gltf.materials[0])
    second.name = "glasses.001"
    second.pbrMetallicRoughness.baseColorFactor[3] = 0.6
    gltf.materials.append(second)
    gltf.set_binary_blob(data)
    _stage_material_names(gltf)
    assert [m.name for m in gltf.materials] == ["glasses", "glasses_2"]
