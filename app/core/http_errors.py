"""Friendly HTTP/DB error messages for HTMX and form responses."""

from __future__ import annotations

import logging
from typing import Any

import sqlite3

from app.core.templates import render_html

_log = logging.getLogger(__name__)

SEARCH_QUERY_MAX_LENGTH = 120

CSRF_USER_MESSAGE = (
    "Your security token expired. Reload the page and try again."
)

UNHANDLED_ERROR_MESSAGE = "Something went wrong. Try again."


def _is_integrity_error(exc: Exception) -> bool:
    """True for sqlite3 IntegrityError."""
    return isinstance(exc, sqlite3.IntegrityError) or type(exc).__name__ == "IntegrityError"


def friendly_integrity_error(exc: Exception) -> str | None:
    """Map common integrity violations to user-facing messages."""
    origin = getattr(exc, "orig", None)
    message = str(origin if origin is not None else exc).lower()
    if "unique constraint failed" in message:
        return "That record already exists."
    return None


def friendly_mutation_error(entity: str, action: str, exc: Exception) -> str:
    """Return a safe error for entity create/update/delete failures."""
    _log.exception("Mutation error trying to %s %s", action, entity)
    if _is_integrity_error(exc):
        mapped = friendly_integrity_error(exc)
        if mapped:
            return mapped
        return f"Could not {action} {entity}."
    if isinstance(exc, ValueError):
        return str(exc)
    return f"Could not {action} {entity}. Try again."


def friendly_read_error(area: str, exc: Exception) -> str:
    """Return a safe error for read-only HTML/HTMX route failures."""
    if isinstance(exc, ValueError):
        return str(exc)
    return f"Could not load {area}. Try again."


def log_and_friendly_read_error(area: str, exc: Exception) -> str:
    """Log a read failure and return a user-safe message."""
    _log.exception("Read error while loading %s", area)
    return friendly_read_error(area, exc)


def http_exception_message(detail: Any) -> str:
    """Normalize an HTTPException detail value to a user-facing string."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return first_validation_error_message(detail)
    return "Invalid request."


def simple_html_error_page(
    title: str,
    message: str,
    *,
    back_url: str = "/",
    status_hint: str | None = None,
) -> str:
    """Build a minimal standalone HTML error page."""
    return render_html(
        "error.html",
        title=title,
        message=message,
        back_url=back_url,
        status_hint=status_hint,
    )


def first_validation_error_message(errors: list[dict[str, Any]]) -> str:
    """Extract a concise message from a FastAPI validation error list."""
    if not errors:
        return "Invalid data. Check the form."

    err = errors[0]
    msg = str(err.get("msg", ""))
    err_type = err.get("type", "")
    loc = err.get("loc", ())

    if err_type == "string_too_long" and loc and loc[-1] == "q":
        return f"Search cannot exceed {SEARCH_QUERY_MAX_LENGTH} characters."
    if err_type == "string_too_long":
        return "One of the fields is longer than allowed."
    if err_type == "missing":
        field = loc[-1] if loc else "field"
        return f"The '{field}' field is required."
    if err_type == "value_error":
        if msg.startswith("Value error, "):
            return msg.removeprefix("Value error, ")
        return msg

    return msg or "Invalid data. Check the form."
