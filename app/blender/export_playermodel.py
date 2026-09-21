"""Headless Blender: import aligned GLTF, helper bones, sequences, capsules, DMX.

Run:
  blender --background --python export_playermodel.py -- \\
    --input in.glb --output outdir --proportions male.smd
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

_ILLEGAL_MAT = re.compile(r"[^A-Za-z0-9_]+")
_BLENDER_DUP = re.compile(r"(?:\.\d{3})+$")

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

_VALVEBIPEDS = (
    "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine1",
    "ValveBiped.Bip01_Spine2",
    "ValveBiped.Bip01_Spine4",
    "ValveBiped.Bip01_Neck1",
    "ValveBiped.Bip01_Head1",
    "ValveBiped.Bip01_R_Clavicle",
    "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_R_Finger0",
    "ValveBiped.Bip01_R_Finger01",
    "ValveBiped.Bip01_R_Finger02",
    "ValveBiped.Bip01_R_Finger1",
    "ValveBiped.Bip01_R_Finger11",
    "ValveBiped.Bip01_R_Finger12",
    "ValveBiped.Bip01_R_Finger2",
    "ValveBiped.Bip01_R_Finger21",
    "ValveBiped.Bip01_R_Finger22",
    "ValveBiped.Bip01_R_Finger3",
    "ValveBiped.Bip01_R_Finger31",
    "ValveBiped.Bip01_R_Finger32",
    "ValveBiped.Bip01_R_Finger4",
    "ValveBiped.Bip01_R_Finger41",
    "ValveBiped.Bip01_R_Finger42",
    "ValveBiped.Bip01_L_Clavicle",
    "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_L_Finger0",
    "ValveBiped.Bip01_L_Finger01",
    "ValveBiped.Bip01_L_Finger02",
    "ValveBiped.Bip01_L_Finger1",
    "ValveBiped.Bip01_L_Finger11",
    "ValveBiped.Bip01_L_Finger12",
    "ValveBiped.Bip01_L_Finger2",
    "ValveBiped.Bip01_L_Finger21",
    "ValveBiped.Bip01_L_Finger22",
    "ValveBiped.Bip01_L_Finger3",
    "ValveBiped.Bip01_L_Finger31",
    "ValveBiped.Bip01_L_Finger32",
    "ValveBiped.Bip01_L_Finger4",
    "ValveBiped.Bip01_L_Finger41",
    "ValveBiped.Bip01_L_Finger42",
    "ValveBiped.Bip01_R_Thigh",
    "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Foot",
    "ValveBiped.Bip01_R_Toe0",
    "ValveBiped.Bip01_L_Thigh",
    "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Foot",
    "ValveBiped.Bip01_L_Toe0",
)

# Guide Align bones script: even entries get LOCKED_TRACK at the odd child.
_VALVEBIPEDS2 = (
    "ValveBiped.Bip01_L_Thigh",
    "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Foot",
    "ValveBiped.Bip01_R_Thigh",
    "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Foot",
    "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_L_Finger1",
    "ValveBiped.Bip01_L_Finger11",
    "ValveBiped.Bip01_L_Finger11",
    "ValveBiped.Bip01_L_Finger12",
    "ValveBiped.Bip01_L_Finger2",
    "ValveBiped.Bip01_L_Finger21",
    "ValveBiped.Bip01_L_Finger21",
    "ValveBiped.Bip01_L_Finger22",
    "ValveBiped.Bip01_L_Finger3",
    "ValveBiped.Bip01_L_Finger31",
    "ValveBiped.Bip01_L_Finger31",
    "ValveBiped.Bip01_L_Finger32",
    "ValveBiped.Bip01_L_Finger4",
    "ValveBiped.Bip01_L_Finger41",
    "ValveBiped.Bip01_L_Finger41",
    "ValveBiped.Bip01_L_Finger42",
    "ValveBiped.Bip01_R_Finger1",
    "ValveBiped.Bip01_R_Finger11",
    "ValveBiped.Bip01_R_Finger11",
    "ValveBiped.Bip01_R_Finger12",
    "ValveBiped.Bip01_R_Finger2",
    "ValveBiped.Bip01_R_Finger21",
    "ValveBiped.Bip01_R_Finger21",
    "ValveBiped.Bip01_R_Finger22",
    "ValveBiped.Bip01_R_Finger3",
    "ValveBiped.Bip01_R_Finger31",
    "ValveBiped.Bip01_R_Finger31",
    "ValveBiped.Bip01_R_Finger32",
    "ValveBiped.Bip01_R_Finger4",
    "ValveBiped.Bip01_R_Finger41",
    "ValveBiped.Bip01_R_Finger41",
    "ValveBiped.Bip01_R_Finger42",
)

_CONDITIONAL_REMOVE_BONES = tuple(
    name
    for name in _VALVEBIPEDS
    if "Finger" in name or name.endswith("Toe0")
)


def _argv_after_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def _smd_operator_ready() -> bool:
    return "smd" in dir(bpy.ops.import_scene)


def _enable_source_tools() -> None:
    import addon_utils

    _shim_source_tools_session_uid()
    last_error = ""
    for name in ("io_scene_valvesource", "io_scene_valvesourcemodel"):
        try:
            addon_utils.enable(name, default_set=True)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if _smd_operator_ready():
            return
    detail = f" {last_error}" if last_error else ""
    raise RuntimeError(
        "Blender Source Tools did not register import_scene.smd."
        + detail
        + " Re-run Setup so the addon is installed in Blender's user scripts/addons."
    )


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
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    for collection in list(bpy.data.collections):
        if collection is not bpy.context.scene.collection:
            bpy.data.collections.remove(collection)


def _set_auto_smooth(mesh, enabled: bool, angle: float | None = None) -> None:
    """Auto-smooth was removed from Mesh in Blender 4.1 / 5.x."""
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = enabled
        if enabled and angle is not None and hasattr(mesh, "auto_smooth_angle"):
            mesh.auto_smooth_angle = angle


def _free_split_normals(mesh) -> None:
    if getattr(mesh, "has_custom_normals", False) and hasattr(mesh, "free_normals_split"):
        mesh.free_normals_split()


def _prepare_source_space() -> None:
    """glTF importer yields Z-up. Scale to 72 and stand on Z=0.

    Do not yaw to +X. Bob's Collision Model I and Source Tools scene
    both use −Y as the model's front. Source Tools export maps that.
    """
    bpy.context.scene.unit_settings.system = "NONE"
    bpy.context.scene.unit_settings.scale_length = 1.0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        _set_auto_smooth(obj.data, False)
        _free_split_normals(obj.data)
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
        print(f"scaled mesh rest by {scale:.4f} to Source height")
        for obj in bpy.context.scene.objects:
            if obj.type != "ARMATURE":
                continue
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            for bone in obj.data.edit_bones:
                bone.transform(scale_mat)
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        print(f"scaled armature bones by {scale:.4f} (same factor as mesh)")
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
        _recalculate_outside(obj)
        if _should_two_side(obj):
            _make_two_sided(obj)
    bpy.context.view_layer.update()
    print("baked world transforms to bind pose")


def _transform_mesh(obj, matrix: Matrix) -> None:
    _free_split_normals(obj.data)
    _set_auto_smooth(obj.data, False)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(matrix)
    if matrix.to_3x3().determinant() < 0.0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    _apply_split_normals(obj)


def _recalculate_outside(obj) -> None:
    """Recalc Outside using the whole mesh, not each face-island volume.

    Blender's *Recalculate Outside* treats each disconnected island as its
    own solid. RPM heads are ~12 islands, so that operator flips eye and
    mouth patches independently. Make each island consistent, then orient
    it so the painted side points away from the mesh centroid.
    """
    _free_split_normals(obj.data)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    if not bm.verts or not bm.faces:
        bm.free()
        return
    center = Vector((0.0, 0.0, 0.0))
    for vert in bm.verts:
        center += vert.co
    center /= len(bm.verts)
    visited = [False] * len(bm.faces)
    islands = 0
    flipped = 0
    for start in bm.faces:
        if visited[start.index]:
            continue
        island = _flood_island(start, visited)
        islands += 1
        _make_island_consistent(island)
        for face in island:
            face.normal_update()
        score = 0.0
        for face in island:
            score += (face.calc_center_median() - center).dot(face.normal) * face.calc_area()
        if score < 0.0:
            for face in island:
                face.normal_flip()
            flipped += len(island)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    _apply_split_normals(obj)
    print(f"recalc outside {obj.name}: {islands} islands, flipped {flipped} faces")


def _mesh_kind(obj) -> str:
    """RPM slot from the mesh/material name, not a specific outfit.

    Ready Player Me pieces are ``head``, ``body``, ``hair: …``, ``shirt: …``.
    Only the head (painted face + cavities) and body skin must stay one-sided.
    """
    slot = obj.name.split(":", 1)[0].strip().lower()
    if slot.startswith("capsule") or slot.startswith("collision"):
        return "physics"
    if slot == "head":
        return "head"
    if slot == "body":
        return "body"
    for mat in obj.data.materials:
        if mat is None:
            continue
        name = mat.name.split(":", 1)[0].strip().lower()
        if name == "face" or name.startswith("face_"):
            return "head"
        if name == "body" or name.startswith("body_"):
            return "body"
    return "outfit"


def _should_two_side(obj) -> bool:
    """Clothes and hair can keep holes after Recalc Outside; skin cannot."""
    return _mesh_kind(obj) == "outfit"


def _make_two_sided(obj) -> None:
    """Duplicate every face onto new verts and flip the copies.

    Source culls backfaces. Recalc Outside orients the outer shell, but RPM
    clothes are open islands with lining, so some views still see holes.
    Two-siding fills those on any outfit slot. Do not use this on the head.
    """
    _free_split_normals(obj.data)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    if not bm.verts or not bm.faces:
        bm.free()
        return
    bm.verts.layers.deform.verify()
    faces = list(bm.faces)
    verts = set()
    edges = set()
    for face in faces:
        verts.update(face.verts)
        edges.update(face.edges)
    result = bmesh.ops.duplicate(bm, geom=list(verts) + list(edges) + faces)
    new_faces = [item for item in result["geom"] if isinstance(item, bmesh.types.BMFace)]
    for face in new_faces:
        face.normal_flip()
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    _apply_split_normals(obj)
    print(f"two-sided {len(new_faces)} faces on {obj.name}")


def _flood_island(start, visited: list[bool]):
    stack = [start]
    visited[start.index] = True
    faces = []
    while stack:
        face = stack.pop()
        faces.append(face)
        for edge in face.edges:
            for other in edge.link_faces:
                if visited[other.index]:
                    continue
                visited[other.index] = True
                stack.append(other)
    return faces


def _make_island_consistent(faces) -> None:
    """Same winding across shared edges; does not pick inside vs outside."""
    if not faces:
        return
    seen = {faces[0].index}
    stack = [faces[0]]
    while stack:
        face = stack.pop()
        for edge in face.edges:
            linked = edge.link_faces
            if len(linked) != 2:
                continue
            other = linked[1] if linked[0] == face else linked[0]
            if other.index in seen:
                continue
            if _edge_winding_dir(face, edge) == _edge_winding_dir(other, edge):
                other.normal_flip()
            seen.add(other.index)
            stack.append(other)


def _edge_winding_dir(face, edge) -> int:
    a, b = edge.verts
    for loop in face.loops:
        if loop.vert == a and loop.link_loop_next.vert == b:
            return 1
        if loop.vert == b and loop.link_loop_next.vert == a:
            return -1
    return 0


def _apply_split_normals(obj) -> None:
    mesh = obj.data
    for poly in mesh.polygons:
        poly.use_smooth = True
    _set_auto_smooth(mesh, True, math.pi)
    if hasattr(mesh, "shade_smooth"):
        mesh.shade_smooth()
    mesh.calc_loop_triangles()
    if hasattr(mesh, "calc_normals_split"):
        mesh.calc_normals_split()
    if hasattr(mesh, "normals_split_custom_set") and mesh.loops:
        mesh.normals_split_custom_set([tuple(loop.normal) for loop in mesh.loops])


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


_SPAN_CHILD = {
    "ValveBiped.Bip01_Pelvis": "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine2": "ValveBiped.Bip01_Neck1",
    "ValveBiped.Bip01_Head1": "",
    "ValveBiped.Bip01_L_Thigh": "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_L_Calf": "ValveBiped.Bip01_L_Foot",
    "ValveBiped.Bip01_L_Foot": "ValveBiped.Bip01_L_Toe0",
    "ValveBiped.Bip01_R_Thigh": "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_R_Calf": "ValveBiped.Bip01_R_Foot",
    "ValveBiped.Bip01_R_Foot": "ValveBiped.Bip01_R_Toe0",
    "ValveBiped.Bip01_L_UpperArm": "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_L_Forearm": "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_R_UpperArm": "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_R_Forearm": "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_L_Hand": "ValveBiped.Bip01_L_Finger2",
    "ValveBiped.Bip01_R_Hand": "ValveBiped.Bip01_R_Finger2",
}


def _bone_endpoints(armature, bone) -> tuple[Vector, Vector]:
    """Joint → next ValveBiped joint. Visual tails often point along +X."""
    head = armature.matrix_world @ bone.head_local
    child_name = _SPAN_CHILD.get(bone.name)
    if child_name == "":
        return head, head + Vector((0.0, 0.0, 8.0))
    if child_name:
        child = _bone_by_name(armature, child_name)
        if child is not None:
            return head, armature.matrix_world @ child.head_local
    best = None
    best_len = 1.0
    for child in armature.data.bones:
        if child.parent != bone or child.name not in _VALVEBIPEDS:
            continue
        loc = armature.matrix_world @ child.head_local
        dist = (loc - head).length
        if dist > best_len:
            best_len = dist
            best = loc
    if best is not None:
        return head, best
    return head, armature.matrix_world @ bone.tail_local


def _bake_armature_identity(armature) -> None:
    """Fold object rotation into the rest pose so bone Y equals world limb."""
    world = armature.matrix_world.copy()
    if world.is_identity:
        return
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in armature.data.edit_bones:
        bone.transform(world)
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    print("baked citizen armature object transform into rest bones")


_ARM_BONE_MARKERS = (
    "Clavicle",
    "UpperArm",
    "Forearm",
    "Hand",
    "Wrist",
    "Finger",
    "Anim_Attachment_L",
    "Anim_Attachment_R",
)

# Xbox avatar joints that map onto the ValveBiped arm chain. Convert remaps
# these before Blender; keep the raw names so a leftover joint_* skin still
# crops C-arms instead of deleting every vert.
_ARM_JOINTS = frozenset(
    {
        "joint_12",
        "joint_16",
        "joint_20",
        "joint_22",
        "joint_25",
        "joint_28",
        "joint_33",
        "joint_36",
        "joint_37",
        "joint_38",
        "joint_39",
        "joint_40",
        "joint_43",
        "joint_44",
        "joint_45",
        "joint_46",
        "joint_47",
        "joint_50",
        "joint_51",
        "joint_52",
        "joint_53",
        "joint_54",
        "joint_55",
        "joint_56",
        "joint_57",
        "joint_58",
        "joint_59",
        "joint_60",
        "joint_61",
        "joint_62",
        "joint_63",
        "joint_64",
        "joint_65",
        "joint_66",
        "joint_67",
        "joint_68",
        "joint_69",
        "joint_70",
    }
)


def _is_arm_bone(name: str) -> bool:
    return name in _ARM_JOINTS or any(marker in name for marker in _ARM_BONE_MARKERS)


def _build_carms(reference, arms, armature) -> int:
    """Guide 'fast' C-arms: keep verts whose strongest weight is an arm bone."""
    kept = 0
    print(
        f"c-arms candidates {[obj.name for obj in reference.objects if obj.type == 'MESH']}"
    )
    for obj in list(reference.objects):
        if obj.type != "MESH" or obj.name.startswith("capsule"):
            continue
        copy = obj.copy()
        copy.data = obj.data.copy()
        copy.name = f"arms_{obj.name.split(':')[0][:40]}"
        arms.objects.link(copy)
        if _keep_arm_verts(copy):
            kept += 1
            continue
        arms.objects.unlink(copy)
        bpy.data.objects.remove(copy, do_unlink=True)
    if armature.name not in arms.objects:
        arms.objects.link(armature)
    if kept == 0:
        raise RuntimeError("C-arms export produced no arm meshes")
    print(f"c-arms meshes {kept}")
    return kept


_CARMS_FIT_BONES = (
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_L_Finger0",
    "ValveBiped.Bip01_L_Finger01",
    "ValveBiped.Bip01_L_Finger02",
    "ValveBiped.Bip01_L_Finger1",
    "ValveBiped.Bip01_L_Finger11",
    "ValveBiped.Bip01_L_Finger12",
    "ValveBiped.Bip01_L_Finger2",
    "ValveBiped.Bip01_L_Finger21",
    "ValveBiped.Bip01_L_Finger22",
    "ValveBiped.Bip01_L_Finger3",
    "ValveBiped.Bip01_L_Finger31",
    "ValveBiped.Bip01_L_Finger32",
    "ValveBiped.Bip01_L_Finger4",
    "ValveBiped.Bip01_L_Finger41",
    "ValveBiped.Bip01_L_Finger42",
    "ValveBiped.Bip01_R_Finger0",
    "ValveBiped.Bip01_R_Finger01",
    "ValveBiped.Bip01_R_Finger02",
    "ValveBiped.Bip01_R_Finger1",
    "ValveBiped.Bip01_R_Finger11",
    "ValveBiped.Bip01_R_Finger12",
    "ValveBiped.Bip01_R_Finger2",
    "ValveBiped.Bip01_R_Finger21",
    "ValveBiped.Bip01_R_Finger22",
    "ValveBiped.Bip01_R_Finger3",
    "ValveBiped.Bip01_R_Finger31",
    "ValveBiped.Bip01_R_Finger32",
    "ValveBiped.Bip01_R_Finger4",
    "ValveBiped.Bip01_R_Finger41",
    "ValveBiped.Bip01_R_Finger42",
)


def _fit_carms_to_default(armature, arms, carms_ref: Path) -> None:
    """Guide Better C-arm: pose our fingers to the default citizen C-arm.

    Thumb first (citizen thumbs are rotated), then the other chains. Uses a
    duplicate armature so the playermodel rest stays on the avatar bind.
    """
    if not carms_ref.is_file():
        print(f"c-arms: skip default fit, missing {carms_ref}")
        return
    before = set(bpy.data.objects)
    ref = _import_citizen(carms_ref)
    ref.name = "c_arms_citizen"
    imported = [obj for obj in bpy.data.objects if obj not in before]
    carms_arm = armature.copy()
    carms_arm.data = armature.data.copy()
    carms_arm.name = "c_arms"
    bpy.context.scene.collection.objects.link(carms_arm)
    if carms_arm.name not in arms.objects:
        arms.objects.link(carms_arm)
    if armature.name in arms.objects:
        arms.objects.unlink(armature)
    for obj in list(arms.objects):
        if obj.type != "MESH":
            continue
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE":
                modifier.object = carms_arm
        if obj.parent == armature:
            obj.parent = carms_arm
            obj.matrix_parent_inverse = carms_arm.matrix_world.inverted()

    our_hand = armature.data.bones.get("ValveBiped.Bip01_R_Hand")
    ref_hand = ref.data.bones.get("ValveBiped.Bip01_R_Hand")
    if our_hand is not None and ref_hand is not None:
        lift = (armature.matrix_world @ our_hand.head_local).z - (
            ref.matrix_world @ ref_hand.head_local
        ).z
        ref.location.z += lift
        bpy.context.view_layer.update()

    bpy.context.view_layer.objects.active = carms_arm
    bpy.ops.object.mode_set(mode="POSE")
    _reset_pose(carms_arm)
    fitted = 0
    for name in _CARMS_FIT_BONES:
        dest = carms_arm.pose.bones.get(name)
        src = ref.pose.bones.get(name)
        if dest is None or src is None:
            continue
        dest.matrix = ref.matrix_world @ src.matrix
        bpy.context.view_layer.update()
        fitted += 1
    print(f"c-arms: posed {fitted} bones to default citizen C-arm")

    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(arms.objects):
        if obj.type != "MESH":
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for modifier in list(obj.modifiers):
            if modifier.type == "ARMATURE":
                bpy.ops.object.modifier_apply(modifier=modifier.name)

    bpy.context.view_layer.objects.active = carms_arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(arms.objects):
        if obj.type != "MESH":
            continue
        modifier = obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = carms_arm

    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)


def _deform_layer(bm):
    """Blender 5.2 ``verify()`` can create a second empty deform layer.

    Use the existing named layer when present; never let ``verify()`` become
    the active empty one we then read as 'no weights'.
    """
    existing = bm.verts.layers.deform.active
    if existing is not None:
        return existing
    return bm.verts.layers.deform.verify()


def _keep_arm_verts(obj) -> bool:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    deform = _deform_layer(bm)
    groups = {group.index: group.name for group in obj.vertex_groups}
    dead = []
    empty = 0
    armish = 0
    for vert in bm.verts:
        weights = vert[deform]
        if not weights:
            empty += 1
            dead.append(vert)
            continue
        best = max(weights.keys(), key=lambda index: weights[index])
        if _is_arm_bone(groups.get(best, "")):
            armish += 1
        else:
            dead.append(vert)
    print(
        f"c-arms {obj.name}: verts={len(bm.verts)} groups={len(groups)} "
        f"empty={empty} arm={armish} dead={len(dead)}"
    )
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="VERTS")
    kept = bool(bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return kept


def _move_to_collection(obj, collection) -> None:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    collection.objects.link(obj)


def _is_physics_mesh(obj) -> bool:
    name = obj.name.lower()
    return name.startswith("capsule") or name.startswith("collision")


def _mesh_world_aabb(objects):
    xs, ys, zs = [], [], []
    for obj in objects:
        if obj.type != "MESH" or not obj.data.vertices:
            continue
        for vert in obj.data.vertices:
            world = obj.matrix_world @ vert.co
            xs.append(world.x)
            ys.append(world.y)
            zs.append(world.z)
    if not xs:
        return None
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


_FIT_GROUP_ALIASES = {
    "ValveBiped.Bip01_Spine": (
        "ValveBiped.Bip01_Spine",
        "ValveBiped.Bip01_Spine1",
        "ValveBiped.Bip01_Spine2",
    ),
    "ValveBiped.Bip01_L_Foot": (
        "ValveBiped.Bip01_L_Foot",
        "ValveBiped.Bip01_L_Toe0",
    ),
    "ValveBiped.Bip01_R_Foot": (
        "ValveBiped.Bip01_R_Foot",
        "ValveBiped.Bip01_R_Toe0",
    ),
}
_PER_AXIS_FIT_GROUPS = {
    "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Pelvis",
    "ValveBiped.Bip01_L_Calf",
    "ValveBiped.Bip01_R_Calf",
    "ValveBiped.Bip01_L_UpperArm",
    "ValveBiped.Bip01_R_UpperArm",
    "ValveBiped.Bip01_L_Forearm",
    "ValveBiped.Bip01_R_Forearm",
    "ValveBiped.Bip01_L_Hand",
    "ValveBiped.Bip01_R_Hand",
    "ValveBiped.Bip01_L_Foot",
    "ValveBiped.Bip01_R_Foot",
}


def _aabb_points(points: list[Vector]) -> tuple[Vector, Vector]:
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def _fit_target_points(
    bone_names: tuple[str, ...], *, union: bool = False
) -> list[Vector]:
    """Prefer skin (head/body); clothes only if the bone has no skin verts.

    ``union`` keeps every listed bone (chest = whole spine chain). The default
    returns as soon as one bone has enough verts, which crushed Spine to 0.55.
    """
    skin: list[Vector] = []
    clothes: list[Vector] = []
    for name in bone_names:
        short = name.split(".")[-1]
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH" or _is_physics_mesh(obj) or not obj.vertex_groups:
                continue
            groups = {
                group.index
                for group in obj.vertex_groups
                if group.name == name or group.name.endswith(short)
            }
            if not groups:
                continue
            dest = skin if _mesh_kind(obj) in {"head", "body"} else clothes
            for vert in obj.data.vertices:
                if not vert.groups:
                    continue
                best = max(vert.groups, key=lambda item: item.weight)
                if best.weight < 0.35 or best.group not in groups:
                    continue
                dest.append(obj.matrix_world @ vert.co)
        if not union and len(skin) >= 6:
            return skin
    if len(skin) >= 6:
        return skin
    return clothes if len(clothes) >= 6 else skin or clothes


def _group_island(obj, group) -> tuple[list[int], list[Vector]]:
    island: list[int] = []
    points: list[Vector] = []
    for vert in obj.data.vertices:
        if not any(
            item.group == group.index and item.weight >= 0.5 for item in vert.groups
        ):
            continue
        island.append(vert.index)
        points.append(obj.matrix_world @ vert.co)
    return island, points


def _fit_collision_islands(obj, armature, *, uniform: bool = False) -> None:
    """Scale/move each convex piece onto this avatar, like Bob's guide does by hand."""
    inv = obj.matrix_world.inverted()
    for group in obj.vertex_groups:
        names = _FIT_GROUP_ALIASES.get(group.name, (group.name,))
        per_axis = group.name in _PER_AXIS_FIT_GROUPS
        body = _fit_target_points(names, union=per_axis)
        if len(body) < 3:
            bone = _bone_by_name(armature, names[0])
            if bone is None:
                print(f"skip fit {group.name}")
                continue
            head, tail = _bone_endpoints(armature, bone)
            body = [head, (head + tail) * 0.5, tail]
        island, points = _group_island(obj, group)
        if len(points) < 4:
            continue
        c0, c1 = _aabb_points(points)
        b0, b1 = _aabb_points(body)
        col_c = (c0 + c1) * 0.5
        bone_c = _island_bone_center(armature, group.name)
        body_c = bone_c if bone_c is not None else (b0 + b1) * 0.5
        col_s = c1 - c0
        body_s = b1 - b0
        if per_axis:
            scale = Vector((1.0, 1.0, 1.0))
            for axis in range(3):
                if col_s[axis] > 0.5:
                    scale[axis] = max(0.85, min(2.2, body_s[axis] / col_s[axis]))
        elif uniform:
            long_i = max(range(3), key=lambda axis: col_s[axis])
            if col_s[long_i] > 0.5:
                u = max(0.55, min(1.8, body_s[long_i] / col_s[long_i]))
            else:
                u = 1.0
            scale = Vector((u, u, u))
        else:
            scale = Vector((1.0, 1.0, 1.0))
            for axis in range(3):
                if col_s[axis] > 0.5:
                    scale[axis] = max(0.45, min(2.2, body_s[axis] / col_s[axis]))
        for index in island:
            world = obj.matrix_world @ obj.data.vertices[index].co
            offset = world - col_c
            world = body_c + Vector(
                (offset.x * scale.x, offset.y * scale.y, offset.z * scale.z)
            )
            obj.data.vertices[index].co = inv @ world
        if group.name == "ValveBiped.Bip01_Spine":
            drop = _spine_drop(armature, obj, group)
            if drop > 0.5:
                for index in island:
                    world = obj.matrix_world @ obj.data.vertices[index].co
                    world.z -= drop
                    obj.data.vertices[index].co = inv @ world
                print(f"fit Spine lowered {drop:.1f}")
        obj.data.update()
        print(
            f"fit {group.name} "
            f"scale=({scale.x:.2f},{scale.y:.2f},{scale.z:.2f}) "
            f"n={len(island)}"
        )


