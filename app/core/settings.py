"""Loopback bind address for the desktop window."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.core.paths import resource_root, writable_root

load_dotenv(resource_root() / ".env")
load_dotenv(writable_root() / ".env", override=True)

APP_NAME = "Avatar to Playermodel"
# Starlette signs the hallway cookie. This window is local; the key is not a deployed secret.
SESSION_KEY = "avatartoplayermodel-local"
DEFAULT_HOST = "127.0.0.1"
# Stay above Windows Hyper-V excluded blocks around 8xxx (WinError 10013).
DEFAULT_PORT = 18765
SINGLE_INSTANCE_PORT = 18764


def get_host() -> str:
    """Return the loopback host the desktop API binds to."""
    return os.getenv("APP_HOST", DEFAULT_HOST)


def get_port() -> int:
    """Return the loopback port the desktop API binds to."""
    raw = os.getenv("APP_PORT", str(DEFAULT_PORT))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT
