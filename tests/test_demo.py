"""Demo service and /api/v1/demo routes."""

from app.core.settings import APP_NAME
from app.services.demo import DemoService
from app.version import VERSION
from tests.conftest import extract_csrf


def test_demo_service_status_and_ping():
    service = DemoService()
    assert service.ping() == "Pong."
    assert service.status() == {"ok": True, "app": APP_NAME, "version": VERSION}


def test_demo_status_endpoint(client):
    response = client.get("/api/v1/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["app"] == APP_NAME
    assert body["version"] == VERSION


def test_demo_ping_swaps_partial(client):
    page = client.get("/")
    token = extract_csrf(page.text)
    response = client.post(
        "/api/v1/demo/ping",
        data={"csrf_token": token},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "Pong." in response.text
