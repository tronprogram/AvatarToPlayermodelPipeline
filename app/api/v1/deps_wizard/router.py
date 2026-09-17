"""Dependency Wizard API routes."""

from __future__ import annotations
from typing import TypedDict

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.core.csrf import verify_csrf_form
from app.core.dependencies import get_deps_wizard_service, get_ui_service

from app.services.deps_wizard import DepsWizardService
from app.services.ui import TemplateRenderService

router = APIRouter(prefix="/deps-wizard", tags=["deps-wizard"])

class CheckResult(TypedDict):
    paths: dict[str, list[str] | None]
    missing: list[str]
    ok: bool



@router.get("")
def wizard_test(service: DepsWizardService = Depends(get_deps_wizard_service)) -> CheckResult:
    """JSON demo endpoint."""
    return service.check_dependencies()
