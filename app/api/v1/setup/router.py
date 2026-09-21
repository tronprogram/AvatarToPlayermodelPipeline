"""Metro Setup hallway."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.dependencies import get_ui_service
from app.services.deps.catalog import load_catalog
from app.services.hallway import apply_path, selected_ids, store_selected, wine_hang
from app.services.setup_install import snapshot as install_snapshot
from app.services.setup_install import start as start_install
from app.services.setup_inventory import (
    disk_budget_for,
    gmod_tools_needs_step,
    selected_ready,
    setup_tree,
    source_tools_needs_warning,
    tool_rows,
)
from app.services.ui import TemplateRenderService

router = APIRouter(tags=["setup"])


def _tree() -> list[dict[str, str | None]]:
    return [
        {"id": item_id, "label": label, "parent": parent}
        for item_id, label, parent in setup_tree()
    ]


def _after_tools(
    request: Request,
    *,
    skip_source: bool = False,
    skip_gmod: bool = False,
) -> RedirectResponse:
    selected = selected_ids(request)
    rows = tool_rows()
    if selected_ready(selected, rows):
        return RedirectResponse("/setup/verify", status_code=303)
    if not skip_source and source_tools_needs_warning(selected, rows):
        return RedirectResponse("/setup/sourcetools", status_code=303)
    if not skip_gmod and gmod_tools_needs_step(selected, rows):
        return RedirectResponse("/setup/gmod", status_code=303)
    return RedirectResponse("/setup/install", status_code=303)


@router.get("/setup", response_class=HTMLResponse)
def setup_intro(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    selected = selected_ids(request)
    return ui.render(
        request,
        "setup/intro.html",
        {
            "title": "System setup",
            "nav": "setup",
            "disk_budget": disk_budget_for(selected),
        },
    )


@router.get("/setup/canceled", response_class=HTMLResponse)
def setup_canceled(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    return ui.render(
        request,
        "metro/canceled.html",
        {"title": "System setup", "nav": "setup", "heading": "System setup"},
    )


@router.get("/setup/fatal", response_class=HTMLResponse)
def setup_fatal(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    job = install_snapshot()
    return ui.render(
        request,
        "metro/fatal.html",
        {
            "title": "System setup",
            "nav": "setup",
            "heading": "System setup",
            "error": job.error,
        },
    )


@router.post("/setup/select", response_class=HTMLResponse)
def setup_select(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    return ui.render(
        request,
        "setup/select.html",
        {
            "title": "System setup",
            "nav": "setup",
            "tree": _tree(),
            "selected": selected_ids(request),
        },
    )


@router.get("/setup/select", response_class=HTMLResponse)
def setup_select_get(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    return ui.render(
        request,
        "setup/select.html",
        {
            "title": "System setup",
            "nav": "setup",
            "tree": _tree(),
            "selected": selected_ids(request),
        },
    )


@router.post("/setup/scan")
async def setup_scan(request: Request) -> RedirectResponse:
    form = await request.form()
    tools = [str(value) for value in form.getlist("tool")]
    if tools:
        store_selected(request, tools)
    selected = selected_ids(request)
    if selected_ready(selected):
        return RedirectResponse("/setup/verify", status_code=303)
    return RedirectResponse("/setup/missing", status_code=303)


@router.get("/setup/missing", response_class=HTMLResponse)
def setup_missing(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    selected = selected_ids(request)
    rows = [row for row in tool_rows() if row.id in selected]
    return ui.render(
        request,
        "setup/missing.html",
        {
            "title": "System setup",
            "nav": "setup",
            "rows": rows,
            "selected": selected,
        },
    )


@router.post("/setup/point")
def setup_point(
    field: str = Form(...), path: str = Form(...)
) -> RedirectResponse:
    apply_path(field, path)
    return RedirectResponse("/setup/missing", status_code=303)


@router.post("/setup/from-missing")
def setup_from_missing(request: Request) -> RedirectResponse:
    return _after_tools(request)


@router.get("/setup/sourcetools", response_class=HTMLResponse)
def setup_sourcetools(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    return ui.render(
        request,
        "setup/sourcetools.html",
        {
            "title": "System setup",
            "nav": "setup",
            "source_tools_url": load_catalog().source_tools_url,
        },
    )


@router.post("/setup/after-sourcetools")
def setup_after_sourcetools(request: Request) -> RedirectResponse:
    return _after_tools(request, skip_source=True)


@router.get("/setup/gmod", response_class=HTMLResponse)
def setup_gmod(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    selected = selected_ids(request)
    return ui.render(
        request,
        "setup/gmod.html",
        {
            "title": "System setup",
            "nav": "setup",
            "gmod_uri": load_catalog().gmod_steam_uri,
            "selected": selected,
        },
    )


@router.post("/setup/after-gmod")
def setup_after_gmod(request: Request) -> RedirectResponse:
    return _after_tools(request, skip_source=True, skip_gmod=True)


@router.get("/setup/install", response_class=HTMLResponse)
def setup_install(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    selected = selected_ids(request)
    job = start_install(selected)
    return ui.render(
        request,
        "setup/install.html",
        {
            "title": "System setup",
            "nav": "setup",
            "ready": job.state == "succeeded",
            "log": "\n".join(job.log) or "Starting…",
            "state": job.state,
            "error": job.error,
        },
    )


@router.get("/setup/install/status", response_class=HTMLResponse)
def setup_install_status(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    job = install_snapshot()
    return ui.render(
        request,
        "setup/status.html",
        {
            "log": "\n".join(job.log) or "Working…",
            "state": job.state,
            "error": job.error,
            "oob_continue": True,
        },
    )


@router.post("/setup/after-install")
def setup_after_install(request: Request) -> RedirectResponse:
    job = install_snapshot()
    if job.state == "failed":
        return RedirectResponse("/setup/fatal", status_code=303)
    selected = selected_ids(request)
    rows = tool_rows()
    if selected_ready(selected, rows):
        return RedirectResponse("/setup/verify", status_code=303)
    if gmod_tools_needs_step(selected, rows):
        return RedirectResponse("/setup/gmod", status_code=303)
    return RedirectResponse("/setup/missing", status_code=303)


@router.get("/setup/verify", response_class=HTMLResponse)
def setup_verify(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    if not selected_ready(selected_ids(request)):
        return RedirectResponse("/setup/missing", status_code=303)
    return ui.render(
        request,
        "setup/verify.html",
        {"title": "System setup", "nav": "setup"},
    )


@router.get("/setup/done", response_class=HTMLResponse)
def setup_done(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="setup")
    if hung is not None:
        return hung
    return ui.render(
        request,
        "setup/done.html",
        {"title": "System setup", "nav": "setup"},
    )
