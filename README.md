# Avatar → GMod playermodel pipeline

A desktop hallway: set up the tools, drop in an avatar, convert it, and leave with a Garry’s Mod addon zip (playermodel, first-person hands, textures). Publishing to the Workshop is out of scope.

The convert engine is one job. The app around it is Metro Setup / Convert / Settings — not a workbench of shelves. Product shape: [docs/overview.md](docs/overview.md). Compile uses BobmacU’s modified SFM `studiomdl.exe` (Setup fetches it).

## Quick path

1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && cp .env.example .env`
2. Run Setup in the desktop window (or `/setup`). Setup downloads the modified Source compiler and HLMV++ (no Steam login). GMod dedicated (app 4020) uses anonymous SteamCMD. See [docs/platform.md](docs/platform.md).
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

4. Throw `{slug}.zip` into `garrysmod/addons/` (or copy `build.addon.root`). Workshop publish is out of scope.

Desktop window:

```bash
python run_desktop.py
```

Desktop exe (PyInstaller one-file): `.\scripts\build_desktop.ps1` then run `dist\AvatarToPlayermodel.exe`. `data/` and `logs/` land next to the exe.

Browser-only: `uvicorn app.main:app --reload --port 18765` then open `http://127.0.0.1:18765`. Folder pickers use a typed path unless you launch through pywebview.

## Details

| Topic | Where |
|-------|--------|
| Product overview | [docs/overview.md](docs/overview.md) |
| How to export / what comes back | [docs/export.md](docs/export.md) |
| Preview (Blender, Crowbar, HLMV) | [docs/preview.md](docs/preview.md) |
| Windows vs Wine, `data/`, deps | [docs/platform.md](docs/platform.md) |
| Service APIs and return types | [docs/services.md](docs/services.md) |
| Valve templates | `templates/valve/` (`[[ ]]` / `[% %]`) |
| UI templates | `templates/html/` |
| Paths | `resource_root()` = bundled (`_MEIPASS` when frozen); `writable_root()` = folder next to the .exe |
| Python | `.venv` in this repo (`AGENTS.md`) |

## Out of scope

Workshop / `gmpublish`, flex, jigglebones, bodygroups, NPC QC/Lua, fancy VMTs, and citizen-pose C-arm matching.

## Checklist

- [ ] `.venv` is active and `pytest -q` is green on the export tests
- [ ] Setup reports Blender + GMod tools; `data/compiler/bin/studiomdl.exe` is on disk
- [ ] `export_playermodel` writes an addon with Lua `AddValidModel` + `AddValidHands`
- [ ] Convert hands you a zip, or HLMV can open the compiled MDL without pink checkers

## Next step

[docs/overview.md](docs/overview.md) — then [docs/index.md](docs/index.md) for the how-to pages.
