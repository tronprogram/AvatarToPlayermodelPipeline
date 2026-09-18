"""Convert GLB-embedded images into Source VTF + VMT files."""

from __future__ import annotations

import io
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from srctools.vtf import ImageFormats, VTF, VTFFlags


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
class ValveMaterial:
    """One albedo written as VTF plus a matching VertexLitGeneric VMT."""

    vtf: Path
    vmt: Path
    has_alpha: bool


class ValveTextureService:
    """Write Source VTF and VMT files into one output directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def convert(
        self,
        textures: list[EmbeddedTexture],
        *,
        cdmaterials: str = "",
    ) -> list[ValveMaterial]:
        """Write one ``.vtf`` + ``.vmt`` per texture into ``self.directory``.

        Filenames come from ``EmbeddedTexture.filename`` with the suffix forced
        to ``.vtf`` / ``.vmt``. ``$basetexture`` is ``cdmaterials/stem``.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        written: list[ValveMaterial] = []
        for texture in textures:
            stem_path = Path(texture.filename).with_suffix(".vtf")
            vtf_path = self.directory / stem_path.name
            has_alpha = self._write_vtf(texture.data, vtf_path)
            vmt_path = vtf_path.with_suffix(".vmt")
            self._write_vmt(vmt_path, cdmaterials, vtf_path.stem, has_alpha)
            written.append(
                ValveMaterial(vtf=vtf_path, vmt=vmt_path, has_alpha=has_alpha)
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
        lines = [
            '"VertexLitGeneric"',
            "{",
            f'\t"$basetexture" "{_basetexture(cdmaterials, stem)}"',
        ]
        if has_alpha:
            lines.append('\t"$alphatest" "1"')
        lines.extend(["}", ""])
        dest.write_text("\n".join(lines), encoding="utf-8", newline="\n")

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


def source_material_name(name: str) -> str:
    """Ready Player Me ``hair: Teased spikes_3`` → Source-legal ``hair``."""
    head = name.split(":", 1)[0].strip() or name
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", head).strip("_") or "mat"
    if clean[0].isdigit():
        clean = f"mat_{clean}"
    return clean[:63]


def texture_stem_from_material(name: str) -> str:
    """Map a DMX material name onto the GLB texture we already wrote (``tex_N``)."""
    match = re.search(r"_(\d+)$", name.strip())
    if match:
        return f"tex_{match.group(1)}"
    if name.strip() == "body_0":
        return "tex_0"
    return source_material_name(name)


def material_renames(names: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """``$renamematerial`` pairs for names that are not already Source-legal."""
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


def alias_materials(directory: Path, names: Sequence[str]) -> list[Path]:
    """Copy ``tex_N.vmt`` onto sanitized names HLMV will look up."""
    written: list[Path] = []
    directory.mkdir(parents=True, exist_ok=True)
    for original in names:
        new = source_material_name(original)
        stem = texture_stem_from_material(original)
        src = directory / f"{stem}.vmt"
        dest = directory / f"{new}.vmt"
        if not src.is_file() or dest.resolve() == src.resolve():
            continue
        shutil.copy2(src, dest)
        written.append(dest)
    return written


def _basetexture(cdmaterials: str, stem: str) -> str:
    prefix = cdmaterials.replace("\\", "/").strip().strip("/")
    return f"{prefix}/{stem}" if prefix else stem
