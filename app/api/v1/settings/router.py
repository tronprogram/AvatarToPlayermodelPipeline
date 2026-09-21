"""Settings page: persist tool paths and Convert defaults."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.csrf import verify_csrf_form
from app.core.dependencies import get_ui_service
from app.services.hallway import PATH_FIELDS, apply_path
from app.services.ui import TemplateRenderService
from app.services.user_settings import load_settings, save_settings, wine_is_required

router = APIRouter(tags=["settings"])

_PATH_LABELS = (
    ("blender", "Blender"),
    ("sourcetools", "Blender Source Tools"),
    ("steamcmd", "SteamCMD"),
    ("gmod_tools", "Garry's Mod dedicated"),
    ("compiler", "Modified Source compiler"),
    ("hlmvplusplus", "HLMV++"),
    ("sdk2013", "Source SDK 2013 Multiplayer"),
    ("crowbar", "Crowbar"),
    ("wine_prefix", "Wine prefix"),
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
    return ui.render(
        request,
        "settings/page.html",
        {
            "title": "Settings",
            "nav": "settings",
            "settings": settings,
            "paths": _path_rows(),
            "require_wine": wine_is_required(settings),
        },
    )


@router.post(
    "/settings",
    dependencies=[Depends(verify_csrf_form)],
)
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
    settings.offer_crowbar = form.get("offer_crowbar") == "1"
    settings.offer_hlmv = form.get("offer_hlmv") == "1"
    settings.require_wine = form.get("require_wine") == "1"
    save_settings(settings)
    return RedirectResponse("/", status_code=303)


@router.post(
    "/settings/point",
    dependencies=[Depends(verify_csrf_form)],
)
def settings_point(
    field: str = Form(...), path: str = Form(...)
) -> RedirectResponse:
    apply_path(field, path)
    return RedirectResponse("/settings", status_code=303)
