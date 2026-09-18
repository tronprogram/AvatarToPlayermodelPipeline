"""Headless Blender: import aligned GLTF, helper bones, sequences, capsules, DMX.

Run:
  blender --background --python export_playermodel.py -- \\
    --input in.glb --output outdir --proportions male.smd
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

RAGDOLL_CAPSULES = (
    ("ValveBiped.Bip01_Head1", 0.55),
    ("ValveBiped.Bip01_Spine2", 0.45),
    ("ValveBiped.Bip01_Pelvis", 0.40),
    ("ValveBiped.Bip01_L_UpperArm", 0.22),
    ("ValveBiped.Bip01_L_Forearm", 0.20),
    ("ValveBiped.Bip01_L_Hand", 0.35),
    ("ValveBiped.Bip01_R_UpperArm", 0.22),
    ("ValveBiped.Bip01_R_Forearm", 0.20),
    ("ValveBiped.Bip01_R_Hand", 0.35),
    ("ValveBiped.Bip01_L_Thigh", 0.22),
    ("ValveBiped.Bip01_L_Calf", 0.20),
    ("ValveBiped.Bip01_L_Foot", 0.35),
    ("ValveBiped.Bip01_R_Thigh", 0.22),
    ("ValveBiped.Bip01_R_Calf", 0.20),
    ("ValveBiped.Bip01_R_Foot", 0.35),
)

WEIGHT_CULL = 0.0001
SOURCE_BONE_INFLUENCES = 3


def _argv_after_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def _enable_source_tools() -> None:
    import addon_utils

    for name in ("io_scene_valvesource", "io_scene_valvesourcemodel"):
        try:
            addon_utils.enable(name, default_set=True)
            _shim_source_tools_on_blender36()
            return
        except Exception:
            continue
    raise RuntimeError("Blender Source Tools addon is not installed")


def _shim_source_tools_on_blender36() -> None:
    """Source Tools 3.4+ wants Blender 4.1; the wizard still ships 3.6 LTS."""
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
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    for collection in list(bpy.data.collections):
        if collection is not bpy.context.scene.collection:
            bpy.data.collections.remove(collection)


def _prepare_source_space() -> None:
    """glTF importer yields Z-up; match mesh rest to bones, face +X, bake scale."""
    bpy.context.scene.unit_settings.system = "NONE"
    bpy.context.scene.unit_settings.scale_length = 1.0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        obj.data.use_auto_smooth = False
        if getattr(obj.data, "has_custom_normals", False):
            obj.data.free_normals_split()
    # Skinned glTF ignores the mesh node, so root scale hits bones but not verts.
    zs: list[float] = []
    meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.data.vertices
    ]
    for obj in meshes:
        zs.extend((obj.matrix_world @ vert.co).z for vert in obj.data.vertices)
    if zs:
        extent = max(zs) - min(zs)
        scale = 72.0 / extent if extent > 1e-4 else 1.0
        scale_mat = Matrix.Diagonal((scale, scale, scale, 1.0))
        for obj in meshes:
            _transform_mesh(obj, scale_mat)
        bpy.context.view_layer.update()
        print(f"scaled mesh rest by {scale:.4f} to match armature")
    rotate = Matrix.Rotation(math.pi / 2.0, 4, "Z")
    for obj in list(bpy.context.scene.objects):
        if obj.parent is None:
            obj.matrix_world = rotate @ obj.matrix_world
    bpy.context.view_layer.update()
    zs: list[float] = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not obj.data.vertices:
            continue
        zs.extend((obj.matrix_world @ vert.co).z for vert in obj.data.vertices)
    if zs:
        lift = Matrix.Translation((0.0, 0.0, -min(zs)))
        for obj in list(bpy.context.scene.objects):
            if obj.parent is None:
                obj.matrix_world = lift @ obj.matrix_world
        bpy.context.view_layer.update()
    _bake_world_transforms()


def _bake_world_transforms() -> None:
    """Source Tools double-applies object scale; bind data must be 1.0 scale."""
    identity = Matrix.Identity(4)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    mesh_world = {obj.name: obj.matrix_world.copy() for obj in meshes}
    arm_world = {obj.name: obj.matrix_world.copy() for obj in armatures}
    for obj in meshes:
        _transform_mesh(obj, mesh_world[obj.name])
    for obj in armatures:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        for bone in obj.data.edit_bones:
            bone.transform(arm_world[obj.name])
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in meshes + armatures:
        obj.parent = None
        obj.matrix_world = identity
    armature = armatures[0] if armatures else None
    if armature is None:
        return
    for obj in meshes:
        obj.parent = armature
        obj.matrix_parent_inverse = identity.copy()
        if not any(mod.type == "ARMATURE" for mod in obj.modifiers):
            modifier = obj.modifiers.new("Armature", "ARMATURE")
            modifier.object = armature
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    print("baked world transforms to bind pose")


def _transform_mesh(obj, matrix: Matrix) -> None:
    if getattr(obj.data, "has_custom_normals", False):
        obj.data.free_normals_split()
    obj.data.use_auto_smooth = False
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(matrix)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.data.use_auto_smooth = True
    obj.data.auto_smooth_angle = math.pi
    obj.data.calc_loop_triangles()
    obj.data.calc_normals_split()
    obj.data.normals_split_custom_set([tuple(loop.normal) for loop in obj.data.loops])


def _find_armature():
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("Imported GLTF has no armature")


def _named(bones, name: str):
    if name in bones:
        return bones[name]
    short = name.split(".")[-1]
    for bone in bones:
        if bone.name == name or bone.name.endswith(short) or bone.name == short:
            return bone
    return None


def _bone_by_name(armature, name: str):
    return _named(armature.data.bones, name)


def _pose_bone(armature, name: str):
    return _named(armature.pose.bones, name)


def _make_capsule(name: str, radius: float, length: float):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    depth = max(length, radius * 2.0)
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=8,
        radius1=radius,
        radius2=radius,
        depth=depth,
    )
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _align_capsule(obj, armature, bone) -> None:
    head = armature.matrix_world @ bone.head_local
    tail = armature.matrix_world @ bone.tail_local
    center = (head + tail) * 0.5
    direction = tail - head
    if direction.length < 1e-6:
        direction = Vector((0.0, 0.0, 1.0))
    else:
        direction.normalize()
    rotation = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()
    rotation.translation = center
    obj.matrix_world = rotation


def _skin_to_bone(obj, armature, bone_name: str) -> None:
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = armature
    keep = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = keep


def _move_to_collection(obj, collection) -> None:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    collection.objects.link(obj)


def _build_ragdoll(armature, physics):
    built = 0
    for name, radius_scale in RAGDOLL_CAPSULES:
        bone = _bone_by_name(armature, name)
        if bone is None:
            print(f"skip capsule, missing bone {name}")
            continue
        length = (bone.tail_local - bone.head_local).length
        radius = max(length * radius_scale, 1.0)
        obj = _make_capsule(f"capsule_{bone.name.split('.')[-1]}", radius, length)
        _align_capsule(obj, armature, bone)
        _skin_to_bone(obj, armature, bone.name)
        _move_to_collection(obj, physics)
        built += 1
    if built == 0:
        raise RuntimeError("No ragdoll capsules could be aligned to bones")
    print(f"built {built} ragdoll capsules")


def _import_citizen(smd_path: Path):
    before = set(bpy.data.objects)
    result = bpy.ops.import_scene.smd(
        filepath=str(smd_path),
        append="NEW_ARMATURE",
        doAnim=False,
        upAxis="Z",
        createCollections=False,
    )
    if result != {"FINISHED"}:
        raise RuntimeError(f"Failed to import bind pose {smd_path}: {result}")
    added = [
        obj
        for obj in bpy.data.objects
        if obj not in before and obj.type == "ARMATURE"
    ]
    if not added:
        raise RuntimeError(f"Bind pose SMD did not create an armature: {smd_path}")
    print(f"imported citizen bind {smd_path.name} as {added[0].name}")
    return added[0]


def _ensure_helper_bones(target, citizen) -> int:
    """Copy citizen-only bones (forward, Anim_Attachment_*) onto the avatar."""
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="EDIT")
    added = 0
    pending = [
        bone
        for bone in citizen.data.bones
        if _named(target.data.edit_bones, bone.name) is None
    ]
    progress = True
    while pending and progress:
        progress = False
        leftover = []
        for source in pending:
            parent_edit = (
                _named(target.data.edit_bones, source.parent.name)
                if source.parent
                else None
            )
            if source.parent is not None and parent_edit is None:
                leftover.append(source)
                continue
            bone = target.data.edit_bones.new(source.name)
            if parent_edit is not None:
                bone.parent = parent_edit
            inv = target.matrix_world.inverted()
            bone.head = inv @ (citizen.matrix_world @ source.head_local)
            bone.tail = inv @ (citizen.matrix_world @ source.tail_local)
            if (bone.tail - bone.head).length < 0.5:
                direction = Vector((0.0, 1.0, 0.0))
                if parent_edit is not None:
                    parent_dir = parent_edit.tail - parent_edit.head
                    if parent_dir.length > 1e-4:
                        direction = parent_dir.normalized()
                bone.tail = bone.head + direction * 2.0
            bone.use_connect = False
            bone.use_deform = True
            added += 1
            progress = True
        pending = leftover
    bpy.ops.object.mode_set(mode="OBJECT")
    if pending:
        names = ", ".join(bone.name for bone in pending)
        print(f"could not parent helper bones: {names}")
    print(f"added {added} helper bones")
    return added


def _reset_pose(armature) -> None:
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    for pbone in armature.pose.bones:
        pbone.matrix_basis.identity()
    bpy.context.view_layer.update()


def _apply_citizen_pose(target, citizen) -> int:
    """Snap ValveBiped pose bones to the citizen bind (proportion trick)."""
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="POSE")
    applied = 0
    inv = target.matrix_world.inverted()
    for pbone in target.pose.bones:
        source = _pose_bone(citizen, pbone.name)
        if source is None:
            continue
        pbone.matrix = inv @ (citizen.matrix_world @ source.bone.matrix_local)
        applied += 1
    bpy.context.view_layer.update()
    print(f"posed {applied} bones to citizen bind")
    return applied


def _ensure_pose_invertible(armature) -> int:
    """Source Tools inverts each parent pose matrix when writing animation DMX."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    fixed = 0
    for pbone in armature.pose.bones:
        if abs(pbone.matrix.to_3x3().determinant()) > 1e-8:
            continue
        pbone.matrix_basis.identity()
        fixed += 1
    bpy.context.view_layer.update()
    if fixed:
        print(f"restored {fixed} singular pose bones")
    return fixed


