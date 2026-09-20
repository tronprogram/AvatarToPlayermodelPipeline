"""Run SteamCMD and pull Garry's Mod dedicated server (app 4020)."""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypedDict

from app.core.paths import data_dir, logs_dir
from app.core.process import SpawnedProcess, command_env, spawn_command
from app.services.deps.catalog import DIRECTORY_INFO, GMOD_APP_ID, SDK2013_APP_ID
from app.services.deps.detect import gmod_app_installed, gmod_named_tools_present

_log = logging.getLogger(__name__)

STEAMCMD_RESTART_EXITCODE = 42
_STEAMCMD_PERCENT = re.compile(r"\[\s*(\d+)%\]")
_STEAMCMD_PROGRESS = re.compile(r"progress:\s*([\d.]+)", re.I)
_STEAMCMD_BOOTSTRAP = re.compile(
    r"update complete, launching|restarting steamcmd by request", re.I
)

DownloadState = Literal["idle", "running", "succeeded", "failed"]
LineCallback = Callable[[str], None]


class DownloadStatus(TypedDict):
    state: DownloadState
    percent: int | None
    message: str
    log_tail: list[str]


def find_steamcmd(root: Path) -> Path | None:
    """Locate the SteamCMD launcher for this OS."""
    if os.name == "nt":
        names = ("steamcmd.exe", "steamcmd")
    else:
        names = (
            "steamcmd.sh",
            "linux32/steamcmd",
            "linuxarm64/steamcmd",
            "steamcmd",
        )
    for name in names:
        path = root / name
        if path.is_file():
            return path
    return None


def steamcmd_bin(data: Path) -> Path:
    path = find_steamcmd(data / DIRECTORY_INFO["steamcmd"][1])
    if path is None:
        raise FileNotFoundError("steamcmd is not extracted")
    return path


def parse_steamcmd_percent(line: str) -> int | None:
    match = _STEAMCMD_PROGRESS.search(line)
    if match:
        return min(100, max(0, int(float(match.group(1)))))
    match = _STEAMCMD_PERCENT.search(line)
    if match:
        return min(100, max(0, int(match.group(1))))
    return None


def _is_bootstrap(output: str, returncode: int) -> bool:
    if returncode == STEAMCMD_RESTART_EXITCODE:
        return True
    return bool(_STEAMCMD_BOOTSTRAP.search(output))


def _steamcmd_log_files(steamcmd_root: Path, home: Path) -> list[Path]:
    names = ("console_log.txt", "bootstrap_log.txt", "content_log.txt", "stderr.txt")
    log_dirs = [
        steamcmd_root / "logs",
        home / "Library" / "Application Support" / "Steam" / "logs",
        home / "AppData" / "Local" / "Steam" / "logs",
        home / ".steam" / "steam" / "logs",
        home / ".steam" / "logs",
        home / "Steam" / "logs",
    ]
    paths: list[Path] = []
    for log_dir in log_dirs:
        for name in names:
            path = log_dir / name
            if path not in paths:
                paths.append(path)
    return paths


def _steamcmd_env(steamcmd_root: Path, home: Path) -> dict[str, str]:
    extra: dict[str, str] = {"HOME": str(home)}
    if sys.platform == "darwin":
        extra["DYLD_LIBRARY_PATH"] = str(steamcmd_root)
        extra["DYLD_FRAMEWORK_PATH"] = str(steamcmd_root)
    elif sys.platform.startswith("linux"):
        lib_dirs = [
            steamcmd_root / "linux32",
            steamcmd_root / "linuxarm64",
            steamcmd_root,
        ]
        libs = [str(path) for path in lib_dirs if path.is_dir()]
        current = os.environ.get("LD_LIBRARY_PATH", "")
        extra["LD_LIBRARY_PATH"] = ":".join([*libs, current] if current else libs)
    return command_env(extra)


def _log_file_offsets(paths: list[Path]) -> dict[Path, int]:
    return {path: path.stat().st_size if path.exists() else 0 for path in paths}


def _drain_log_files(
    offsets: dict[Path, int], paths: list[Path], on_line: LineCallback
) -> None:
    for path in paths:
        if not path.exists():
            continue
        offset = offsets.get(path, 0)
        size = path.stat().st_size
        if size < offset:
            offset = 0
        if size == offset:
            continue
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            text = handle.read()
            offsets[path] = handle.tell()
        for raw in text.replace("\r", "\n").split("\n"):
            line = raw.strip()
            if line:
                on_line(line)


class _LineSplitter:
    def __init__(self) -> None:
        self._buf = ""

    def feed(self, chunk: str, on_line: LineCallback) -> None:
        self._buf += chunk.replace("\r", "\n")
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                on_line(line)

    def flush(self, on_line: LineCallback) -> None:
        if self._buf.strip():
            on_line(self._buf)
        self._buf = ""


