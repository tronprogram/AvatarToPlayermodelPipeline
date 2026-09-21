"""Metro Convert hallway."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.core.dependencies import get_ui_service
from app.core.paths import data_dir
from app.services.convert_job import ConvertJob, get_job, start_convert
from app.services.deps.detect import find_hlmvplusplus, gmod_tools_root
from app.services.hallway import (
    CONVERT_AUTHOR_KEY,
    CONVERT_DESC_KEY,
    CONVERT_GENDER_KEY,
    CONVERT_JOB_KEY,
    CONVERT_MODEL_KEY,
    CONVERT_NAME_KEY,
    open_folder,
    wine_hang,
)
from app.services.hlmv_preview import open_in_hlmv
from app.services.setup_inventory import required_ready, tool_rows
from app.services.ui import TemplateRenderService
from app.services.user_settings import load_settings, path_or_none
from app.services.windows_tools import is_windows

router = APIRouter(tags=["convert"])

_AVATAR_SUFFIXES = {".glb", ".gltf"}


def _avatar_warning(request: Request, ui: TemplateRenderService, filename: str = "") -> HTMLResponse:
    return ui.render(
        request,
        "convert/avatar.html",
        {
            "title": "Convert",
            "nav": "convert",
            "filename": filename,
            "warn": "avatar",
        },
    )


def _store_avatar(request: Request, data: bytes, suffix: str) -> RedirectResponse:
    dest = data_dir() / "uploads" / f"{uuid.uuid4().hex}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    request.session[CONVERT_MODEL_KEY] = str(dest)
    return RedirectResponse("/convert/identity", status_code=303)


def _hlmv_ready() -> bool:
    """HLMV++ preview is a Windows button. Unix hosts lack the 2013 engine DLLs."""
    if not is_windows():
        return False
    settings = load_settings()
    return find_hlmvplusplus(data_dir(), path_or_none(settings.hlmvplusplus)) is not None


def _job_mdl(job: ConvertJob) -> Path | None:
    if job.mdl is not None and job.mdl.is_file():
        return job.mdl
    if not job.slug:
        return None
    return _last_player_mdl(job.slug)


def _last_player_mdl(slug: str) -> Path | None:
    root = gmod_tools_root(data_dir()) / "garrysmod" / "models" / "player" / slug
    mdl = root / f"{slug}.mdl"
    return mdl if mdl.is_file() else None


@router.get("/convert", response_class=HTMLResponse)
def convert_intro(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    return ui.render(
        request,
        "convert/intro.html",
        {"title": "Convert", "nav": "convert"},
    )


@router.get("/convert/canceled", response_class=HTMLResponse)
def convert_canceled(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    return ui.render(
        request,
        "metro/canceled.html",
        {"title": "Convert", "nav": "convert", "heading": "Convert"},
    )


@router.get("/convert/fatal", response_class=HTMLResponse)
def convert_fatal(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    job_id = str(request.session.get(CONVERT_JOB_KEY) or "")
    job = get_job(job_id) if job_id else None
    return ui.render(
        request,
        "metro/fatal.html",
        {
            "title": "Convert",
            "nav": "convert",
            "heading": "Convert",
            "error": job.error if job is not None else "",
        },
    )


@router.get("/convert/avatar", response_class=HTMLResponse)
def convert_avatar_get(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="convert")
    if hung is not None:
        return hung
    stored = request.session.get(CONVERT_MODEL_KEY) or ""
    filename = Path(str(stored)).name if stored else ""
    return ui.render(
        request,
        "convert/avatar.html",
        {
            "title": "Convert",
            "nav": "convert",
            "filename": filename,
            "warn": request.query_params.get("warn", ""),
        },
    )


@router.post("/convert/avatar", response_class=HTMLResponse)
async def convert_avatar_post(
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
    avatar: UploadFile | None = File(default=None),
    path: str = Form(""),
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="convert")
    if hung is not None:
        return hung
    chosen = Path(path).expanduser() if path.strip() else None
    if chosen is not None and chosen.is_file():
        suffix = chosen.suffix.lower()
        if suffix in _AVATAR_SUFFIXES:
            return _store_avatar(request, chosen.read_bytes(), suffix)
        return _avatar_warning(request, ui, chosen.name)
    filename = avatar.filename if avatar is not None else ""
    suffix = Path(filename).suffix.lower() if filename else ""
    data = await avatar.read() if avatar is not None else b""
    if not filename or suffix not in _AVATAR_SUFFIXES or not data:
        return _avatar_warning(request, ui, filename)
    return _store_avatar(request, data, suffix)


@router.get("/convert/identity", response_class=HTMLResponse)
def convert_identity_get(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="convert")
    if hung is not None:
        return hung
    if not request.session.get(CONVERT_MODEL_KEY):
        return RedirectResponse("/convert/avatar", status_code=303)
    settings = load_settings()
    return ui.render(
        request,
        "convert/identity.html",
        {
            "title": "Convert",
            "nav": "convert",
            "display_name": request.session.get(CONVERT_NAME_KEY, ""),
            "gender": request.session.get(CONVERT_GENDER_KEY, settings.default_gender),
            "author": request.session.get(CONVERT_AUTHOR_KEY, settings.default_author),
            "description": request.session.get(
                CONVERT_DESC_KEY, settings.default_description
            ),
            "warn": request.query_params.get("warn", ""),
        },
    )


@router.post("/convert/identity")
async def convert_identity_post(request: Request) -> RedirectResponse:
    form = await request.form()
    name = str(form.get("display_name") or "").strip()
    gender = str(form.get("gender") or "male")
    author = str(form.get("author") or "")
    description = str(form.get("description") or "")
    request.session[CONVERT_GENDER_KEY] = gender
    request.session[CONVERT_AUTHOR_KEY] = author
    request.session[CONVERT_DESC_KEY] = description
    if not name:
        request.session[CONVERT_NAME_KEY] = ""
        return RedirectResponse("/convert/identity?warn=name", status_code=303)
    request.session[CONVERT_NAME_KEY] = name
    return RedirectResponse("/convert/check", status_code=303)


@router.get("/convert/check", response_class=HTMLResponse)
def convert_check(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="convert")
    if hung is not None:
        return hung
    rows = tool_rows()
    return ui.render(
        request,
        "convert/check.html",
        {
            "title": "Convert",
            "nav": "convert",
            "rows": rows,
            "ready": required_ready(rows),
        },
    )


@router.get("/convert/verify", response_class=HTMLResponse)
def convert_verify(
    request: Request, ui: TemplateRenderService = Depends(get_ui_service)
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="convert")
    if hung is not None:
        return hung
    if not request.session.get(CONVERT_MODEL_KEY) or not request.session.get(
        CONVERT_NAME_KEY
    ):
        return RedirectResponse("/convert/avatar", status_code=303)
    if not required_ready():
        return RedirectResponse("/convert/check", status_code=303)
    return ui.render(
        request,
        "convert/verify.html",
        {"title": "Convert", "nav": "convert"},
    )


@router.post("/convert/run")
def convert_run(request: Request) -> RedirectResponse:
    model = request.session.get(CONVERT_MODEL_KEY)
    name = request.session.get(CONVERT_NAME_KEY)
    if not model or not name:
        return RedirectResponse("/convert/avatar", status_code=303)
    job = start_convert(
        Path(str(model)),
        display_name=str(name),
        gender=str(request.session.get(CONVERT_GENDER_KEY) or "male"),
        author=str(request.session.get(CONVERT_AUTHOR_KEY) or ""),
        description=str(request.session.get(CONVERT_DESC_KEY) or ""),
    )
    request.session[CONVERT_JOB_KEY] = job.id
    return RedirectResponse(f"/convert/run/{job.id}", status_code=303)


@router.get("/convert/run/{job_id}", response_class=HTMLResponse)
def convert_run_page(
    job_id: str,
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    hung = wine_hang(request, ui, kind="convert")
    if hung is not None:
        return hung
    job = get_job(job_id)
    if job is None:
        return RedirectResponse("/convert/fatal", status_code=303)
    return ui.render(
        request,
        "convert/run.html",
        {
            "title": "Convert",
            "nav": "convert",
            "job_id": job_id,
            "state": job.state,
            "log": job.log,
        },
    )


@router.get("/convert/status/{job_id}", response_class=HTMLResponse)
def convert_status(
    job_id: str,
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    job = get_job(job_id)
    if job is None:
        return ui.render(
            request,
            "convert/status.html",
            {"log": ["error      job missing"], "state": "failed", "job_id": job_id},
        )
    return ui.render(
        request,
        "convert/status.html",
        {"log": job.log, "state": job.state, "job_id": job_id},
    )


@router.get("/convert/result/{job_id}", response_class=HTMLResponse)
def convert_result(
    job_id: str,
    request: Request,
    ui: TemplateRenderService = Depends(get_ui_service),
) -> HTMLResponse:
    job = get_job(job_id)
    if job is None or job.state != "succeeded" or job.zip_path is None:
        return RedirectResponse("/convert/fatal", status_code=303)
    settings = load_settings()
    if settings.open_zip_folder and not request.session.get("zip_folder_opened"):
        open_folder(job.zip_path)
        request.session["zip_folder_opened"] = True
    return ui.render(
        request,
        "convert/result.html",
        {
            "title": "Convert",
            "nav": "convert",
            "job_id": job_id,
            "slug": job.slug,
            "zip_path": str(job.zip_path),
            "offer_hlmv": _hlmv_ready(),
            "hlmv_on_windows": is_windows(),
        },
    )


@router.get("/convert/zip/{job_id}")
def convert_zip(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if job is None or job.zip_path is None or not job.zip_path.is_file():
        raise HTTPException(status_code=404, detail="Zip is not ready.")
    return FileResponse(
        job.zip_path,
        media_type="application/zip",
        filename=job.zip_path.name,
    )


@router.post("/convert/open-hlmv")
def convert_open_hlmv(
    request: Request,
    job_id: str = Form(""),
) -> RedirectResponse:
    job_id = job_id or str(request.session.get(CONVERT_JOB_KEY) or "")
    job = get_job(job_id) if job_id else None
    mdl = _job_mdl(job) if job is not None else None
    if not is_windows():
        raise HTTPException(status_code=404, detail="HLMV++ preview runs on Windows.")
    if mdl is None:
        raise HTTPException(status_code=404, detail="No compiled MDL to open in HLMV++.")
    try:
        open_in_hlmv(mdl)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    target = f"/convert/result/{job_id}" if job_id else "/convert"
    return RedirectResponse(target, status_code=303)
