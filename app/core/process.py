"""Run external programs with consistent capture, env, and errors."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

Argv: TypeAlias = Sequence[str | os.PathLike[str]]

# Child tools with their own interpreter (Blender) must not inherit the app venv.
PYTHON_ENV_KEYS = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")


def command_env(
    extra: Mapping[str, str] | None = None,
    *,
    drop: Sequence[str] = (),
) -> dict[str, str]:
    """Copy the current environment, drop keys, then apply extra."""
    env = os.environ.copy()
    for key in drop:
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result of ``run_command``.

    ``output`` is stderr if that is non-empty, otherwise stdout, stripped.
    That is the string raised in RuntimeError when ``check=True``.
    """

    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return (self.stderr or self.stdout).strip()


def run_command(
    argv: Argv,
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> CommandResult:
    """Run argv to completion and capture text stdout/stderr.

    Raises RuntimeError on a nonzero exit when check is True.
    """
    cmd = [os.fspath(part) for part in argv]
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
    )
    result = CommandResult(
        argv=cmd,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.output or f"{cmd[0]} exited {result.returncode}")
    return result


@dataclass(slots=True)
class SpawnedProcess:
    proc: subprocess.Popen
    pty_master: int | None = None


def spawn_command(
    argv: Argv,
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    pty: bool = False,
) -> SpawnedProcess:
    """Start a process. stdin is closed. stdout and stderr are merged.

    pty=True uses a PTY on Unix so tools that detect a TTY stream progress;
    Windows always uses a pipe.
    """
    cmd = [os.fspath(part) for part in argv]
    env_map = dict(env) if env is not None else None
    if pty and os.name != "nt":
        return _spawn_pty(cmd, cwd=cwd, env=env_map)
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env_map,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    return SpawnedProcess(proc=proc)


def _spawn_pty(
    cmd: list[str],
    *,
    cwd: Path | str | None,
    env: dict[str, str] | None,
) -> SpawnedProcess:
    import pty

    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
    except Exception:
        os.close(master)
        os.close(slave)
        raise
    os.close(slave)
    os.set_blocking(master, False)
    return SpawnedProcess(proc=proc, pty_master=master)
