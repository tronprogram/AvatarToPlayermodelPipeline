"""Global dependencies for the application."""

from __future__ import annotations

from fastapi import Request

from app.services.ui import TemplateRenderService


def get_ui_service(request: Request) -> TemplateRenderService:
    """Retrieve the UI service from the application state."""
    return request.app.state.ui
