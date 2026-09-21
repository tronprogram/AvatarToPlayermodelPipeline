"""Compile a playermodel QC with ``studiomdl.exe``.

The compiler is the BobmacU/SFM ``studiomdl.exe`` (weight cull 0.0001).
``WindowsToolHost`` runs it natively on Windows and under Wine elsewhere.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.paths import data_dir
from app.core.process import CommandResult, run_command
from app.services.deps.detect import gmod_tools_root
from app.services.windows_tools import WindowsToolHost, detect_windows_tool_host

_MODELNAME = re.compile(r'\$modelname\s+"([^"]+)"', re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CompiledModel:
    """studiomdl output under ``garrysmod/models/``.

    ``model_name`` is the QC ``$modelname`` (forward slashes, no ``models/``
    prefix). ``mdl`` is that file on disk; ``vtx`` / ``vvd`` / ``phy`` are
    siblings when studiomdl wrote them.
    """

    mdl: Path
    log: CommandResult
    model_name: str
    vtx: Path | None
    vvd: Path | None
    phy: Path | None


class CompileService:
    """Run ``studiomdl.exe -game garrysmod`` through the platform host."""

    def __init__(self, host: WindowsToolHost | None = None) -> None:
        self.host = host

    def compile(self, qc: Path) -> CompiledModel:
        """Compile ``qc`` into the GMod tools ``models/`` tree.

        Returns ``CompiledModel``. Raises ``RuntimeError`` if studiomdl
        exits non-zero (message is the compiler log).
        """
        if not qc.is_file():
            raise FileNotFoundError(f"No QC at {qc}")
        host = self.host or detect_windows_tool_host()
        compiler = studiomdl_exe()
        if not compiler.is_file():
            raise FileNotFoundError(
                f"Modified SFM studiomdl.exe is missing at {compiler}."
            )
        game = gmod_tools_root(data_dir()) / "garrysmod"
        if not (game / "gameinfo.txt").is_file():
            raise FileNotFoundError(f"Missing gameinfo.txt at {game}")
        result = run_command(
            host.argv(compiler, "-game", game, "-nop4", "-verbose", qc),
            cwd=qc.parent,
            env=host.env(),
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.output or f"studiomdl exited {result.returncode}")
        model_name = modelname_from_qc(qc)
        mdl = game / "models" / Path(*model_name.split("/"))
        return CompiledModel(
            mdl=mdl,
            log=result,
            model_name=model_name,
            vtx=_first_existing(
                mdl.with_name(mdl.stem + ".dx90.vtx"),
                mdl.with_name(mdl.stem + ".dx80.vtx"),
                mdl.with_suffix(".vtx"),
            ),
            vvd=_existing(mdl.with_suffix(".vvd")),
            phy=_existing(mdl.with_suffix(".phy")),
        )


def compiler_dir() -> Path:
    return data_dir() / "compiler"


def template_compiler_dir() -> Path:
    return data_dir() / "_gmod_port_template" / "Modified Complier"


def ensure_modified_compiler() -> Path:
    """BobmacU/SFM ``studiomdl.exe`` (weight cull 0.0001). Copies the template tree once."""
    from app.services.deps.detect import find_modified_compiler
    from app.services.user_settings import load_settings, path_or_none

    found = find_modified_compiler(data_dir(), path_or_none(load_settings().compiler))
    if found is not None:
        return found
    dest = compiler_dir() / "bin" / "studiomdl.exe"
    src_root = template_compiler_dir()
    src = src_root / "bin" / "studiomdl.exe"
    if src.is_file():
        shutil.copytree(src_root, compiler_dir(), dirs_exist_ok=True)
    if dest.is_file():
        return dest
    raise FileNotFoundError(
        f"Modified SFM studiomdl.exe is missing at {dest}. "
        "Run Setup to fetch BobmacU's Modified Complier, or copy it into data/compiler/."
    )


def studiomdl_exe() -> Path:
    """Compile with the BobmacU/SFM studiomdl, not stock 2013 MP."""
    return ensure_modified_compiler()


def modelname_from_qc(qc: Path) -> str:
    """``$modelname`` as a forward-slash Source path under ``models/``."""
    match = _MODELNAME.search(qc.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{qc} has no $modelname")
    return match.group(1).replace("\\", "/")


def _existing(path: Path) -> Path | None:
    return path if path.is_file() else None


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        found = _existing(path)
        if found is not None:
            return found
    return None
