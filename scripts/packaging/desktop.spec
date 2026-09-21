# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file desktop hallway (run_desktop).

This spec lives in ``scripts/packaging/``. SPECPATH is that folder; the
repo root is two levels up.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]

datas = [
    (str(ROOT / "templates"), "templates"),
    (str(ROOT / "static"), "static"),
    (str(ROOT / "VERSION"), "."),
    (str(ROOT / "app" / "blender"), "app/blender"),
    (str(ROOT / "app" / "services" / "deps" / "catalog.json"), "app/services/deps"),
]
binaries: list = []
hidden = collect_submodules("app")
hidden += [
    "plistlib",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "dotenv",
    "multipart",
    "jinja2",
]

if sys.platform == "win32":
    hidden += [
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ]
elif sys.platform == "darwin":
    hidden += [
        "webview.platforms.cocoa",
        "objc",
        "AppKit",
        "Foundation",
        "WebKit",
        "PyObjCTools",
        "PyObjCTools.AppHelper",
    ]
else:
    hidden += ["webview.platforms.gtk"]

extra_packages = ["uvicorn", "webview"]
if sys.platform == "darwin":
    extra_packages += ("objc", "AppKit", "Foundation", "WebKit", "PyObjCTools")
elif sys.platform == "win32":
    extra_packages += ("pythonnet",)

for package in extra_packages:
    extra_datas, extra_binaries, extra_hidden = collect_all(package)
    datas += extra_datas
    binaries += extra_binaries
    hidden += extra_hidden

a = Analysis(
    [str(ROOT / "run_desktop.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="AvatarToPlayermodel",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name="AvatarToPlayermodel",
    )
    app = BUNDLE(
        coll,
        name="AvatarToPlayermodel.app",
        icon=None,
        bundle_identifier="com.avatartoplayermodel.hallway",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="AvatarToPlayermodel",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
    )
