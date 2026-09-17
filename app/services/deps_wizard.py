"""Demo domain service. Copy this file when adding a real feature."""

from __future__ import annotations
import os
from app.core.paths import data_dir
from app.core.settings import APP_NAME
from app.version import VERSION

DIRECTORY_NAMES=['blender','blender/scripts/addons','steamcmd','gmod_tools']

class DepsWizardService:
    """Class dedicated to managing the system's dependencies."""
    def check_dependencies(self) -> dict:
        project_path = data_dir()
        contents: dict[str, list[str] | None] = {}
        missing: list[str] = []

        # Loop through each directory we care about
        for name in DIRECTORY_NAMES:
            subdir = project_path / name
            if subdir.exists():
                files: list[str] = []
                for root, dirs, files_in_dir in os.walk(subdir):
                    for fname in files_in_dir:
                        full_path = os.path.relpath(os.path.join(root, fname), project_path)
                        files.append(full_path)
                contents[name] = files
            else:
                contents[name] = None  # Directory missing
                missing.append(name)

        return {
            "paths": contents,
            "missing": missing,
            "ok": False if missing else True
        }
 
        

class DemoService:
    """In-memory demo logic with no database."""

    def ping(self) -> str:
        """Return a short HTMX-friendly acknowledgement."""
        return "Pong."

    def status(self) -> dict[str, str | bool]:
        """Return a JSON-serializable health payload for the demo API."""
        return {
            "ok": True,
            "app": APP_NAME,
            "version": VERSION,
        }
