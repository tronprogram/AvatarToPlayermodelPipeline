"""Open the exported playermodel in a Blender viewport (not headless).

Run:
  blender --python preview_playermodel.py -- \\
    --input aligned.glb --physics physics.dmx [--screenshot preview.png]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _argv_after_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def _source_tools_addon_roots() -> list[Path]:
    binary = Path(bpy.app.binary_path).resolve().parent
    version = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
    return [
        binary / version / "scripts" / "addons",
        binary / "scripts" / "addons",
    ]


def _promote_source_tools_into_blender_path() -> None:
    import shutil

    dest_parent = _source_tools_addon_roots()[0]
    dest = dest_parent / "io_scene_valvesource"
    if dest.is_dir() and (dest / "__init__.py").is_file():
        return
    for src_parent in _source_tools_addon_roots()[1:]:
        src = src_parent / "io_scene_valvesource"
        if src.is_dir() and (src / "__init__.py").is_file():
            dest_parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest, dirs_exist_ok=True)
            return


def _smd_operator_ready() -> bool:
    return "smd" in dir(bpy.ops.import_scene)


def _enable_source_tools() -> bool:
    import addon_utils
    import importlib

    _promote_source_tools_into_blender_path()
    for extra in _source_tools_addon_roots():
        if extra.is_dir() and str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    _shim_source_tools_session_uid()
    for name in ("io_scene_valvesource", "io_scene_valvesourcemodel"):
        try:
            addon_utils.enable(name, default_set=True)
        except Exception:
            pass
        if _smd_operator_ready():
            return True
        try:
            module = importlib.import_module(name)
            if hasattr(module, "register"):
                module.register()
        except Exception:
            continue
        if _smd_operator_ready():
            return True
    return False


def _shim_source_tools_session_uid() -> None:
    """Source Tools 3.4+ wants Blender 4.1; keep a no-op path for older binaries."""
    if bpy.app.version >= (4, 1, 0):
        return
    for rna_type in (bpy.types.Object, bpy.types.Collection):
        if not hasattr(rna_type, "session_uid"):
            rna_type.session_uid = property(lambda self: self.as_pointer())


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.armatures):
        bpy.data.armatures.remove(block)
    for collection in list(bpy.data.collections):
        if collection is not bpy.context.scene.collection:
            bpy.data.collections.remove(collection)


def _show_armatures() -> None:
    for obj in bpy.context.scene.objects:
        if obj.type != "ARMATURE":
            continue
        obj.show_in_front = True
        obj.data.display_type = "STICK"
        obj.data.show_names = True


def _mesh_bounds() -> tuple[Vector, Vector] | None:
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    found = False
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        found = True
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            mins.x = min(mins.x, world.x)
            mins.y = min(mins.y, world.y)
            mins.z = min(mins.z, world.z)
            maxs.x = max(maxs.x, world.x)
            maxs.y = max(maxs.y, world.y)
            maxs.z = max(maxs.z, world.z)
    if not found:
        return None
    return mins, maxs


def _frame_view() -> None:
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((item for item in area.regions if item.type == "WINDOW"), None)
            space = next((item for item in area.spaces if item.type == "VIEW_3D"), None)
            if space is not None:
                space.clip_end = 2000.0
                space.shading.type = "SOLID"
                space.shading.color_type = "TEXTURE"
                space.overlay.show_bones = True
                space.overlay.show_wireframes = True
                space.overlay.show_stats = True
            if region is None:
                continue
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.object.select_all(action="SELECT")
                bpy.ops.view3d.view_all(center=False)


def _aim_camera() -> None:
    bounds = _mesh_bounds()
    if bounds is None:
        center = Vector((0.0, 0.0, 36.0))
        size = 72.0
    else:
        mins, maxs = bounds
        center = (mins + maxs) * 0.5
        size = max((maxs - mins).length, 32.0)
    bpy.ops.object.camera_add(location=center + Vector((size * 0.9, -size * 1.15, size * 0.45)))
    camera = bpy.context.object
    direction = center - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.clip_start = 0.1
    camera.data.clip_end = 5000.0
    bpy.context.scene.camera = camera


def _render_still(path: Path) -> None:
    _aim_camera()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    world = bpy.data.worlds.new("preview_world")
    world.color = (0.18, 0.2, 0.22)
    scene.world = world
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


def _setup_viewport() -> None:
    _show_armatures()
    _frame_view()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--physics", default="")
    parser.add_argument("--screenshot", default="")
    args = parser.parse_args(_argv_after_dash())
    source = Path(args.input)
    physics = Path(args.physics) if args.physics else None
    shot = Path(args.screenshot) if args.screenshot else None

    tools = _enable_source_tools()
    _clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source))
    if tools and physics is not None and physics.is_file():
        try:
            bpy.ops.import_scene.smd(
                filepath=str(physics),
                append="NEW_ARMATURE",
                doAnim=False,
                upAxis="Z",
                createCollections=False,
            )
        except Exception as exc:
            print(f"physics import skipped: {exc}")
    elif physics is not None and physics.is_file() and not tools:
        print("physics import skipped: Blender Source Tools is not installed")

    _show_armatures()
    if shot is not None:
        _render_still(shot)
        if bpy.app.background:
            return
    if not bpy.app.background:
        bpy.app.timers.register(_setup_viewport, first_interval=0.25)


if __name__ == "__main__":
    main()
