"""Unix Wine assistant: pick or point at a bottle."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.dependencies import get_ui_service
from app.services.ui import TemplateRenderService
from app.services.wine_host import (
    chosen_candidate,
    host_id,
    list_candidates,
    select_prefix,
    wine_is_required,
    wine_ready,
)

router = APIRouter(tags=["wine"])


def _safe_next(value: str) -> str:
    text = (value or "").strip()
    if text.startswith("/") and not text.startswith("//") and "\\" not in text:
        return text
    return "/"


@router.get("/wine", response_class=HTMLResponse, response_model=None)
def wine_assistant(
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
    next: str = "/",
    change: str = "",
) -> HTMLResponse | RedirectResponse:
    resume = _safe_next(next)
    if not wine_is_required():
        return RedirectResponse(resume, status_code=303)
    force = change == "1"
    if wine_ready() and not force:
        return RedirectResponse(resume, status_code=303)
    candidates = list_candidates()
    chosen = chosen_candidate()
    chosen_path = str(chosen.prefix) if chosen else ""
    context = {
        "title": "Wine",
        "nav": "settings",
        "resume": resume,
        "candidates": candidates,
        "chosen_path": chosen_path,
        "wine_prefix": chosen_path,
        "host": host_id(),
        "error": "",
    }
    if not candidates:
        return ui.render(request, "wine/none.html", context)
    return ui.render(request, "wine/pick.html", context)


@router.post("/wine/pick")
def wine_pick(
    prefix: str = Form(...),
    next: str = Form("/"),
) -> RedirectResponse:
    error = select_prefix(Path(prefix))
    resume = _safe_next(next)
    if error:
        return RedirectResponse(
            f"/wine?next={quote(resume, safe='')}&change=1", status_code=303
        )
    return RedirectResponse(resume, status_code=303)


@router.post("/wine/point")
def wine_point(
    path: str = Form(...),
    next: str = Form("/"),
) -> RedirectResponse:
    resume = _safe_next(next)
    if not path.strip():
        return RedirectResponse(
            f"/wine?next={quote(resume, safe='')}&change=1", status_code=303
        )
    error = select_prefix(Path(path))
    if error:
        return RedirectResponse(
            f"/wine?next={quote(resume, safe='')}&change=1", status_code=303
        )
    return RedirectResponse(resume, status_code=303)
