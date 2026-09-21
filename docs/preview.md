# Preview an export

Preview the exported mesh in Blender or the compiled model in HLMV++. Materials must exist under `garrysmod/materials/<cdmaterials>` or HLMV++ shows pink-and-black checkers.

`inspect_export` inventories a work dir (Convert uses `data/export_test`).

## Quick path

| Goal | Call |
|------|------|
| List work files | `inspect_export(out_dir)` → `ExportPreview` |
| Interactive mesh + bones + capsules | `preview_in_blender(out_dir)` |
| Workbench still | `render_preview_png(out_dir)` → `preview.png` |
| Compiled MDL | `open_in_hlmv(mdl)` from `app.services.hlmv_preview` |

## What `inspect_export` reports

`ExportPreview.assets` is a tuple of `ExportAsset` values with `label`, `relative`, `present`, and `detail` fields. It checks for `aligned.glb`, `reference.dmx`, `physics.dmx`, `arms.dmx`, animation DMX files, a `.qc` file, and the number of VTF/VMT files under `materials/`.

`blender_ready` means `aligned.glb` exists. `qc_ready` means a QC file exists.

## HLMV notes

- HLMV++ preview is supported only on Windows. Setup installs it under `data/hlmvplusplus/`, and it launches from `compiler/bin` so the engine DLLs load. Convert shows **Preview in HLMV++** when the executable is installed.
- On macOS and Linux, HLMV++ will probably fail with a `tier0` DLL error. Vanilla HLMV from Source SDK 2013 Multiplayer is a separate manual alternative.
- `open_in_hlmv` stages the MDL under `data/hlmvplusplus/game` and mounts GMod dedicated materials. It writes materials to `custom/pipeline.vpk` as VPK version 2 because HLMV++ ignores loose files and version 1 archives.
- Under Wine, MDL `$cdmaterials` backslashes are changed to forward slashes so the viewer can find VMTs.

Convert compiles with BobmacU `studiomdl`. Preview is HLMV++.

## Next step

[platform.md](platform.md) if a viewer exe or Wine prefix is missing.
