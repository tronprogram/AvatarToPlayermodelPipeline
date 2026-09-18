"""Convert GLB materials into Source VTF + VMT files."""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from pygltflib import GLTF2
from srctools.vtf import ImageFormats, VTF, VTFFlags

from app.core.source_names import allocate_source_name, source_material_name
from app.core.templates import render_valve


@dataclass(frozen=True, slots=True)
class EmbeddedTexture:
    """One image packed inside the source GLB.

    ``data`` is a complete image file (PNG or JPEG bytes), not decoded
    pixels. It is the ``bufferView`` slice of the GLB BIN chunk.
    ``filename`` already includes ``.png`` or ``.jpg``.
    """

    filename: str
    data: bytes
    mime_type: str


@dataclass(frozen=True, slots=True)
class SourceMaterialSpec:
    """One GLB material planned as a Source-legal VTF/VMT stem."""

    original_name: str
    source_name: str
    data: bytes
    mime_type: str


@dataclass(frozen=True, slots=True)
class ValveMaterial:
    """One albedo written as VTF plus a matching VertexLitGeneric VMT."""

    vtf: Path
    vmt: Path
    has_alpha: bool
    source_name: str
    original_name: str


class ValveTextureService:
    """Write Source VTF and VMT files into one output directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def convert(
        self,
        textures: Sequence[EmbeddedTexture | SourceMaterialSpec],
        *,
        cdmaterials: str = "",
    ) -> list[ValveMaterial]:
        """Write one ``.vtf`` + ``.vmt`` per unique ``source_name``.

        ``EmbeddedTexture`` stems are sanitized the same way as GLB material
        names. Duplicate specs that share a stem are written once.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        written: list[ValveMaterial] = []
        seen: set[str] = set()
        for item in textures:
            spec = _as_spec(item)
            if spec.source_name in seen:
                continue
            seen.add(spec.source_name)
            vtf_path = self.directory / f"{spec.source_name}.vtf"
            has_alpha = self._write_vtf(spec.data, vtf_path)
            vmt_path = vtf_path.with_suffix(".vmt")
            self._write_vmt(vmt_path, cdmaterials, spec.source_name, has_alpha)
            written.append(
                ValveMaterial(
                    vtf=vtf_path,
                    vmt=vmt_path,
                    has_alpha=has_alpha,
                    source_name=spec.source_name,
                    original_name=spec.original_name,
                )
            )
        return written

    def _write_vtf(self, data: bytes, dest: Path) -> bool:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            img = self._ensure_power_of_two(img.convert("RGBA"))
            has_alpha = self._has_alpha(img)
            fmt = ImageFormats.DXT5 if has_alpha else ImageFormats.DXT1
            flags = VTFFlags.EIGHTBITALPHA if has_alpha else VTFFlags.EMPTY
            # SDK 2013 HLMV / GMod studiomdl stop at 7.4; srctools defaults to 7.5.
            vtf = VTF(
                img.width,
                img.height,
                version=(7, 4),
                fmt=fmt,
                flags=flags,
            )
            vtf.get().copy_from(img.tobytes(), format=ImageFormats.RGBA8888)
            with dest.open("wb") as handle:
                vtf.save(handle)
            return has_alpha

    def _write_vmt(
        self, dest: Path, cdmaterials: str, stem: str, has_alpha: bool
    ) -> None:
        dest.write_text(
            render_valve(
                "vertexlitgeneric.vmt",
                basetexture=_basetexture(cdmaterials, stem),
                has_alpha=has_alpha,
            ),
            encoding="utf-8",
            newline="\n",
        )

    def _ceil_power_of_two(self, dim: int) -> int:
        if dim <= 1:
            return 1
        return 1 << (dim - 1).bit_length()

    def _ensure_power_of_two(self, img: Image.Image, *, minimum: int = 4) -> Image.Image:
        """Resize to power-of-two sides, at least ``minimum`` (DXT needs 4×4)."""
        width, height = img.size
        new_w = max(minimum, self._ceil_power_of_two(width))
        new_h = max(minimum, self._ceil_power_of_two(height))
        if (width, height) == (new_w, new_h):
            return img
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    def _has_alpha(self, img: Image.Image) -> bool:
        """True when any pixel is actually transparent (not merely RGBA)."""
        return img.getchannel("A").getextrema()[0] < 255


def plan_materials(gltf: GLTF2, blob: bytes | None) -> list[SourceMaterialSpec]:
    """One spec per GLB material that has an embedded albedo texture."""
    if blob is None:
        return []
    assigned: dict[str, object] = {}
    specs: list[SourceMaterialSpec] = []
    images = gltf.images or []
    textures = gltf.textures or []
    views = gltf.bufferViews or []
    for index, material in enumerate(gltf.materials or []):
        original = material.name if material.name else f"mat_{index}"
        image_index = _albedo_image_index(material, textures)
        if image_index is None or image_index >= len(images):
            continue
        image = images[image_index]
        if image.bufferView is None or image.bufferView >= len(views):
            continue
        view = views[image.bufferView]
        start = view.byteOffset or 0
        end = start + view.byteLength
        mime = image.mimeType or "image/png"
        source = allocate_source_name(
            source_material_name(original), image_index, assigned
        )
        specs.append(
            SourceMaterialSpec(
                original_name=original,
                source_name=source,
                data=blob[start:end],
                mime_type=mime,
            )
        )
    return specs


def material_renames(names: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """``$renamematerial`` pairs when a DMX still has illegal Source names."""
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for original in names:
        new = source_material_name(original)
        if original == new or (original, new) in pairs:
            continue
        if new in seen:
            continue
        seen.add(new)
        pairs.append((original, new))
    return tuple(pairs)


def _as_spec(item: EmbeddedTexture | SourceMaterialSpec) -> SourceMaterialSpec:
    if isinstance(item, SourceMaterialSpec):
        return item
    stem = Path(item.filename).stem
    return SourceMaterialSpec(
        original_name=stem,
        source_name=source_material_name(stem),
        data=item.data,
        mime_type=item.mime_type,
    )


def _albedo_image_index(material: object, textures: Sequence[object]) -> int | None:
    pbr = getattr(material, "pbrMetallicRoughness", None)
    info = getattr(pbr, "baseColorTexture", None) if pbr is not None else None
    tex_index = getattr(info, "index", None)
    if tex_index is None:
        extensions = getattr(material, "extensions", None) or {}
        spec_gloss = extensions.get("KHR_materials_pbrSpecularGlossiness") or {}
        diffuse = spec_gloss.get("diffuseTexture") if isinstance(spec_gloss, dict) else None
        if isinstance(diffuse, dict):
            tex_index = diffuse.get("index")
    if tex_index is None or tex_index >= len(textures):
        return None
    source = getattr(textures[tex_index], "source", None)
    return source if isinstance(source, int) else None


def _basetexture(cdmaterials: str, stem: str) -> str:
    prefix = cdmaterials.replace("\\", "/").strip().strip("/")
    return f"{prefix}/{stem}" if prefix else stem
