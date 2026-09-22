"""SteamCMD can finish the install and still refuse to quit on Windows."""

from __future__ import annotations

import subprocess

from app.core.process import SpawnedProcess
from app.services.deps.catalog import load_catalog
from app.services.deps.detect import gmod_app_installed
from app.services.deps.steamcmd import _pump_steamcmd, _stop_process
from app.services.setup_install import watch_steamcmd_download


def _manifest(root, flags: int) -> None:
    app_id = load_catalog().gmod_app_id
    acf = root / "steamapps" / f"appmanifest_{app_id}.acf"
    acf.parent.mkdir(parents=True, exist_ok=True)
    acf.write_text(f'"AppState"\n{{\n\t"StateFlags"\t\t"{flags}"\n}}\n', encoding="utf-8")


class _FakeProc:
    def __init__(self) -> None:
        self.stdout = None
        self._code: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self._code

    def terminate(self) -> None:
        self.terminated = True
        self._code = 0

    def kill(self) -> None:
        self.killed = True
        self._code = 1

    def wait(self, timeout=None) -> int:
        assert self._code is not None
        return self._code


def test_fully_installed_encrypted_counts_as_done(tmp_path):
    _manifest(tmp_path, 0xC)
    assert gmod_app_installed(tmp_path)


def test_update_running_is_not_done(tmp_path):
    _manifest(tmp_path, 4 | 256)
    assert not gmod_app_installed(tmp_path)


def test_watch_does_not_repeat_the_same_line(tmp_path):
    notes: list[str] = []
    snaps = [
        {"download": {"state": "running", "message": "stats: same"}},
        {"download": {"state": "running", "message": "stats: same"}},
        {"download": {"state": "succeeded", "message": "GMod tools ready"}},
    ]

    def poll() -> dict:
        return snaps.pop(0)

    watch_steamcmd_download(poll, tmp_path, note=notes.append, sleep=lambda _: None)
    assert notes == ["stats: same", "GMod tools ready"]


def test_watch_does_not_treat_loose_exes_as_a_finished_install(tmp_path):
    (tmp_path / "gmad.exe").write_bytes(b"MZ")
    (tmp_path / "studiomdl.exe").write_bytes(b"MZ")
    notes: list[str] = []
    snaps = [
        {"download": {"state": "running", "message": "downloading"}},
        {"download": {"state": "succeeded", "message": "GMod tools ready"}},
    ]

    def poll() -> dict:
        return snaps.pop(0)

    watch_steamcmd_download(poll, tmp_path, note=notes.append, sleep=lambda _: None)
    assert notes == ["downloading", "GMod tools ready"]


def test_watch_stops_when_4020_is_on_disk_even_if_job_still_running(tmp_path):
    _manifest(tmp_path, 4)
    notes: list[str] = []
    watch_steamcmd_download(
        lambda: {"download": {"state": "running", "message": "stats: leftover"}},
        tmp_path,
        note=notes.append,
        sleep=lambda _: None,
    )
    assert notes == ["stats: leftover", "steamcmd   install is on disk"]


def test_pump_stops_when_install_is_ready():
    proc = _FakeProc()
    lines: list[str] = []
    checks = {"n": 0}

    def ready() -> bool:
        checks["n"] += 1
        return checks["n"] >= 2

    code = _pump_steamcmd(
        SpawnedProcess(proc=proc),
        log_paths=[],
        offsets={},
        on_line=lines.append,
        ready=ready,
    )
    assert code == 0
    assert proc.terminated
    assert "not waiting for it to quit" in lines[-1]


def test_stop_process_kills_a_process_that_ignores_terminate():
    proc = _FakeProc()

    def terminate() -> None:
        proc.terminated = True

    def wait(timeout=None) -> int:
        if timeout is not None and proc._code is None:
            raise subprocess.TimeoutExpired(cmd="steamcmd", timeout=timeout)
        assert proc._code is not None
        return proc._code

    proc.terminate = terminate  # type: ignore[method-assign]
    proc.wait = wait  # type: ignore[method-assign]
    assert _stop_process(proc) == 1
    assert proc.terminated
    assert proc.killed