# Reference ports keep the chest diamond inside the clothes, not on the sleeves.
_TORSO_INNER_SCALE = {
    "ValveBiped.Bip01_Spine": Vector((0.60, 0.80, 0.90)),
    "ValveBiped.Bip01_Pelvis": Vector((0.78, 0.85, 0.88)),
}


def _shrink_torso_islands(obj) -> None:
    """Scale the spine/pelvis hulls down around their centers after the AABB fit."""
    inv = obj.matrix_world.inverted()
    for name, scale in _TORSO_INNER_SCALE.items():
        group = obj.vertex_groups.get(name)
        if group is None:
            continue
        island, points = _group_island(obj, group)
        if len(points) < 4:
            continue
        c0, c1 = _aabb_points(points)
        center = (c0 + c1) * 0.5
        for index in island:
            world = obj.matrix_world @ obj.data.vertices[index].co
            offset = world - center
            world = center + Vector(
                (offset.x * scale.x, offset.y * scale.y, offset.z * scale.z)
            )
            obj.data.vertices[index].co = inv @ world
        obj.data.update()
        print(
            f"torso shrink {name} "
            f"scale=({scale.x:.2f},{scale.y:.2f},{scale.z:.2f})"
        )


def _island_bone_center(armature, group_name: str) -> Vector | None:
    """Midpoint of the ValveBiped span this hull should sit on."""
    span = _island_bone_span(armature, group_name)
    if span is None:
        return None
    start, end = span
    return (start + end) * 0.5