def _capture_action(armature, name: str) -> None:
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    armature.animation_data_create()
    armature.animation_data.action = action
    bpy.context.scene.frame_set(1)
    for pbone in armature.pose.bones:
        pbone.keyframe_insert("location", frame=1)
        pbone.keyframe_insert("scale", frame=1)
        if pbone.rotation_mode == "QUATERNION":
            pbone.keyframe_insert("rotation_quaternion", frame=1)
        else:
            pbone.keyframe_insert("rotation_euler", frame=1)
    print(f"action {name}: {len(armature.pose.bones)} bones")


def _keep_sequence_actions() -> None:
    for action in list(bpy.data.actions):
        if action.name not in {"ragdoll", "proportions"}:
            bpy.data.actions.remove(action)


def _clear_active_action(armature) -> None:
    """Rest pose, no action, so mesh/physics bake is not the citizen bind."""
    if armature.animation_data:
        armature.animation_data.action = None
    _reset_pose(armature)


def _drop_citizen(citizen) -> None:
    data = citizen.data
    bpy.data.objects.remove(citizen, do_unlink=True)
    if data.users == 0:
        bpy.data.armatures.remove(data)
    for collection in list(bpy.data.collections):
        if collection is bpy.context.scene.collection:
            continue
        if collection.name in {"reference", "physics"}:
            continue
        if len(collection.objects) == 0:
            bpy.data.collections.remove(collection)