def _pump_steamcmd(
    spawned: SpawnedProcess,
    log_paths: list[Path],
    offsets: dict[Path, int],
    on_line: LineCallback,
) -> int:
    proc = spawned.proc
    master = spawned.pty_master
    splitter = _LineSplitter()
    try:
        if os.name == "nt":
            import time

            while proc.poll() is None:
                _drain_log_files(offsets, log_paths, on_line)
                time.sleep(0.4)
            if proc.stdout is not None:
                rest = proc.stdout.read()
                if rest:
                    splitter.feed(rest, on_line)
            splitter.flush(on_line)
            _drain_log_files(offsets, log_paths, on_line)
            return proc.wait()

        import select

        while True:
            _drain_log_files(offsets, log_paths, on_line)
            watch: list = []
            if master is not None:
                watch.append(master)
            if proc.stdout is not None:
                watch.append(proc.stdout)
            ready: list = []
            if watch:
                ready, _, _ = select.select(watch, [], [], 0.4)
            if master in ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    chunk = b""
                if chunk:
                    splitter.feed(chunk.decode("utf-8", errors="replace"), on_line)
            if proc.stdout in ready:
                line = proc.stdout.readline()
                if line:
                    on_line(line)
            if proc.poll() is None:
                continue
            _drain_log_files(offsets, log_paths, on_line)
            if master is not None:
                try:
                    while True:
                        chunk = os.read(master, 4096)
                        if not chunk:
                            break
                        splitter.feed(chunk.decode("utf-8", errors="replace"), on_line)
                except OSError:
                    pass
            splitter.flush(on_line)
            return proc.wait()
    finally:
        if master is not None:
            os.close(master)


def install_gmod_app(data: Path, *, on_line: LineCallback) -> None:
    """Pull Windows GMod (app 4020). First run often only self-updates; retry that."""
    steamcmd = steamcmd_bin(data)
    steamcmd_root = steamcmd.parent
    target = data / DIRECTORY_INFO["gmod_tools"][1]
    target.mkdir(parents=True, exist_ok=True)
    home = steamcmd_root / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = _steamcmd_env(steamcmd_root, home)
    cmd = [
        str(steamcmd),
        "+@sSteamCmdForcePlatformType",
        "windows",
        "+@NoPromptForPassword",
        "1",
        "+force_install_dir",
        str(target.resolve()),
        "+login",
        "anonymous",
        "+app_update",
        GMOD_APP_ID,
        "+quit",
    ]
    log_paths = _steamcmd_log_files(steamcmd_root, home)

    if gmod_app_installed(target):
        on_line("Garry's Mod dedicated server already installed; skipping SteamCMD")
        return

    last_line = "steamcmd failed"
    for attempt in range(1, 4):
        collected: list[str] = []

        def capture(line: str, bucket: list[str] = collected) -> None:
            bucket.append(line)
            on_line(line)

        capture(f"Launching SteamCMD (attempt {attempt}): {' '.join(cmd)}")
        spawned = spawn_command(cmd, cwd=steamcmd_root, env=env, pty=True)
        offsets = _log_file_offsets(log_paths)
        returncode = _pump_steamcmd(spawned, log_paths, offsets, capture)
        blob = "\n".join(collected)
        if collected:
            last_line = collected[-1].strip()
        if gmod_app_installed(target) or gmod_named_tools_present(target):
            return
        if _is_bootstrap(blob, returncode) and attempt < 3:
            capture(f"SteamCMD updated itself (attempt {attempt}), retrying…")
            continue
        if returncode == 0:
            raise RuntimeError(
                "SteamCMD finished but Garry's Mod dedicated server was not installed"
            )
        raise RuntimeError(last_line or f"steamcmd exited {returncode}")
    raise RuntimeError(last_line)