def _island_bone_span(armature, group_name: str) -> tuple[Vector, Vector] | None:
    """Joint → next joint for this hull (aliases cover a bone chain)."""
    names = _FIT_GROUP_ALIASES.get(group_name, (group_name,))
    first = _bone_by_name(armature, names[0])
    last = _bone_by_name(armature, names[-1]) or first
    if first is None or last is None:
        return None
    start, _unused = _bone_endpoints(armature, first)
    _unused, end = _bone_endpoints(armature, last)
    if (end - start).length < 1.0:
        return None
    return start, end


# Head is a blob. Spine/Pelvis stay AABB-fitted + inner-scaled so the chest
# cage does not grow back into a citizen-sized pillar.
_NO_SPAN_GROUPS = {
    "ValveBiped.Bip01_Head1",
    "ValveBiped.Bip01_Spine",
    "ValveBiped.Bip01_Spine2",
    "ValveBiped.Bip01_Pelvis",
}


def _head_mesh_aabb() -> tuple[Vector, Vector] | None:
    meshes = [
        item
        for item in bpy.context.scene.objects
        if item.type == "MESH"
        and not _is_physics_mesh(item)
        and _mesh_kind(item) == "head"
    ]
    box = _mesh_world_aabb(meshes)
    if box is None:
        return None
    return Vector((box[0], box[1], box[2])), Vector((box[3], box[4], box[5]))


