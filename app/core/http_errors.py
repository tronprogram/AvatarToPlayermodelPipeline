"""Friendly HTTP/DB error messages for HTMX and form responses."""

from __future__ import annotations

import html
import logging
from typing import Any

import sqlite3

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
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    safe_back = html.escape(back_url, quote=True)
    subtitle = (
        f'<p class="hint">{html.escape(status_hint)}</p>' if status_hint else ""
    )
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{safe_title}</title>"
        '<link href="/static/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="/static/css/styles.css" rel="stylesheet">'
        "</head><body>"
        '<div class="container py-5">'
        '<div class="card mx-auto" style="max-width: 520px;">'
        '<div class="card-body">'
        f"<h1 class=\"h4\">{safe_title}</h1>"
        f"<p>{safe_message}</p>"
        f"{subtitle}"
        f'<a href="{safe_back}" class="btn btn-primary mt-2">Back</a>'
        "</div></div></div></body></html>"
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
