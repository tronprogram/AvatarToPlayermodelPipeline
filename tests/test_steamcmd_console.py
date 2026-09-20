"""SteamCMD console wrapper for interactive 243750 login."""

from pathlib import Path

from app.services.deps.steamcmd import sdk2013_console_script


def test_windows_script_asks_for_login_not_anonymous(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.deps.steamcmd.os.name", "nt")
    steamcmd = tmp_path / "steamcmd.exe"
    dest = tmp_path / "sdk2013mp"
    text = sdk2013_console_script(steamcmd, dest)
    assert "243750" in text
    assert "+login %STEAMUSER%" in text
    assert "+login anonymous" not in text.lower()
    assert dest.is_dir()


def test_unix_script_asks_for_login_not_anonymous(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.deps.steamcmd.os.name", "posix")
    steamcmd = tmp_path / "steamcmd.sh"
    dest = tmp_path / "sdk2013mp"
    text = sdk2013_console_script(steamcmd, dest)
    assert "243750" in text
    assert "+login" in text
    assert "$STEAMUSER" in text
    assert "+login anonymous" not in text.lower()
