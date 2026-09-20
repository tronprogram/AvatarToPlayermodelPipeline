"""Scale a glTF avatar so Blender's importer yields a ~72-unit Z-up model.

glTF is Y-up. Blender's importer converts that to Z-up. A SourceRoot wrapper
with rewritten inverse-bind matrices makes Blender collapse the skinned mesh
to a point, so this only scales the existing scene roots and leaves IBMs
alone. Forward stays whatever Blender's importer yields (Bob: −Y front).
"""

from __future__ import annotations

import numpy as np
from pygltflib import GLTF2

from app.services.valvebiped import _local_matrix, _read_accessor, _set_local_matrix, _world_matrix

SOURCE_PLAYER_HEIGHT = 72.0


def align_to_source(gltf: GLTF2, *, height: float = SOURCE_PLAYER_HEIGHT) -> GLTF2:
    """Scale and stand the model on Y=0 in glTF space. Does not wrap a new root."""
    if not gltf.nodes or not gltf.scenes:
        return gltf
    if gltf.binary_blob() is None:
        gltf.buffers_to_binary_blob()

    points = _world_mesh_points(gltf)
    if not len(points):
        points = _world_node_origins(gltf)
    if not len(points):
        return gltf

    ymin = float(points[:, 1].min())
    ymax = float(points[:, 1].max())
    extent = ymax - ymin
    scale = height / extent if extent > 1e-4 else 1.0
    root = np.eye(4, dtype=np.float64)
    root[0, 0] = root[1, 1] = root[2, 2] = scale
    root[1, 3] = -ymin * scale

    scene = gltf.scenes[gltf.scene or 0]
    for index in list(scene.nodes or []):
        node = gltf.nodes[index]
        _set_local_matrix(node, root @ _local_matrix(node))
    return gltf


def _world_mesh_points(gltf: GLTF2) -> np.ndarray:
    cache: dict[int, np.ndarray] = {}
    chunks: list[np.ndarray] = []
    for index, node in enumerate(gltf.nodes or []):
        if node.mesh is None:
            continue
        world = _world_matrix(gltf, index, cache)
        mesh = gltf.meshes[node.mesh]
        for primitive in mesh.primitives or []:
            attrs = primitive.attributes
            if attrs is None or attrs.POSITION is None:
                continue
            local = _read_accessor(gltf, attrs.POSITION)
            if local.shape[1] < 3:
                continue
            homog = np.ones((len(local), 4), dtype=np.float64)
            homog[:, :3] = local[:, :3]
            chunks.append((world @ homog.T).T[:, :3])
    if not chunks:
        return np.zeros((0, 3), dtype=np.float64)
    return np.concatenate(chunks, axis=0)


def _world_node_origins(gltf: GLTF2) -> np.ndarray:
    cache: dict[int, np.ndarray] = {}
    points = []
    for index in range(len(gltf.nodes or [])):
        world = _world_matrix(gltf, index, cache)
        points.append(world[:3, 3])
    return np.array(points, dtype=np.float64)
