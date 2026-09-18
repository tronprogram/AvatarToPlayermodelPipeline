"""Open Crowbar 0.74 (via Wine) on an exported playermodel QC.

Place ``Crowbar.exe`` in ``data/crowbar/``
(https://github.com/ZeqMacaw/Crowbar/releases/tag/v0.74).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from srctools.vpk import VPK

from app.core.paths import data_dir
from app.core.process import PYTHON_ENV_KEYS, CommandResult, command_env, run_command
from app.services.deps.detect import gmod_tools_root

_log = logging.getLogger(__name__)

_WHISKY_WINE = (
    Path.home()
    / "Library/Application Support/com.isaacmarovitz.Whisky/Libraries/Wine/bin/wine64"
)
_WHISKY_BOTTLES = (
    Path.home() / "Library/Containers/com.isaacmarovitz.Whisky/Bottles"
)


@dataclass(frozen=True, slots=True)
class WineSession:
    """Wine binary + prefix used to run 32-bit Windows tools."""

    wine: Path
    prefix: Path


def windows_path(path: Path) -> str:
    """Unix path as Wine ``Z:`` (the prefix maps ``Z:`` to ``/``)."""
    resolved = path.resolve()
    return "Z:" + str(resolved).replace("/", "\\")


def windows_gameinfo_path(path: Path) -> str:
    """Quoted ``Z:/...`` path for gameinfo SearchPaths (backslashes break parsing)."""
    return '"' + windows_path(path).replace("\\", "/") + '"'


def crowbar_dir() -> Path:
    return data_dir() / "crowbar"


def compiler_dir() -> Path:
    return data_dir() / "compiler"


def find_wine() -> Path | None:
    """Whisky ``wine64`` first, then ``wine64``/``wine`` on PATH."""
    if _is_executable(_WHISKY_WINE):
        return _WHISKY_WINE
    for name in ("wine64", "wine"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def find_wine_prefix() -> Path | None:
    """Prefer a Whisky bottle that already has a ``drive_c``."""
    env_prefix = os.environ.get("WINEPREFIX")
    if env_prefix:
        prefix = Path(env_prefix)
        if (prefix / "drive_c").is_dir():
            return prefix
    if _WHISKY_BOTTLES.is_dir():
        bottles = sorted(
            path for path in _WHISKY_BOTTLES.iterdir() if (path / "drive_c").is_dir()
        )
        for bottle in bottles:
            if _settings_path(bottle).is_file():
                return bottle
        if bottles:
            return bottles[0]
    fallback = data_dir() / "wineprefix"
    if (fallback / "drive_c").is_dir():
        return fallback
    return None


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


def write_hlmv_gameinfo(game_dir: Path, garrysmod: Path) -> Path:
    """SDK-native gameinfo that also mounts GMod materials/models.

    SDK HLMV treats ``|all_source_engine_paths|`` as the SDK root. Pointing
    ``-game`` at GMod dedicated-server ``garrysmod`` never mounts HL2 scripts,
    which is the ``game_sounds_manifest.txt`` fatal.
    """
    game_dir.mkdir(parents=True, exist_ok=True)
    ensure_hlmv_scripts(game_dir)
    gmod = windows_gameinfo_path(garrysmod)
    pipeline = windows_gameinfo_path(game_dir)
    dest = game_dir / "gameinfo.txt"
    dest.write_text(
        '"GameInfo"\n'
        "{\n"
        '\tgame\t"Pipeline HLMV"\n'
        "\ttype\tmultiplayer_only\n"
        "\tFileSystem\n"
        "\t{\n"
        "\t\tSteamAppId\t\t\t\t243750\n"
        "\t\tSearchPaths\n"
        "\t\t{\n"
        "\t\t\tgame+mod\t\t\t|gameinfo_path|.\n"
        "\t\t\tmod+mod_write+default_write_path\t|gameinfo_path|.\n"
        f"\t\t\tgame\t\t\t\t{pipeline}\n"
        f"\t\t\tgame\t\t\t\t{gmod}\n"
        "\t\t\tgame\t\t\t\t|all_source_engine_paths|hl2/pipeline.vpk\n"
        "\t\t\tgame+mod\t\t\thl2mp/hl2mp_pak.vpk\n"
        "\t\t\tgame\t\t\t\t|all_source_engine_paths|hl2/hl2_textures.vpk\n"
        "\t\t\tgame\t\t\t\t|all_source_engine_paths|hl2/hl2_sound_vo_english.vpk\n"
        "\t\t\tgame\t\t\t\t|all_source_engine_paths|hl2/hl2_sound_misc.vpk\n"
        "\t\t\tgame\t\t\t\t|all_source_engine_paths|hl2/hl2_misc.vpk\n"
        "\t\t\tplatform\t\t\t|all_source_engine_paths|platform/platform_misc.vpk\n"
        "\t\t\tgame+game_write\t\thl2mp\n"
        "\t\t\tgamebin\t\t\t\thl2mp/bin\n"
        "\t\t\tgame\t\t\t\t|all_source_engine_paths|hl2\n"
        "\t\t\tplatform\t\t\t|all_source_engine_paths|platform\n"
        "\t\t}\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )
    return dest


def stage_hlmv_assets(
    game_dir: Path,
    mdl: Path,
    garrysmod: Path,
    extra_material_roots: list[Path] | None = None,
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
    session = _require_wine()
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
    write_crowbar_settings(session.prefix, qc, compiler, gameinfo)
    env = _wine_env(session)
    command = [str(session.wine), str(exe), windows_path(qc)]
    _log.info("crowbar preview: %s", " ".join(command))
    subprocess.Popen(
        command,
        env=env,
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
) -> Path:
    """Write a one-game Crowbar settings file so Compile opens our QC."""
    dest = _settings_path(prefix)
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
        ),
        encoding="utf-8",
        newline="\n",
    )
    return dest


def _require_wine() -> WineSession:
    wine = find_wine()
    if wine is None:
        raise FileNotFoundError(
            "Wine is not installed (Whisky wine64 or wine64 on PATH)."
        )
    prefix = find_wine_prefix()
    if prefix is None:
        raise FileNotFoundError(
            "No Wine prefix found. Create a Whisky bottle or set WINEPREFIX."
        )
    return WineSession(wine=wine, prefix=prefix)


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


def _settings_xml(
    *,
    qc: Path,
    compiler: Path,
    gameinfo: Path,
    app: Path,
    viewer: Path | None,
    packer: Path | None,
    view_gameinfo: Path | None = None,
) -> str:
    viewer_path = windows_path(viewer) if viewer else ""
    packer_path = windows_path(packer) if packer else windows_path(compiler)
    compile_setup = _game_setup_xml(
        name="Garry's Mod (pipeline)",
        gameinfo=gameinfo,
        app=app,
        compiler=compiler,
        viewer_path=viewer_path,
        packer_path=packer_path,
    )
    view_setup = ""
    view_index = "0"
    if view_gameinfo is not None:
        view_setup = _game_setup_xml(
            name="HLMV (SDK 2013)",
            gameinfo=view_gameinfo,
            app=app,
            compiler=compiler,
            viewer_path=viewer_path,
            packer_path=packer_path,
        )
        view_index = "1"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<AppSettings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n'
        "  <GameSetups>\n"
        f"{compile_setup}"
        f"{view_setup}"
        "  </GameSetups>\n"
        "  <CompileGameSetupSelectedIndex>0</CompileGameSetupSelectedIndex>\n"
        f"  <ViewGameSetupSelectedIndex>{view_index}</ViewGameSetupSelectedIndex>\n"
        f"  <PreviewGameSetupSelectedIndex>{view_index}</PreviewGameSetupSelectedIndex>\n"
        f"  <CompileQcPathFileName>{_xml(windows_path(qc))}</CompileQcPathFileName>\n"
        "  <OptionsAutoOpenQcFileIsChecked>true</OptionsAutoOpenQcFileIsChecked>\n"
        "  <AppIsSingleInstance>false</AppIsSingleInstance>\n"
        "</AppSettings>\n"
    )


def _game_setup_xml(
    *,
    name: str,
    gameinfo: Path,
    app: Path,
    compiler: Path,
    viewer_path: str,
    packer_path: str,
) -> str:
    return (
        "    <GameSetup>\n"
        f"      <GameName>{_xml(name)}</GameName>\n"
        "      <GameEngine>Source</GameEngine>\n"
        f"      <GamePathFileName>{_xml(windows_path(gameinfo))}</GamePathFileName>\n"
        f"      <GameAppPathFileName>{_xml(windows_path(app))}</GameAppPathFileName>\n"
        "      <GameAppOptions />\n"
        f"      <CompilerPathFileName>{_xml(windows_path(compiler))}</CompilerPathFileName>\n"
        f"      <ViewerPathFileName>{_xml(viewer_path)}</ViewerPathFileName>\n"
        f"      <MappingToolPathFileName>{_xml(windows_path(compiler))}</MappingToolPathFileName>\n"
        f"      <PackerPathFileName>{_xml(packer_path)}</PackerPathFileName>\n"
        "    </GameSetup>\n"
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


def pack_hlmv_custom_vpk(session: WineSession, folder: Path) -> Path:
    """SDK ``vpk.exe`` writes VPK v2; srctools can only write v1, which HLMV ignores."""
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
        [str(session.wine), str(exe), windows_path(folder)],
        cwd=str(folder.parent),
        env=_wine_env(session),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not dest.is_file():
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "vpk.exe failed")
    return dest


def compile_qc(qc: Path) -> CommandResult:
    """Compile a playermodel QC with Wine ``studiomdl.exe`` into garrysmod."""
    if not qc.is_file():
        raise FileNotFoundError(f"No QC at {qc}")
    session = _require_wine()
    compiler = studiomdl_exe()
    if not compiler.is_file():
        raise FileNotFoundError(
            f"studiomdl.exe is missing at {compiler}. Copy the modified compiler there."
        )
    game = gmod_tools_root(data_dir()) / "garrysmod"
    if not (game / "gameinfo.txt").is_file():
        raise FileNotFoundError(f"Missing gameinfo.txt at {game}")
    result = run_command(
        [
            str(session.wine),
            str(compiler),
            "-game",
            windows_path(game),
            "-nop4",
            "-verbose",
            windows_path(qc),
        ],
        cwd=qc.parent,
        env=_wine_env(session),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.output or f"studiomdl exited {result.returncode}")
    return result


def open_in_hlmv(mdl: Path) -> Path:
    """Open the compiled MDL in SDK HLMV via Wine. Returns the viewer exe."""
    if not mdl.is_file():
        raise FileNotFoundError(f"No compiled MDL at {mdl}")
    session = _require_wine()
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
        hl2mp, mdl, garrysmod, extra_material_roots=[custom]
    )
    mat_src = garrysmod / "materials" / Path(model_rel).parent
    if mat_src.is_dir():
        pack_hlmv_custom_vpk(session, custom)
    staged = hl2mp / Path(model_rel)
    _stop_hlmv()
    command = [
        str(session.wine),
        str(viewer),
        "-olddialogs",
        "-game",
        windows_path(hl2mp),
        windows_path(staged),
    ]
    _log.info("hlmv preview: %s", " ".join(command))
    subprocess.Popen(
        command,
        cwd=str(viewer.parent),
        env=_wine_env(session),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return viewer


def _wine_env(session: WineSession) -> dict[str, str]:
    return command_env(
        extra={
            "WINEPREFIX": str(session.prefix),
            "WINEARCH": "win64",
            "WINEDEBUG": "-all",
            "PATH": f"{session.wine.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        },
        drop=PYTHON_ENV_KEYS,
    )


def _stop_crowbar() -> None:
    """Kill a running Crowbar so it cannot overwrite settings on exit."""
    _stop_named("Crowbar.exe")


def _stop_hlmv() -> None:
    """Dismiss a stuck HLMV fatal-error dialog before relaunch."""
    _stop_named("hlmv.exe")


def _stop_named(name: str) -> None:
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


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
