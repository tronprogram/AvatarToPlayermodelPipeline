"""Settings page: persist tool paths and Convert defaults."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.dependencies import get_ui_service
from app.core.paths import data_dir
from app.services.deps.catalog import ensure_user_catalog, load_catalog
from app.services.folder_pick import pick_file as native_pick_file
from app.services.folder_pick import pick_folder as native_pick_folder
from app.services.hallway import PATH_FIELDS, apply_path
from app.services.ui import TemplateRenderService
from app.services.user_settings import load_settings, save_settings
from app.services.wine_host import chosen_candidate, wine_is_required

router = APIRouter(tags=["settings"])

_PATH_LABELS = (
    ("blender", "Blender"),
    ("sourcetools", "Blender Source Tools"),
    ("steamcmd", "SteamCMD"),
    ("gmod_tools", "Garry's Mod dedicated"),
    ("compiler", "Modified Source compiler"),
    ("hlmvplusplus", "HLMV++"),
    ("sdk2013", "Source SDK 2013 Multiplayer"),
    ("zip_dir", "Zip destination"),
)


def _path_rows() -> list[dict[str, str]]:
    settings = load_settings()
    return [
        {
            "field": field,
            "label": label,
            "value": getattr(settings, field) or "",
        }
        for field, label in _PATH_LABELS
    ]


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    settings = load_settings()
    chosen = chosen_candidate()
    catalog = load_catalog()
    return ui.render(
        request,
        "settings/page.html",
        {
            "title": "Settings",
            "nav": "settings",
            "settings": settings,
            "paths": _path_rows(),
            "wine_needed": wine_is_required(),
            "wine_label": chosen.label if chosen else "",
            "data_dir": str(data_dir()),
            "catalog_path": str(ensure_user_catalog()),
            "catalog_blender": catalog.blender_lts,
            "catalog_blender_intel": catalog.blender_intel_mac_lts,
            "catalog_hlmv": catalog.hlmvpp_build,
        },
    )


@router.post("/settings")
async def settings_save(request: Request) -> RedirectResponse:
    form = await request.form()
    settings = load_settings()
    for field in PATH_FIELDS:
        value = form.get(field)
        if value is not None:
            setattr(settings, field, str(value).strip())
    gender = str(form.get("default_gender") or "male")
    settings.default_gender = "female" if gender == "female" else "male"
    settings.default_author = str(form.get("default_author") or "")
    settings.default_description = str(form.get("default_description") or "")
    settings.open_zip_folder = form.get("open_zip_folder") == "1"
    save_settings(settings)
    return RedirectResponse("/", status_code=303)


@router.post("/pick-folder")
def pick_folder() -> JSONResponse:
    """Open a native folder dialog. Used when the UI is a normal browser."""
    return JSONResponse({"path": native_pick_folder()})


@router.post("/pick-file")
def pick_file() -> JSONResponse:
    """Open a native file dialog. WKWebView file inputs often post an empty file."""
    return JSONResponse({"path": native_pick_file()})


@router.post("/settings/clear-paths")
def settings_clear_paths() -> RedirectResponse:
    """Forget every tool directory chosen on this page."""
    settings = load_settings()
    for field, _label in _PATH_LABELS:
        setattr(settings, field, "")
    save_settings(settings)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/point")
def settings_point(
    field: str = Form(...),
    path: str = Form(...),
    next: str = Form("/settings"),
) -> RedirectResponse:
    apply_path(field, path)
    return RedirectResponse(_safe_next(next), status_code=303)


def _safe_next(value: str) -> str:
    text = value.strip()
    if text.startswith("/") and not text.startswith("//") and "\\" not in text:
        return text
    return "/settings"
