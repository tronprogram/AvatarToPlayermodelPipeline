# Avatar → GMod playermodel pipeline

A desktop workshop: drop in an avatar, convert it, and leave with a Garry’s Mod addon folder (playermodel, first-person hands, textures). Publishing to the Workshop is out of scope.

The convert engine is one job. The app around it is a workbench — tools, a library of past converts, shelves for body / hands / textures / the addon — not a step-by-step website. Product shape: [docs/overview.md](docs/overview.md). The engine exists; the workbench UI does not yet.

## Quick path

1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && cp .env.example .env`
2. Install Blender, Source Tools, SteamCMD GMod tools (app 4020), Crowbar 0.74, and a modified `studiomdl.exe` — see [docs/platform.md](docs/platform.md).
3. Export:

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

4. Copy `build.addon.root` into `garrysmod/addons/`. Workshop publish is out of scope.

Desktop window (deps wizard + preview of `data/export_test`):

```bash
python run_desktop.py
```

Browser-only: `uvicorn app.main:app --reload --port 8765` then open `http://127.0.0.1:8765`.

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
- [ ] Deps wizard reports Blender + GMod tools; Crowbar and `studiomdl.exe` are under `data/`
- [ ] `export_playermodel` writes an addon with Lua `AddValidModel` + `AddValidHands`
- [ ] Preview page or HLMV can open the compiled MDL without pink checkers

## Next step

[docs/overview.md](docs/overview.md) — then [docs/index.md](docs/index.md) for the how-to pages.
