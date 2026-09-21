# Platform, paths, and tools

Windows runs Source `.exe` files natively. macOS and Linux run them through Wine.

## Quick path

1. Put Python deps in `.venv` (`pip install -r requirements-dev.txt`).
2. Copy `.env.example` to `.env`. The desktop app uses `127.0.0.1:18765`.In case the system finds a conflicting port, the desktop executable looks for a free port.
3. Run **Setup** (`/setup`) so Blender 5.2 LTS, Source Tools, the modified Source compiler, HLMV++, SteamCMD, and the Garry's Mod Dedicated Server tooling exist. Intel Macs get Blender 4.5 LTS (5.2 has no macOS x64 build).

On macOS, the Wine assistant finds Whisky and CrossOver bottles. On Linux, it finds Bottles prefixes. On both platforms, it also checks `WINEPREFIX`, `data/wineprefix`, and `~/.wine`. It uses the only valid prefix automatically or asks you to choose when it finds several. This step is not shown on Windows.

`WindowsToolHost` (`app.services.windows_tools`) builds the command and environment for Windows tools. Native Windows removes inherited `WINE*` variables.

## Roots

| Function          | Frozen .exe                                              | Dev checkout |
| ----------------- | -------------------------------------------------------- | ------------ |
| `resource_root()` | PyInstaller `_MEIPASS` (templates, scripts)              | repo root    |
| `writable_root()` | folder next to the .exe (or next to the `.app` on macOS; Application Support if that folder is a translocated copy) | repo root    |
| `data_dir()`      | `<writable>/data`                                        | `data/`      |
| `logs_dir()`      | `<writable>/logs`                                        | `logs/`      |

Build with [build.md](build.md). Windows and Linux are one file (`dist/AvatarToPlayermodel.exe` / `dist/AvatarToPlayermodel`). macOS is an onedir `.app` (`dist/AvatarToPlayermodel.app`).

## `data/` layout

| Path                      | Role                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `data/blender/`           | Blender and the Source Tools addon (5.2 LTS on supported platforms; 4.5 LTS on Intel macOS)                  |
| `data/gmod_tools/`        | SteamCMD Garry's Mod dedicated (gameinfo, `models/`, `materials/`)                                           |
| `data/compiler/`          | BobmacU/SFM `studiomdl.exe` (Convert compile)                                                                |
| `data/hlmvplusplus/`      | ficool2 HLMV++ (preview; also copied into `compiler/bin`)                                                    |
| `data/addons/<slug>/`     | Default packaged addon                                                                                       |
| `data/zips/<slug>.zip`    | Convert hand-off (or Settings zip destination)                                                               |
| `data/export_test/`       | Convert work tree / preview inventory                                                                        |
| `data/user_settings.json` | Path overrides and Convert defaults                                                                          |
| `data/catalog.json`       | Install versions and download links. Created from the bundled default when Setup or Settings first needs it. |
| `data/wineprefix/`        | Optional bundled Wine prefix                                                                                 |

## Next step

[export.md](export.md) once tools are present.
