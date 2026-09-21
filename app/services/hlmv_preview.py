"""Launch HLMV++ on a compiled playermodel.

Windows .exe tools run natively on Windows and through Wine on macOS/Linux.
See ``app.services.windows_tools`` for host detection.
"""

from __future__ import annotations

import binascii
import hashlib
import logging
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

from srctools.vpk import VPK

from app.core.paths import data_dir
from app.core.templates import render_valve
from app.services.compile import compiler_dir
from app.services.deps.detect import gmod_tools_root
from app.services.windows_tools import (
    WindowsToolHost,
    detect_windows_tool_host,
    windows_gameinfo_path,
)

_log = logging.getLogger(__name__)


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


def pack_hlmv_custom_vpk(folder: Path) -> Path | None:
    """Pack ``folder`` as a single-file VPK v2 next to it.

    HLMV mounts ``custom/*.vpk`` and ignores loose materials and VPK v1.
    srctools can read v2 but cannot write it. Returns None when ``folder``
    has no files.
    """
    if not folder.is_dir() or not any(path.is_file() for path in folder.rglob("*")):
        return None
    dest = folder.with_suffix(".vpk")
    for old in folder.parent.glob(f"{folder.name}*.vpk"):
        old.unlink()
    _write_vpk_v2(folder, dest)
    return dest


def _write_vpk_v2(folder: Path, dest: Path) -> None:
    """Write one v2 archive with file bytes embedded after the directory tree."""
    tree = bytearray()
    payload = bytearray()
    entries = _vpk_entries(folder)
    for ext in sorted(entries):
        _vpk_cstring(tree, ext)
        for directory in sorted(entries[ext]):
            _vpk_cstring(tree, directory)
            for name in sorted(entries[ext][directory]):
                data = entries[ext][directory][name]
                _vpk_cstring(tree, name)
                tree += struct.pack(
                    "<IHHIIH",
                    binascii.crc32(data) & 0xFFFFFFFF,
                    0,
                    0x7FFF,
                    len(payload),
                    len(data),
                    0xFFFF,
                )
                payload += data
            tree += b"\x00"
        tree += b"\x00"
    tree += b"\x00"
    header = struct.pack(
        "<IIIIIII",
        0x55AA1234,
        2,
        len(tree),
        len(payload),
        0,
        48,
        0,
    )
    tree_md5 = hashlib.md5(tree).digest()
    chunk_md5 = hashlib.md5(b"").digest()
    prefix = header + bytes(tree) + bytes(payload) + tree_md5 + chunk_md5
    dest.write_bytes(prefix + hashlib.md5(prefix).digest())


def _vpk_entries(folder: Path) -> dict[str, dict[str, dict[str, bytes]]]:
    entries: dict[str, dict[str, dict[str, bytes]]] = {}
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        ext, directory, name = _split_vpk_entry(path.relative_to(folder).as_posix())
        entries.setdefault(ext, {}).setdefault(directory, {})[name] = path.read_bytes()
    return entries


def _split_vpk_entry(rel: str) -> tuple[str, str, str]:
    directory, _, filename = rel.rpartition("/")
    if directory in ("", "."):
        directory = " "
    stem, dot, ext = filename.rpartition(".")
    if not dot:
        return " ", directory, filename
    return ext, directory, stem


def _vpk_cstring(buf: bytearray, text: str) -> None:
    raw = text.encode("ascii")
    if b"\x00" in raw:
        raise ValueError(f"VPK path contains a null: {text!r}")
    buf += raw + b"\x00"


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
        pack_hlmv_custom_vpk(custom)
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
