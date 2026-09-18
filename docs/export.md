# Export a playermodel

`ExportSystemService(glb).export_playermodel(...)` is the whole compile. It returns a `PlayermodelBuild`. You do not need to call the daughter methods unless you are debugging one step.

## Quick path

```python
from pathlib import Path
from app.services.export_system import ExportSystemService

service = ExportSystemService(Path("/path/to/avatar.glb"))
build = service.export_playermodel(
    Path("data/export_test"),
    display_name="My Avatar",
    gender="male",          # "male" → m_anm.mdl, "female" → f_anm.mdl
    author="you",
    description="Converted avatar playermodel",
    tags=("fun", "roleplay"),
)
```

`display_name` becomes every Source path. `"My Avatar"` → slug `my_avatar`:

| Field | Value |
|-------|--------|
| `$modelname` | `player/my_avatar/my_avatar.mdl` |
| `$cdmaterials` | `models/player/my_avatar` |
| Lua model | `models/player/my_avatar/my_avatar.mdl` |
| C-arms `$modelname` | `weapons/c_arms_my_avatar.mdl` |
| Lua hands | `models/weapons/c_arms_my_avatar.mdl` |
| Addon folder | `data/addons/my_avatar` (or `addon_dir=`) |

Same mapping: `playermodel_identity("My Avatar")` → `PlayermodelIdentity`.

## What `PlayermodelBuild` contains

| Attribute | Type | Content |
|-----------|------|---------|
| `identity` | `PlayermodelIdentity` | Names above |
| `dmx` | `SourceDmxFiles` | `aligned.glb`, `reference.dmx`, `physics.dmx`, `anims/*.dmx`, `arms.dmx` |
| `materials` | `tuple[ValveMaterial, ...]` | Each VTF/VMT pair written under `work_dir/materials` |
| `staged_materials` | `Path` | `garrysmod/materials/<cdmaterials>` (compile + HLMV + addon all read this) |
| `qc` / `carms_qc` | `Path` | `work_dir/<slug>.qc` and `work_dir/c_arms_<slug>.qc` |
| `compiled` / `carms` | `CompiledModel` | studiomdl output under `garrysmod/models/` |
| `addon` | `GmodAddon` | Drop-in folder: `addon.json`, Lua, both MDL families, materials |

## What the facade runs

1. ValveBiped rename + Source align (`+X` forward, `~72` units tall)
2. Headless Blender Source Tools → DMX (reference, 15 capsules, ragdoll + proportion clips, arm-weighted C-arms)
3. GLB albedos → VTF 7.4 + VertexLitGeneric VMT (shared image → same stem)
4. Stage VTF/VMT into the GMod tools materials tree
5. Compile playermodel QC, then C-arms QC
6. Package `addon.json` + autorun Lua (`AddValidModel` + `AddValidHands`)

Optional kwargs: `addon_dir`, `garrysmod` (defaults to the deps-wizard GMod tools tree).

## Stepping one stage

Use the same service instance:

| Method | Returns |
|--------|---------|
| `translate_bones()` / `align_model()` | mutated `GLTF2` |
| `export_source_dmx(work_dir, gender=…)` | `SourceDmxFiles` |
| `plan_valve_materials()` | `list[SourceMaterialSpec]` |
| `export_valve_textures(dir, cdmaterials=…)` | `list[ValveMaterial]` |
| `write_playermodel_qc` / `write_carms_qc` | QC `Path` |
| `compile_qc(qc)` | `CompiledModel` |
| `package_addon(dest, spec)` | `GmodAddon` |

## Install the addon

Copy `build.addon.root` to `garrysmod/addons/<slug>/`. Do not run `gmpublish` from this repo.

## Next step

[preview.md](preview.md) to open the mesh or the compiled MDL.
