from app.services.deps.catalog import (
    BLENDER_INTEL_MAC_LTS,
    BLENDER_LTS,
    dependency_links,
)


def test_setup_fetches_blender_5_2_lts():
    windows = dependency_links("windows", "x86_64")
    assert BLENDER_LTS in windows["blender"]
    assert "Blender5.2" in windows["blender"]
    assert windows["blender"].endswith(f"blender-{BLENDER_LTS}-windows-x64.zip")

    linux = dependency_links("linux", "x86_64")
    assert linux["blender"].endswith(f"blender-{BLENDER_LTS}-linux-x64.tar.xz")

    mac = dependency_links("darwin", "arm64")
    assert mac["blender"].endswith(f"blender-{BLENDER_LTS}-macos-arm64.dmg")


def test_setup_fetches_modified_compiler():
    windows = dependency_links("windows", "x86_64")
    assert "BobmacU/Gmod-Model-Port-Template" in windows["compiler"]
    linux = dependency_links("linux", "x86_64")
    assert linux["compiler"] == windows["compiler"]


def test_setup_fetches_hlmvplusplus():
    windows = dependency_links("windows", "x86_64")
    assert "HammerPlusPlus-Website" in windows["hlmvplusplus"]
    assert "hlmvplusplus" in windows


def test_intel_mac_uses_last_x64_lts():
    mac = dependency_links("darwin", "x86_64")
    assert BLENDER_INTEL_MAC_LTS in mac["blender"]
    assert "macos-x64" in mac["blender"]
