"""Persisted user settings for tool paths and Convert defaults."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Literal

from app.core.paths import data_dir
from app.services.windows_tools import is_windows

BindGender = Literal["male", "female"]


@dataclass
class UserSettings:
    """Paths and Convert defaults stored under the writable data directory."""

    blender: str = ""
    sourcetools: str = ""
    steamcmd: str = ""
    gmod_tools: str = ""
    sdk2013: str = ""
    crowbar: str = ""
    wine_prefix: str = ""
    zip_dir: str = ""
    require_wine: bool | None = None
    default_author: str = ""
    default_description: str = ""
    default_gender: BindGender = "male"
    open_zip_folder: bool = False
    offer_crowbar: bool = False
    offer_hlmv: bool = False


def settings_path() -> Path:
    return data_dir() / "user_settings.json"


def default_require_wine() -> bool:
    return not is_windows()


def wine_is_required(settings: UserSettings) -> bool:
    if settings.require_wine is None:
        return default_require_wine()
    return bool(settings.require_wine)


def load_settings() -> UserSettings:
    path = settings_path()
    if not path.is_file():
        return UserSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserSettings()
    if not isinstance(raw, dict):
        return UserSettings()
    allowed = {item.name for item in fields(UserSettings)}
    clean: dict[str, Any] = {key: raw[key] for key in allowed if key in raw}
    if clean.get("default_gender") not in ("male", "female"):
        clean["default_gender"] = "male"
    return UserSettings(**clean)


def save_settings(settings: UserSettings) -> UserSettings:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    return settings


def path_or_none(value: str) -> Path | None:
    text = value.strip()
    if not text:
        return None
    return Path(text).expanduser()
