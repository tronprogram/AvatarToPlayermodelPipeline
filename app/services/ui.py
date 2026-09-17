"""Service for rendering Jinja2 templates."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.csrf import get_or_create_token
from app.core.settings import APP_NAME
from app.version import VERSION


class TemplateRenderService:
    """Centralized service for template rendering and UI context assembly."""

    def __init__(self, templates: Jinja2Templates) -> None:
        self.templates = templates

    def render(
        self, request: Request, template_name: str, context: dict[str, Any]
    ) -> HTMLResponse:
        """Generic render with base context."""
        context.setdefault("request", request)
        context.setdefault("csrf_token", get_or_create_token(request))
        context.setdefault("version", VERSION)
        context.setdefault("app_name", APP_NAME)
        return self.templates.TemplateResponse(request, template_name, context)

    def render_error(self, request: Request, error: str) -> HTMLResponse:
        """Render a generic error alert."""
        return self.render(
            request,
            "partials/common/error_alert.html",
            {"error": error},
        )
