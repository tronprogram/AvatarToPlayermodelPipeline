"""Native folder dialog used by the folder-plus buttons."""

from types import SimpleNamespace

from app.services.folder_pick import pick_folder


def test_darwin_choose_folder(monkeypatch):
    monkeypatch.setattr("app.services.folder_pick.sys.platform", "darwin")

    def fake_run(cmd, **_kwargs):
        assert cmd[0] == "osascript"
        assert "choose folder" in cmd[-1]
        return SimpleNamespace(stdout="/Users/me/prefix/\n", returncode=0)

    monkeypatch.setattr("app.services.folder_pick.subprocess.run", fake_run)
    assert pick_folder() == "/Users/me/prefix/"


def test_darwin_cancel_is_empty(monkeypatch):
    monkeypatch.setattr("app.services.folder_pick.sys.platform", "darwin")
    monkeypatch.setattr(
        "app.services.folder_pick.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="", returncode=0),
    )
    assert pick_folder() == ""


def test_linux_uses_zenity(monkeypatch):
    monkeypatch.setattr("app.services.folder_pick.sys.platform", "linux")
    monkeypatch.setattr("app.services.folder_pick.shutil.which", lambda name: name == "zenity")

    def fake_run(cmd, **_kwargs):
        assert cmd[0] == "zenity"
        return SimpleNamespace(stdout="/home/me/.wine\n", returncode=0)

    monkeypatch.setattr("app.services.folder_pick.subprocess.run", fake_run)
    assert pick_folder() == "/home/me/.wine"
