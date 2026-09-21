from pathlib import Path


def test_desktop_spec_packs_hallway_roots():
    spec = Path("desktop.spec").read_text(encoding="utf-8")
    assert "run_desktop.py" in spec
    assert 'name="AvatarToPlayermodel"' in spec
    assert '"templates"' in spec
    assert '"static"' in spec
    assert "VERSION" in spec
    assert "app/blender" in spec
    assert "console=False" in spec
