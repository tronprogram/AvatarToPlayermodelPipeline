# Avatar To GMod playermodel pipeline

![Logo](static/img/favicon.webp)

Basic system designed to convert 360sona avatar models into Garry's Mod Playermodels.

Uses BobmacU’s modified SFM `studiomdl.exe` to compile custom QC files.

## Quick path

1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && cp .env.example .env`
2. Run Setup in the desktop window (or `/setup`). Setup will download the modified Source compiler, HLMV++ and Garry's Mod Dedicated Server tooling for playermodel building via SteamCMD. See [docs/platform.md](docs/platform.md).
3. Convert a `.glb` in Convert, or from Python:

```python
from pathlib import Path
from app.services.export_system import ExportSystemService

build = ExportSystemService(Path("avatar.glb")).export_playermodel(
    Path("data/export_test"),
    display_name="My Avatar",
    gender="male",
    author="you",
    description="Converted avatar playermodel",
)
print(build.addon.root)
```

4. Unzip `{slug}.zip` into `garrysmod/addons/`.

Desktop window:

```bash
python run_desktop.py
```

Desktop executable: To build, run `.venv/bin/python scripts/packaging/freeze.py`. Open `dist/AvatarToPlayermodel.app` on macOS, or the one-file binary on Windows and Linux. Steps, ports, and what the rebuild details are in [docs/build.md](docs/build.md).

You may also download and use the releases from the Releases tab.

Browser-only: `uvicorn app.main:app --reload --port 8765` then open `http://127.0.0.1:8765`.

## Details

| Topic                           | Where                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------- |
| Product overview                | [docs/overview.md](docs/overview.md)                                                              |
| How to export / what comes back | [docs/export.md](docs/export.md)                                                                  |
| Preview (Blender, HLMV++)       | [docs/preview.md](docs/preview.md)                                                                |
| Windows vs Wine, `data/`, deps  | [docs/platform.md](docs/platform.md)                                                              |
| Freeze the desktop window       | [docs/build.md](docs/build.md)                                                                    |
| Service APIs and return types   | [docs/services.md](docs/services.md)                                                              |
| Valve templates                 | `templates/valve/` (`[[ ]]` / `[% %]`)                                                            |
| UI templates                    | `templates/html/`                                                                                 |
| Paths                           | `resource_root()` = bundled (`_MEIPASS` when frozen); `writable_root()` = folder next to the .exe |
| Python                          | `.venv` in this repo (`AGENTS.md`)                                                                |

## Next step

[docs/overview.md](docs/overview.md) — then [docs/index.md](docs/index.md) for the how-to pages.