def _seat_head_on_skull(obj, armature) -> None:
    """The Head1 island is a sphere. Uniform fit grows it down onto Neck1."""
    group = obj.vertex_groups.get("ValveBiped.Bip01_Head1")
    if group is None:
        return
    island, points = _group_island(obj, group)
    if len(points) < 4:
        return
    inv = obj.matrix_world.inverted()
    c0, c1 = _aabb_points(points)
    center = (c0 + c1) * 0.5
    mesh = _head_mesh_aabb()
    if mesh is not None:
        m0, m1 = mesh
        dest = (m0 + m1) * 0.5
        delta = dest - center
        if delta.length >= 0.05:
            for index in island:
                world = obj.matrix_world @ obj.data.vertices[index].co
                obj.data.vertices[index].co = inv @ (world + delta)
            obj.data.update()
            island, points = _group_island(obj, group)
            c0, c1 = _aabb_points(points)
            center = (c0 + c1) * 0.5
            print(
                f"head lift d=({delta.x:.1f},{delta.y:.1f},{delta.z:.1f})"
            )
    head = _bone_by_name(armature, "ValveBiped.Bip01_Head1")
    neck = _bone_by_name(armature, "ValveBiped.Bip01_Neck1")
    pivot = armature.matrix_world @ head.head_local if head is not None else center
    scale = Vector((0.88, 0.88, 0.82))
    for index in island:
        world = obj.matrix_world @ obj.data.vertices[index].co
        offset = world - pivot
        world = pivot + Vector(
            (offset.x * scale.x, offset.y * scale.y, offset.z * scale.z)
        )
        obj.data.vertices[index].co = inv @ world
    obj.data.update()
    island, points = _group_island(obj, group)
    c0, c1 = _aabb_points(points)
    if neck is not None:
        floor = (armature.matrix_world @ neck.head_local).z + 2.0
        extra = floor - c0.z
        if extra > 0.05:
            for index in island:
                world = obj.matrix_world @ obj.data.vertices[index].co
                world.z += extra
                obj.data.vertices[index].co = inv @ world
            obj.data.update()
            print(f"head clear neck +{extra:.1f}")
    print(f"head shrink around Head1 scale=({scale.x:.2f},{scale.y:.2f},{scale.z:.2f})")


