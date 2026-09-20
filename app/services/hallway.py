"""Shared Setup / Convert hallway helpers (session, paths, Wine hang)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.services.setup_inventory import DEFAULT_SELECTED, wine_ready
from app.services.ui import TemplateRenderService
from app.services.user_settings import UserSettings, load_settings, save_settings

PATH_FIELDS = (
    "blender",
    "sourcetools",
    "steamcmd",
    "gmod_tools",
    "sdk2013",
    "crowbar",
    "wine_prefix",
    "zip_dir",
)

SETUP_SELECTED_KEY = "setup_selected"
CONVERT_MODEL_KEY = "convert_model"
CONVERT_NAME_KEY = "convert_name"
CONVERT_GENDER_KEY = "convert_gender"
CONVERT_AUTHOR_KEY = "convert_author"
CONVERT_DESC_KEY = "convert_description"
CONVERT_JOB_KEY = "convert_job_id"


def selected_ids(request: Request) -> set[str]:
    raw = request.session.get(SETUP_SELECTED_KEY)
    if not raw:
        return set(DEFAULT_SELECTED)
    return {str(item) for item in raw}


def store_selected(request: Request, values: list[str]) -> set[str]:
    allowed = set(DEFAULT_SELECTED) | {"crowbar"}
    clean = [item for item in values if item in allowed]
    request.session[SETUP_SELECTED_KEY] = clean
    return set(clean)


def apply_path(field: str, path: str) -> UserSettings:
    settings = load_settings()
    if field not in PATH_FIELDS:
        return settings
    setattr(settings, field, path.strip())
    return save_settings(settings)


def wine_hang(
    request: Request,
    ui: TemplateRenderService,
    *,
    kind: str,
) -> HTMLResponse | None:
    if wine_ready():
        return None
    title = "System setup" if kind == "setup" else "Convert"
    return ui.render(
        request,
        "metro/wine.html",
        {
            "title": title,
            "nav": kind,
            "kind": kind,
            "heading": title,
        },
    )


def open_folder(path: Path) -> None:
    target = str(path if path.is_dir() else path.parent)
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])
