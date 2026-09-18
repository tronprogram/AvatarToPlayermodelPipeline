"""Small HTTP header helpers."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from urllib.parse import unquote


def filename_from_content_disposition(header: str | None) -> str | None:
    """Return the basename from a Content-Disposition header, if present.

    PEP 594 (cgi removal) points at EmailMessage.get_filename() for this header.
    """
    if not header:
        return None
    msg = EmailMessage()
    msg["Content-Disposition"] = header
    name = msg.get_filename()
    if not name:
        return None
    return Path(unquote(name)).name