class GmodDownloadJob:
    """Single in-process SteamCMD job. Desktop app is one user."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.state: DownloadState = "idle"
        self.percent: int | None = None
        self.message = ""
        self.log_tail: list[str] = []
        self._thread: threading.Thread | None = None

    def snapshot(self) -> DownloadStatus:
        with self._lock:
            return {
                "state": self.state,
                "percent": self.percent,
                "message": self.message,
                "log_tail": list(self.log_tail),
            }

    def start(self, data: Path) -> None:
        with self._lock:
            if self.state == "running" and self._thread is not None and self._thread.is_alive():
                return
            self.state = "running"
            self.percent = 0
            self.message = "Starting SteamCMD…"
            self.log_tail = []
            self._thread = threading.Thread(
                target=self._run, args=(data,), daemon=True
            )
            self._thread.start()

    def _note(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        _log.info("steamcmd: %s", line)
        try:
            with (logs_dir() / "steamcmd.log").open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass
        percent = parse_steamcmd_percent(line)
        with self._lock:
            self.log_tail.append(line)
            del self.log_tail[:-20]
            self.message = line
            if percent is not None:
                self.percent = percent

    def _run(self, data: Path) -> None:
        try:
            install_gmod_app(data, on_line=self._note)
        except Exception as exc:
            _log.exception("GMod tools download failed")
            with self._lock:
                self.state = "failed"
                self.message = str(exc)
            return
        with self._lock:
            self.state = "succeeded"
            self.percent = 100
            self.message = "GMod tools ready"


gmod_download = GmodDownloadJob()


def resolve_steamcmd(data: Path | None = None) -> Path:
    """SteamCMD from Settings, then the data tree."""
    from app.services.user_settings import load_settings, path_or_none

    root = data or data_dir()
    extra = path_or_none(load_settings().steamcmd)
    if extra is not None:
        if extra.is_file():
            return extra
        found = find_steamcmd(extra)
        if found is not None:
            return found
    return steamcmd_bin(root)


def sdk2013_install_dir(data: Path | None = None) -> Path:
    """Where SteamCMD should drop app 243750."""
    from app.services.user_settings import load_settings, path_or_none

    root = data or data_dir()
    override = path_or_none(load_settings().sdk2013)
    if override is not None:
        return override
    return root / "sdk2013mp"


def sdk2013_console_script(steamcmd: Path, dest: Path) -> str:
    """Wrapper that asks for a username, then lets SteamCMD prompt in this console."""
    dest.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        return (
            "@echo off\r\n"
            "echo Source SDK Base 2013 Multiplayer (243750) is not anonymous.\r\n"
            "echo Log in here. Password and Steam Guard stay in this window.\r\n"
            "echo.\r\n"
            "set /p STEAMUSER=Steam username: \r\n"
            f"\"{steamcmd}\" "
            "+@sSteamCmdForcePlatformType windows "
            f"+force_install_dir \"{dest.resolve()}\" "
            "+login %STEAMUSER% "
            f"+app_update {SDK2013_APP_ID} "
            "+quit\r\n"
            "echo.\r\n"
            "echo SteamCMD finished. Close this window, then Refresh Setup.\r\n"
            "pause\r\n"
        )
    quoted = [
        str(steamcmd),
        "+@sSteamCmdForcePlatformType",
        "windows",
        "+force_install_dir",
        str(dest.resolve()),
        "+login",
        "$STEAMUSER",
        "+app_update",
        SDK2013_APP_ID,
        "+quit",
    ]
    # $STEAMUSER must expand in the shell, not be quoted as a literal.
    body = " ".join(
        part if part == "$STEAMUSER" else shlex.quote(part) for part in quoted
    )
    return (
        "#!/bin/sh\n"
        "echo 'Source SDK Base 2013 Multiplayer (243750) is not anonymous.'\n"
        "echo 'Log in here. Password and Steam Guard stay in this window.'\n"
        "printf 'Steam username: '\n"
        "read STEAMUSER\n"
        f"{body}\n"
        "echo\n"
        "echo 'SteamCMD finished. Close this window, then Refresh Setup.'\n"
        "echo 'Press Enter to close.'\n"
        "read _\n"
    )


def _unix_terminal_command(script: Path) -> list[str]:
    shell = f"exec /bin/sh {shlex.quote(str(script))}"
    for binary, args in (
        ("x-terminal-emulator", ["-e", "sh", "-c", shell]),
        ("gnome-terminal", ["--", "sh", "-c", shell]),
        ("konsole", ["-e", "sh", "-c", shell]),
        ("xfce4-terminal", ["-e", f"sh -c {shlex.quote(shell)}"]),
        ("xterm", ["-e", "sh", "-c", shell]),
    ):
        found = shutil.which(binary)
        if found:
            return [found, *args]
    raise FileNotFoundError(
        "No system terminal was found to open SteamCMD. "
        "Install xterm or gnome-terminal, or use steam://install/243750."
    )


def open_sdk2013_steamcmd_console(data: Path | None = None) -> Path:
    """Open a real OS console so the user can log in and pull app 243750."""
    root = data or data_dir()
    steamcmd = resolve_steamcmd(root)
    dest = sdk2013_install_dir(root)
    steamcmd_root = steamcmd.parent
    home = steamcmd_root / "home"
    home.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    script = steamcmd_root / ("sdk2013_login.bat" if os.name == "nt" else "sdk2013_login.sh")
    script.write_text(sdk2013_console_script(steamcmd, dest), encoding="utf-8")
    if os.name != "nt":
        script.chmod(0o755)
    env = _steamcmd_env(steamcmd_root, home)
    _log.info("Opening SteamCMD console for app %s -> %s", SDK2013_APP_ID, dest)
    if os.name == "nt":
        subprocess.Popen(
            ["cmd.exe", "/k", str(script)],
            cwd=str(steamcmd_root),
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        return script
    if sys.platform == "darwin":
        subprocess.Popen(
            ["open", "-a", "Terminal", str(script)],
            cwd=str(steamcmd_root),
            env=env,
        )
        return script
    subprocess.Popen(
        _unix_terminal_command(script),
        cwd=str(steamcmd_root),
        env=env,
        start_new_session=True,
    )
    return script
