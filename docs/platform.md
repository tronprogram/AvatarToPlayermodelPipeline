# Platform, paths, and tools

Windows runs Source `.exe` files natively. macOS and Linux run them through Wine.

## Quick path

1. Put Python deps in `.venv` (`pip install -r requirements-dev.txt`).
2. Copy `.env.example` → `.env` (loopback `127.0.0.1:8765`).
3. Run **Setup** (`/setup`) so Blender 5.2 LTS, Source Tools, SteamCMD, and GMod tools (app **4020**, anonymous SteamCMD) exist. Intel Macs get Blender 4.5 LTS (5.2 has no macOS x64 build).
4. Install **Source SDK Base 2013 Multiplayer** with Steam (`steam://install/243750`), or open Setup’s **SteamCMD prompt** (a real console — login is not anonymous and is not embedded in the page). Setup detects a common Steam library folder, `data/sdk2013mp/`, or a path you set in Settings. That tree’s `bin/studiomdl.exe` is the compiler.
5. Optionally drop **Crowbar 0.74** at `data/crowbar/Crowbar.exe` or point Settings at it.

On macOS: Whisky’s `wine64`, then PATH `wine`. Prefix: Settings override, `WINEPREFIX`, a Whisky bottle, `data/wineprefix`, or `~/.wine`.
On Linux: PATH `wine64`/`wine` only (not Whisky). Same prefix order without bottles.

If Wine is required and no prefix is valid, Setup and Convert cannot continue past the intro.

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
| `data/blender/` | Blender 5.2 LTS + Source Tools addon |
| `data/gmod_tools/` | SteamCMD Garry's Mod dedicated (gameinfo, `models/`, `materials/`) |
| `data/sdk2013mp/` | Stock 2013 MP (`studiomdl`, HLMV) if not using a Steam library path |
| `data/crowbar/Crowbar.exe` | QC UI (optional) |
| `data/addons/<slug>/` | Default packaged addon |
| `data/zips/<slug>.zip` | Convert hand-off (or Settings zip destination) |
| `data/export_test/` | Convert work tree / preview inventory |
| `data/user_settings.json` | Path overrides and Convert defaults |
| `data/wineprefix/` | Optional bundled Wine prefix |

Setup is HTML under `/setup`. App **243750** is not installed by SteamCMD. Use `steam://install/243750`.

## Next step

[export.md](export.md) once tools are present.
