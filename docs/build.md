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

Windows and Linux use one-file executables. macOS does not; see below. The PyInstaller spec is `scripts/packaging/desktop.spec`.

## macOS

Run the same freeze. You get a directory named `dist/AvatarToPlayermodel.app`, then open it:

```bash
open dist/AvatarToPlayermodel.app
```

A one-file `.app` is rejected by Gatekeeper and by PyInstaller 7, so the spec builds an onedir bundle and wraps that. `open` starts `Contents/MacOS/AvatarToPlayermodel`. PyInstaller also leaves a sibling folder `dist/AvatarToPlayermodel`; `freeze.py` deletes it once the `.app` exists. Keep the `.app`.

`data/` and `logs/` are created next to the `.app` (`dist/data` and `dist/logs` in this repo), not under `Contents/`. The bundle is signed as one unit, so writes inside it are blocked, and the unpack directory inside the app is removed when the process exits.

The `.app` matches the Python that ran the freeze. An Apple silicon `.venv` produces an arm64 app. An Intel Mac needs an x86_64 `.venv`. This repo does not build a universal binary.

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

## Release

Tag `v*` runs [`.github/workflows/release.yml`](../.github/workflows/release.yml). That freezes once per OS, then attaches the three files to a GitHub Release. Running the workflow by hand builds the same files and leaves them on the Actions run, so you can look before you tag.

Pushes to `master` and pull requests run pytest on Ubuntu ([`.github/workflows/tests.yml`](../.github/workflows/tests.yml)). That does not freeze the app.

| Job | Runner | Release asset |
|-----|--------|----------------|
| Windows | `windows-latest` | `AvatarToPlayermodel.exe` |
| Linux | `ubuntu-latest` | `AvatarToPlayermodel` |
| macOS | `macos-15` (Apple silicon) | `AvatarToPlayermodel-macos.zip` |

The Linux job installs GTK, WebKit, and `libgirepository-2.0-dev` so pip can build PyGObject for pywebview. Both freeze and publish check out the tag with `actions/checkout@v4`.

Leave `dist/data`, `dist/logs`, and `build/pyinstaller` off the release. The first launch creates `data/` beside the app on the user's machine.

### macOS release

Zip the bundle with `ditto` so the folder structure survives:

```bash
ditto -c -k --keepParent dist/AvatarToPlayermodel.app AvatarToPlayermodel-macos.zip
```

A download from Releases is quarantined. Gatekeeper blocks the first open. The person who downloaded it clears that once:

1. Move `AvatarToPlayermodel.app` out of the zip. Leave it where they want `data/` to appear beside it.
2. Control-click the app and choose **Open**, then **Open** again. Or open **System Settings → Privacy & Security** and choose **Open Anyway**.

After that, a normal double-click launches it. `data/` is created next to the `.app`.

An Intel download is a second Mac job with an x86_64 Python. It is not a universal build of the arm64 `.app`.

## Next step

[platform.md](platform.md) for the `data/` layout once the window is open.
