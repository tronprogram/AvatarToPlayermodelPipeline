"""Shared test fixtures. Isolate each test on its own SQLite file."""

from __future__ import annotations

import os
import re

os.environ.setdefault("SESSION_SECRET", "test-session-secret-value-32chars!!")
os.environ.setdefault("APP_ENV", "development")

import pytest
from starlette.testclient import TestClient

from app.main import app


def extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "CSRF token not found in HTML"
    return match.group(1)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}
