"""Shared test client."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.deps.catalog import bundled_catalog_path, set_catalog_path


@pytest.fixture(autouse=True)
def bundled_catalog():
    """Tests read the shipped catalog unless a test points at another file."""
    set_catalog_path(bundled_catalog_path())
    yield
    set_catalog_path(None)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}
