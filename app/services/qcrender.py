"""Write a GMod playermodel QC from named inputs.

Renders ``templates/valve/playermodel.qc`` with Jinja delimiters that do
not collide with Valve ``{ }`` blocks. This does not compile, and it
does not create DMX/VTF/VMT files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.templates import render_valve

IncludeAnims = Literal["m_anm.mdl", "f_anm.mdl"]
INCLUDE_ANIMS: tuple[IncludeAnims, ...] = ("m_anm.mdl", "f_anm.mdl")

_TEMPLATE_NAME = "playermodel.qc"


@dataclass(frozen=True, slots=True)
class PlayermodelQc:
    """Named inputs for one playermodel QC.

    Paths may be relative (emitted as-is) or absolute under the QC
    directory (made relative). ``model_name`` is the Source path under
    ``models/``, e.g. ``player/avatar/avatar.mdl``. ``include_anims`` is
    exactly one of ``m_anm.mdl`` or ``f_anm.mdl``.
    """

    model_name: str
    reference: str | Path
    physics: str | Path
    ragdoll: str | Path
    proportions: str | Path
    cdmaterials: str
    include_anims: IncludeAnims
    surfaceprop: str = "flesh"
    mass: float = 90.0
    illumposition: tuple[float, float, float] = (0.0, 0.0, 36.0)
    bbox: tuple[float, float, float, float, float, float] = (
        -40.0,
        -40.0,
        0.0,
        40.0,
        40.0,
        72.0,
    )
    rename_materials: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CarmsQc:
    """Named inputs for first-person C-arms QC.

    ``model_name`` is under ``models/``, e.g. ``weapons/c_arms_avatar.mdl``.
    """

    model_name: str
    arms: str | Path
    cdmaterials: str
    surfaceprop: str = "flesh"


class QCRenderService:
    """Write playermodel and C-arms ``.qc`` files into one output directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, spec: PlayermodelQc) -> Path:
        """Render ``spec`` and write ``<model stem>.qc``. Returns that path."""
        self._validate(spec)
        self.directory.mkdir(parents=True, exist_ok=True)
        dest = self.directory / Path(spec.model_name).with_suffix(".qc").name
        dest.write_text(self._render(spec), encoding="utf-8", newline="\n")
        return dest

    def write_carms(self, spec: CarmsQc) -> Path:
        """Render C-arms QC as ``<model stem>.qc``. Returns that path."""
        if not spec.model_name.strip():
            raise ValueError("model_name is required")
        if not spec.cdmaterials.strip():
            raise ValueError("cdmaterials is required")
        self.directory.mkdir(parents=True, exist_ok=True)
        dest = self.directory / Path(spec.model_name).with_suffix(".qc").name
        dest.write_text(
            render_valve(
                "carms.qc",
                model_name=_slash(spec.model_name),
                arms=self._rel(spec.arms),
                cdmaterials=_slash(spec.cdmaterials),
                surfaceprop=spec.surfaceprop,
            ),
            encoding="utf-8",
            newline="\n",
        )
        return dest

    def _validate(self, spec: PlayermodelQc) -> None:
        if not spec.model_name.strip():
            raise ValueError("model_name is required")
        if not spec.cdmaterials.strip():
            raise ValueError("cdmaterials is required")
        if spec.include_anims not in INCLUDE_ANIMS:
            raise ValueError(
                "include_anims must be m_anm.mdl or f_anm.mdl, "
                f"not {spec.include_anims!r}"
            )
        if len(spec.illumposition) != 3:
            raise ValueError("illumposition must be (x, y, z)")
        if len(spec.bbox) != 6:
            raise ValueError("bbox must be (min_x, min_y, min_z, max_x, max_y, max_z)")

    def _render(self, spec: PlayermodelQc) -> str:
        return render_valve(
            _TEMPLATE_NAME,
            model_name=_slash(spec.model_name),
            reference=self._rel(spec.reference),
            physics=self._rel(spec.physics),
            ragdoll=self._rel(spec.ragdoll),
            proportions=self._rel(spec.proportions),
            cdmaterials=_slash(spec.cdmaterials),
            include_anims=spec.include_anims,
            surfaceprop=spec.surfaceprop,
            mass=_fmt(spec.mass),
            illumposition=_vec(spec.illumposition),
            bbox=_bbox(spec.bbox),
            rename_materials=tuple(
                (old, new) for old, new in spec.rename_materials if old and new and old != new
            ),
        )

    def _rel(self, value: str | Path) -> str:
        path = Path(value)
        if path.is_absolute():
            try:
                path = path.relative_to(self.directory)
            except ValueError as exc:
                raise ValueError(
                    f"{value} is not under the QC directory {self.directory}"
                ) from exc
        return path.as_posix()


def _slash(value: str) -> str:
    return value.replace("\\", "/")


def _fmt(number: float) -> str:
    return f"{number:g}"


def _vec(values: tuple[float, float, float]) -> str:
    return " ".join(_fmt(part) for part in values)


def _bbox(values: tuple[float, float, float, float, float, float]) -> str:
    return " ".join(_fmt(part) for part in values)
