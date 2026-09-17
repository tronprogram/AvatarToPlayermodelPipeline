"""Demo domain service. Copy this file when adding a real feature."""

from __future__ import annotations

from app.core.settings import APP_NAME
from app.version import VERSION


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
