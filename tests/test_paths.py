"""Path helpers for a PyInstaller one-file layout."""

from app.core.paths import data_dir, logs_dir, resource_root, writable_root


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
