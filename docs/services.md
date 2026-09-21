# Service APIs

Structured results use named dataclasses instead of untyped dictionaries. Other methods use the typed return values documented below.

Valve files render from `templates/valve/` with `[[ var ]]` / `[% %]` so Source `{ }` stays literal (`render_valve` in `app.core.templates`).

## Export service

`ExportSystemService(model_path: Path)` — see [export.md](export.md).

## Compile and package

| Type                                          | Module                       | What you get                                                                                                    |
| --------------------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `CompileService.compile(qc)`                  | `app.services.compile`       | `CompiledModel`: `mdl`, `log` (`CommandResult`), `model_name` (QC `$modelname`), optional `vtx` / `vvd` / `phy` |
| `QCRenderService(dir).write(PlayermodelQc)`   | `app.services.qcrender`      | `Path` to `<stem>.qc`                                                                                           |
| `QCRenderService(dir).write_carms(CarmsQc)`   | same                         | `Path` to `c_arms_<slug>.qc`                                                                                    |
| `PlayerLuaService(dir).write(PlayermodelLua)` | `app.services.playerlua`     | `Path` to `<slug>.lua`                                                                                          |
| `AddonPackageService(dir).write(AddonSpec)`   | `app.services.addon_package` | `GmodAddon`: `root`, `addon_json`, `lua`, `mdl`, `materials`, `hands`                                           |

`AddonMetadata` (`title`, `author`, `description`, `addon_type="model"`, at most two gmad `tags`, `ignore`) is required on `AddonSpec`. Types and tags are validated (`ADDON_TYPES` / `ADDON_TAGS`).

`source_slug("My Avatar")` → `"my_avatar"`. `lua_filename` appends `.lua`.

## Materials and names

| Call                                                     | Returns                                                                                   |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `plan_materials(gltf, blob)`                             | `list[SourceMaterialSpec]` (`original_name`, `source_name`, image `data`, `mime_type`)    |
| `ValveTextureService(dir).convert(specs, cdmaterials=…)` | `list[ValveMaterial]` (`vtf`, `vmt`, `has_alpha`, names)                                  |
| `source_material_name` / `allocate_source_name`          | Functions from `app.core.source_names`; Blender imports this standard-library-only module |

Same albedo → same stem (`face` + `face` stay `face`). Different image → `face_2`. VTF version is **7.4**.

## Bones and Windows tools

| Call                         | Returns                                                   |
| ---------------------------- | --------------------------------------------------------- |
| `apply_valvebiped(gltf)`     | same `GLTF2`, joints renamed / helpers merged             |
| `align_to_source(gltf)`      | same `GLTF2`, Source axes + height                        |
| `detect_windows_tool_host()` | `WindowsToolHost` (`kind` `native` or `wine`)             |
| `host.argv(exe, *args)`      | process argv                                              |
| `host.env()`                 | env (Wine prefix on Unix; no inherited `WINE*` on native) |
| `open_in_hlmv`               | [preview.md](preview.md)                                  |

## Templates

| File                   | Used by                       |
| ---------------------- | ----------------------------- |
| `playermodel.qc`       | `QCRenderService.write`       |
| `carms.qc`             | `QCRenderService.write_carms` |
| `playermodel.lua`      | `PlayerLuaService`            |
| `vertexlitgeneric.vmt` | `ValveTextureService`         |
| `hlmv_gameinfo.txt`    | HLMV++ helpers                |

HTML UI stays in `templates/html/` (normal Jinja via FastAPI).

## Next step

Call sites live under `app/services/`. Tests under `tests/test_*.py` are the executable examples.
