"""Background Setup install: HTTP archives, then anonymous SteamCMD for 4020."""

from __future__ import annotations

import asyncio
import platform
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.core.paths import data_dir
from app.services.deps.detect import gmod_app_installed, gmod_tools_present, gmod_tools_root
from app.services.deps_wizard import DepsWizardService

JobState = Literal["idle", "running", "succeeded", "failed"]


@dataclass
class SetupInstallJob:
    state: JobState = "idle"
    log: list[str] = field(default_factory=list)
    error: str = ""


_job = SetupInstallJob()
_lock = threading.Lock()


def snapshot() -> SetupInstallJob:
    with _lock:
        return SetupInstallJob(state=_job.state, log=list(_job.log), error=_job.error)


def _note(line: str) -> None:
    with _lock:
        _job.log.append(line)


def watch_steamcmd_download(
    poll: Callable[[], dict],
    root: Path,
    *,
    note: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Follow SteamCMD until the job ends or app 4020 is already on disk.

    Windows SteamCMD often stays alive after a finished install (OneDrive, a
    running Steam client, an unread stdout pipe). The last log line must not
    be appended every second while that happens.
    """
    last = ""
    while True:
        status = poll()
        snap = status["download"]
        message = str(snap.get("message") or "")
        if message and message != last:
            note(message)
            last = message
        if snap["state"] == "failed":
            raise RuntimeError(message or "SteamCMD failed")
        if snap["state"] in ("succeeded", "idle"):
            return
        if gmod_app_installed(root):
            if last != "steamcmd   install is on disk":
                note("steamcmd   install is on disk")
            return
        sleep(1)


def start(selected: set[str]) -> SetupInstallJob:
    with _lock:
        if _job.state == "running":
            return snapshot()
        _job.state = "running"
        _job.log = []
        _job.error = ""
    thread = threading.Thread(target=_run, args=(set(selected),), daemon=True)
    thread.start()
    return snapshot()


def _run(selected: set[str]) -> None:
    try:
        _note("fetch      archives")
        service = DepsWizardService(platform.system().lower(), platform.machine().lower())
        fetch = asyncio.run(service.fetch_dependencies())
        if fetch.get("error"):
            raise RuntimeError(str(fetch["error"]))
        for name in fetch.get("downloaded") or []:
            _note(f"fetched    {name}")
        _note("extract    archives")
        extract = asyncio.run(service.extract_dependencies())
        if extract.get("error"):
            raise RuntimeError(str(extract["error"]))
        for name in extract.get("extracted") or []:
            _note(f"extracted  {name}")
        want_gmod = "gmod_tools" in selected
        root = gmod_tools_root(data_dir())
        if want_gmod and not gmod_tools_present(root) and not gmod_app_installed(root):
            _note("steamcmd   +login anonymous +app_update 4020")
            service.gmod_tools_status(start=True)
            watch_steamcmd_download(
                lambda: service.gmod_tools_status(start=False),
                root,
                note=_note,
            )
        _note("ready      tooling pass finished")
        with _lock:
            _job.state = "succeeded"
    except Exception as exc:
        with _lock:
            _job.state = "failed"
            _job.error = str(exc)
            _job.log.append(f"error      {exc}")
