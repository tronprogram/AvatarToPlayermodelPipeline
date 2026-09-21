"""What the wizard installs, and where the archives come from."""

from __future__ import annotations

# program -> [executable name, search path under data/, check for an executable]
DIRECTORY_INFO: dict[str, list] = {
    "blender": ["blender", "blender", True],
    "blender_addons": ["", "blender/scripts/addons", False],
    "steamcmd": ["steamcmd", "steamcmd", True],
    "compiler": ["studiomdl", "compiler", True],
    "hlmvplusplus": ["hlmvplusplus", "hlmvplusplus", True],
    "gmod_tools": ["", "gmod_tools", True],
}

# download key -> install-tree key those archives unpack into
ARCHIVE_INSTALLS = {
    "blender": "blender",
    "steamcmd": "steamcmd",
    "sourcetools": "blender_addons",
    "compiler": "compiler",
    "hlmvplusplus": "hlmvplusplus",
}

# present in the install tree, never fetched over HTTP
MANUAL_INSTALLS = ("gmod_tools",)

SOURCE_TOOLS_ADDON_NAMES = ("io_scene_valvesource", "io_scene_valvesourcemodel")
SOURCE_TOOLS_URL = "http://steamreview.org/BlenderSourceTools/download"
PORT_TEMPLATE_URL = (
    "https://github.com/BobmacU/Gmod-Model-Port-Template/archive/refs/heads/main.zip"
)
PORT_TEMPLATE_HINT = "https://github.com/BobmacU/Gmod-Model-Port-Template"
# 5.2 is Apple Silicon only on macOS; Intel Mac Setup still fetches 4.5 LTS.
BLENDER_LTS = "5.2.2"
BLENDER_INTEL_MAC_LTS = "4.5.14"
_BLENDER_CDN = "https://download.blender.org/release"

GMOD_APP_ID = "4020"
SDK2013_APP_ID = "243750"
GMOD_STEAM_URI = f"steam://install/{GMOD_APP_ID}"
SDK2013_STEAM_URI = f"steam://install/{SDK2013_APP_ID}"
GMOD_TOOL_NAMES = ("gmad.exe", "studiomdl.exe")
CROWBAR_RELEASE = "https://github.com/ZeqMacaw/Crowbar/releases/tag/v0.74"
HLMVPP_BUILD = "8871"
HLMVPP_URL = (
    "https://github.com/ficool2/HammerPlusPlus-Website/releases/download/"
    f"{HLMVPP_BUILD}/hammerplusplus_2013mp_build{HLMVPP_BUILD}.zip"
)
HLMVPP_HINT = "https://github.com/ficool2/HammerPlusPlus-Website/releases"

# Rough install sizes used on the Setup intro (gibibytes).
DISK_BUDGET_GIB = {
    "blender": 0.5,
    "sourcetools": 0.02,
    "steamcmd": 0.02,
    "compiler": 0.08,
    "hlmvplusplus": 0.02,
    "gmod_tools": 6.0,
    "sdk2013": 5.0,
    "crowbar": 0.03,
}

DEPENDENCY_LINKS = {
    "win32": {
        "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd.zip",
        "blender": f"{_BLENDER_CDN}/Blender5.2/blender-{BLENDER_LTS}-windows-x64.zip",
        "sourcetools": SOURCE_TOOLS_URL,
        "compiler": PORT_TEMPLATE_URL,
        "hlmvplusplus": HLMVPP_URL,
    },
    "darwin": {
        "arm64": {
            "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd_osx.tar.gz",
            "blender": f"{_BLENDER_CDN}/Blender5.2/blender-{BLENDER_LTS}-macos-arm64.dmg",
            "sourcetools": SOURCE_TOOLS_URL,
            "compiler": PORT_TEMPLATE_URL,
            "hlmvplusplus": HLMVPP_URL,
        },
        "x86_64": {
            "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd_osx.tar.gz",
            "blender": (
                f"{_BLENDER_CDN}/Blender4.5/"
                f"blender-{BLENDER_INTEL_MAC_LTS}-macos-x64.dmg"
            ),
            "sourcetools": SOURCE_TOOLS_URL,
            "compiler": PORT_TEMPLATE_URL,
            "hlmvplusplus": HLMVPP_URL,
        },
    },
    "linux": {
        "steamcmd": "https://client-update.steamstatic.com/installer/steamcmd_linux.tar.gz",
        "blender": f"{_BLENDER_CDN}/Blender5.2/blender-{BLENDER_LTS}-linux-x64.tar.xz",
        "sourcetools": SOURCE_TOOLS_URL,
        "compiler": PORT_TEMPLATE_URL,
        "hlmvplusplus": HLMVPP_URL,
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
