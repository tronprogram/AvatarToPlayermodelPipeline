"""VTF + VMT conversion."""

from io import BytesIO
from pathlib import Path

from PIL import Image
from pygltflib import (
    GLTF2,
    BufferView,
    Image as GLTFImage,
    Material,
    PbrMetallicRoughness,
    Texture,
    TextureInfo,
)

from app.services.valvetextures import (
    EmbeddedTexture,
    SourceMaterialSpec,
    ValveTextureService,
    material_renames,
    plan_materials,
    source_material_name,
)


def _png(color: tuple[int, int, int, int], size: int = 8) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (size, size), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_opaque_writes_vtf_and_vmt_without_alphatest(tmp_path: Path):
    materials = ValveTextureService(tmp_path).convert(
        [EmbeddedTexture("face.png", _png((10, 20, 30, 255)), "image/png")],
        cdmaterials="models/player/avatar",
    )
    assert len(materials) == 1
    material = materials[0]
    assert material.vtf == tmp_path / "face.vtf"
    assert material.vmt == tmp_path / "face.vmt"
    assert material.source_name == "face"
    assert material.has_alpha is False
    assert material.vtf.read_bytes()[:4] == b"VTF\x00"
    assert material.vtf.read_bytes()[4:12] == (7).to_bytes(4, "little") + (4).to_bytes(4, "little")
    text = material.vmt.read_text(encoding="utf-8")
    assert '"VertexLitGeneric"' in text
    assert '"$basetexture" "models/player/avatar/face"' in text
    assert "$alphatest" not in text


def test_transparent_sets_alphatest(tmp_path: Path):
    materials = ValveTextureService(tmp_path).convert(
        [EmbeddedTexture("hair.png", _png((10, 20, 30, 128)), "image/png")]
    )
    assert materials[0].has_alpha is True
    assert materials[0].translucent is False
    text = materials[0].vmt.read_text(encoding="utf-8")
    assert '"$alphatest" "1"' in text
    assert "$translucent" not in text
    assert '"$basetexture" "hair"' in text


def test_translucent_glass_uses_envmap_not_alphatest(tmp_path: Path):
    materials = ValveTextureService(tmp_path).convert(
        [
            SourceMaterialSpec(
                original_name="glasses_6",
                source_name="glasses_2",
                data=_png((20, 20, 20, 26)),
                mime_type="image/png",
                translucent=True,
            )
        ]
    )
    material = materials[0]
    assert material.translucent is True
    text = material.vmt.read_text(encoding="utf-8")
    assert '"$translucent" "1"' in text
    assert '"$envmap" "env_cubemap"' in text
    assert '"$nocull" "1"' in text
    assert "$alphatest" not in text


def test_rpm_material_writes_slot_stem_not_tex_n(tmp_path: Path):
    materials = ValveTextureService(tmp_path).convert(
        [
            SourceMaterialSpec(
                original_name="hair: Teased spikes_3",
                source_name=source_material_name("hair: Teased spikes_3"),
                data=_png((10, 20, 30, 128)),
                mime_type="image/png",
            )
        ]
    )
    assert materials[0].source_name == "hair"
    assert materials[0].vtf == tmp_path / "hair.vtf"
    assert (tmp_path / "tex_3.vtf").exists() is False


def test_convert_writes_shared_stem_once(tmp_path: Path):
    data = _png((1, 2, 3, 255))
    materials = ValveTextureService(tmp_path).convert(
        [
            SourceMaterialSpec("face", "face", data, "image/png"),
            SourceMaterialSpec("face", "face", data, "image/png"),
        ]
    )
    assert len(materials) == 1
    assert materials[0].vtf == tmp_path / "face.vtf"


def test_source_material_name_strips_rpm_slot():
    assert source_material_name("hair: Teased spikes_3") == "hair"


def test_material_renames_maps_blender_duplicate_to_face():
    assert material_renames(["face", "face.001", "body_0"]) == (("face.001", "face"),)


def test_material_renames_skips_legal_names():
    pairs = material_renames(
        [
            "body_0",
            "face",
            "hair: Teased spikes_3",
            "trousers: Boot cut jeans_4",
        ]
    )
    assert pairs == (
        ("hair: Teased spikes_3", "hair"),
        ("trousers: Boot cut jeans_4", "trousers"),
    )


def test_plan_materials_reuses_shared_albedo():
    blob = b"AAAA" + b"BBBB"
    gltf = GLTF2()
    gltf.bufferViews = [
        BufferView(byteOffset=0, byteLength=4),
        BufferView(byteOffset=4, byteLength=4),
    ]
    gltf.images = [
        GLTFImage(bufferView=0, mimeType="image/png", name="face"),
        GLTFImage(bufferView=1, mimeType="image/png", name="other"),
    ]
    gltf.textures = [Texture(source=0), Texture(source=1)]
    gltf.materials = [
        Material(
            name="face",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorTexture=TextureInfo(index=0)
            ),
        ),
        Material(
            name="face.001",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorTexture=TextureInfo(index=0)
            ),
        ),
        Material(
            name="hair: Teased spikes_3",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorTexture=TextureInfo(index=1)
            ),
        ),
    ]
    specs = plan_materials(gltf, blob)
    assert [spec.source_name for spec in specs] == ["face", "face", "hair"]
    assert specs[1].original_name == "face.001"
    assert specs[0].data == b"AAAA"
    assert specs[2].original_name == "hair: Teased spikes_3"
    assert specs[2].data == b"BBBB"
    assert all(spec.translucent is False for spec in specs)


def test_plan_materials_blend_bakes_factor_alpha_as_glass():
    frames = _png((80, 80, 80, 255), size=4)
    lenses = _png((40, 40, 40, 255), size=4)
    blob = frames + lenses
    gltf = GLTF2()
    gltf.bufferViews = [
        BufferView(byteOffset=0, byteLength=len(frames)),
        BufferView(byteOffset=len(frames), byteLength=len(lenses)),
    ]
    gltf.images = [
        GLTFImage(bufferView=0, mimeType="image/png", name="tex_5"),
        GLTFImage(bufferView=1, mimeType="image/png", name="tex_6"),
    ]
    gltf.textures = [Texture(source=0), Texture(source=1)]
    gltf.materials = [
        Material(
            name="glasses: Art house glasses_5",
            alphaMode="OPAQUE",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorTexture=TextureInfo(index=0),
                baseColorFactor=[1.0, 1.0, 1.0, 1.0],
            ),
        ),
        Material(
            name="glasses: Art house glasses_6",
            alphaMode="BLEND",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorTexture=TextureInfo(index=1),
                baseColorFactor=[1.0, 1.0, 1.0, 0.1],
            ),
        ),
    ]
    specs = plan_materials(gltf, blob)
    assert [spec.source_name for spec in specs] == ["glasses", "glasses_2"]
    assert specs[0].translucent is False
    assert specs[1].translucent is True
    with Image.open(BytesIO(specs[1].data)) as baked:
        baked.load()
        assert baked.getchannel("A").getextrema()[1] <= 30
