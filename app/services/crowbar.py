"""Open Crowbar 0.74 on an exported playermodel QC.

Windows .exe tools run natively on Windows and through Wine on macOS/Linux.
See ``app.services.windows_tools`` for host detection.

Place ``Crowbar.exe`` in ``data/crowbar/``
(https://github.com/ZeqMacaw/Crowbar/releases/tag/v0.74).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from srctools.vpk import VPK

from app.core.paths import data_dir
from app.core.process import CommandResult
from app.core.templates import render_valve
from app.services.deps.detect import gmod_tools_root
from app.services.windows_tools import (
    WindowsToolHost,
    crowbar_settings_file,
    detect_windows_tool_host,
    windows_gameinfo_path,
    windows_path,
)

_log = logging.getLogger(__name__)


def crowbar_dir() -> Path:
    return data_dir() / "crowbar"


def compiler_dir() -> Path:
    return data_dir() / "compiler"


def crowbar_exe() -> Path:
    return crowbar_dir() / "Crowbar.exe"


def studiomdl_exe() -> Path:
    return compiler_dir() / "bin" / "studiomdl.exe"


def find_viewer() -> Path | None:
    """Classic HLMV from a Source client/SDK bin, not GMod dedicated-server files.

    HLMV++ next to srcds ``tier0.dll`` / ``shaderapiempty.dll`` crashes in Wine
    (missing ``CommandLine`` / ``CommandLine_Tier0``).
    """
    game_root = gmod_tools_root(data_dir())
    compiler = studiomdl_exe().parent
    sdk = data_dir() / "sdk2013mp" / "bin"
    return _first_existing(
        sdk / "x64" / "hlmv.exe",
        sdk / "hlmv.exe",
        compiler / "hlmv.exe",
        game_root / "bin" / "hlmv.exe",
    )


def find_qc(out_dir: Path) -> Path | None:
    """First playermodel QC in ``out_dir``, preferring a leftover ``myavatar.qc``."""
    named = out_dir / "myavatar.qc"
    if named.is_file():
        return named
    matches = sorted(out_dir.glob("*.qc"))
    return matches[0] if matches else None


def sdk2013mp_root() -> Path:
    return data_dir() / "sdk2013mp"


def hlmv_game_dir() -> Path:
    """Tiny game dir inside the SDK so HLMV search paths resolve."""
    return sdk2013mp_root() / "pipeline"


def ensure_hlmv_scripts(game_dir: Path) -> Path:
    """Write ``scripts/game_sounds_manifest.txt`` so HLMV does not fatal on boot."""
    scripts = game_dir / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    manifest = scripts / "game_sounds_manifest.txt"
    if not manifest.is_file():
        manifest.write_text("game_sounds_manifest\n{\n}\n", encoding="utf-8")
    src_scripts = sdk2013mp_root() / "hl2" / "scripts"
    if not src_scripts.is_dir():
        src_scripts = gmod_tools_root(data_dir()) / "sourceengine" / "scripts"
    for name in (
        "surfaceproperties_manifest.txt",
        "surfaceproperties.txt",
        "surfaceproperties_hl2.txt",
    ):
        dest = scripts / name
        src = src_scripts / name
        if not dest.is_file() and src.is_file():
            shutil.copy2(src, dest)
    return manifest


def write_hlmv_gameinfo(
    game_dir: Path,
    garrysmod: Path,
    *,
    host: WindowsToolHost | None = None,
) -> Path:
    """SDK-native gameinfo that also mounts GMod materials/models.

    SDK HLMV treats ``|all_source_engine_paths|`` as the SDK root. Pointing
    ``-game`` at GMod dedicated-server ``garrysmod`` never mounts HL2 scripts,
    which is the ``game_sounds_manifest.txt`` fatal.
    """
    game_dir.mkdir(parents=True, exist_ok=True)
    ensure_hlmv_scripts(game_dir)
    path_of = host.gameinfo_path if host is not None else windows_gameinfo_path
    gmod = path_of(garrysmod)
    pipeline = path_of(game_dir)
    dest = game_dir / "gameinfo.txt"
    dest.write_text(
        render_valve("hlmv_gameinfo.txt", pipeline=pipeline, gmod=gmod),
        encoding="utf-8",
    )
    return dest


def stage_hlmv_assets(
    game_dir: Path,
    mdl: Path,
    garrysmod: Path,
    extra_material_roots: list[Path] | None = None,
    *,
    rewrite_mdl_slashes: bool = True,
) -> str:
    """Copy compiled MDL companions and VTFs onto ``|gameinfo_path|``.

    HLMV loads ``.vvd``/``.vtx`` next to the MDL, but VMTs only through the
    game filesystem. Returns the game-relative model path.
    """
    models_root = (garrysmod / "models").resolve()
    try:
        rel = mdl.resolve().relative_to(models_root)
    except ValueError as exc:
        raise FileNotFoundError(
            f"{mdl} is not under {models_root}"
        ) from exc
    dest_dir = game_dir / "models" / rel.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in mdl.parent.iterdir():
        if src.is_file():
            shutil.copy2(src, dest_dir / src.name)
    if rewrite_mdl_slashes:
        _forward_slash_mdl_paths(dest_dir / mdl.name)
    mat_rel = Path("materials") / "models" / rel.parent
    mat_src = garrysmod / mat_rel
    if mat_src.is_dir():
        dests = [game_dir / mat_rel]
        for root in extra_material_roots or []:
            dests.append(root / mat_rel)
        for dest in dests:
            dest.mkdir(parents=True, exist_ok=True)
            for src in mat_src.iterdir():
                if src.is_file():
                    shutil.copy2(src, dest / src.name)
    return str(Path("models") / rel).replace("\\", "/")


def write_hlmv_material_vpk(
    materials_dir: Path,
    dest_dir_vpk: Path,
    *,
    prefix: str,
) -> Path:
    """Pack VMTs/VTFs into an HL2-style ``*_dir.vpk`` HLMV will actually mount."""
    dest_dir_vpk.parent.mkdir(parents=True, exist_ok=True)
    stem = dest_dir_vpk.name.removesuffix("_dir.vpk")
    for old in dest_dir_vpk.parent.glob(f"{stem}*.vpk"):
        old.unlink()
    with VPK(str(dest_dir_vpk), mode="w") as pak:
        pak.add_folder(str(materials_dir), prefix=prefix.replace("\\", "/"))
    return dest_dir_vpk


def _forward_slash_mdl_paths(mdl: Path) -> None:
    """studiomdl writes ``$cdmaterials`` with backslashes; Wine Z: treats those as letters.

    Replace ``\\`` between path characters so HLMV looks for
    ``materials/models/player/...`` instead of a file named ``models\\player\\...``.
    """
    data = bytearray(mdl.read_bytes())
    changed = False
    for index, byte in enumerate(data):
        if byte != 0x5C:
            continue
        prev = data[index - 1] if index else 0
        nxt = data[index + 1] if index + 1 < len(data) else 0
        if _is_mdl_path_byte(prev) and (nxt == 0 or _is_mdl_path_byte(nxt)):
            data[index] = 0x2F
            changed = True
    if changed:
        mdl.write_bytes(data)


def _is_mdl_path_byte(byte: int) -> bool:
    return byte in (
        b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._"
    )


def preview_in_crowbar(out_dir: Path) -> Path:
    """Launch Crowbar's Compile tab on the export QC. Returns the QC path."""
    qc = find_qc(out_dir)
    if qc is None:
        raise FileNotFoundError(f"No .qc in {out_dir}")
    host = detect_windows_tool_host()
    exe = crowbar_exe()
    if not exe.is_file():
        raise FileNotFoundError(
            f"Crowbar.exe is missing at {exe}. Place Crowbar 0.74 there."
        )
    compiler = studiomdl_exe()
    if not compiler.is_file():
        raise FileNotFoundError(
            f"studiomdl.exe is missing at {compiler}. Copy the modified compiler there."
        )
    gameinfo = gmod_tools_root(data_dir()) / "garrysmod" / "gameinfo.txt"
    if not gameinfo.is_file():
        raise FileNotFoundError(
            "Garry's Mod gameinfo.txt is missing (run the deps wizard)."
        )
    _stop_crowbar()
    settings = crowbar_settings_file(host) if host.kind == "native" else None
    prefix = host.prefix if host.prefix is not None else Path(".")
    write_crowbar_settings(prefix, qc, compiler, gameinfo, host=host, dest=settings)
    command = host.argv(exe, qc)
    _log.info("crowbar preview: %s", " ".join(command))
    subprocess.Popen(
        command,
        env=host.env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return qc


def write_crowbar_settings(
    prefix: Path,
    qc: Path,
    compiler: Path,
    gameinfo: Path,
    *,
    host: WindowsToolHost | None = None,
    dest: Path | None = None,
) -> Path:
    """Write a one-game Crowbar settings file so Compile opens our QC."""
    dest = dest or _settings_path(prefix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    game_root = gmod_tools_root(data_dir())
    app = game_root / "srcds.exe"
    packer = _first_existing(game_root / "bin" / "gmad.exe")
    viewer = find_viewer()
    view_gameinfo = None
    hl2mp_info = sdk2013mp_root() / "hl2mp" / "gameinfo.txt"
    if hl2mp_info.is_file():
        view_gameinfo = hl2mp_info
    dest.write_text(
        _settings_xml(
            qc=qc,
            compiler=compiler,
            gameinfo=gameinfo,
            app=app if app.is_file() else compiler,
            viewer=viewer,
            packer=packer,
            view_gameinfo=view_gameinfo,
            host=host,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return dest


def _settings_path(prefix: Path) -> Path:
    users = prefix / "drive_c" / "users"
    existing = sorted(users.glob("*/AppData/Roaming/ZeqMacaw/Crowbar 0.74"))
    if existing:
        return existing[0] / "Crowbar Settings.xml"
    for name in ("crossover", "steamuser", os.environ.get("USER", "user")):
        candidate = users / name
        if candidate.is_dir():
            return (
                candidate
                / "AppData"
                / "Roaming"
                / "ZeqMacaw"
                / "Crowbar 0.74"
                / "Crowbar Settings.xml"
            )
    return (
        users
        / "crossover"
        / "AppData"
        / "Roaming"
        / "ZeqMacaw"
        / "Crowbar 0.74"
        / "Crowbar Settings.xml"
    )


def _tool_path(path: Path, host: WindowsToolHost | None) -> str:
    return host.tool_path(path) if host is not None else windows_path(path)


def _settings_xml(
    *,
    qc: Path,
    compiler: Path,
    gameinfo: Path,
    app: Path,
    viewer: Path | None,
    packer: Path | None,
    view_gameinfo: Path | None = None,
    host: WindowsToolHost | None = None,
) -> str:
    viewer_path = _tool_path(viewer, host) if viewer else ""
    packer_path = _tool_path(packer, host) if packer else _tool_path(compiler, host)
    games = [
        {
            "name": "Garry's Mod (pipeline)",
            "gameinfo": _tool_path(gameinfo, host),
            "app": _tool_path(app, host),
            "compiler": _tool_path(compiler, host),
            "viewer": viewer_path,
            "packer": packer_path,
        }
    ]
    view_index = "0"
    if view_gameinfo is not None:
        games.append(
            {
                "name": "HLMV (SDK 2013)",
                "gameinfo": _tool_path(view_gameinfo, host),
                "app": _tool_path(app, host),
                "compiler": _tool_path(compiler, host),
                "viewer": viewer_path,
                "packer": packer_path,
            }
        )
        view_index = "1"
    return render_valve(
        "crowbar_settings.xml",
        games=games,
        view_index=view_index,
        qc_path=_tool_path(qc, host),
    )


def ensure_hl2mp_game_searchpath(gameinfo: Path) -> None:
    """Materials resolve on the GAME path; stock hl2mp only mounts |gameinfo_path| as MOD."""
    text = gameinfo.read_text(encoding="utf-8")
    if "game\t\t\t\t|gameinfo_path|." in text:
        return
    marker = "mod+mod_write+default_write_path\t\t|gameinfo_path|.\n"
    if marker not in text:
        return
    gameinfo.write_text(
        text.replace(
            marker,
            marker + "\t\t\tgame\t\t\t\t|gameinfo_path|.\n",
            1,
        ),
        encoding="utf-8",
    )


def pack_hlmv_custom_vpk(
    folder: Path,
    host: WindowsToolHost | None = None,
) -> Path:
    """SDK ``vpk.exe`` writes VPK v2; srctools can only write v1, which HLMV ignores."""
    host = host or detect_windows_tool_host()
    exe = _first_existing(
        sdk2013mp_root() / "bin" / "x64" / "vpk.exe",
        sdk2013mp_root() / "bin" / "vpk.exe",
    )
    if exe is None:
        raise FileNotFoundError("vpk.exe is missing from Source SDK Base 2013 MP")
    dest = folder.with_suffix(".vpk")
    if dest.is_file():
        dest.unlink()
    result = subprocess.run(
        host.argv(exe, folder),
        cwd=str(folder.parent),
        env=host.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not dest.is_file():
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "vpk.exe failed")
    return dest


def compile_qc(qc: Path) -> CommandResult:
    """Compile a playermodel QC with ``studiomdl.exe`` into garrysmod."""
    from app.services.compile import CompileService

    return CompileService().compile(qc).log


def open_in_hlmv(mdl: Path) -> Path:
    """Open the compiled MDL in SDK HLMV. Returns the viewer exe."""
    if not mdl.is_file():
        raise FileNotFoundError(f"No compiled MDL at {mdl}")
    host = detect_windows_tool_host()
    viewer = find_viewer()
    if viewer is None:
        raise FileNotFoundError(
            "HLMV is not installed (expected data/sdk2013mp/bin/x64/hlmv.exe)"
        )
    sdk = sdk2013mp_root()
    hl2mp = sdk / "hl2mp"
    if not (hl2mp / "gameinfo.txt").is_file():
        raise FileNotFoundError(
            f"Source SDK Base 2013 MP is missing hl2mp at {hl2mp}."
        )
    ensure_hl2mp_game_searchpath(hl2mp / "gameinfo.txt")
    garrysmod = gmod_tools_root(data_dir()) / "garrysmod"
    custom = hl2mp / "custom" / "pipeline"
    model_rel = stage_hlmv_assets(
        hl2mp,
        mdl,
        garrysmod,
        extra_material_roots=[custom],
        rewrite_mdl_slashes=host.uses_wine,
    )
    mat_src = garrysmod / "materials" / Path(model_rel).parent
    if mat_src.is_dir():
        pack_hlmv_custom_vpk(custom, host)
    staged = hl2mp / Path(model_rel)
    _stop_hlmv()
    command = host.argv(viewer, "-olddialogs", "-game", hl2mp, staged)
    _log.info("hlmv preview: %s", " ".join(command))
    subprocess.Popen(
        command,
        cwd=str(viewer.parent),
        env=host.env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return viewer


def _stop_crowbar() -> None:
    """Kill a running Crowbar so it cannot overwrite settings on exit."""
    _stop_named("Crowbar.exe")


def _stop_hlmv() -> None:
    """Dismiss a stuck HLMV fatal-error dialog before relaunch."""
    _stop_named("hlmv.exe")


def _stop_named(name: str) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    subprocess.run(
        ["pkill", "-9", "-f", name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        result = subprocess.run(
            ["pgrep", "-f", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return
        time.sleep(0.1)


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None