def _configure_export(armature) -> None:
    scene = bpy.context.scene
    scene.vs.dmx_weightlink_threshold = WEIGHT_CULL
    armature.vs.export = True
    armature.vs.subdir = "anims"
    armature.vs.action_filter = "*"
    armature.data.vs.action_selection = "FILTERED"
    try:
        armature.data.vs.implicit_zero_bone = False
    except Exception:
        pass
    print(f"dmx_weightlink_threshold={scene.vs.dmx_weightlink_threshold}")


def _limit_bone_influences(limit: int = SOURCE_BONE_INFLUENCES) -> None:
    """Source studiomdl aborts if any vertex has more than 3 bone weights."""
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not obj.vertex_groups:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.vertex_group_limit_total(limit=limit)
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        print(f"limited {obj.name} to {limit} bone influences")


def _sanitize_material_names() -> None:
    """Source VMT filenames cannot contain colons, spaces, or quotes.

    Ready Player Me slots look like ``hair: Teased spikes_3``; HLMV then
    looks for that literal name under $cdmaterials.
    """
    import re

    used: set[str] = set()
    for mat in bpy.data.materials:
        head = mat.name.split(":", 1)[0].strip() or mat.name
        clean = re.sub(r"[^A-Za-z0-9_]+", "_", head).strip("_") or "mat"
        if clean[0].isdigit():
            clean = f"mat_{clean}"
        name = clean[:63]
        suffix = 2
        while name in used and name != mat.name:
            name = f"{clean[:60]}_{suffix}"
            suffix += 1
        used.add(name)
        if name != mat.name:
            print(f"material {mat.name!r} -> {name!r}")
            mat.name = name


