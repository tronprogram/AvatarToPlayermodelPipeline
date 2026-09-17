"""Demo API routes. Copy this package when adding a real feature."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.core.csrf import verify_csrf_form
from app.core.dependencies import get_demo_service, get_ui_service
from app.services.demo import DemoService
from app.services.ui import TemplateRenderService

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.get("")
def demo_status(service: DemoService = Depends(get_demo_service)) -> dict[str, str | bool]:
    """JSON demo endpoint."""
    return service.status()


@router.post("/ping", response_class=HTMLResponse, dependencies=[Depends(verify_csrf_form)])
def demo_ping(
    request: Request,
    service: DemoService = Depends(get_demo_service),
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    """HTMX demo: CSRF-protected POST that swaps a partial."""
    return ui.render(
        request,
        "partials/common/pong.html",
        {"message": service.ping()},
    )
