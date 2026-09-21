"""Home page."""


def test_folder_picker_script_uses_server_dialog(client):
    script = client.get("/static/js/metro.js")
    assert script.status_code == 200
    assert "/pick-folder" in script.text
    assert "pick_folder" in script.text
    assert "/pick-file" in script.text
    assert "pick_file" in script.text


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


def test_favicon_is_webp(client):
    page = client.get("/")
    assert 'type="image/webp"' in page.text
    assert "img/favicon.webp" in page.text
    icon = client.get("/static/img/favicon.webp")
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/webp")


def test_home_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome!" in response.text
    assert "Begin configuration" in response.text
