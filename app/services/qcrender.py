"""Write a GMod playermodel QC from named inputs.

Renders ``templates/qc/playermodel.qc`` with Jinja delimiters that do
not collide with Valve ``{ }`` blocks. This does not compile, and it
does not create DMX/VTF/VMT files.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.core.paths import resource_root

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


class QCRenderService:
    """Write a playermodel ``.qc`` into one output directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, spec: PlayermodelQc) -> Path:
        """Render ``spec`` and write ``<model stem>.qc``. Returns that path."""
        self._validate(spec)
        self.directory.mkdir(parents=True, exist_ok=True)
        dest = self.directory / Path(spec.model_name).with_suffix(".qc").name
        dest.write_text(self._render(spec), encoding="utf-8", newline="\n")
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
        return _environment().get_template(_TEMPLATE_NAME).render(
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


def _template_dir() -> Path:
    path = resource_root() / "templates" / "qc"
    if (path / _TEMPLATE_NAME).is_file():
        return path
    bundled = resource_root() / "app" / "templates" / "qc"
    if (bundled / _TEMPLATE_NAME).is_file():
        return bundled
    raise FileNotFoundError(f"Missing QC template {_TEMPLATE_NAME} in {path}")


def _environment() -> Environment:
    """QC-only Jinja env: ``[[ var ]]`` / ``[% %]``, Valve braces stay literal."""
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=False,
        undefined=StrictUndefined,
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _slash(value: str) -> str:
    return value.replace("\\", "/")


def _fmt(number: float) -> str:
    return f"{number:g}"


def _vec(values: tuple[float, float, float]) -> str:
    return " ".join(_fmt(part) for part in values)


def _bbox(values: tuple[float, float, float, float, float, float]) -> str:
    return " ".join(_fmt(part) for part in values)
