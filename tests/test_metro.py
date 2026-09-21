"""Metro hallway: Welcome, Settings, Wine hang, zip, Steam URI."""

from pathlib import Path

from app.services.addon_zip import zip_addon
from app.services.user_settings import UserSettings, load_settings, save_settings


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
    response = client.post(
        "/settings",
        data={
            "default_author": "tron",
            "default_description": "a model",
            "default_gender": "female",
            "sdk2013": r"C:\Steam\sdk",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    settings = load_settings()
    assert settings.default_author == "tron"
    assert settings.default_description == "a model"
    assert settings.default_gender == "female"
    assert settings.sdk2013 == r"C:\Steam\sdk"
    assert "require_wine" not in page.text
    assert "This machine needs a Wine prefix" not in page.text
    assert 'name="offer_hlmv"' not in page.text
    assert 'name="offer_crowbar"' not in page.text
    assert "Install catalog" in page.text
    assert "catalog.json" in page.text
    assert "Clear all" in page.text
    assert 'formaction="/settings/clear-paths"' in page.text
    assert "data" in page.text


def test_settings_clear_all_forgets_tool_directories(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    save_settings(
        UserSettings(
            blender="/tools/blender",
            steamcmd="/tools/steamcmd",
            sdk2013=r"C:\Steam\sdk",
            zip_dir="/zips",
            default_author="tron",
            wine_prefix="/wine",
        )
    )
    response = client.post("/settings/clear-paths", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/settings"
    settings = load_settings()
    assert settings.blender == ""
    assert settings.steamcmd == ""
    assert settings.sdk2013 == ""
    assert settings.zip_dir == ""
    assert settings.default_author == "tron"
    assert settings.wine_prefix == "/wine"


def test_wine_hang_blocks_setup_continue(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: False)
    response = client.post("/setup/select", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/wine")


def test_wine_hang_blocks_convert_past_intro(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: False)
    intro = client.get("/convert")
    assert "Welcome to Convert" in intro.text
    hung = client.get("/convert/avatar", follow_redirects=False)
    assert hung.status_code == 303
    assert hung.headers["location"].startswith("/wine")


def test_require_wine_without_prefix_hangs(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: False)
    save_settings(UserSettings(wine_prefix=""))
    hung = client.get("/convert/avatar", follow_redirects=False)
    assert hung.status_code == 303
    assert hung.headers["location"].startswith("/wine")
    select = client.post("/setup/select", follow_redirects=False)
    assert select.status_code == 303
    assert select.headers["location"].startswith("/wine")


def test_settings_host_links_to_wine_assistant(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.settings.router.wine_is_required", lambda: True)
    monkeypatch.setattr("app.api.v1.settings.router.chosen_candidate", lambda: None)
    page = client.get("/settings")
    assert "This machine needs a Wine prefix" not in page.text
    assert 'name="require_wine"' not in page.text
    assert "/wine?next=/settings" in page.text


def test_wine_pick_explains_unix_host_and_bottles(client, tmp_path, monkeypatch):
    from app.services.wine_host import WineCandidate

    wine = tmp_path / "wine64"
    wine.write_text("", encoding="utf-8")
    wine.chmod(0o755)
    first = tmp_path / "test"
    second = tmp_path / "openmpt"
    (first / "drive_c").mkdir(parents=True)
    (second / "drive_c").mkdir(parents=True)
    candidates = (
        WineCandidate(
            kind="whisky",
            name="test",
            version="7.7",
            prefix=first,
            wine=wine,
        ),
        WineCandidate(
            kind="whisky",
            name="openmpt",
            version="7.7",
            prefix=second,
            wine=wine,
        ),
    )
    monkeypatch.setattr("app.api.v1.wine.router.wine_is_required", lambda: True)
    monkeypatch.setattr("app.api.v1.wine.router.wine_ready", lambda: False)
    monkeypatch.setattr("app.api.v1.wine.router.list_candidates", lambda: candidates)
    monkeypatch.setattr("app.api.v1.wine.router.chosen_candidate", lambda: None)
    monkeypatch.setattr("app.api.v1.wine.router.host_id", lambda: "darwin-arm64")
    page = client.get("/wine?next=/setup")
    assert page.status_code == 200
    assert "Unix-like system (darwin-arm64)" in page.text
    assert "Source related tools will need to run under Wine" in page.text
    assert "Setup has detected the following Wine prefixes" in page.text
    assert f"Whisky 7.7, Bottle test - {first}" in page.text
    assert f"Whisky 7.7, Bottle openmpt - {second}" in page.text
    assert "You may also point Setup to the correct location" in page.text
    assert 'data-pick-folder' in page.text
    assert 'data-action="/wine/point"' in page.text


def test_wine_none_explains_unix_host_without_prefixes(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.wine.router.wine_is_required", lambda: True)
    monkeypatch.setattr("app.api.v1.wine.router.wine_ready", lambda: False)
    monkeypatch.setattr("app.api.v1.wine.router.list_candidates", lambda: ())
    monkeypatch.setattr("app.api.v1.wine.router.chosen_candidate", lambda: None)
    monkeypatch.setattr("app.api.v1.wine.router.host_id", lambda: "linux-x86_64")
    page = client.get("/wine?next=/setup")
    assert page.status_code == 200
    assert "Unix-like system (linux-x86_64)" in page.text
    assert "couldn't detect any Wine prefixes" in page.text
    assert "You may also point Setup to the correct location" in page.text
    assert 'data-pick-folder' in page.text
    assert "Setup has detected the following Wine prefixes" not in page.text


def test_pick_folder_returns_json_path(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.settings.router.native_pick_folder",
        lambda: "/tmp/wine-prefix",
    )
    response = client.post("/pick-folder")
    assert response.status_code == 200
    assert response.json() == {"path": "/tmp/wine-prefix"}


def test_point_wine_prefix_returns_to_convert(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    response = client.post(
        "/settings/point",
        data={
            "field": "wine_prefix",
            "path": str(tmp_path / "prefix"),
            "next": "/convert/avatar",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/convert/avatar"
    assert load_settings().wine_prefix == str(tmp_path / "prefix")


def test_wine_ready_accepts_detected_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    save_settings(UserSettings(wine_prefix=""))
    bottle = tmp_path / "WhiskyBottle"
    (bottle / "drive_c").mkdir(parents=True)
    wine = tmp_path / "wine64"
    wine.write_text("", encoding="utf-8")
    wine.chmod(0o755)
    monkeypatch.setattr("app.services.wine_host.wine_is_required", lambda: True)
    monkeypatch.setattr("app.services.wine_host.list_candidates", lambda: (
        __import__("app.services.wine_host", fromlist=["WineCandidate"]).WineCandidate(
            kind="whisky",
            name="test",
            version="7.7",
            prefix=bottle,
            wine=wine,
        ),
    ))
    from app.services.wine_host import wine_ready

    assert wine_ready() is True


def test_convert_intro_continue_is_get(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
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


def test_gmod_dedicated_is_its_own_setup_step(client, monkeypatch):
    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    page = client.get("/setup/gmod")
    assert page.status_code == 200
    assert "Garry's Mod dedicated" in page.text
    assert "steam://install/4020" in page.text
    assert "Open SteamCMD prompt" not in page.text
    assert "steam://install/243750" not in page.text


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


def test_convert_result_offers_hlmvplusplus(client, tmp_path, monkeypatch):
    import app.services.convert_job as jobs
    from app.services.convert_job import ConvertJob

    monkeypatch.setattr("app.services.hallway.wine_ready", lambda: True)
    monkeypatch.setattr("app.api.v1.convert.router.is_windows", lambda: True)
    zip_path = tmp_path / "hero.zip"
    zip_path.write_bytes(b"PK")
    mdl = tmp_path / "hero.mdl"
    mdl.write_bytes(b"mdl")
    job = ConvertJob(
        id="jobhlmv",
        state="succeeded",
        zip_path=zip_path,
        mdl=mdl,
        slug="hero",
    )
    jobs._jobs[job.id] = job
    monkeypatch.setattr(
        "app.api.v1.convert.router.find_hlmvplusplus",
        lambda *_a, **_k: tmp_path / "hlmvplusplus.exe",
    )
    page = client.get("/convert/result/jobhlmv")
    assert page.status_code == 200
    assert "Preview in HLMV++" in page.text
    assert 'action="/convert/open-hlmv"' in page.text
    assert "Open QC in Crowbar" not in page.text
    seen: list[Path] = []
    monkeypatch.setattr(
        "app.api.v1.convert.router.open_in_hlmv",
        lambda path: seen.append(path),
    )
    launched = client.post(
        "/convert/open-hlmv",
        data={"job_id": "jobhlmv"},
        follow_redirects=False,
    )
    assert launched.status_code == 303
    assert launched.headers["location"] == "/convert/result/jobhlmv"
    assert seen == [mdl]


def test_open_hlmv_shows_a_missing_file(client, tmp_path, monkeypatch):
    import app.services.convert_job as jobs
    from app.services.convert_job import ConvertJob

    monkeypatch.setattr("app.api.v1.convert.router.is_windows", lambda: True)
    mdl = tmp_path / "hero.mdl"
    mdl.write_bytes(b"mdl")
    job = ConvertJob(id="jobmiss", state="succeeded", zip_path=tmp_path / "hero.zip", mdl=mdl, slug="hero")
    jobs._jobs[job.id] = job

    def missing(_path: Path) -> Path:
        raise FileNotFoundError("Garry's Mod gameinfo.txt is missing (run Setup).")

    monkeypatch.setattr("app.api.v1.convert.router.open_in_hlmv", missing)
    page = client.post("/convert/open-hlmv", data={"job_id": "jobmiss"})
    assert page.status_code == 404
    assert "gameinfo.txt is missing" in page.text
    assert "Something went wrong" not in page.text


def test_convert_result_explains_missing_hlmv(client, tmp_path, monkeypatch):
    import app.services.convert_job as jobs
    from app.services.convert_job import ConvertJob

    zip_path = tmp_path / "hero.zip"
    zip_path.write_bytes(b"PK")
    job = ConvertJob(id="jobnohlmv", state="succeeded", zip_path=zip_path, slug="hero")
    jobs._jobs[job.id] = job
    monkeypatch.setattr("app.api.v1.convert.router.is_windows", lambda: True)
    monkeypatch.setattr(
        "app.api.v1.convert.router.find_hlmvplusplus",
        lambda *_a, **_k: None,
    )
    page = client.get("/convert/result/jobnohlmv")
    assert "Preview in HLMV++" not in page.text
    assert "HLMV++ is not installed" in page.text


def test_convert_result_disables_hlmv_on_unix(client, tmp_path, monkeypatch):
    import app.services.convert_job as jobs
    from app.services.convert_job import ConvertJob

    zip_path = tmp_path / "hero.zip"
    zip_path.write_bytes(b"PK")
    mdl = tmp_path / "hero.mdl"
    mdl.write_bytes(b"mdl")
    job = ConvertJob(
        id="jobunix",
        state="succeeded",
        zip_path=zip_path,
        mdl=mdl,
        slug="hero",
    )
    jobs._jobs[job.id] = job
    monkeypatch.setattr("app.api.v1.convert.router.is_windows", lambda: False)
    monkeypatch.setattr(
        "app.api.v1.convert.router.find_hlmvplusplus",
        lambda *_a, **_k: tmp_path / "hlmvplusplus.exe",
    )
    page = client.get("/convert/result/jobunix")
    assert page.status_code == 200
    assert '<button class="cmd" type="button" disabled>Preview in HLMV++</button>' in page.text
    assert 'action="/convert/open-hlmv"' not in page.text
    launched: list[Path] = []
    monkeypatch.setattr(
        "app.api.v1.convert.router.open_in_hlmv",
        lambda path: launched.append(path),
    )
    blocked = client.post("/convert/open-hlmv", data={"job_id": "jobunix"})
    assert blocked.status_code == 404
    assert "runs on Windows" in blocked.text
    assert launched == []
