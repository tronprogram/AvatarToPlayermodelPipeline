"""glTF scale into Source-sized Y-up without a SourceRoot wrapper."""

from pygltflib import GLTF2, Node, Scene

from app.services.source_space import SOURCE_PLAYER_HEIGHT, align_to_source, _world_node_origins
from app.services.valvebiped import _local_matrix


def test_align_scales_root_nodes_and_does_not_wrap():
    gltf = GLTF2()
    gltf.nodes = [
        Node(name="feet", translation=[0.0, 0.0, 0.0]),
        Node(name="head", translation=[0.0, 1.5, 0.0]),
    ]
    gltf.scenes = [Scene(nodes=[0, 1])]
    gltf.scene = 0

    align_to_source(gltf)

    names = [node.name for node in gltf.nodes]
    assert "SourceRoot" not in names
    assert gltf.scenes[0].nodes == [0, 1]
    origins = _world_node_origins(gltf)
    height = origins[:, 1].max() - origins[:, 1].min()
    assert abs(height - SOURCE_PLAYER_HEIGHT) < 1e-4
    assert abs(_local_matrix(gltf.nodes[0])[1, 3]) < 1e-4


def test_align_leaves_inverse_binds_untouched():
    gltf = GLTF2()
    gltf.nodes = [Node(name="root", translation=[0.0, 1.0, 0.0])]
    gltf.scenes = [Scene(nodes=[0])]
    gltf.scene = 0
    gltf.skins = []
    align_to_source(gltf)
    assert gltf.skins == []
