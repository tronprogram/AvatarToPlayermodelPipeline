"""Home page and health checks."""


def test_healthz_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_home_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "FastAPI on loopback" in response.text
    assert 'hx-post="/api/v1/demo/ping"' in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
