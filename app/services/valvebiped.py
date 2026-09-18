"""ValveBiped mapping for the avatar joint_* skeleton.

This is a mapping specification: rest orientations, IK, and ragdoll still
need a reference-rig check after compile.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from pygltflib import ARRAY_BUFFER, FLOAT, MAT4, BufferView, GLTF2

# Source helper -> retained source bone. Add weights; never overwrite.
WEIGHT_MERGES = {
    "joint_04": "joint_00",
    "joint_07": "joint_02",
    "joint_09": "joint_03",
    "joint_13": "joint_06",
    "joint_17": "joint_08",
    "joint_26": "joint_20",
    "joint_27": "joint_20",
    "joint_29": "joint_22",
    "joint_30": "joint_22",
    "joint_31": "joint_25",
    "joint_32": "joint_25",
    "joint_34": "joint_28",
    "joint_35": "joint_28",
    "joint_24": "joint_14",
}

NAME_LOOKUP = {
    "joint_00": "ValveBiped.Bip01_Pelvis",
    "joint_01": "ValveBiped.Bip01_Spine",
    "joint_10": "ValveBiped.Bip01_Spine1",
    "joint_05": "ValveBiped.Bip01_Spine2",
    "joint_18": "ValveBiped.Bip01_Spine4",
    "joint_14": "ValveBiped.Bip01_Neck1",
    "joint_19": "ValveBiped.Bip01_Head1",
    "joint_02": "ValveBiped.Bip01_L_Thigh",
    "joint_06": "ValveBiped.Bip01_L_Calf",
    "joint_11": "ValveBiped.Bip01_L_Foot",
    "joint_21": "ValveBiped.Bip01_L_Toe0",
    "joint_03": "ValveBiped.Bip01_R_Thigh",
    "joint_08": "ValveBiped.Bip01_R_Calf",
    "joint_15": "ValveBiped.Bip01_R_Foot",
    "joint_23": "ValveBiped.Bip01_R_Toe0",
    "joint_12": "ValveBiped.Bip01_L_Clavicle",
    "joint_20": "ValveBiped.Bip01_L_UpperArm",
    "joint_25": "ValveBiped.Bip01_L_Forearm",
    "joint_33": "ValveBiped.Bip01_L_Hand",
    "joint_16": "ValveBiped.Bip01_R_Clavicle",
    "joint_22": "ValveBiped.Bip01_R_UpperArm",
    "joint_28": "ValveBiped.Bip01_R_Forearm",
    "joint_36": "ValveBiped.Bip01_R_Hand",
    "joint_43": "ValveBiped.Bip01_L_Finger0",
    "joint_55": "ValveBiped.Bip01_L_Finger01",
    "joint_65": "ValveBiped.Bip01_L_Finger02",
    "joint_37": "ValveBiped.Bip01_L_Finger1",
    "joint_51": "ValveBiped.Bip01_L_Finger11",
    "joint_61": "ValveBiped.Bip01_L_Finger12",
    "joint_38": "ValveBiped.Bip01_L_Finger2",
    "joint_52": "ValveBiped.Bip01_L_Finger21",
    "joint_62": "ValveBiped.Bip01_L_Finger22",
    "joint_39": "ValveBiped.Bip01_L_Finger3",
    "joint_53": "ValveBiped.Bip01_L_Finger31",
    "joint_63": "ValveBiped.Bip01_L_Finger32",
    "joint_40": "ValveBiped.Bip01_L_Finger4",
    "joint_54": "ValveBiped.Bip01_L_Finger41",
    "joint_64": "ValveBiped.Bip01_L_Finger42",
    "joint_50": "ValveBiped.Bip01_R_Finger0",
    "joint_60": "ValveBiped.Bip01_R_Finger01",
    "joint_70": "ValveBiped.Bip01_R_Finger02",
    "joint_44": "ValveBiped.Bip01_R_Finger1",
    "joint_56": "ValveBiped.Bip01_R_Finger11",
    "joint_66": "ValveBiped.Bip01_R_Finger12",
    "joint_45": "ValveBiped.Bip01_R_Finger2",
    "joint_57": "ValveBiped.Bip01_R_Finger21",
    "joint_67": "ValveBiped.Bip01_R_Finger22",
    "joint_46": "ValveBiped.Bip01_R_Finger3",
    "joint_58": "ValveBiped.Bip01_R_Finger31",
    "joint_68": "ValveBiped.Bip01_R_Finger32",
    "joint_47": "ValveBiped.Bip01_R_Finger4",
    "joint_59": "ValveBiped.Bip01_R_Finger41",
    "joint_69": "ValveBiped.Bip01_R_Finger42",
}

# Retained bone -> intended parent (original names). None = armature root.
PARENT_LOOKUP: dict[str, str | None] = {
    "joint_00": None,
    "joint_01": "joint_00",
    "joint_10": "joint_01",
    "joint_05": "joint_10",
    "joint_18": "joint_05",
    "joint_14": "joint_18",
    "joint_19": "joint_14",
    "joint_12": "joint_18",
    "joint_16": "joint_18",
}

UNWEIGHTED_BONES_TO_REMOVE = {
    "joint_41",
    "joint_42",
    "joint_48",
    "joint_49",
}

BONES_TO_REMOVE = set(WEIGHT_MERGES) | UNWEIGHTED_BONES_TO_REMOVE

_COMPONENT = {
    5120: (1, "<i1"),
    5121: (1, "<u1"),
    5122: (2, "<i2"),
    5123: (2, "<u2"),
    5125: (4, "<u4"),
    5126: (4, "<f4"),
}
_TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def apply_valvebiped(gltf: GLTF2) -> GLTF2:
    """Convert joint_* names, weights, and spine parents to ValveBiped.

    Mutates and returns the same ``GLTF2``. Skin joints become the 53
    ValveBiped names; helper bones are merged into parents and dropped.
    """
    if not gltf.nodes:
        return gltf
    if gltf.binary_blob() is None:
        gltf.buffers_to_binary_blob()

    _merge_skin_weights(gltf)
    _apply_hierarchy(gltf)
    _remove_bones(gltf)
    _rename_bones(gltf)
    return gltf


def _node_by_name(gltf: GLTF2) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, node in enumerate(gltf.nodes or []):
        if node.name:
            found[node.name] = index
    return found


def _parent_of(gltf: GLTF2, child: int) -> int | None:
    for index, node in enumerate(gltf.nodes or []):
        if node.children and child in node.children:
            return index
    return None


def _local_matrix(node) -> np.ndarray:
    if node.matrix:
        return np.array(node.matrix, dtype=np.float64).reshape((4, 4), order="F")
    translation = np.array(node.translation or (0.0, 0.0, 0.0), dtype=np.float64)
    rotation = np.array(node.rotation or (0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    scale = np.array(node.scale or (1.0, 1.0, 1.0), dtype=np.float64)
    return _trs_matrix(translation, rotation, scale)


def _trs_matrix(translation: np.ndarray, quat: np.ndarray, scale: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(quat)
    if norm:
        quat = quat / norm
    x, y, z, w = quat
    rot = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 0] = rot[:, 0] * scale[0]
    matrix[:3, 1] = rot[:, 1] * scale[1]
    matrix[:3, 2] = rot[:, 2] * scale[2]
    matrix[:3, 3] = translation
    return matrix


def _world_matrix(gltf: GLTF2, index: int, cache: dict[int, np.ndarray]) -> np.ndarray:
    if index in cache:
        return cache[index]
    local = _local_matrix(gltf.nodes[index])
    parent = _parent_of(gltf, index)
    world = local if parent is None else _world_matrix(gltf, parent, cache) @ local
    cache[index] = world
    return world


def _set_local_matrix(node, matrix: np.ndarray) -> None:
    node.matrix = matrix.astype(np.float64).flatten(order="F").tolist()
    node.translation = None
    node.rotation = None
    node.scale = None


def _detach(gltf: GLTF2, child: int) -> None:
    parent = _parent_of(gltf, child)
    if parent is None:
        return
    children = gltf.nodes[parent].children or []
    gltf.nodes[parent].children = [index for index in children if index != child]


def _attach(gltf: GLTF2, parent: int, child: int) -> None:
    node = gltf.nodes[parent]
    children = list(node.children or [])
    if child not in children:
        children.append(child)
    node.children = children


def _ensure_root(gltf: GLTF2, index: int) -> None:
    if not gltf.scenes:
        return
    roots = list(gltf.scenes[gltf.scene or 0].nodes or [])
    if index not in roots:
        roots.append(index)
    gltf.scenes[gltf.scene or 0].nodes = roots


def _drop_root(gltf: GLTF2, index: int) -> None:
    if not gltf.scenes:
        return
    scene = gltf.scenes[gltf.scene or 0]
    scene.nodes = [node for node in (scene.nodes or []) if node != index]


def _read_accessor(gltf: GLTF2, accessor_index: int) -> np.ndarray:
    accessor = gltf.accessors[accessor_index]
    view = gltf.bufferViews[accessor.bufferView]
    blob = gltf.binary_blob()
    start = (view.byteOffset or 0) + (accessor.byteOffset or 0)
    width, dtype = _COMPONENT[accessor.componentType]
    comps = _TYPE_COUNT[accessor.type]
    stride = view.byteStride or (width * comps)
    rows = []
    for i in range(accessor.count):
        offset = start + i * stride
        rows.append(np.frombuffer(blob, dtype=dtype, count=comps, offset=offset))
    return np.stack(rows, axis=0).copy()


def _write_accessor(gltf: GLTF2, accessor_index: int, data: np.ndarray) -> None:
    accessor = gltf.accessors[accessor_index]
    view = gltf.bufferViews[accessor.bufferView]
    blob = bytearray(gltf.binary_blob())
    start = (view.byteOffset or 0) + (accessor.byteOffset or 0)
    width, dtype = _COMPONENT[accessor.componentType]
    comps = _TYPE_COUNT[accessor.type]
    stride = view.byteStride or (width * comps)
    packed = np.asarray(data, dtype=np.dtype(dtype))
    if packed.ndim == 1:
        packed = packed.reshape((-1, 1))
    for i, row in enumerate(packed):
        raw = np.asarray(row, dtype=np.dtype(dtype)).tobytes()
        offset = start + i * stride
        blob[offset : offset + len(raw)] = raw
    gltf.set_binary_blob(bytes(blob))


def _append_bytes(gltf: GLTF2, data: bytes) -> int:
    blob = bytearray(gltf.binary_blob() or b"")
    pad = (4 - (len(blob) % 4)) % 4
    blob.extend(b"\x00" * pad)
    offset = len(blob)
    blob.extend(data)
    gltf.set_binary_blob(bytes(blob))
    if not gltf.buffers:
        raise RuntimeError("GLTF has no buffers")
    gltf.buffers[0].byteLength = len(blob)
    gltf.bufferViews.append(
        BufferView(buffer=0, byteOffset=offset, byteLength=len(data), target=ARRAY_BUFFER)
    )
    return len(gltf.bufferViews) - 1


def _merge_vertex_weights(
    joint_slots: np.ndarray,
    weight_slots: np.ndarray,
    slot_to_name: dict[int, str],
    name_to_slot: dict[str, int],
) -> tuple[np.ndarray, np.ndarray]:
    merged = defaultdict(float)
    for slot, weight in zip(joint_slots.tolist(), weight_slots.tolist(), strict=True):
        slot = int(slot)
        if weight <= 0 or slot not in slot_to_name:
            continue
        name = slot_to_name[slot]
        dest = WEIGHT_MERGES.get(name, name)
        if dest in BONES_TO_REMOVE:
            continue
        merged[dest] += float(weight)

    total = sum(merged.values())
    if total > 0:
        for name in list(merged):
            merged[name] /= total

    ranked = sorted(merged.items(), key=lambda item: item[1], reverse=True)[:3]
    joints = np.zeros(4, dtype=joint_slots.dtype)
    weights = np.zeros(4, dtype=weight_slots.dtype)
    for i, (name, weight) in enumerate(ranked):
        if name not in name_to_slot:
            continue
        joints[i] = name_to_slot[name]
        weights[i] = weight
    weight_sum = float(weights.sum())
    if weight_sum > 0:
        weights /= weight_sum
    return joints, weights


def _skin_slot_names(gltf: GLTF2, skin) -> tuple[dict[int, str], dict[str, int]]:
    slot_to_name: dict[int, str] = {}
    name_to_slot: dict[str, int] = {}
    for slot, node_index in enumerate(skin.joints or []):
        name = gltf.nodes[node_index].name
        if not name:
            continue
        slot_to_name[slot] = name
        name_to_slot[name] = slot
    return slot_to_name, name_to_slot


def _iter_skin_primitives(gltf: GLTF2, skin_index: int):
    for node in gltf.nodes or []:
        if node.mesh is None or node.skin != skin_index:
            continue
        mesh = gltf.meshes[node.mesh]
        for primitive in mesh.primitives or []:
            attributes = primitive.attributes
            if attributes is None or attributes.JOINTS_0 is None or attributes.WEIGHTS_0 is None:
                continue
            yield attributes


def _merge_skin_weights(gltf: GLTF2) -> None:
    for skin_index, skin in enumerate(gltf.skins or []):
        slot_to_name, name_to_slot = _skin_slot_names(gltf, skin)
        for attributes in _iter_skin_primitives(gltf, skin_index):
            joints = _read_accessor(gltf, attributes.JOINTS_0)
            weights = _read_accessor(gltf, attributes.WEIGHTS_0)
            extra_joints = getattr(attributes, "JOINTS_1", None)
            extra_weights = getattr(attributes, "WEIGHTS_1", None)
            if extra_joints is not None and extra_weights is not None:
                joints = np.concatenate([joints, _read_accessor(gltf, extra_joints)], axis=1)
                weights = np.concatenate([weights, _read_accessor(gltf, extra_weights)], axis=1)
            new_joints = np.zeros((len(joints), 4), dtype=joints.dtype)
            new_weights = np.zeros((len(weights), 4), dtype=weights.dtype)
            for i, (joint_row, weight_row) in enumerate(zip(joints, weights, strict=True)):
                new_joints[i], new_weights[i] = _merge_vertex_weights(
                    joint_row, weight_row, slot_to_name, name_to_slot
                )
            _write_accessor(gltf, attributes.JOINTS_0, new_joints)
            _write_accessor(gltf, attributes.WEIGHTS_0, new_weights)
            if extra_joints is not None:
                zeros_j = np.zeros((len(joints), 4), dtype=joints.dtype)
                zeros_w = np.zeros((len(weights), 4), dtype=weights.dtype)
                _write_accessor(gltf, extra_joints, zeros_j)
                _write_accessor(gltf, extra_weights, zeros_w)


def _apply_hierarchy(gltf: GLTF2) -> None:
    names = _node_by_name(gltf)
    cache: dict[int, np.ndarray] = {}
    worlds = {
        name: _world_matrix(gltf, index, cache)
        for name, index in names.items()
        if name in PARENT_LOOKUP
    }
    for name, parent_name in PARENT_LOOKUP.items():
        if name not in names:
            continue
        child = names[name]
        _detach(gltf, child)
        _drop_root(gltf, child)
        world = worlds[name]
        if parent_name is None:
            _set_local_matrix(gltf.nodes[child], world)
            _ensure_root(gltf, child)
            continue
        if parent_name not in names:
            continue
        parent = names[parent_name]
        parent_world = worlds.get(parent_name)
        if parent_world is None:
            parent_world = _world_matrix(gltf, parent, {})
        _set_local_matrix(gltf.nodes[child], np.linalg.inv(parent_world) @ world)
        _attach(gltf, parent, child)


def _remove_bones(gltf: GLTF2) -> None:
    names = _node_by_name(gltf)
    removed = {names[name] for name in BONES_TO_REMOVE if name in names}
    for child in removed:
        parent = _parent_of(gltf, child)
        leftovers = [index for index in (gltf.nodes[child].children or []) if index not in removed]
        world_cache: dict[int, np.ndarray] = {}
        for leftover in leftovers:
            world = _world_matrix(gltf, leftover, world_cache)
            _detach(gltf, leftover)
            if parent is None:
                _set_local_matrix(gltf.nodes[leftover], world)
                _ensure_root(gltf, leftover)
            else:
                parent_world = _world_matrix(gltf, parent, world_cache)
                _set_local_matrix(gltf.nodes[leftover], np.linalg.inv(parent_world) @ world)
                _attach(gltf, parent, leftover)
        _detach(gltf, child)
        _drop_root(gltf, child)
        gltf.nodes[child].children = []

    for skin_index, skin in enumerate(gltf.skins or []):
        old_joints = list(skin.joints or [])
        keep = [node for node in old_joints if node not in removed]
        old_slot = {node: slot for slot, node in enumerate(old_joints)}
        new_slot = {node: slot for slot, node in enumerate(keep)}
        remap = {
            old_slot[node]: new_slot[node]
            for node in keep
            if node in old_slot
        }
        if skin.inverseBindMatrices is not None and keep:
            ibms = _read_accessor(gltf, skin.inverseBindMatrices)
            kept = np.stack([ibms[old_slot[node]] for node in keep], axis=0)
            raw = np.ascontiguousarray(kept.astype(np.float32)).tobytes()
            view = _append_bytes(gltf, raw)
            accessor = gltf.accessors[skin.inverseBindMatrices]
            accessor.bufferView = view
            accessor.byteOffset = 0
            accessor.count = len(keep)
            accessor.type = MAT4
            accessor.componentType = FLOAT
        skin.joints = keep
        if skin.skeleton in removed:
            skin.skeleton = names.get("joint_00")
        _remap_joint_slots(gltf, skin_index=skin_index, remap=remap)


def _remap_joint_slots(gltf: GLTF2, *, skin_index: int, remap: dict[int, int]) -> None:
    if not remap:
        return
    for attributes in _iter_skin_primitives(gltf, skin_index):
        joints = _read_accessor(gltf, attributes.JOINTS_0)
        weights = _read_accessor(gltf, attributes.WEIGHTS_0)
        remapped = np.zeros_like(joints)
        for i, (joint_row, weight_row) in enumerate(zip(joints, weights, strict=True)):
            for col, (slot, weight) in enumerate(
                zip(joint_row.tolist(), weight_row.tolist(), strict=True)
            ):
                slot = int(slot)
                if weight <= 0:
                    continue
                if slot in remap:
                    remapped[i, col] = remap[slot]
        _write_accessor(gltf, attributes.JOINTS_0, remapped)


def _rename_bones(gltf: GLTF2) -> None:
    for node in gltf.nodes or []:
        if node.name in NAME_LOOKUP:
            node.name = NAME_LOOKUP[node.name]
