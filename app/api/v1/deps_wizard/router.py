"""Dependency Wizard API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_deps_wizard_service
from app.services.deps_wizard import (
    DependencyStatus,
    DepsWizardService,
    ExtractResult,
    FetchResult,
)

router = APIRouter(prefix="/deps-wizard", tags=["deps-wizard"])


# TODO: Create GET website endpoint that returns the website content

@router.get("/status")
def wizard_test(service: DepsWizardService = Depends(get_deps_wizard_service)) -> DependencyStatus:
    """JSON demo endpoint."""
    return service.check_dependencies()


@router.get("/fetch")
async def fetch_dependencies(service: DepsWizardService = Depends(get_deps_wizard_service)) -> FetchResult:
    """Fetch missing archives. No-ops unless phase is needs_download."""
    return await service.fetch_dependencies()


@router.get("/extract")
async def extract_dependencies(service: DepsWizardService = Depends(get_deps_wizard_service)) -> ExtractResult:
    """Unpack downloaded archives. No-ops unless phase is needs_extract."""
    return await service.extract_dependencies()


@router.get("/gmod-tools")
def gmod_tools_status(service: DepsWizardService = Depends(get_deps_wizard_service)) -> DependencyStatus:
    """Current GMod tools download status. Reloading this URL does not start SteamCMD."""
    return service.gmod_tools_status(start=False)


@router.post("/gmod-tools")
def gmod_tools_start(service: DepsWizardService = Depends(get_deps_wizard_service)) -> DependencyStatus:
    """Start SteamCMD only if app 4020 is not already installed."""
    return service.gmod_tools_status(start=True)
