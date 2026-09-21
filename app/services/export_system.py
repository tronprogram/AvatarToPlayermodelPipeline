"""Avatar → Source playermodel export.

Public methods return named dataclasses (not tuples or string-keyed dicts)
so the payload is visible from the type. The happy path is
``ExportSystemService.export_playermodel`` → ``PlayermodelBuild``.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Literal

from pygltflib import GLTF2

from app.core.paths import data_dir, resource_root
from app.core.process import PYTHON_ENV_KEYS, command_env, run_command
from app.services.addon_package import (
    AddonMetadata,
    AddonPackageService,
    AddonSpec,
    GmodAddon,
)
from app.services.compile import CompiledModel, CompileService
from app.services.crowbar import find_qc
from app.services.deps.detect import find_blender_bin, gmod_tools_root
from app.services.playerlua import PlayerLuaService, PlayermodelLua, source_slug
from app.services.qcrender import CarmsQc, PlayermodelQc, QCRenderService
from app.services.source_space import align_to_source
from app.services.valvebiped import apply_valvebiped
from app.services.valvetextures import (
    EmbeddedTexture,
    SourceMaterialSpec,
    ValveMaterial,
    ValveTextureService,
    plan_materials,
)

BindGender = Literal["male", "female"]

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceDmxFiles:
    """Files written by headless Blender Source Tools (DMX binary 2 / model 1)."""

    reference: Path  # visual meshes + ValveBiped armature
    physics: Path  # 15 ragdoll capsules skinned to those bones
    ragdoll: Path  # 1-frame rest clip for ACT_DIERAGDOLL
    proportions: Path  # custom-bind clip for the size-proportion subtract
    size_reference: Path  # HL2 locations + custom rotations
    arms: Path  # first-person C-arms (arm-weighted verts only)
    aligned_glb: Path  # staged GLB Blender imported


@dataclass(frozen=True, slots=True)
class PlayermodelIdentity:
    """Stable names for one playermodel across QC, materials, Lua, and the addon.

    Example for display name ``My Avatar``:

    * ``slug`` — ``my_avatar``
    * ``model_name`` — QC ``$modelname`` (``player/my_avatar/my_avatar.mdl``)
    * ``cdmaterials`` — folder under ``materials/`` (``models/player/my_avatar``)
    * ``model_path`` — Lua path starting at ``models/``
    * ``hands_name`` / ``hands_path`` — C-arms ``$modelname`` and Lua path
    """

    display_name: str
    slug: str
    model_name: str
    cdmaterials: str
    model_path: str
    hands_name: str
    hands_path: str


@dataclass(frozen=True, slots=True)
class PlayermodelBuild:
    """Result of ``export_playermodel``: work files plus the drop-in addon.

    ``staged_materials`` is ``garrysmod/materials/<cdmaterials>``.
    ``compiled.mdl`` / ``carms.mdl`` live under ``garrysmod/models/``.
    ``addon.root`` is ready to copy into ``garrysmod/addons/``.
    """

    identity: PlayermodelIdentity
    dmx: SourceDmxFiles
    materials: tuple[ValveMaterial, ...]
    staged_materials: Path
    qc: Path
    compiled: CompiledModel
    carms_qc: Path
    carms: CompiledModel
    addon: GmodAddon


def _blender_script() -> Path:
    return resource_root() / "app" / "blender" / "export_playermodel.py"


def _bind_pose_smd(gender: BindGender) -> Path:
    folder = "Male" if gender == "male" else "Female"
    template = (
        data_dir()
        / "_gmod_port_template"
        / "Proportion Trick"
        / "Bind Pose Animations"
        / folder
        / "proportions.smd"
    )
    if template.is_file():
        return template
    return resource_root() / "app" / "blender" / "proportions" / f"{gender}.smd"


def _collision_dmx() -> Path:
    return resource_root() / "app" / "blender" / "collision" / "Collision Model.dmx"


def _carms_ref_dmx() -> Path:
    return (
        data_dir()
        / "_gmod_port_template"
        / "Custom arms"
        / "Default C-arm"
        / "c_arms_citizen.dmx"
    )


class ExportSystemService:
    """Orchestrate one GLB through DMX, VTF, compile, C-arms, and addon package.

    ``model_path`` is the input ``.glb``. Construct once and either call
    ``export_playermodel`` or the individual stage methods (same return types
    the facade stores on ``PlayermodelBuild``).
    """

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
        """``translate_bones``, then ~72-unit height on the floor.

        Mutates and returns the same GLTF2. Scene roots are scaled in glTF
        Y-up; Blender's importer converts that to Z-up. Facing is not
        yawed to +X — Collision Model I and Source Tools use −Y as front.
        """
        return align_to_source(self.translate_bones(gltf))

    def export_source_dmx(
        self,
        out_dir: Path,
        gltf: GLTF2 | None = None,
        *,
        gender: BindGender = "male",
    ) -> SourceDmxFiles:
        """Write reference, physics, ragdoll, proportions, and C-arms DMX via Blender."""
        out_dir = out_dir.resolve()
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
            "--collision",
            str(_collision_dmx()),
        ]
        carms_ref = _carms_ref_dmx()
        if carms_ref.is_file():
            command.extend(["--carms-ref", str(carms_ref)])
        _log.info("blender export: %s", " ".join(command))
        result = run_command(command, env=command_env(drop=PYTHON_ENV_KEYS))
        if result.stdout:
            _log.info("%s", result.stdout)
        log = f"{result.stdout}\n{result.stderr}"
        if "Traceback (most recent call last)" in log:
            raise RuntimeError(result.output or "Blender export failed")

        files = SourceDmxFiles(
            reference=out_dir / "reference.dmx",
            physics=out_dir / "physics.dmx",
            ragdoll=out_dir / "anims" / "ragdoll.dmx",
            proportions=out_dir / "anims" / "proportions.dmx",
            size_reference=out_dir / "anims" / "size_reference.dmx",
            arms=out_dir / "arms.dmx",
            aligned_glb=staged,
        )
        missing = [
            name
            for name, path in (
                ("reference", files.reference),
                ("physics", files.physics),
                ("ragdoll", files.ragdoll),
                ("proportions", files.proportions),
                ("size_reference", files.size_reference),
                ("arms", files.arms),
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

    def plan_valve_materials(self, gltf: GLTF2 | None = None) -> list[SourceMaterialSpec]:
        """GLB materials → Source-legal stems + embedded albedo bytes."""
        if gltf is None:
            gltf = GLTF2().load(str(self.model_path))
        if gltf.binary_blob() is None:
            gltf.buffers_to_binary_blob()
        return plan_materials(gltf, gltf.binary_blob())

    def get_embedded_textures(self) -> list[EmbeddedTexture]:
        """Albedo images from ``plan_valve_materials()``, named by Source stem."""
        textures: list[EmbeddedTexture] = []
        seen: set[str] = set()
        for spec in self.plan_valve_materials():
            if spec.source_name in seen:
                continue
            seen.add(spec.source_name)
            ext = ".jpg" if spec.mime_type == "image/jpeg" else ".png"
            textures.append(
                EmbeddedTexture(
                    filename=spec.source_name + ext,
                    data=spec.data,
                    mime_type=spec.mime_type,
                )
            )
        return textures

    def export_valve_textures(
        self,
        directory: Path,
        textures: list[EmbeddedTexture | SourceMaterialSpec] | None = None,
        *,
        cdmaterials: str = "",
    ) -> list[ValveMaterial]:
        """Write VTF + VMT pairs into ``directory``.

        Uses ``plan_valve_materials()`` when ``textures`` is omitted.
        """
        if textures is None:
            textures = self.plan_valve_materials()
        return ValveTextureService(directory).convert(
            textures, cdmaterials=cdmaterials
        )

    def write_playermodel_qc(self, out_dir: Path, spec: PlayermodelQc) -> Path:
        """Write the compile QC into ``out_dir``."""
        return QCRenderService(out_dir).write(spec)

    def write_carms_qc(self, out_dir: Path, spec: CarmsQc) -> Path:
        """Write the C-arms compile QC into ``out_dir``."""
        return QCRenderService(out_dir).write_carms(spec)

    def compile_qc(self, qc: Path) -> CompiledModel:
        """Compile ``qc`` with studiomdl (native on Windows, Wine elsewhere)."""
        return CompileService().compile(qc)

    def write_player_lua(self, out_dir: Path, spec: PlayermodelLua) -> Path:
        """Write autorun Lua (``AddValidModel``, and ``AddValidHands`` when set)."""
        return PlayerLuaService(out_dir).write(spec)

    def package_addon(self, dest: Path, spec: AddonSpec) -> GmodAddon:
        """Write ``addon.json``, Lua, models, and materials into ``dest``."""
        return AddonPackageService(dest).write(spec)

    def playermodel_qc(
        self,
        dmx: SourceDmxFiles,
        identity: PlayermodelIdentity,
        *,
        gender: BindGender = "male",
        rename_materials: tuple[tuple[str, str], ...] = (),
    ) -> PlayermodelQc:
        """QC spec that points at the DMX files we just wrote."""
        return PlayermodelQc(
            model_name=identity.model_name,
            reference=dmx.reference,
            physics=dmx.physics,
            ragdoll=dmx.ragdoll,
            proportions=dmx.proportions,
            size_reference=dmx.size_reference,
            cdmaterials=identity.cdmaterials,
            include_anims="f_anm.mdl" if gender == "female" else "m_anm.mdl",
            rename_materials=rename_materials,
        )

    def carms_qc(
        self,
        dmx: SourceDmxFiles,
        identity: PlayermodelIdentity,
    ) -> CarmsQc:
        """C-arms QC spec pointing at ``arms.dmx``."""
        return CarmsQc(
            model_name=identity.hands_name,
            arms=dmx.arms,
            cdmaterials=identity.cdmaterials,
        )

    def stage_valve_materials(
        self,
        source: Path,
        cdmaterials: str,
        *,
        garrysmod: Path | None = None,
    ) -> Path:
        """Copy VTF/VMT files into ``garrysmod/materials/<cdmaterials>``.

        That folder is the shared tree compile, HLMV, and the addon all read.
        """
        if not source.is_dir():
            raise FileNotFoundError(f"No materials directory at {source}")
        dest = garrysmod_dir(garrysmod) / "materials" / Path(*_slash(cdmaterials).split("/"))
        dest.mkdir(parents=True, exist_ok=True)
        copied = 0
        for src in source.iterdir():
            if src.is_file() and src.suffix.lower() in {".vtf", ".vmt"}:
                shutil.copy2(src, dest / src.name)
                copied += 1
        if copied == 0:
            raise FileNotFoundError(f"No VTF/VMT files in {source}")
        return dest

    def export_playermodel(
        self,
        work_dir: Path,
        *,
        display_name: str,
        gender: BindGender = "male",
        addon_dir: Path | None = None,
        garrysmod: Path | None = None,
        author: str = "",
        description: str = "",
        tags: tuple[str, ...] = ("fun", "roleplay"),
        on_stage: Callable[[str], None] | None = None,
    ) -> PlayermodelBuild:
        """Run DMX → VTF → stage materials → QC → compile PM + C-arms → addon.

        ``work_dir`` keeps the intermediate GLB/DMX/QC/VTF copy.
        Materials are also copied into ``garrysmod/materials/<cdmaterials>``.
        The addon lands in ``addon_dir`` or ``data/addons/<slug>``.
        """
        def stage(name: str) -> None:
            if on_stage is not None:
                on_stage(name)

        identity = playermodel_identity(display_name)
        work_dir = work_dir.resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        stage("rig        bones lined up")
        stage("mesh       exporting Source DMX")
        dmx = self.export_source_dmx(work_dir, gender=gender)
        materials_dir = work_dir / "materials"
        stage("textures   skins ready")
        materials = self.export_valve_textures(
            materials_dir, cdmaterials=identity.cdmaterials
        )
        staged = self.stage_valve_materials(
            materials_dir, identity.cdmaterials, garrysmod=garrysmod
        )
        qc = self.write_playermodel_qc(
            work_dir,
            self.playermodel_qc(dmx, identity, gender=gender),
        )
        stage("compile    playermodel")
        compiled = self.compile_qc(qc)
        carms_qc = self.write_carms_qc(work_dir, self.carms_qc(dmx, identity))
        stage("compile    first-person hands")
        carms = self.compile_qc(carms_qc)
        dest = addon_dir or (data_dir() / "addons" / identity.slug)
        stage("pack       addon folder")
        addon = self.package_addon(
            dest,
            AddonSpec(
                metadata=AddonMetadata(
                    title=display_name,
                    author=author,
                    description=description,
                    tags=tags,
                ),
                display_name=identity.display_name,
                model_path=identity.model_path,
                mdl=compiled.mdl,
                materials=staged,
                cdmaterials=identity.cdmaterials,
                hands_path=identity.hands_path,
                hands_mdl=carms.mdl,
            ),
        )
        return PlayermodelBuild(
            identity=identity,
            dmx=dmx,
            materials=tuple(materials),
            staged_materials=staged,
            qc=qc,
            compiled=compiled,
            carms_qc=carms_qc,
            carms=carms,
            addon=addon,
        )


def playermodel_identity(display_name: str) -> PlayermodelIdentity:
    """Derive Source paths from the in-game display name."""
    slug = source_slug(display_name)
    model_name = f"player/{slug}/{slug}.mdl"
    hands_name = f"weapons/c_arms_{slug}.mdl"
    return PlayermodelIdentity(
        display_name=display_name.strip(),
        slug=slug,
        model_name=model_name,
        cdmaterials=f"models/player/{slug}",
        model_path=f"models/{model_name}",
        hands_name=hands_name,
        hands_path=f"models/{hands_name}",
    )


def garrysmod_dir(garrysmod: Path | None = None) -> Path:
    """GMod tools ``garrysmod`` folder (models + materials)."""
    if garrysmod is not None:
        return garrysmod
    root = gmod_tools_root(data_dir()) / "garrysmod"
    if not (root / "gameinfo.txt").is_file():
        raise FileNotFoundError(
            f"Garry's Mod gameinfo.txt is missing at {root} (run the deps wizard)."
        )
    return root


def _slash(value: str) -> str:
    return value.replace("\\", "/")


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
    """List the DMX/VTF/VMT/QC files a GMod package would consume.

    Returns ``ExportPreview`` with one ``ExportAsset`` per expected work
    file (including ``arms.dmx``) plus a materials count row.
    """
    vtf_count = len(list((out_dir / "materials").glob("*.vtf")))
    vmt_count = len(list((out_dir / "materials").glob("*.vmt")))
    assets = (
        _file_asset(out_dir, "aligned.glb", "Aligned GLB"),
        _file_asset(out_dir, "reference.dmx", "Reference mesh"),
        _file_asset(out_dir, "physics.dmx", "Ragdoll capsules"),
        _file_asset(out_dir, "arms.dmx", "C-arms mesh"),
        _file_asset(out_dir, "anims/ragdoll.dmx", "Ragdoll sequence"),
        _file_asset(out_dir, "anims/proportions.dmx", "Custom-bind proportion clip"),
        _file_asset(out_dir, "anims/size_reference.dmx", "HL2 size-reference clip"),
        _qc_asset(out_dir),
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


def _qc_asset(out_dir: Path) -> ExportAsset:
    qc = find_qc(out_dir)
    if qc is None:
        return ExportAsset(label="Playermodel QC", relative="*.qc", present=False, detail="")
    return _file_asset(out_dir, qc.name, "Playermodel QC")
