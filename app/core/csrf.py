"""CSRF token helpers using stdlib secrets and HMAC constant-time compare.

Tokens are bound to the Starlette session and support a small rotation window
for multi-tab usage.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Final

from fastapi import Request


CSRF_SESSION_KEY: Final[str] = "_csrf_token"
CSRF_PREVIOUS_KEY: Final[str] = "_csrf_token_prev"
TOKEN_BYTES: Final[int] = 32


class CsrfError(Exception):
    """Raised when CSRF token validation fails."""


def _generate_token() -> str:
    """Generate a new random CSRF token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def get_or_create_token(request: Request) -> str:
    """Return the current CSRF token for the session, creating one if absent."""
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = _generate_token()
        request.session[CSRF_SESSION_KEY] = token
    return token


def validate_token(request: Request, submitted_token: str | None) -> None:
    """Validate a submitted CSRF token against the session.

    Accepts either the current token or the previous token (rotation window)
    to avoid breaking multi-tab submissions.
    """
    if not submitted_token:
        raise CsrfError("CSRF token is missing.")

    current = request.session.get(CSRF_SESSION_KEY, "")
    previous = request.session.get(CSRF_PREVIOUS_KEY, "")

    if hmac.compare_digest(submitted_token, current):
        return
    if previous and hmac.compare_digest(submitted_token, previous):
        return

    raise CsrfError("CSRF token is invalid or expired.")


def rotate_token(request: Request) -> str:
    """Rotate the CSRF token and preserve the previous one."""
    current = request.session.get(CSRF_SESSION_KEY, "")
    if current:
        request.session[CSRF_PREVIOUS_KEY] = current
    new_token = _generate_token()
    request.session[CSRF_SESSION_KEY] = new_token
    return new_token


async def verify_csrf_form(request: Request) -> None:
    """Validate CSRF token from form data on state-changing requests."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    form = await request.form()
    submitted_token = form.get("csrf_token")
    validate_token(request, submitted_token)
