from pathlib import Path


def test_desktop_spec_packs_hallway_roots():
    spec = Path("scripts/packaging/desktop.spec").read_text(encoding="utf-8")
    assert "run_desktop.py" in spec
    assert 'name="AvatarToPlayermodel"' in spec
    assert '"templates"' in spec
    assert '"static"' in spec
    assert "VERSION" in spec
    assert "app/blender" in spec
    assert "catalog.json" in spec
    assert "favicon.webp" in spec
    assert "console=False" in spec
    assert "webview.platforms.cocoa" in spec
    assert "webview.platforms.winforms" in spec
    assert "exclude_binaries=True" in spec
    assert "AvatarToPlayermodel.app" in spec


def test_freeze_script_points_at_packaged_spec():
    freeze = Path("scripts/packaging/freeze.py").read_text(encoding="utf-8")
    assert "desktop.spec" in freeze
    assert "PyInstaller" in freeze


def test_release_workflow_can_build_pygobject_and_checks_out_v4():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "actions/checkout@v4" in workflow
    assert workflow.count("actions/checkout@v4") >= 2
    assert "libgirepository-2.0-dev" in workflow
    assert "libgirepository1.0-dev" not in workflow
