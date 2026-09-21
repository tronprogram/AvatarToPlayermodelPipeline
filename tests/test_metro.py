"""Metro hallway: Welcome, Settings, Wine hang, zip, Steam URI."""

from pathlib import Path

from app.services.addon_zip import zip_addon
from app.services.user_settings import UserSettings, load_settings, save_settings
from tests.conftest import extract_csrf


def test_home_is_welcome(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome!" in response.text
    assert "Begin configuration" in response.text
    assert "360sona" in response.text
    assert 'hx-post="/api/v1/demo/ping"' not in response.text


def test_settings_persists(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    page = client.get("/settings")
    token = extract_csrf(page.text)
    response = client.post(
        "/settings",
        data={
            "csrf_token": token,
            "default_author": "tron",
            "default_description": "a model",
            "default_gender": "female",
            "sdk2013": r"C:\Steam\sdk",
            "require_wine": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    settings = load_settings()
    assert settings.default_author == "tron"
    assert settings.default_description == "a model"
    assert settings.default_gender == "female"
    assert settings.sdk2013 == r"C:\Steam\sdk"
    assert settings.require_wine is True


def test_wine_hang_blocks_setup_continue(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: False)
    page = client.get("/setup")
    token = extract_csrf(page.text)
    response = client.post(
        "/setup/select",
        data={"csrf_token": token},
    )
    assert response.status_code == 200
    assert "valid Wine prefix" in response.text
    assert "Settings" in response.text
    assert "cannot continue" in response.text


def test_wine_hang_blocks_convert_past_intro(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: False)
    intro = client.get("/convert")
    assert "Welcome to Convert" in intro.text
    hung = client.get("/convert/avatar")
    assert "valid Wine prefix" in hung.text
    assert "Convert cannot continue" in hung.text or "cannot continue" in hung.text


def test_require_wine_without_prefix_hangs(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    save_settings(UserSettings(require_wine=True, wine_prefix=""))
    hung = client.get("/convert/avatar")
    assert "valid Wine prefix" in hung.text
    page = client.get("/setup")
    token = extract_csrf(page.text)
    select = client.post("/setup/select", data={"csrf_token": token})
    assert "valid Wine prefix" in select.text


def test_convert_intro_continue_is_get(client):
    intro = client.get("/convert")
    assert 'href="/convert/avatar"' in intro.text
    assert 'action="/convert/avatar"' not in intro.text
    avatar = client.get("/convert/avatar")
    assert "Drop a model here" in avatar.text
    assert "Please provide a 360sona before continuing." not in avatar.text


def test_setup_canceled(client):
    response = client.get("/setup/canceled")
    assert response.status_code == 200
    assert "Setup has been canceled" in response.text or "has been canceled" in response.text


def test_steam_uri_on_setup_steam(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    monkeypatch.setattr("app.api.v1.setup.router.steamcmd_is_ready", lambda: False)
    response = client.get("/setup/steam")
    assert response.status_code == 200
    assert "could not find" in response.text.lower()
    assert "usual directories" in response.text.lower()
    assert "steam://install/243750" in response.text
    assert "Open SteamCMD prompt" in response.text
    assert "Set manually" in response.text
    assert 'href="/setup/missing"' in response.text
    assert 'action="/setup/steam/refresh"' in response.text
    assert 'action="/setup/scan"' not in response.text
    assert "Install GMod dedicated" not in response.text
    assert "steam://install/4020" not in response.text
    assert 'action="/setup/after-steam"' in response.text


def test_steam_hides_continue_when_steamcmd_ready(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    monkeypatch.setattr("app.api.v1.setup.router.steamcmd_is_ready", lambda: True)
    response = client.get("/setup/steam")
    assert response.status_code == 200
    assert 'action="/setup/after-steam"' not in response.text
    assert "SteamCMD is on disk" in response.text
    assert 'href="/setup/missing"' in response.text


def test_steam_refresh_stays_when_sdk_missing(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    monkeypatch.setattr("app.api.v1.setup.router.sdk2013_needs_steam", lambda *_a, **_k: True)
    page = client.get("/setup/steam")
    token = extract_csrf(page.text)
    response = client.post(
        "/setup/steam/refresh",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/setup/steam?checked=1"


def test_steam_refresh_advances_when_sdk_found(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    monkeypatch.setattr("app.api.v1.setup.router.sdk2013_needs_steam", lambda *_a, **_k: False)
    monkeypatch.setattr("app.api.v1.setup.router.selected_ready", lambda *_a, **_k: False)
    monkeypatch.setattr("app.api.v1.setup.router.gmod_tools_needs_step", lambda *_a, **_k: True)
    page = client.get("/setup/steam")
    token = extract_csrf(page.text)
    response = client.post(
        "/setup/steam/refresh",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/setup/gmod"


def test_gmod_dedicated_is_its_own_setup_step(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    page = client.get("/setup/gmod")
    assert page.status_code == 200
    assert "Garry's Mod dedicated" in page.text
    assert "steam://install/4020" in page.text
    assert "Open SteamCMD prompt" not in page.text
    assert "steam://install/243750" not in page.text

    steam = client.get("/setup/steam")
    token = extract_csrf(steam.text)
    monkeypatch.setattr("app.api.v1.setup.router.selected_ready", lambda *_a, **_k: False)
    monkeypatch.setattr("app.api.v1.setup.router.gmod_tools_needs_step", lambda *_a, **_k: True)
    nxt = client.post(
        "/setup/after-steam",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert nxt.status_code == 303
    assert nxt.headers["location"] == "/setup/gmod"


def test_steamcmd_prompt_opens_console(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    called: list[bool] = []

    def fake_open():
        called.append(True)

    monkeypatch.setattr(
        "app.api.v1.setup.router.open_sdk2013_steamcmd_console", fake_open
    )
    page = client.get("/setup/steam")
    token = extract_csrf(page.text)
    response = client.post(
        "/setup/steamcmd",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/setup/steam?launched=1"
    assert called == [True]


def test_settings_without_csrf_is_forbidden(client):
    response = client.post(
        "/settings",
        data={"default_author": "x"},
        headers={"HX-Request": "true", "Accept": "text/html"},
    )
    assert "security token expired" in response.text.lower()
    assert response.headers.get("HX-Retarget") == "#global-alerts"


def test_zip_addon_nests_slug(tmp_path: Path):
    root = tmp_path / "my_avatar"
    (root / "lua").mkdir(parents=True)
    (root / "lua" / "autorun.lua").write_text("-- addon\n", encoding="utf-8")
    dest = tmp_path / "out" / "my_avatar.zip"
    zip_addon(root, dest)
    import zipfile

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert "my_avatar/lua/autorun.lua" in names
