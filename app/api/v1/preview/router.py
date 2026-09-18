"""Playermodel preview: Blender viewport + export file listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.core.csrf import verify_csrf_form
from app.core.dependencies import get_ui_service
from app.services.crowbar import preview_in_crowbar
from app.services.export_system import (
    default_export_dir,
    inspect_export,
    preview_in_blender,
    render_preview_png,
)
from app.services.ui import TemplateRenderService

router = APIRouter(tags=["preview"])


@router.get("/preview", response_class=HTMLResponse)
def preview_page(
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    preview = inspect_export(default_export_dir())
    return ui.render(
        request,
        "preview.html",
        {
            "title": "Preview",
            "preview": preview,
            "has_shot": preview.screenshot.is_file(),
        },
    )


@router.post(
    "/preview/crowbar",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_form)],
)
def open_crowbar(
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    try:
        preview_in_crowbar(default_export_dir())
    except FileNotFoundError as exc:
        return ui.render(request, "partials/common/error_alert.html", {"error": str(exc)})
    return ui.render(
        request,
        "partials/preview/opened.html",
        {
            "message": "Crowbar is opening the playermodel QC on the Compile tab. Compile, then use View to inspect the MDL."
        },
    )


@router.post(
    "/preview/blender",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_form)],
)
def open_blender(
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    try:
        preview_in_blender(default_export_dir())
    except FileNotFoundError as exc:
        return ui.render(request, "partials/common/error_alert.html", {"error": str(exc)})
    return ui.render(
        request,
        "partials/preview/opened.html",
        {
            "message": "Blender is opening with the Source-space mesh, ValveBiped bones, and ragdoll capsules."
        },
    )


@router.post(
    "/preview/shot",
    response_class=HTMLResponse,
    dependencies=[Depends(verify_csrf_form)],
)
def render_shot(
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    try:
        render_preview_png(default_export_dir())
    except (FileNotFoundError, RuntimeError) as exc:
        return ui.render(request, "partials/common/error_alert.html", {"error": str(exc)})
    preview = inspect_export(default_export_dir())
    return ui.render(
        request,
        "partials/preview/shot.html",
        {"preview": preview, "has_shot": True},
    )


@router.get("/preview/aligned.glb")
def aligned_glb() -> FileResponse:
    path = default_export_dir() / "aligned.glb"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No aligned.glb to preview.")
    return FileResponse(path, media_type="model/gltf-binary", filename="aligned.glb")


@router.get("/preview/shot.png")
def preview_shot() -> FileResponse:
    path = default_export_dir() / "preview.png"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No preview still yet.")
    return FileResponse(path, media_type="image/png", filename="preview.png")