def _join_pelvis_to_thighs(obj) -> None:
    """Drop the hip box onto the thigh tops. Seat-on-spine-center left a crotch gap."""
    inv = obj.matrix_world.inverted()
    pelvis = obj.vertex_groups.get("ValveBiped.Bip01_Pelvis")
    if pelvis is None:
        return
    island, points = _group_island(obj, pelvis)
    if len(points) < 4:
        return
    thigh_z: list[float] = []
    for name in ("ValveBiped.Bip01_L_Thigh", "ValveBiped.Bip01_R_Thigh"):
        group = obj.vertex_groups.get(name)
        if group is None:
            continue
        _unused, thigh_pts = _group_island(obj, group)
        if thigh_pts:
            thigh_z.append(max(point.z for point in thigh_pts))
    if not thigh_z:
        return
    target = max(thigh_z) - 1.5
    p0, _p1 = _aabb_points(points)
    drop = p0.z - target
    if drop < 0.25:
        return
    for index in island:
        world = obj.matrix_world @ obj.data.vertices[index].co
        world.z -= drop
        obj.data.vertices[index].co = inv @ world
    obj.data.update()
    print(f"pelvis drop {drop:.1f} onto thighs")


def _seat_islands_on_bones(obj, armature) -> None:
    """Slide each hull onto its bone so the ragdoll is not a pile of gaps."""
    inv = obj.matrix_world.inverted()
    for group in obj.vertex_groups:
        if group.name in _NO_SPAN_GROUPS:
            continue
        island, points = _group_island(obj, group)
        if len(points) < 4:
            continue
        dest = _island_bone_center(armature, group.name)
        if dest is None:
            continue
        c0, c1 = _aabb_points(points)
        delta = dest - (c0 + c1) * 0.5
        if delta.length < 0.05:
            continue
        for index in island:
            world = obj.matrix_world @ obj.data.vertices[index].co
            obj.data.vertices[index].co = inv @ (world + delta)
        obj.data.update()
        print(
            f"seat {group.name} "
            f"d=({delta.x:.1f},{delta.y:.1f},{delta.z:.1f})"
        )


def _span_islands_along_bones(obj, armature) -> None:
    """Stretch limb hulls to the bone they cover so pieces meet at the joints.

    Only the component along the bone moves. Thickness stays. Torso/head are
    skipped — those were already sized to the mesh on purpose.
    """
    inv = obj.matrix_world.inverted()
    for group in obj.vertex_groups:
        if group.name in _NO_SPAN_GROUPS:
            continue
        island, points = _group_island(obj, group)
        if len(points) < 4:
            continue
        span = _island_bone_span(armature, group.name)
        if span is None:
            continue
        start, end = span
        axis = end - start
        bone_len = axis.length
        if bone_len < 2.0:
            continue
        axis = axis / bone_len
        dest = (start + end) * 0.5
        c0, c1 = _aabb_points(points)
        center = (c0 + c1) * 0.5
        dots = [(point - center).dot(axis) for point in points]
        cur_len = max(dots) - min(dots)
        perps = [
            ((point - center) - axis * (point - center).dot(axis)).length
            for point in points
        ]
        perp = max(perps) * 2.0 if perps else 1.0
        if cur_len < 1.0 or cur_len < perp * 0.30:
            delta = dest - center
            for index in island:
                world = obj.matrix_world @ obj.data.vertices[index].co
                obj.data.vertices[index].co = inv @ (world + delta)
            obj.data.update()
            print(
                f"span seat-only {group.name} "
                f"bone={bone_len:.1f} had={cur_len:.1f}"
            )
            continue
        scale_along = max(0.70, min(2.4, (bone_len * 0.96) / cur_len))
        for index in island:
            world = obj.matrix_world @ obj.data.vertices[index].co
            offset = world - center
            along = offset.dot(axis)
            perp_v = offset - axis * along
            world = dest + axis * (along * scale_along) + perp_v
            obj.data.vertices[index].co = inv @ world
        obj.data.update()
        print(
            f"span {group.name} along={scale_along:.2f} "
            f"bone={bone_len:.1f} had={cur_len:.1f}"
        )


def _spine_drop(armature, obj, group) -> float:
    """Slide the chest island down to mid-torso (pelvis → Spine2)."""
    pelvis = _bone_by_name(armature, "ValveBiped.Bip01_Pelvis")
    chest = _bone_by_name(armature, "ValveBiped.Bip01_Spine2")
    if pelvis is None or chest is None:
        return 0.0
    mid_z = (
        (armature.matrix_world @ pelvis.head_local).z
        + (armature.matrix_world @ chest.head_local).z
    ) * 0.5
    _island, points = _group_island(obj, group)
    if not points:
        return 0.0
    return (sum(point.z for point in points) / len(points)) - mid_z


def _build_ragdoll(armature, physics, collision_path: Path):
    """BobmacU Collision Model I, as the guide writes it.

    Import the template, delete its armature, scale to height, G/S each
    island onto the body, Apply Transforms, Armature modifier →
    ``proportions``. No extra yaw.
    """
    if not collision_path.is_file():
        raise FileNotFoundError(f"Missing collision template: {collision_path}")
    keep_name = armature.name
    before_names = set(bpy.data.objects.keys())
    result = bpy.ops.import_scene.smd(
        filepath=str(collision_path),
        append="NEW_ARMATURE",
        doAnim=False,
        upAxis="Z",
        createCollections=False,
    )
    if result != {"FINISHED"}:
        raise RuntimeError(f"Failed to import collision model: {result}")
    added = [
        bpy.data.objects[name]
        for name in bpy.data.objects.keys()
        if name not in before_names
    ]
    meshes = [item for item in added if item.type == "MESH"]
    imported_arms = [item for item in added if item.type == "ARMATURE"]
    if not meshes:
        raise RuntimeError(f"Collision DMX had no mesh: {collision_path}")
    obj = meshes[0]
    obj.parent = None
    for imported in imported_arms:
        if imported.name == keep_name:
            continue
        data = imported.data
        bpy.data.objects.remove(imported, do_unlink=True)
        if data.users == 0:
            bpy.data.armatures.remove(data)
    armature = bpy.data.objects.get(keep_name) or _find_armature()

    obj.matrix_world = Matrix.Identity(4)

    body = [
        item
        for item in bpy.context.scene.objects
        if item.type == "MESH"
        and item != obj
        and not item.name.lower().startswith("collision")
    ]
    body_aabb = _mesh_world_aabb(body)
    phy_aabb = _mesh_world_aabb([obj])
    if body_aabb and phy_aabb:
        body_h = max(body_aabb[5] - body_aabb[2], 1.0)
        phy_h = max(phy_aabb[5] - phy_aabb[2], 1.0)
        scale = body_h / phy_h
        _transform_mesh(obj, Matrix.Diagonal((scale, scale, scale, 1.0)))
        phy_aabb = _mesh_world_aabb([obj])
        lift = Matrix.Translation((0.0, 0.0, body_aabb[2] - phy_aabb[2]))
        _transform_mesh(obj, lift)
        print(
            f"collision template {collision_path.name} "
            f"scaled {scale:.3f} to body height {body_h:.1f}"
        )

    _fit_collision_islands(obj, armature, uniform=True)
    _shrink_torso_islands(obj)
    _span_islands_along_bones(obj, armature)
    _join_pelvis_to_thighs(obj)
    _seat_head_on_skull(obj, armature)
    _seat_islands_on_bones(obj, armature)
    print("physics mode guide (Bob: no yaw, height + island G/S)")

    armature.name = "proportions"
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE":
            modifier.object = armature
            break
    else:
        modifier = obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = armature
    obj.parent = None
    obj.matrix_world = Matrix.Identity(4)
    obj.name = "Collision Model"
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")
    if bpy.ops.object.transform_apply.poll():
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.view_layer.objects.active = armature
    _move_to_collection(obj, physics)
    missing = [
        name
        for name, _scale in RAGDOLL_CAPSULES
        if obj.vertex_groups.get(name) is None
    ]
    if missing:
        print(f"collision missing groups: {', '.join(missing)}")
    print(f"collision groups {len(obj.vertex_groups)} verts={len(obj.data.vertices)}")
    _print_physics_bounds(physics)


