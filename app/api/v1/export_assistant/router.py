"""Demo API routes. Copy this package when adding a real feature."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse


from app.core.dependencies import get_demo_service, get_ui_service
from app.services.demo import DemoService
from app.services.ui import TemplateRenderService

router = APIRouter(prefix="/api/v1/export_assistant", tags=["export_assistant"])


@router.get("")
def demo_status(service: DemoService = Depends(get_demo_service)) -> dict[str, str | bool]:
    """JSON export assistant endpoint."""
    return service.status()


