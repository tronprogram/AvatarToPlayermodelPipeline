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


def find_viewer() -> Path | None:
    """HLMV++ next to the modified compiler, then leftover SDK copies."""
    from app.services.deps.detect import find_hlmvplusplus
    from app.services.user_settings import load_settings, path_or_none

    found = find_hlmvplusplus(data_dir(), path_or_none(load_settings().hlmvplusplus))
    if found is not None:
        return found
    game_root = gmod_tools_root(data_dir())
    return _first_existing(
        compiler_dir() / "bin" / "hlmvplusplus.exe",
        data_dir() / "sdk2013mp" / "bin" / "hlmvplusplus.exe",
        game_root / "bin" / "win64" / "hlmvplusplus.exe",
        game_root / "bin" / "hlmv.exe",
    )


def _hlmv_runtime() -> Path:
    """Copy HLMV++ beside compiler DLLs so Windows can load tier0/engine."""
    viewer = find_viewer()
    if viewer is None:
        raise FileNotFoundError(
            "HLMV++ is not installed. Run Setup and keep HLMV++ checked."
        )
    dest_dir = compiler_dir() / "bin"
    dest = dest_dir / "hlmvplusplus.exe"
    if dest_dir.is_dir() and viewer.resolve() != dest.resolve():
        shutil.copy2(viewer, dest)
        dll = viewer.with_name("hlmvplusplus.dll")
        if dll.is_file():
            shutil.copy2(dll, dest_dir / "hlmvplusplus.dll")
        return dest
    return viewer


def find_qc(out_dir: Path) -> Path | None:
    """First playermodel QC in ``out_dir``, preferring a leftover ``myavatar.qc``."""
    named = out_dir / "myavatar.qc"
    if named.is_file():
        return named
    matches = sorted(out_dir.glob("*.qc"))
    return matches[0] if matches else None


def sdk2013mp_root() -> Path:
    from app.services.deps.detect import find_sdk2013mp
    from app.services.user_settings import load_settings, path_or_none

    found = find_sdk2013mp(data_dir(), path_or_none(load_settings().sdk2013))
    return found if found is not None else data_dir() / "sdk2013mp"


def hlmv_game_dir() -> Path:
    """Tiny game dir so HLMV++ search paths resolve without Source SDK 2013."""
    return data_dir() / "hlmvplusplus" / "game"


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


_INCLUDE_ANIM_NAMES = ("m_anm.mdl", "m_anm.ani", "f_anm.mdl", "f_anm.ani")


def _gmod_dir_vpk() -> Path | None:
    """Loose GMod ``garrysmod_dir.vpk`` that still packs ``models/m_anm``."""
    program_files = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    candidates = (
        program_files / "Steam" / "steamapps" / "common" / "GarrysMod" / "garrysmod" / "garrysmod_dir.vpk",
        gmod_tools_root(data_dir()) / "garrysmod" / "garrysmod_dir.vpk",
    )
    return next((path for path in candidates if path.is_file()), None)


def _read_include_anim(name: str) -> bytes | None:
    cache = data_dir() / "sdk2013mp" / "models" / name
    if cache.is_file():
        return cache.read_bytes()
    tools = gmod_tools_root(data_dir()) / "garrysmod" / "models" / name
    if tools.is_file():
        return tools.read_bytes()
    vpk_path = _gmod_dir_vpk()
    if vpk_path is None:
        return None
    needle = f"models/{name}"
    for info in VPK(vpk_path):
        if info.filename.replace("\\", "/") == needle:
            return info.read()
    return None


def ensure_hlmv_include_anims(*dest_roots: Path) -> list[Path]:
    """Copy GMod ``m_anm`` / ``f_anm`` into each HLMV game ``models/``.

    ``$includemodel "m_anm.mdl"`` is resolved on the viewer ``-game`` path,
    which is ``hl2mp``, not the SDK root.
    """
    written: list[Path] = []
    payloads: dict[str, bytes] = {}
    for root in dest_roots:
        models = root / "models"
        models.mkdir(parents=True, exist_ok=True)
        for name in _INCLUDE_ANIM_NAMES:
            dest = models / name
            if dest.is_file() and dest.stat().st_size > 0:
                written.append(dest)
                continue
            if name not in payloads:
                data = _read_include_anim(name)
                if data is None:
                    continue
                payloads[name] = data
            dest.write_bytes(payloads[name])
            written.append(dest)
            _log.info("hlmv include anim: %s", dest)
    return written


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
            f"Modified SFM studiomdl.exe is missing at {compiler}."
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


def open_in_hlmv(mdl: Path, *, stop_existing: bool = True) -> Path:
    """Open the compiled MDL in HLMV++. Returns the viewer exe."""
    if not mdl.is_file():
        raise FileNotFoundError(f"No compiled MDL at {mdl}")
    host = detect_windows_tool_host()
    viewer = _hlmv_runtime()
    garrysmod = gmod_tools_root(data_dir()) / "garrysmod"
    if not (garrysmod / "gameinfo.txt").is_file():
        raise FileNotFoundError(
            f"Garry's Mod gameinfo.txt is missing at {garrysmod} (run Setup)."
        )
    game_dir = hlmv_game_dir()
    write_hlmv_gameinfo(game_dir, garrysmod, host=host)
    ensure_hlmv_include_anims(game_dir, garrysmod)
    custom = game_dir / "custom" / "pipeline"
    model_rel = stage_hlmv_assets(
        game_dir,
        mdl,
        garrysmod,
        extra_material_roots=[custom],
        rewrite_mdl_slashes=host.uses_wine,
    )
    mat_src = garrysmod / "materials" / Path(model_rel).parent
    if mat_src.is_dir():
        pack_hlmv_custom_vpk(custom, host)
    staged = game_dir / Path(model_rel)
    if stop_existing:
        _stop_hlmv()
    command = host.argv(viewer, "-olddialogs", "-game", game_dir, staged)
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
    _stop_named("hlmvplusplus.exe")
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