def _print_physics_bounds(physics) -> None:
    def _aabb(objects):
        xs, ys, zs = [], [], []
        for obj in objects:
            if obj.type != "MESH" or not obj.data.vertices:
                continue
            for vert in obj.data.vertices:
                world = obj.matrix_world @ vert.co
                xs.append(world.x)
                ys.append(world.y)
                zs.append(world.z)
        if not xs:
            return None
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    bpy.context.view_layer.update()
    mesh_aabb = _aabb(
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and not obj.name.startswith("capsule")
        and not obj.name.lower().startswith("collision")
    )
    phy_aabb = _aabb(physics.objects)
    print(f"mesh aabb {mesh_aabb}")
    print(f"physics aabb {phy_aabb}")
    if mesh_aabb and phy_aabb:
        mesh_span = max(mesh_aabb[3] - mesh_aabb[0], mesh_aabb[5] - mesh_aabb[2], 1.0)
        phy_span = max(phy_aabb[3] - phy_aabb[0], phy_aabb[5] - phy_aabb[2])
        if phy_span > mesh_span * 3.0:
            raise RuntimeError(
                f"physics hull {phy_aabb} is far larger than the mesh {mesh_aabb}"
            )


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
        and "Finger" not in bone.name
        and not bone.name.endswith("Toe0")
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


def _bone_is_weighted(bone_name: str) -> bool:
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        group = obj.vertex_groups.get(bone_name)
        if group is None:
            continue
        for vert in obj.data.vertices:
            for item in vert.groups:
                if item.group == group.index and item.weight > 0.0:
                    return True
    return False


def _remove_unweighted_conditional_bones(armature) -> int:
    """Drop unused fingers/toes so they do not fight the citizen bind."""
    to_remove = [
        name
        for name in _CONDITIONAL_REMOVE_BONES
        if armature.data.bones.get(name) is not None and not _bone_is_weighted(name)
    ]
    if not to_remove:
        return 0
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    for name in to_remove:
        bone = armature.data.edit_bones.get(name)
        if bone is not None:
            armature.data.edit_bones.remove(bone)
            print(f"removed unweighted {name}")
    bpy.ops.object.mode_set(mode="OBJECT")
    return len(to_remove)


def _retarget_meshes(old, new) -> int:
    """Point skinned meshes at the destination armature."""
    moved = 0
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        changed = False
        had_armature = False
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == old:
                modifier.object = new
                changed = True
                had_armature = True
        if obj.parent == old:
            obj.parent = new
            obj.parent_type = "OBJECT"
            obj.matrix_parent_inverse = new.matrix_world.inverted()
            changed = True
            if not had_armature and not any(mod.type == "ARMATURE" for mod in obj.modifiers):
                modifier = obj.modifiers.new("Armature", "ARMATURE")
                modifier.object = new
        if changed:
            moved += 1
    print(f"retargeted {moved} meshes to {new.name}")
    return moved


def _world_bone_span(armature, name: str) -> tuple[Vector, Vector] | None:
    bone = armature.data.bones.get(name)
    if bone is None:
        return None
    return (
        armature.matrix_world @ bone.head_local,
        armature.matrix_world @ bone.tail_local,
    )


def _edit_bones_parent_first(armature):
    remaining = {bone.name: bone for bone in armature.data.edit_bones}
    ordered = []
    while remaining:
        progressed = False
        for name, bone in list(remaining.items()):
            parent = bone.parent
            if parent is not None and parent.name in remaining:
                continue
            ordered.append(bone)
            del remaining[name]
            progressed = True
        if not progressed:
            ordered.extend(remaining.values())
            break
    return ordered


def _constrain_copy_and_track(dest, src) -> tuple[int, int]:
    """COPY_LOCATION + LOCKED_TRACK: ``dest`` joints follow ``src``."""
    bpy.context.view_layer.objects.active = dest
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")
    _reset_pose(dest)
    _reset_pose(src)
    copied = 0
    for name in _VALVEBIPEDS:
        bone = dest.pose.bones.get(name)
        if bone is None or src.pose.bones.get(name) is None:
            continue
        constraint = bone.constraints.new("COPY_LOCATION")
        constraint.target = src
        constraint.subtarget = name
        copied += 1
    tracked = 0
    for bone_name, aim_name in zip(_VALVEBIPEDS2[::2], _VALVEBIPEDS2[1::2]):
        bone = dest.pose.bones.get(bone_name)
        if bone is None or src.pose.bones.get(bone_name) is None:
            continue
        if src.pose.bones.get(aim_name) is None:
            continue
        for lock_axis in ("LOCK_Z", "LOCK_Y"):
            constraint = bone.constraints.new("LOCKED_TRACK")
            constraint.target = src
            constraint.subtarget = aim_name
            constraint.track_axis = "TRACK_X"
            constraint.lock_axis = lock_axis
        tracked += 1
    bpy.context.view_layer.update()
    return copied, tracked


def _clear_pose_constraints(armature) -> None:
    for pbone in armature.pose.bones:
        for constraint in list(pbone.constraints):
            pbone.constraints.remove(constraint)


def _apply_bob_align_constraints(avatar, citizen) -> tuple[int, int]:
    """Guide Align bones script: snap citizen onto the avatar, then apply as rest."""
    copied, tracked = _constrain_copy_and_track(citizen, avatar)
    bpy.context.view_layer.objects.active = citizen
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    citizen.select_set(True)
    bpy.context.view_layer.objects.active = citizen
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode="OBJECT")
    _clear_pose_constraints(citizen)
    print(f"align constraints: {copied} copy loc, {tracked} locked tracks, applied as rest")
    return copied, tracked


