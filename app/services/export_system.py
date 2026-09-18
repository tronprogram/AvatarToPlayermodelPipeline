"""Avatar → Source playermodel export.

Public methods return named dataclasses (not tuples or string-keyed dicts)
so the payload is visible from the type.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pygltflib import GLTF2

from app.core.paths import data_dir, resource_root
from app.core.process import PYTHON_ENV_KEYS, command_env, run_command
from app.services.crowbar import find_qc
from app.services.deps.detect import find_blender_bin
from app.services.source_space import align_to_source
from app.services.valvebiped import apply_valvebiped
from app.services.valvetextures import (
    EmbeddedTexture,
    ValveMaterial,
    ValveTextureService,
)

BindGender = Literal["male", "female"]

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceDmxFiles:
    """Files written by headless Blender Source Tools (DMX binary 2 / model 1)."""

    reference: Path  # visual meshes + ValveBiped armature
    physics: Path  # 15 ragdoll capsules skinned to those bones
    ragdoll: Path  # 1-frame rest clip for ACT_DIERAGDOLL
    proportions: Path  # 1-frame citizen-bind pose for the proportion trick
    aligned_glb: Path  # staged GLB Blender imported


def _blender_script() -> Path:
    return resource_root() / "app" / "blender" / "export_playermodel.py"


def _bind_pose_smd(gender: BindGender) -> Path:
    return resource_root() / "app" / "blender" / "proportions" / f"{gender}.smd"


class ExportSystemService:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path

    def translate_bones(self, gltf: GLTF2 | None = None) -> GLTF2:
        """Map ``joint_*`` helpers onto ValveBiped names, weights, and spine parents.

        Mutates and returns the same GLTF2. Skin joints become the 53
        ValveBiped names; helper bones are folded into parents and dropped
        from the skin.
        """
        if gltf is None:
            gltf = GLTF2().load(str(self.model_path))
        return apply_valvebiped(gltf)

    def align_model(self, gltf: GLTF2 | None = None) -> GLTF2:
        """``translate_bones``, then Source +X forward / +Z up / ~72-unit height.

        Mutates and returns the same GLTF2. Scene roots are scaled in glTF
        Y-up; Blender's importer converts that to Z-up. Does not wrap a
        ``SourceRoot`` node (that collapses skinned meshes on import).
        """
        return align_to_source(self.translate_bones(gltf))

    def export_source_dmx(
        self,
        out_dir: Path,
        gltf: GLTF2 | None = None,
        *,
        gender: BindGender = "male",
    ) -> SourceDmxFiles:
        """Write reference, physics, ragdoll, and proportions DMX via Blender."""
        out_dir.mkdir(parents=True, exist_ok=True)
        aligned = self.align_model(gltf)
        staged = out_dir / "aligned.glb"
        aligned.save(str(staged))

        blender = find_blender_bin(data_dir())
        if blender is None:
            raise FileNotFoundError("Blender is not installed (run the deps wizard)")
        script = _blender_script()
        if not script.is_file():
            raise FileNotFoundError(f"Missing Blender export script: {script}")
        bind = _bind_pose_smd(gender)
        if not bind.is_file():
            raise FileNotFoundError(f"Missing citizen bind pose: {bind}")

        command = [
            str(blender),
            "--background",
            "--python",
            str(script),
            "--",
            "--input",
            str(staged),
            "--output",
            str(out_dir),
            "--proportions",
            str(bind),
        ]
        _log.info("blender export: %s", " ".join(command))
        result = run_command(command, env=command_env(drop=PYTHON_ENV_KEYS))
        if result.stdout:
            _log.info("%s", result.stdout)

        files = SourceDmxFiles(
            reference=out_dir / "reference.dmx",
            physics=out_dir / "physics.dmx",
            ragdoll=out_dir / "anims" / "ragdoll.dmx",
            proportions=out_dir / "anims" / "proportions.dmx",
            aligned_glb=staged,
        )
        missing = [
            name
            for name, path in (
                ("reference", files.reference),
                ("physics", files.physics),
                ("ragdoll", files.ragdoll),
                ("proportions", files.proportions),
            )
            if not path.is_file()
        ]
        if missing:
            raise RuntimeError(
                "Blender finished but did not write "
                + ", ".join(missing)
                + (f"\n{result.stdout}" if result.stdout else "")
            )
        return files

    def get_embedded_textures(self) -> list[EmbeddedTexture]:
        """Images stored in the GLB BIN chunk (``gltf.images`` + ``bufferView``).

        URI-only images (external files) are skipped. Returns an empty list
        when the GLB has no binary blob.
        """
        gltf = GLTF2().load(str(self.model_path))
        if gltf.binary_blob() is None:
            gltf.buffers_to_binary_blob()
        blob = gltf.binary_blob()
        if blob is None:
            return []

        textures: list[EmbeddedTexture] = []
        for index, image in enumerate(gltf.images or []):
            if image.bufferView is None:
                continue
            mime = image.mimeType or "image/png"
            ext = ".jpg" if mime == "image/jpeg" else ".png"
            name = image.name if image.name else f"texture_{index}"
            view = gltf.bufferViews[image.bufferView]
            start = view.byteOffset or 0
            end = start + view.byteLength
            textures.append(
                EmbeddedTexture(
                    filename=name + ext,
                    data=blob[start:end],
                    mime_type=mime,
                )
            )
        return textures

    def export_valve_textures(
        self,
        directory: Path,
        textures: list[EmbeddedTexture] | None = None,
        *,
        cdmaterials: str = "",
    ) -> list[ValveMaterial]:
        """Write VTF + VMT pairs into ``directory``.

        Uses ``get_embedded_textures()`` when ``textures`` is omitted.
        """
        if textures is None:
            textures = self.get_embedded_textures()
        return ValveTextureService(directory).convert(
            textures, cdmaterials=cdmaterials
        )


def _preview_script() -> Path:
    return resource_root() / "app" / "blender" / "preview_playermodel.py"


def default_export_dir() -> Path:
    """Last sample/export tree under the writable data directory."""
    return data_dir() / "export_test"


@dataclass(frozen=True, slots=True)
class ExportAsset:
    """One file the compile QC expects, plus a short size line when present."""

    label: str
    relative: str
    present: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ExportPreview:
    """Inventory of ``default_export_dir()`` for the preview page."""

    directory: Path
    screenshot: Path
    blender_ready: bool
    crowbar_ready: bool
    assets: tuple[ExportAsset, ...]


def inspect_export(out_dir: Path) -> ExportPreview:
    """List the DMX/VTF/VMT/QC files a GMod package would consume."""
    vtf_count = len(list((out_dir / "materials").glob("*.vtf")))
    vmt_count = len(list((out_dir / "materials").glob("*.vmt")))
    assets = (
        _file_asset(out_dir, "aligned.glb", "Aligned GLB"),
        _file_asset(out_dir, "reference.dmx", "Reference mesh"),
        _file_asset(out_dir, "physics.dmx", "Ragdoll capsules"),
        _file_asset(out_dir, "anims/ragdoll.dmx", "Ragdoll sequence"),
        _file_asset(out_dir, "anims/proportions.dmx", "Proportion sequence"),
        _file_asset(out_dir, "myavatar.qc", "Playermodel QC"),
        ExportAsset(
            label="Materials",
            relative="materials/",
            present=vtf_count > 0 and vmt_count > 0,
            detail=f"{vtf_count} VTF / {vmt_count} VMT" if vtf_count or vmt_count else "",
        ),
    )
    aligned = out_dir / "aligned.glb"
    return ExportPreview(
        directory=out_dir,
        screenshot=out_dir / "preview.png",
        blender_ready=aligned.is_file(),
        crowbar_ready=find_qc(out_dir) is not None,
        assets=assets,
    )


def preview_in_blender(out_dir: Path) -> None:
    """Open a Blender window on the aligned mesh, bones, and capsules."""
    blender, script, aligned, physics = _preview_inputs(out_dir)
    command = [
        str(blender),
        "--python",
        str(script),
        "--",
        "--input",
        str(aligned),
    ]
    if physics.is_file():
        command.extend(["--physics", str(physics)])
    _log.info("blender preview: %s", " ".join(command))
    subprocess.Popen(
        command,
        env=command_env(drop=PYTHON_ENV_KEYS),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def render_preview_png(out_dir: Path) -> Path:
    """Headless Workbench still of the same scene. Returns ``preview.png``."""
    blender, script, aligned, physics = _preview_inputs(out_dir)
    dest = out_dir / "preview.png"
    command = [
        str(blender),
        "--background",
        "--python",
        str(script),
        "--",
        "--input",
        str(aligned),
        "--screenshot",
        str(dest),
    ]
    if physics.is_file():
        command.extend(["--physics", str(physics)])
    _log.info("blender still: %s", " ".join(command))
    result = run_command(command, env=command_env(drop=PYTHON_ENV_KEYS))
    if result.stdout:
        _log.info("%s", result.stdout)
    if not dest.is_file():
        raise RuntimeError(
            "Blender finished but did not write preview.png"
            + (f"\n{result.stdout}" if result.stdout else "")
        )
    return dest


def _preview_inputs(out_dir: Path) -> tuple[Path, Path, Path, Path]:
    blender = find_blender_bin(data_dir())
    if blender is None:
        raise FileNotFoundError("Blender is not installed (run the deps wizard)")
    script = _preview_script()
    if not script.is_file():
        raise FileNotFoundError(f"Missing Blender preview script: {script}")
    aligned = out_dir / "aligned.glb"
    if not aligned.is_file():
        raise FileNotFoundError(f"No aligned.glb in {out_dir}")
    return blender, script, aligned, out_dir / "physics.dmx"


def _file_asset(out_dir: Path, relative: str, label: str) -> ExportAsset:
    path = out_dir / relative
    if not path.is_file():
        return ExportAsset(label=label, relative=relative, present=False, detail="")
    size = path.stat().st_size
    detail = f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} B"
    return ExportAsset(label=label, relative=relative, present=True, detail=detail)
