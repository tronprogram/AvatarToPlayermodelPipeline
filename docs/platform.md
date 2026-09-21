# Platform, paths, and tools

Windows runs Source `.exe` files natively. macOS and Linux run them through Wine.

## Quick path

1. Put Python deps in `.venv` (`pip install -r requirements-dev.txt`).
2. Copy `.env.example` → `.env` (loopback `127.0.0.1:18765`). Windows may reserve the old `8765` block (Hyper-V); the desktop exe probes for a free port if that happens.
3. Run **Setup** (`/setup`) so Blender 5.2 LTS, Source Tools, the modified Source compiler, HLMV++, SteamCMD, and GMod tools (app **4020**, anonymous SteamCMD) exist. Intel Macs get Blender 4.5 LTS (5.2 has no macOS x64 build).
4. Optionally drop **Crowbar 0.74** at `data/crowbar/Crowbar.exe` or point Settings at it.

On macOS: Whisky’s `wine64`, then PATH `wine`. Prefix: Settings override, `WINEPREFIX`, a Whisky bottle, `data/wineprefix`, or `~/.wine`.
On Linux: PATH `wine64`/`wine` only (not Whisky). Same prefix order without bottles.

If Wine is required and no prefix is valid, Setup and Convert cannot continue past the intro.

`WindowsToolHost` (`app.services.windows_tools`) builds argv + env. Native Windows drops inherited `WINE*` vars so a Darwin prefix cannot leak in.

## Roots

| Function | Frozen .exe | Dev checkout |
|----------|-------------|--------------|
| `resource_root()` | PyInstaller `_MEIPASS` (templates, scripts) | repo root |
| `writable_root()` | folder next to the .exe | repo root |

Build the one-file desktop exe with `.\scripts\build_desktop.ps1` (`desktop.spec`). The binary is `dist/AvatarToPlayermodel.exe`.
| `data_dir()` | `<writable>/data` | `data/` |
| `logs_dir()` | `<writable>/logs` | `logs/` |

## `data/` layout

| Path | Role |
|------|------|
| `data/blender/` | Blender 5.2 LTS + Source Tools addon |
| `data/gmod_tools/` | SteamCMD Garry's Mod dedicated (gameinfo, `models/`, `materials/`) |
| `data/compiler/` | BobmacU/SFM `studiomdl.exe` (Convert compile) |
| `data/hlmvplusplus/` | ficool2 HLMV++ (preview; also copied into `compiler/bin`) |
| `data/crowbar/Crowbar.exe` | QC UI (optional) |
| `data/addons/<slug>/` | Default packaged addon |
| `data/zips/<slug>.zip` | Convert hand-off (or Settings zip destination) |
| `data/export_test/` | Convert work tree / preview inventory |
| `data/user_settings.json` | Path overrides and Convert defaults |
| `data/wineprefix/` | Optional bundled Wine prefix |

Setup is HTML under `/setup`. HLMV++ is a GitHub zip; Steam app **243750** is not required.

## Next step

[export.md](export.md) once tools are present.
