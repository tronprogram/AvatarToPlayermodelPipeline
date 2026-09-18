# Preview an export

Three viewers, one rule: materials live in `garrysmod/materials/<cdmaterials>`. If that tree is empty, HLMV shows pink/black checkers.

The UI page `/preview` inventories `data/export_test` (see `default_export_dir()`).

## Quick path

| Goal | Call |
|------|------|
| List work files | `inspect_export(out_dir)` → `ExportPreview` |
| Interactive mesh + bones + capsules | `preview_in_blender(out_dir)` |
| Workbench still | `render_preview_png(out_dir)` → `preview.png` |
| Crowbar Compile tab | `preview_in_crowbar(out_dir)` (needs `data/crowbar/Crowbar.exe`) |
| Compiled MDL | `open_in_hlmv(mdl)` from `app.services.crowbar` |

UI buttons on `/preview` hit the same functions for `data/export_test`.

## What `inspect_export` reports

`ExportPreview.assets` is a tuple of `ExportAsset` (`label`, `relative`, `present`, `detail`). It looks for `aligned.glb`, `reference.dmx`, `physics.dmx`, `arms.dmx`, the anim DMX files, a `.qc`, and a `materials/` VTF/VMT count. `blender_ready` is “aligned GLB exists”; `crowbar_ready` is “a QC exists”.

## HLMV notes

- Prefer SDK 2013 MP `data/sdk2013mp/bin/x64/hlmv.exe` with `-game hl2mp`.
- `open_in_hlmv` stages the MDL into that game and packs materials into `hl2mp/custom/pipeline.vpk`.
- On Wine only, MDL `$cdmaterials` backslashes are rewritten to forward slashes so the viewer finds VMTs.

Crowbar “View” uses the same compiler/gameinfo the pipeline already wrote.

## Next step

[platform.md](platform.md) if a viewer exe or Wine prefix is missing.
