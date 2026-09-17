"""Shared query utilities for SQL filtering patterns."""

from __future__ import annotations


def escape_like_pattern(value: str) -> str:
    """Escape SQL LIKE wildcard characters in a user-supplied search pattern."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
