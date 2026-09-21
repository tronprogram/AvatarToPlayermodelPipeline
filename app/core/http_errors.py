"""Friendly form error messages for the desktop window."""

from __future__ import annotations

from typing import Any

from app.core.templates import render_html

UNHANDLED_ERROR_MESSAGE = "Something went wrong. Try again."


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
