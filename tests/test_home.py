"""Home page and health checks."""


def test_healthz_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_javascript_is_executable_mime(client, monkeypatch):
    monkeypatch.setattr(
        "starlette.responses.guess_type", lambda path: ("text/plain", None)
    )
    response = client.get("/static/js/metro.js")
    assert response.status_code == 200
    ctype = response.headers["content-type"]
    assert "javascript" in ctype
    assert "text/plain" not in ctype
    home = client.get("/")
    assert "htmx.min.js" in home.text
    assert "?v=" in home.text


def test_home_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome!" in response.text
    assert "Begin configuration" in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
