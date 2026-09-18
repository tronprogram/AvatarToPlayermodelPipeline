"""Jinja loaders for bundled document templates.

Valve/Source files use ``{ }`` and ``$`` heavily, so those templates use
``[[ var ]]`` / ``[% %]`` (same as QC and Lua). HTML uses normal Jinja.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.core.paths import resource_root


def templates_root() -> Path:
    """Checkout or PyInstaller copy of ``templates/``."""
    for candidate in (
        resource_root() / "templates",
        resource_root() / "app" / "templates",
    ):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Missing templates directory under {resource_root()}")


@cache
def valve_environment() -> Environment:
    """Shared env for everything under ``templates/valve/``."""
    env = Environment(
        loader=FileSystemLoader(templates_root() / "valve"),
        autoescape=False,
        undefined=StrictUndefined,
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["xml"] = xml_escape
    return env


@cache
def html_environment() -> Environment:
    """Standalone HTML (error pages) with autoescape. No FastAPI request."""
    return Environment(
        loader=FileSystemLoader(templates_root() / "html"),
        autoescape=True,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_valve(relative: str, **context: object) -> str:
    """Render ``templates/valve/<relative>``. Returns the file body as text."""
    return valve_environment().get_template(relative).render(**context)


def render_html(relative: str, **context: object) -> str:
    """Render ``templates/html/<relative>`` with autoescape. Returns HTML text."""
    return html_environment().get_template(relative).render(**context)


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
