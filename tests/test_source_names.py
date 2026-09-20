"""Source-legal material name allocation."""

from app.core.source_names import allocate_source_name, source_material_name


def test_source_material_name_strips_rpm_slot():
    assert source_material_name("hair: Teased spikes_3") == "hair"
    assert source_material_name("shirt: 70's full-zip jacket_5") == "shirt"
    assert source_material_name("face") == "face"
    assert source_material_name("face.001") == "face"
    assert source_material_name("face.002") == "face"
    assert source_material_name("body_0") == "body_0"
    assert source_material_name("9lives") == "mat_9lives"


def test_allocate_reuses_name_for_same_texture():
    assigned: dict[str, object] = {}
    first = allocate_source_name(source_material_name("face"), 0, assigned)
    second = allocate_source_name(source_material_name("face.001"), 0, assigned)
    assert first == second == "face"


def test_allocate_uniquifies_when_texture_differs():
    assigned: dict[str, object] = {}
    first = allocate_source_name("face", 0, assigned)
    second = allocate_source_name("face", 1, assigned)
    assert first == "face"
    assert second == "face_2"
