"""What the wizard installs, and where the archives come from."""

from __future__ import annotations

# program -> [executable name, search path under data/, check for an executable]
DIRECTORY_INFO: dict[str, list] = {
    "blender": ["blender", "blender", True],
    "blender_addons": ["", "blender/scripts/addons", False],
    "steamcmd": ["steamcmd", "steamcmd", True],
    "gmod_tools": ["", "gmod_tools", True],
}

# download key -> install-tree key those archives unpack into
ARCHIVE_INSTALLS = {
    "blender": "blender",
    "steamcmd": "steamcmd",
    "sourcetools": "blender_addons",
}

# present in the install tree, never fetched over HTTP
MANUAL_INSTALLS = ("gmod_tools",)

SOURCE_TOOLS_ADDON_NAMES = ("io_scene_valvesource", "io_scene_valvesourcemodel")
SOURCE_TOOLS_URL = "http://steamreview.org/BlenderSourceTools/download"

GMOD_APP_ID = "4020"
SDK2013_APP_ID = "243750"
GMOD_STEAM_URI = f"steam://install/{GMOD_APP_ID}"
SDK2013_STEAM_URI = f"steam://install/{SDK2013_APP_ID}"
GMOD_TOOL_NAMES = ("gmad.exe", "studiomdl.exe")
CROWBAR_RELEASE = "https://github.com/ZeqMacaw/Crowbar/releases/tag/v0.74"

# Rough install sizes used on the Setup intro (gibibytes).
DISK_BUDGET_GIB = {
    "blender": 0.4,
    "sourcetools": 0.02,
    "steamcmd": 0.02,
    "gmod_tools": 6.0,
    "sdk2013": 5.0,
    "crowbar": 0.03,
}

DEPENDENCY_LINKS = {
    "win32": {
        "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd.zip",
        "blender": "https://download.blender.org/release/Blender3.6/blender-3.6.18-windows-x64.zip",
        "sourcetools": SOURCE_TOOLS_URL,
    },
    "darwin": {
        "arm64": {
            "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd_osx.tar.gz",
            "blender": "https://download.blender.org/release/Blender3.6/blender-3.6.18-macos-arm64.dmg",
            "sourcetools": SOURCE_TOOLS_URL,
        },
        "x86_64": {
            "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd_osx.tar.gz",
            "blender": "https://download.blender.org/release/Blender3.6/blender-3.6.18-macos-x64.dmg",
            "sourcetools": SOURCE_TOOLS_URL,
        },
    },
    "linux": {
        "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd_linux.tar.gz",
        "blender": "https://download.blender.org/release/Blender3.6/blender-3.6.18-linux-x64.tar.xz",
        "sourcetools": SOURCE_TOOLS_URL,
    },
}


def dependency_links(system_type: str, system_arch: str) -> dict[str, str]:
    match system_type:
        case "windows":
            return DEPENDENCY_LINKS["win32"]
        case "darwin":
            return DEPENDENCY_LINKS["darwin"][system_arch]
        case "linux":
            return DEPENDENCY_LINKS["linux"]
        case _:
            raise ValueError(f"Unknown system type {system_type}!")