def _align_citizen_to_avatar(avatar, citizen):
    """Guide Align bones script, then parent meshes to ``proportions``."""
    avatar.name = "Armature"
    citizen.name = "proportions"
    if avatar.data.users > 1:
        avatar.data = avatar.data.copy()
    if citizen.data.users > 1:
        citizen.data = citizen.data.copy()
    _clear_active_action(avatar)
    _clear_active_action(citizen)
    _bake_armature_identity(avatar)
    _bake_armature_identity(citizen)
    _apply_bob_align_constraints(avatar, citizen)

    extras = []
    bpy.context.view_layer.objects.active = citizen
    bpy.ops.object.mode_set(mode="EDIT")
    inv = citizen.matrix_world.inverted()
    for bone in avatar.data.bones:
        if bone.name in _VALVEBIPEDS or citizen.data.edit_bones.get(bone.name) is not None:
            continue
        dest = citizen.data.edit_bones.new(bone.name)
        dest.use_connect = False
        dest.head = inv @ (avatar.matrix_world @ bone.head_local)
        dest.tail = inv @ (avatar.matrix_world @ bone.tail_local)
        if (dest.tail - dest.head).length < 0.5:
            dest.tail = dest.head + Vector((0.0, 1.0, 0.0)) * 2.0
        parent_name = bone.parent.name if bone.parent else "ValveBiped.Bip01_Pelvis"
        parent = citizen.data.edit_bones.get(parent_name)
        if parent is not None:
            dest.parent = parent
        extras.append(bone.name)
    bpy.ops.object.mode_set(mode="OBJECT")
    _reset_pose(citizen)
    _retarget_meshes(avatar, citizen)
    _remove_unweighted_conditional_bones(citizen)
    bpy.data.objects.remove(avatar, do_unlink=True)
    for name in (
        "ValveBiped.Bip01_L_Thigh",
        "ValveBiped.Bip01_L_UpperArm",
        "ValveBiped.Bip01_Neck1",
        "ValveBiped.Bip01_Head1",
    ):
        _print_bone_axis(citizen, name)
    print(f"align bones: Bob constraints, {len(extras)} extras")
    return citizen


def _print_bone_axis(armature, name: str) -> None:
    bone = armature.data.bones.get(name)
    if bone is None:
        return
    axis = (armature.matrix_world.to_3x3() @ bone.matrix_local.to_3x3() @ Vector((0.0, 1.0, 0.0)))
    head = armature.matrix_world @ bone.head_local
    print(f"align {name} head=({head.x:.1f},{head.y:.1f},{head.z:.1f}) Y={tuple(round(v, 3) for v in axis)}")


def _assert_rest_on_character(armature) -> None:
    """Refuse an exploded rest so we never compile spaghetti legs / stray hulls."""
    zs = [(armature.matrix_world @ bone.head_local).z for bone in armature.data.bones]
    if not zs:
        raise RuntimeError("aligned armature has no bones")
    lo, hi = min(zs), max(zs)
    print(f"aligned rest z={lo:.1f}..{hi:.1f}")
    if hi > 120.0 or lo < -20.0:
        raise RuntimeError(
            f"aligned rest left bones at z={lo:.1f}..{hi:.1f} (expected ~0..72)"
        )


def _append_bind_pose(armature, smd_path: Path) -> None:
    """Guide: import male/female bind SMD with Append to Target."""
    bpy.context.view_layer.objects.active = armature
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    before = set(bpy.data.objects.keys())
    result = bpy.ops.import_scene.smd(
        filepath=str(smd_path),
        append="APPEND",
        doAnim=True,
        upAxis="Z",
        createCollections=False,
    )
    if result != {"FINISHED"}:
        raise RuntimeError(f"Failed to append bind pose {smd_path}: {result}")
    for name in list(bpy.data.objects.keys()):
        if name in before:
            continue
        extra = bpy.data.objects[name]
        if extra.type == "MESH":
            data = extra.data
            bpy.data.objects.remove(extra, do_unlink=True)
            if data.users == 0:
                bpy.data.meshes.remove(data)
        elif extra.type == "ARMATURE" and extra != armature:
            data = extra.data
            bpy.data.objects.remove(extra, do_unlink=True)
            if data.users == 0:
                bpy.data.armatures.remove(data)
    print(f"appended bind pose {smd_path.name} onto {armature.name}")


def _key_pose_bone(pbone, frame: int) -> None:
    pbone.keyframe_insert("location", frame=frame)
    pbone.keyframe_insert("scale", frame=frame)
    if pbone.rotation_mode == "QUATERNION":
        pbone.keyframe_insert("rotation_quaternion", frame=frame)
    else:
        pbone.keyframe_insert("rotation_euler", frame=frame)


