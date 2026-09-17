"""Shared pagination helpers for sqlite3 queries."""

from __future__ import annotations

MAX_PAGE_SIZE: int = 10000


def page_bounds(page: int = 1, page_size: int = 50) -> tuple[int, int]:
    """Return (offset, limit) for a 1-indexed page."""
    safe_page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    offset = (max(1, page) - 1) * safe_page_size
    return offset, safe_page_size


def compute_total_pages(total_rows: int, page_size: int) -> int:
    """Calculate the total number of pages for a given row count."""
    safe_page_size = max(1, page_size)
    total_pages = (total_rows + safe_page_size - 1) // safe_page_size
    return max(total_pages, 1)
