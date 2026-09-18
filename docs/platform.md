# Platform, paths, and tools

Windows runs Source `.exe` files natively. macOS and Linux run them through Wine. 

## Quick path

1. Put Python deps in `.venv` (`pip install -r requirements-dev.txt`).
2. Copy `.env.example` → `.env` (loopback `127.0.0.1:8765`).
3. Run the deps wizard (`/deps-wizard` or `DepsWizardService`) so `data/blender`, Source Tools, SteamCMD, and GMod tools (app **4020**) exist.
4. Drop **Crowbar 0.74** at `data/crowbar/Crowbar.exe` and the modified compiler at `data/compiler/bin/studiomdl.exe`.
5. For HLMV, install Source SDK Base 2013 Multiplayer under `data/sdk2013mp/` (Steam app **243750**).

On macOS: Whisky’s `wine64`, then PATH `wine`. Prefix: `WINEPREFIX`, a Whisky bottle, `data/wineprefix`, or `~/.wine`.  
On Linux: PATH `wine64`/`wine` only (not Whisky). Same prefix order without bottles.

`WindowsToolHost` (`app.services.windows_tools`) builds argv + env. Native Windows drops inherited `WINE*` vars so a Darwin prefix cannot leak in.

## Roots

| Function | Frozen .exe | Dev checkout |
|----------|-------------|--------------|
| `resource_root()` | PyInstaller `_MEIPASS` (templates, scripts) | repo root |
| `writable_root()` | folder next to the .exe | repo root |
| `data_dir()` | `<writable>/data` | `data/` |
| `logs_dir()` | `<writable>/logs` | `logs/` |

## `data/` layout

| Path | Role |
|------|------|
| `data/blender/` | Blender 3.6 LTS + Source Tools addon |
| `data/gmod_tools/` | SteamCMD Garry's Mod dedicated (gameinfo, `models/`, `materials/`) |
| `data/compiler/bin/studiomdl.exe` | Compile |
| `data/crowbar/Crowbar.exe` | QC UI |
| `data/sdk2013mp/` | HLMV |
| `data/addons/<slug>/` | Default packaged addon |
| `data/export_test/` | Default preview inventory |
| `data/wineprefix/` | Optional bundled Wine prefix |

## Deps wizard HTTP

| Method | Path | Effect |
|--------|------|--------|
| GET | `/deps-wizard/status` | `DependencyStatus` |
| GET | `/deps-wizard/fetch` | download archives if needed |
| GET | `/deps-wizard/extract` | unpack if needed |
| GET | `/deps-wizard/gmod-tools` | status only (no SteamCMD) |
| POST | `/deps-wizard/gmod-tools` | start SteamCMD for app 4020 if missing |

## Next step

[export.md](export.md) once tools are present.
