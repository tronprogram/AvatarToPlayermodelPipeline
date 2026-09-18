"""VTF + VMT conversion."""

from io import BytesIO
from pathlib import Path

from PIL import Image

from app.services.valvetextures import (
    EmbeddedTexture,
    ValveTextureService,
    alias_materials,
    material_renames,
    source_material_name,
    texture_stem_from_material,
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
    assert '"$alphatest" "1"' in materials[0].vmt.read_text(encoding="utf-8")
    assert '"$basetexture" "hair"' in materials[0].vmt.read_text(encoding="utf-8")


def test_source_material_name_strips_rpm_slot():
    assert source_material_name("hair: Teased spikes_3") == "hair"
    assert source_material_name("shirt: 70's full-zip jacket_5") == "shirt"
    assert source_material_name("face") == "face"
    assert source_material_name("body_0") == "body_0"


def test_texture_stem_from_material_uses_rpm_suffix():
    assert texture_stem_from_material("hair: Teased spikes_3") == "tex_3"
    assert texture_stem_from_material("body_0") == "tex_0"
    assert texture_stem_from_material("face") == "face"


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


def test_alias_materials_copies_tex_vmt(tmp_path: Path):
    (tmp_path / "tex_3.vmt").write_text("hair", encoding="utf-8")
    written = alias_materials(tmp_path, ["hair: Teased spikes_3", "face"])
    assert written == [tmp_path / "hair.vmt"]
    assert (tmp_path / "hair.vmt").read_text(encoding="utf-8") == "hair"
    assert not (tmp_path / "face.vmt").exists()
