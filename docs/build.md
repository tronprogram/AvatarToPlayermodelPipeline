# Build the desktop app

PyInstaller packages `run_desktop.py`, the templates, and the default install catalog. Setup installs Blender, the compiler, and Garry's Mod tools into `data/` after the first launch.

## Quick path

From the repo root, with `.venv` already installed (`pip install -r requirements-dev.txt`):

1. Quit any running Avatar to Playermodel window. The build deletes `dist/AvatarToPlayermodel*` and cannot replace an open bundle. Port **18764** is the single-instance lock; the window listens on **127.0.0.1:18765**.
2. Freeze:

```bash
.venv/bin/python scripts/packaging/freeze.py
```

Windows: `.\scripts\packaging\freeze.ps1`. macOS/Linux: `./scripts/packaging/freeze.sh`. All three call the same script.

3. Open the result.

| OS | Command | File |
|----|---------|------|
| macOS | `open dist/AvatarToPlayermodel.app` | `dist/AvatarToPlayermodel.app` |
| Windows | `dist\AvatarToPlayermodel.exe` | one file |
| Linux | `./dist/AvatarToPlayermodel` | one file |

macOS uses an onedir `.app` because Gatekeeper and PyInstaller 7 reject a one-file `.app`. Windows and Linux use one-file executables. The PyInstaller spec is `scripts/packaging/desktop.spec`.

## Where files land

`data/` and `logs/` stay next to the binary, not inside it. On macOS, they are next to the `.app` (`dist/data` and `dist/logs` when built in the repo). A rebuild removes only `dist/AvatarToPlayermodel*`, so an existing `dist/data` remains.

| Path | Role |
|------|------|
| `dist/AvatarToPlayermodel.app` or the one-file binary | Desktop app |
| `data/` beside that binary | Setup downloads, `catalog.json`, Convert work |
| `logs/api_error.log` beside that binary | Server log. The frozen window has no console. |

`python run_desktop.py` from a checkout uses the repo's `data/` and the same two ports. Do not run that and the frozen app together.

A browser reload server (`uvicorn app.main:app --reload`) needs a different port while **18765** is taken.

## What the bundle contains

| Packed | Left out |
|--------|----------|
| `templates/`, `static/`, `VERSION` | `data/`, `logs/`, `.env` |
| `app/blender/` (export and preview scripts) | Blender itself, Source Tools, the compiler, HLMV++, GMod |
| Bundled `app/services/deps/catalog.json` (the default) | The user's `data/catalog.json` (created when Setup or Settings first needs it) |
| pywebview for this OS (Cocoa on macOS, WinForms on Windows, GTK on Linux) | pytest |

PyInstaller's scratch copy is `build/pyinstaller`. It is not the app.

## Checklist

- [ ] The previous window is quit before the freeze
- [ ] `dist/AvatarToPlayermodel.app` (or the exe) exists and opens
- [ ] Setup still sees `data/` beside the bundle after a rebuild

## Next step

[platform.md](platform.md) for the `data/` layout once the window is open.