def _clear_pose_rotation(armature) -> None:
    """Alt+R: keep location, drop rotation. Size-trick reference pose."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    for pbone in armature.pose.bones:
        loc = pbone.location.copy()
        pbone.matrix_basis.identity()
        pbone.location = loc
    bpy.context.view_layer.update()


def _capture_proportion_action(armature, smd_path: Path) -> None:
    """CaptainBigButt size trick: two 1-frame clips.

    ``proportions`` is the custom bind (identity). ``size_reference`` is the
    citizen bind appended onto that rest, then Alt+R so HL2 locations stay
    and rotations match the custom skeleton.
    """
    _reset_pose(armature)
    _capture_action(armature, "proportions")
    # Detach before the SMD append or Source Tools adds a leftover "male" slot.
    _clear_active_action(armature)

    _append_bind_pose(armature, smd_path)
    _clear_pose_rotation(armature)
    moved = sum(1 for pbone in armature.pose.bones if pbone.location.length > 0.05)
    _capture_action(armature, "size_reference")
    print(f"size proportion: size_reference keeps {moved} citizen translations")


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


_SEQUENCES_ACTION = "sequences"


def _uses_action_slots() -> bool:
    """Blender 4.4+ / Source Tools 3.4 export clips as slots on one Action."""
    return tuple(bpy.app.version[:2]) >= (4, 4)


def _slot_display_name(slot) -> str:
    return getattr(slot, "name_display", None) or getattr(slot, "identifier", "") or str(slot)


def _ensure_sequences_action(armature):
    ad = armature.animation_data_create()
    action = bpy.data.actions.get(_SEQUENCES_ACTION)
    if action is None:
        action = bpy.data.actions.new(_SEQUENCES_ACTION)
        action.use_fake_user = True
    ad.action = action
    return ad, action


def _activate_sequence_slot(armature, name: str):
    """Point the armature at a named slot (Source Tools exports ``name_display``)."""
    ad, action = _ensure_sequences_action(armature)
    slot = next((item for item in action.slots if _slot_display_name(item) == name), None)
    if slot is None:
        slot = action.slots.new(id_type="OBJECT", name=name)
    ad.action_slot = slot
    layer = action.layers[0] if action.layers else action.layers.new(name)
    strip = layer.strips[0] if layer.strips else layer.strips.new(type="KEYFRAME")
    strip.channelbag(slot, ensure=True)
    return slot


def _capture_action(armature, name: str) -> None:
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    bpy.context.scene.frame_set(1)
    if _uses_action_slots():
        _activate_sequence_slot(armature, name)
    else:
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        armature.animation_data_create()
        armature.animation_data.action = action
    for pbone in armature.pose.bones:
        pbone.keyframe_insert("location", frame=1)
        pbone.keyframe_insert("scale", frame=1)
        if pbone.rotation_mode == "QUATERNION":
            pbone.keyframe_insert("rotation_quaternion", frame=1)
        else:
            pbone.keyframe_insert("rotation_euler", frame=1)
    print(f"action {name}: {len(armature.pose.bones)} bones")


_KEEP_SLOTS = frozenset({"ragdoll", "proportions", "size_reference"})


def _keep_sequence_actions() -> None:
    keep = {"ragdoll", "proportions", "size_reference", _SEQUENCES_ACTION}
    for action in list(bpy.data.actions):
        if action.name not in keep:
            bpy.data.actions.remove(action)
    action = bpy.data.actions.get(_SEQUENCES_ACTION)
    if action is None or not _uses_action_slots():
        return
    for slot in list(action.slots):
        if _slot_display_name(slot) in _KEEP_SLOTS:
            continue
        try:
            action.slots.remove(slot)
        except Exception:
            print(f"kept extra slot {_slot_display_name(slot)}")


def _clear_active_action(armature) -> None:
    """Rest pose, no action, so mesh/physics bake is the avatar bind."""
    ad = armature.animation_data
    if ad is not None:
        if _uses_action_slots() and ad.action is not None and getattr(ad, "action_slot", None):
            ad.action_slot = None
        ad.action = None
    _reset_pose(armature)


def _restore_sequences_for_export(armature) -> None:
    """Reattach the slotted action so Source Tools can see the three clips."""
    if not _uses_action_slots():
        return
    ad, action = _ensure_sequences_action(armature)
    names = [_slot_display_name(slot) for slot in action.slots]
    if action.slots:
        ad.action_slot = action.slots[0]
    print(f"export slots {names}")


def _drop_citizen(citizen) -> None:
    data = citizen.data
    bpy.data.objects.remove(citizen, do_unlink=True)
    if data.users == 0:
        bpy.data.armatures.remove(data)
    for collection in list(bpy.data.collections):
        if collection is bpy.context.scene.collection:
            continue
        if collection.name in {"reference", "physics", "arms"}:
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
    if bpy.context.view_layer.objects.active is None:
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH":
                bpy.context.view_layer.objects.active = obj
                break
    if bpy.context.view_layer.objects.active is not None:
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not obj.vertex_groups:
            continue
        if obj.name.startswith("capsule") or obj.name.lower().startswith("collision"):
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.vertex_group_limit_total(limit=limit)
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        print(f"limited {obj.name} to {limit} bone influences")


def _retarget_material(old, new) -> None:
    """Point every mesh slot at ``new`` so ``old`` can be removed."""
    for obj in bpy.data.objects:
        data = getattr(obj, "data", None)
        materials = getattr(data, "materials", None)
        if materials is None:
            continue
        for index, slot in enumerate(materials):
            if slot == old:
                materials[index] = new


def _source_material_name(name: str) -> str:
    """Stdlib copy of ``app.core.source_names`` — Blender cannot import ``app``."""
    head = name.split(":", 1)[0].strip() or name
    head = _BLENDER_DUP.sub("", head)
    clean = _ILLEGAL_MAT.sub("_", head).strip("_") or "mat"
    if clean[0].isdigit():
        clean = f"mat_{clean}"
    return clean[:63]


def _allocate_source_name(base: str, texture_key, assigned: dict) -> str:
    if base not in assigned:
        assigned[base] = texture_key
        return base
    if assigned[base] == texture_key:
        return base
    suffix = 2
    while True:
        candidate = f"{base[:60]}_{suffix}"
        if candidate not in assigned:
            assigned[candidate] = texture_key
            return candidate
        if assigned[candidate] == texture_key:
            return candidate
        suffix += 1


def _sanitize_material_names() -> None:
    """Match ``app.core.source_names`` so DMX stems equal the VTF/VMT files.

    Two materials that share an image keep one name (RPM's split ``face``).
    A second material that sanitizes to the same stem but uses a different
    image becomes ``face_2``. Blender cannot store two datablocks named
    ``face``, so merge the extras onto the winner instead of leaving
    ``face.001`` for studiomdl to emit as ``face_001``.
    """
    assigned: dict[str, object] = {}
    targets: dict[str, list] = {}
    for mat in list(bpy.data.materials):
        name = _allocate_source_name(
            _source_material_name(mat.name), _material_image_key(mat), assigned
        )
        targets.setdefault(name, []).append(mat)

    for name, mats in targets.items():
        winner = next((mat for mat in mats if mat.name == name), mats[0])
        for mat in mats:
            if mat == winner:
                continue
            print(f"material {mat.name!r} -> {name!r} (merge)")
            _retarget_material(mat, winner)
            if mat.users == 0:
                bpy.data.materials.remove(mat)
        occupant = bpy.data.materials.get(name)
        if occupant is not None and occupant != winner:
            occupant.name = f"{name}__tmp"
        if winner.name != name:
            print(f"material {winner.name!r} -> {name!r}")
            winner.name = name


def _material_image_key(mat: bpy.types.Material) -> str:
    if mat.use_nodes and mat.node_tree is not None:
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                return node.image.name
    return mat.name


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
    for dmx in (out_dir / "reference.dmx", out_dir / "physics.dmx", out_dir / "arms.dmx"):
        if dmx.is_file():
            _rebuild_dmx_normals(dmx)


def _rebuild_dmx_normals(path: Path) -> None:
    """Rebuild loop normals from triangle winding without mixing hemispheres.

    Source Tools writes zeros after our mesh transforms. Averaging every
    face that shares a vertex cancels outer skin against mouth/eye cavities
    on RPM heads, which lights those features as a black hole.
    """
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
            loop = _hemisphere_loop_normals(positions, indices, datamodel)
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


def _hemisphere_loop_normals(positions, indices, datamodel):
    """Per-corner normals: only average faces that agree with this triangle."""
    tri_count = len(indices) // 3
    face_n: list[tuple[float, float, float]] = []
    for i in range(0, tri_count * 3, 3):
        ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
        ax, ay, az = positions[ia]
        bx, by, bz = positions[ib]
        cx, cy, cz = positions[ic]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = (nx * nx + ny * ny + nz * nz) ** 0.5
        if length < 1e-8:
            face_n.append((0.0, 0.0, 1.0))
        else:
            face_n.append((nx / length, ny / length, nz / length))
    at_vert: list[list[int]] = [[] for _ in positions]
    for t in range(tri_count):
        for k in range(3):
            at_vert[indices[t * 3 + k]].append(t)
    loop = []
    for t in range(tri_count):
        nx, ny, nz = face_n[t]
        for k in range(3):
            idx = indices[t * 3 + k]
            sx = sy = sz = 0.0
            for other in at_vert[idx]:
                ox, oy, oz = face_n[other]
                if ox * nx + oy * ny + oz * nz >= 0.0:
                    sx += ox
                    sy += oy
                    sz += oz
            length = (sx * sx + sy * sy + sz * sz) ** 0.5
            if length < 1e-8:
                loop.append(datamodel.Vector3([nx, ny, nz]))
            else:
                loop.append(
                    datamodel.Vector3([sx / length, sy / length, sz / length])
                )
    return loop


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--proportions", required=True)
    parser.add_argument("--collision", default="")
    parser.add_argument(
        "--carms-ref",
        default="",
        help="Default citizen C-arm DMX for the guide's Better finger fit",
    )
    parser.add_argument(
        "--save-blend",
        default="",
        help="Write the finished export scene to this .blend for inspection",
    )
    args = parser.parse_args(_argv_after_dash())
    source = Path(args.input)
    out_dir = Path(args.output)
    proportions = Path(args.proportions)
    collision = (
        Path(args.collision)
        if args.collision
        else Path(__file__).resolve().parent / "collision" / "Collision Model.dmx"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    if not proportions.is_file():
        raise FileNotFoundError(f"Missing bind-pose SMD: {proportions}")
    if not collision.is_file():
        raise FileNotFoundError(f"Missing collision template: {collision}")

    _enable_source_tools()
    _clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source))
    _prepare_source_space()

    armature = _find_armature()
    citizen = _import_citizen(proportions)
    _ensure_helper_bones(armature, citizen)
    armature = _align_citizen_to_avatar(armature, citizen)
    armature.name = "proportions"
    _assert_rest_on_character(armature)
    _reset_pose(armature)
    _capture_action(armature, "ragdoll")
    _capture_proportion_action(armature, proportions)
    _keep_sequence_actions()
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

    _limit_bone_influences()
    _sanitize_material_names()
    arms = bpy.data.collections.new("arms")
    bpy.context.scene.collection.children.link(arms)
    arms.vs.export = True
    arms.vs.subdir = ""
    _build_carms(reference, arms, armature)
    if args.carms_ref:
        _fit_carms_to_default(armature, arms, Path(args.carms_ref))

    _build_ragdoll(armature, physics, collision)
    _keep_sequence_actions()
    _restore_sequences_for_export(armature)
    _export_dmx(out_dir)
    if args.save_blend:
        blend = Path(args.save_blend)
        blend.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        print(f"wrote blend {blend}")
    print(f"wrote DMX under {out_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
