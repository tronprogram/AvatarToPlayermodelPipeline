import json
from pathlib import Path

from app.services.deps.catalog import (
    bundled_catalog_path,
    dependency_links,
    load_catalog,
    set_catalog_path,
)

_CATALOG_PATH = bundled_catalog_path()


def test_setup_fetches_blender_5_2_lts():
    blender = load_catalog().blender_lts
    windows = dependency_links("windows", "x86_64")
    assert blender in windows["blender"]
    assert "Blender5.2" in windows["blender"]
    assert windows["blender"].endswith(f"blender-{blender}-windows-x64.zip")

    linux = dependency_links("linux", "x86_64")
    assert linux["blender"].endswith(f"blender-{blender}-linux-x64.tar.xz")

    mac = dependency_links("darwin", "arm64")
    assert mac["blender"].endswith(f"blender-{blender}-macos-arm64.dmg")


def test_setup_fetches_modified_compiler():
    windows = dependency_links("windows", "x86_64")
    assert "BobmacU/Gmod-Model-Port-Template" in windows["compiler"]
    linux = dependency_links("linux", "x86_64")
    assert linux["compiler"] == windows["compiler"]


def test_setup_fetches_hlmvplusplus():
    windows = dependency_links("windows", "x86_64")
    assert "HammerPlusPlus-Website" in windows["hlmvplusplus"]
    assert "hlmvplusplus" in windows


def test_versions_are_named_once():
    raw = Path(_CATALOG_PATH).read_text(encoding="utf-8")
    data = json.loads(raw)
    assert raw.count(data["blender_lts"]) == 1
    assert raw.count(data["blender_intel_mac_lts"]) == 1
    assert raw.count(data["hlmvpp_build"]) == 1


def test_user_catalog_overrides_bundled_versions(tmp_path):
    raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    raw["blender_lts"] = "9.9.9"
    raw["hlmvpp_build"] = "1000"
    user = tmp_path / "catalog.json"
    user.write_text(json.dumps(raw), encoding="utf-8")
    set_catalog_path(user)
    windows = dependency_links("windows", "x86_64")
    assert windows["blender"].endswith("blender-9.9.9-windows-x64.zip")
    assert "Blender9.9" in windows["blender"]
    assert "/download/1000/hammerplusplus_2013mp_build1000.zip" in windows["hlmvplusplus"]
    assert load_catalog().blender_lts == "9.9.9"


def test_missing_user_catalog_is_seeded_from_the_default(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.deps.catalog.data_dir", lambda: tmp_path)
    set_catalog_path(None)
    catalog = load_catalog()
    saved = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert saved["blender_lts"] == catalog.blender_lts
    assert catalog.blender_lts == json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))["blender_lts"]


def test_intel_mac_uses_last_x64_lts():
    mac = dependency_links("darwin", "x86_64")
    assert load_catalog().blender_intel_mac_lts in mac["blender"]
    assert "macos-x64" in mac["blender"]
