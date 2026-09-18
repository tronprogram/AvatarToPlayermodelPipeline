"""Native vs Wine host for Windows Source tools."""

from pathlib import Path

from app.services.windows_tools import (
    WindowsToolHost,
    find_wine,
    find_wine_prefix,
    try_detect_windows_tool_host,
    wine_z_path,
)


def test_native_host_keeps_os_paths(tmp_path: Path):
    host = WindowsToolHost(kind="native")
    qc = tmp_path / "avatar.qc"
    qc.write_text("$modelname x\n", encoding="utf-8")
    exe = tmp_path / "studiomdl.exe"
    argv = host.argv(exe, "-game", tmp_path, "-nop4", qc)
    assert argv[0] == str(exe)
    assert argv[1] == "-game"
    assert argv[2] == str(tmp_path.resolve())
    assert not argv[2].startswith("Z:")
    assert argv[-1] == str(qc.resolve())
    assert host.env().get("WINEPREFIX") is None


def test_wine_host_prefixes_z_drive(tmp_path: Path):
    wine = tmp_path / "wine64"
    prefix = tmp_path / "pfx"
    host = WindowsToolHost(kind="wine", wine=wine, prefix=prefix)
    qc = tmp_path / "avatar.qc"
    qc.write_text("$modelname x\n", encoding="utf-8")
    exe = tmp_path / "studiomdl.exe"
    argv = host.argv(exe, "-nop4", qc)
    assert argv == [str(wine), str(exe), "-nop4", wine_z_path(qc)]
    assert host.tool_path(qc).startswith("Z:")
    assert "\\" in host.tool_path(qc)
    assert host.env()["WINEPREFIX"] == str(prefix)
    assert host.env()["WINEARCH"] == "win64"


def test_detect_host_is_native_on_windows(monkeypatch):
    monkeypatch.setattr("app.services.windows_tools.sys.platform", "win32")
    host = try_detect_windows_tool_host()
    assert host is not None
    assert host.kind == "native"
    assert host.wine is None


def test_find_wine_skips_whisky_on_linux(monkeypatch):
    monkeypatch.setattr("app.services.windows_tools.sys.platform", "linux")
    monkeypatch.setattr(
        "app.services.windows_tools.whisky_wine",
        lambda: Path("/Library/Whisky/wine64"),
    )
    monkeypatch.setattr(
        "app.services.windows_tools.path_wine",
        lambda: Path("/usr/bin/wine"),
    )
    assert find_wine() == Path("/usr/bin/wine")


def test_find_wine_prefers_whisky_on_darwin(monkeypatch):
    monkeypatch.setattr("app.services.windows_tools.sys.platform", "darwin")
    monkeypatch.setattr(
        "app.services.windows_tools.whisky_wine",
        lambda: Path("/Library/Whisky/wine64"),
    )
    monkeypatch.setattr(
        "app.services.windows_tools.path_wine",
        lambda: Path("/opt/homebrew/bin/wine64"),
    )
    assert find_wine() == Path("/Library/Whisky/wine64")


def test_find_wine_prefix_skips_whisky_on_linux(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("app.services.windows_tools.sys.platform", "linux")
    monkeypatch.delenv("WINEPREFIX", raising=False)
    bottle = tmp_path / "whisky"
    (bottle / "drive_c").mkdir(parents=True)
    home_wine = tmp_path / ".wine"
    (home_wine / "drive_c").mkdir(parents=True)
    monkeypatch.setattr("app.services.windows_tools.whisky_bottle", lambda: bottle)
    monkeypatch.setattr("app.services.windows_tools.data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert find_wine_prefix() == home_wine


def test_find_wine_prefix_uses_whisky_on_darwin(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("app.services.windows_tools.sys.platform", "darwin")
    monkeypatch.delenv("WINEPREFIX", raising=False)
    bottle = tmp_path / "bottle"
    (bottle / "drive_c").mkdir(parents=True)
    monkeypatch.setattr("app.services.windows_tools.whisky_bottle", lambda: bottle)
    monkeypatch.setattr("app.services.windows_tools.data_dir", lambda: tmp_path / "data")
    assert find_wine_prefix() == bottle


def test_find_wine_prefix_honors_wineprefix(monkeypatch, tmp_path: Path):
    prefix = tmp_path / "custom"
    (prefix / "drive_c").mkdir(parents=True)
    monkeypatch.setenv("WINEPREFIX", str(prefix))
    monkeypatch.setattr("app.services.windows_tools.sys.platform", "linux")
    assert find_wine_prefix() == prefix
