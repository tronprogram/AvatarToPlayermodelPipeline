"""Demo service and /api/v1/demo routes."""

from app.core.settings import APP_NAME
from app.services.demo import DemoService
from app.version import VERSION


def test_demo_service_status_and_ping():
    service = DemoService()
    assert service.ping() == "Pong."
    assert service.status() == {"ok": True, "app": APP_NAME, "version": VERSION}


