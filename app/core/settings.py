"""Application settings with environment parsing and validation."""

from __future__ import annotations

import os
import secrets
import warnings

from dotenv import load_dotenv

from app.core.paths import resource_root, writable_root

load_dotenv(resource_root() / ".env")
load_dotenv(writable_root() / ".env", override=True)

APP_NAME = os.getenv("APP_NAME", "App")
APP_ID = os.getenv("APP_ID", "App")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
SINGLE_INSTANCE_PORT = 8764


class SecurityConfigurationError(Exception):
    """Raised when a security-critical configuration value is missing or invalid."""


def is_production() -> bool:
    """Determine if the application is running in production mode."""
    env = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower()
    return env in ("production", "prod")


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


def get_session_secret() -> str:
    """Retrieve and validate the session signing secret.

    Production fails fast if the secret is missing or shorter than 32 characters.
    Development warns and falls back to an ephemeral random secret.
    """
    secret = os.getenv("SESSION_SECRET", "")
    min_length = 32

    if not secret or len(secret) < min_length:
        if is_production():
            raise SecurityConfigurationError(
                f"SESSION_SECRET is missing or shorter than {min_length} characters. "
                "Set a strong, random secret in the environment before starting the app."
            )
        ephemeral = secrets.token_urlsafe(32)
        warnings.warn(
            "SESSION_SECRET is missing or weak. Using an ephemeral secret for this session. "
            "Set SESSION_SECRET in your environment to suppress this warning.",
            stacklevel=2,
        )
        return ephemeral

    placeholder_fragments = ("change-me", "placeholder", "secret", "default", "fallback")
    lowered = secret.lower()
    if any(frag in lowered for frag in placeholder_fragments) and is_production():
        raise SecurityConfigurationError(
            "SESSION_SECRET appears to be a placeholder value. "
            "Set a strong, random secret in the environment before starting the app."
        )

    return secret
