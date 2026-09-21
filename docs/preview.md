# Preview an export

Three viewers, one rule: materials live in `garrysmod/materials/<cdmaterials>`. If that tree is empty, HLMV shows pink/black checkers.

`inspect_export` inventories a work dir (Convert uses `data/export_test`).

## Quick path

| Goal | Call |
|------|------|
| List work files | `inspect_export(out_dir)` → `ExportPreview` |
| Interactive mesh + bones + capsules | `preview_in_blender(out_dir)` |
| Workbench still | `render_preview_png(out_dir)` → `preview.png` |
| Crowbar Compile tab | `preview_in_crowbar(out_dir)` (needs `data/crowbar/Crowbar.exe`) |
| Compiled MDL | `open_in_hlmv(mdl)` from `app.services.crowbar` |

## What `inspect_export` reports

`ExportPreview.assets` is a tuple of `ExportAsset` (`label`, `relative`, `present`, `detail`). It looks for `aligned.glb`, `reference.dmx`, `physics.dmx`, `arms.dmx`, the anim DMX files, a `.qc`, and a `materials/` VTF/VMT count. `blender_ready` is “aligned GLB exists”; `crowbar_ready` is “a QC exists”.

## HLMV notes

- Prefer HLMV++ from Setup (`data/hlmvplusplus/`, launched from `compiler/bin` so engine DLLs load).
- `open_in_hlmv` stages the MDL into `data/hlmvplusplus/game` and mounts GMod dedicated materials. No Source SDK 2013 login.
- On Wine only, MDL `$cdmaterials` backslashes are rewritten to forward slashes so the viewer finds VMTs.

Crowbar “View” uses the same compiler/gameinfo the pipeline already wrote.

## Next step

[platform.md](platform.md) if a viewer exe or Wine prefix is missing.
