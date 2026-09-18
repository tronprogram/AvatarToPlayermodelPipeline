"""Global dependencies for the application."""

from __future__ import annotations
import platform

from fastapi import Request

from app.services.demo import DemoService
from app.services.deps_wizard import DepsWizardService

from app.services.ui import TemplateRenderService


def get_ui_service(request: Request) -> TemplateRenderService:
    """Retrieve the UI service from the application state."""
    return request.app.state.ui


def get_demo_service() -> DemoService:
    """Provide a demo service instance for API routes."""
    return DemoService()

def get_deps_wizard_service()->DepsWizardService:
    """Provide a dependency wizard service instance for API routes."""
    return DepsWizardService(platform.system().lower(), platform.machine().lower())
