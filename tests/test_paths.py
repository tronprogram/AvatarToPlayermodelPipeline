"""Path helpers for a PyInstaller one-file layout."""

from app.core.paths import (
    _frozen_writable_root,
    data_dir,
    logs_dir,
    resource_root,
    writable_root,
)


def test_dev_roots_are_the_repo():
    root = resource_root()
    assert root == writable_root()
    assert (root / "run_desktop.py").is_file()
    assert (root / "templates" / "html").is_dir()
    assert (root / "templates" / "valve").is_dir()
    assert (root / "static").is_dir()


def test_data_and_logs_live_under_writable_root():
    root = writable_root()
    assert data_dir() == root / "data"
    assert logs_dir() == root / "logs"
    assert data_dir().is_dir()
    assert logs_dir().is_dir()


def test_frozen_macos_app_writable_root_is_next_to_the_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.paths.sys.platform", "darwin")
    macos = tmp_path / "AvatarToPlayermodel.app" / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    exe = macos / "AvatarToPlayermodel"
    exe.write_text("", encoding="utf-8")
    assert _frozen_writable_root(exe) == tmp_path


def test_frozen_macos_translocated_app_uses_application_support(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.paths.sys.platform", "darwin")
    monkeypatch.setattr("app.core.paths.Path.home", lambda: tmp_path / "home")
    macos = (
        tmp_path
        / "var"
        / "folders"
        / "xx"
        / "T"
        / "AppTranslocation"
        / "ABC"
        / "d"
        / "AvatarToPlayermodel.app"
        / "Contents"
        / "MacOS"
    )
    macos.mkdir(parents=True)
    exe = macos / "AvatarToPlayermodel"
    exe.write_text("", encoding="utf-8")
    assert _frozen_writable_root(exe) == (
        tmp_path / "home" / "Library" / "Application Support" / "AvatarToPlayermodel"
    )


def test_frozen_plain_binary_writable_root_is_the_parent(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.paths.sys.platform", "win32")
    exe = tmp_path / "AvatarToPlayermodel.exe"
    exe.write_text("", encoding="utf-8")
    assert _frozen_writable_root(exe) == tmp_path