def _export_dmx(out_dir: Path) -> None:
    from io_scene_valvesource.utils import State

    scene = bpy.context.scene
    scene.vs.export_path = str(out_dir)
    scene.vs.export_format = "DMX"
    scene.vs.up_axis = "Z"
    try:
        scene.vs.dmx_encoding = "2"
    except TypeError:
        pass
    try:
        scene.vs.dmx_format = "1"
    except TypeError:
        pass

    State.update_scene()
    names = [item.name for item in scene.vs.export_list]
    print(f"export_list ({len(names)}): {names}")
    if not scene.vs.export_list:
        raise RuntimeError("Source Tools export list is empty")

    result = bpy.ops.export_scene.smd(export_scene=True)
    if result != {"FINISHED"}:
        raise RuntimeError(f"Source Tools export failed: {result}")
    for dmx in (out_dir / "reference.dmx", out_dir / "physics.dmx"):
        if dmx.is_file():
            _rebuild_dmx_normals(dmx)


def _rebuild_dmx_normals(path: Path) -> None:
    """Source Tools writes loop.normal as zeros after mesh transforms; rebuild from faces."""
    from io_scene_valvesource import datamodel

    dm = datamodel.load(str(path))
    seen: set[int] = set()
    filled = 0

    def visit(elem) -> None:
        nonlocal filled
        if elem is None or id(elem) in seen:
            return
        if not hasattr(elem, "type") or not hasattr(elem, "keys"):
            return
        seen.add(id(elem))
        if elem.type == "DmeVertexData" and "positions" in elem and "positionsIndices" in elem:
            positions = [tuple(p) for p in elem["positions"]]
            indices = [int(i) for i in elem["positionsIndices"]]
            accum = [[0.0, 0.0, 0.0] for _ in positions]
            for i in range(0, (len(indices) // 3) * 3, 3):
                ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
                ax, ay, az = positions[ia]
                bx, by, bz = positions[ib]
                cx, cy, cz = positions[ic]
                ux, uy, uz = bx - ax, by - ay, bz - az
                vx, vy, vz = cx - ax, cy - ay, cz - az
                nx = uy * vz - uz * vy
                ny = uz * vx - ux * vz
                nz = ux * vy - uy * vx
                for idx in (ia, ib, ic):
                    accum[idx][0] += nx
                    accum[idx][1] += ny
                    accum[idx][2] += nz
            unit = []
            for x, y, z in accum:
                length = (x * x + y * y + z * z) ** 0.5
                if length < 1e-8:
                    unit.append(datamodel.Vector3([0.0, 0.0, 1.0]))
                else:
                    unit.append(datamodel.Vector3([x / length, y / length, z / length]))
            loop = [unit[idx] for idx in indices]
            elem["normals"] = datamodel.make_array(loop, datamodel.Vector3)
            elem["normalsIndices"] = datamodel.make_array(list(range(len(loop))), int)
            filled += 1
            return
        for value in elem.values():
            if hasattr(value, "type") and hasattr(value, "keys"):
                visit(value)
                continue
            if isinstance(value, (str, bytes)):
                continue
            try:
                items = iter(value)
            except TypeError:
                continue
            for child in items:
                if hasattr(child, "type") and hasattr(child, "keys"):
                    visit(child)

    visit(dm.root)
    dm.write(str(path), "binary", 2)
    print(f"rebuilt normals in {path.name} ({filled} meshes)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--proportions", required=True)
    args = parser.parse_args(_argv_after_dash())
    source = Path(args.input)
    out_dir = Path(args.output)
    proportions = Path(args.proportions)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not proportions.is_file():
        raise FileNotFoundError(f"Missing bind-pose SMD: {proportions}")

    _enable_source_tools()
    _clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source))
    _prepare_source_space()

    armature = _find_armature()
    citizen = _import_citizen(proportions)
    _ensure_helper_bones(armature, citizen)
    _reset_pose(armature)
    _capture_action(armature, "ragdoll")
    _apply_citizen_pose(armature, citizen)
    _ensure_pose_invertible(armature)
    _capture_action(armature, "proportions")
    _keep_sequence_actions()
    _drop_citizen(citizen)
    _clear_active_action(armature)
    _configure_export(armature)

    reference = bpy.data.collections.new("reference")
    physics = bpy.data.collections.new("physics")
    bpy.context.scene.collection.children.link(reference)
    bpy.context.scene.collection.children.link(physics)
    reference.vs.export = True
    physics.vs.export = True
    reference.vs.subdir = ""
    physics.vs.subdir = ""

    for obj in list(bpy.context.scene.objects):
        if obj.type in {"MESH", "ARMATURE"}:
            _move_to_collection(obj, reference)

    _build_ragdoll(armature, physics)
    _limit_bone_influences()
    _sanitize_material_names()
    _export_dmx(out_dir)
    print(f"wrote DMX under {out_dir}")


if __name__ == "__main__":
    main()
