"""CSRF validation on state-changing HTMX posts."""


def test_ping_without_csrf_returns_htmx_error(client):
    response = client.post(
        "/api/v1/demo/ping",
        headers={"HX-Request": "true", "Accept": "text/html"},
    )
    assert "security token expired" in response.text.lower()
    assert response.headers.get("HX-Retarget") == "#global-alerts"


def test_ping_with_invalid_csrf_returns_htmx_error(client):
    client.get("/")
    response = client.post(
        "/api/v1/demo/ping",
        data={"csrf_token": "not-a-real-token"},
        headers={"HX-Request": "true", "Accept": "text/html"},
    )
    assert "security token expired" in response.text.lower()
    assert response.headers.get("HX-Retarget") == "#global-alerts"


def test_ping_without_csrf_returns_403_for_browser_posts(client):
    response = client.post("/api/v1/demo/ping", headers={"Accept": "text/html"})
    assert response.status_code == 403
    assert "Session expired" in response.text
