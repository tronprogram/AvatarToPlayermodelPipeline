"""Version handling for the application."""

from __future__ import annotations

from app.core.paths import resource_root


def get_version() -> str:
    """Read the version file packed with the app."""
    version_file = resource_root() / "VERSION"
    try:
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return "0.0.0-unknown"


VERSION = get_version()
