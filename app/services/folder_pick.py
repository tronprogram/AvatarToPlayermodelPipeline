"""Native folder chooser for the loopback UI (browser or pywebview)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def pick_folder() -> str:
    """Open a system folder dialog and return the chosen path, or empty."""
    if sys.platform == "darwin":
        return _darwin()
    if sys.platform == "win32":
        return _windows()
    return _linux()


def pick_file(*, suffixes: tuple[str, ...] = (".glb", ".gltf")) -> str:
    """Open a system file dialog and return a path with an allowed suffix."""
    if sys.platform == "darwin":
        path = _darwin_file()
    elif sys.platform == "win32":
        path = _windows_file()
    else:
        path = _linux_file()
    if path and Path(path).suffix.lower() not in suffixes:
        return ""
    return path


def _darwin() -> str:
    script = (
        'try\n'
        '  POSIX path of (choose folder with prompt "Point at a directory")\n'
        'on error\n'
        '  return ""\n'
        'end try'
    )
    return _run(["osascript", "-e", script])


def _windows() -> str:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$d.Description = 'Point at a directory'; "
        "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "[Console]::Out.Write($d.SelectedPath) }"
    )
    return _run(["powershell", "-STA", "-NoProfile", "-Command", script])


def _darwin_file() -> str:
    script = (
        'try\n'
        '  POSIX path of (choose file with prompt "Please provide the 360sona to convert")\n'
        'on error\n'
        '  return ""\n'
        'end try'
    )
    return _run(["osascript", "-e", script])


def _windows_file() -> str:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d = New-Object System.Windows.Forms.OpenFileDialog; "
        "$d.Title = 'Please provide the 360sona to convert'; "
        "$d.Filter = '360sona (*.glb;*.gltf)|*.glb;*.gltf'; "
        "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "[Console]::Out.Write($d.FileName) }"
    )
    return _run(["powershell", "-STA", "-NoProfile", "-Command", script])


def _linux_file() -> str:
    commands = (
        [
            "zenity",
            "--file-selection",
            "--title=Please provide the 360sona to convert",
            "--file-filter=360sona | *.glb *.gltf",
        ],
        ["kdialog", "--getopenfilename", ".", "*.glb *.gltf"],
    )
    for cmd in commands:
        if shutil.which(cmd[0]) is None:
            continue
        path = _run(cmd, ok_only=True)
        if path:
            return path
        return ""
    return ""


def _linux() -> str:
    home = str(Path.home())
    commands = (
        ["zenity", "--file-selection", "--directory", "--title=Point at a directory"],
        ["kdialog", "--getexistingdirectory", home, "Point at a directory"],
    )
    for cmd in commands:
        if shutil.which(cmd[0]) is None:
            continue
        path = _run(cmd, ok_only=True)
        if path:
            return path
        return ""
    return ""


def _run(cmd: list[str], *, ok_only: bool = False) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if ok_only and result.returncode != 0:
        return ""
    return (result.stdout or "").strip()
