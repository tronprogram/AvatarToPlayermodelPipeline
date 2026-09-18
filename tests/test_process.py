"""External process helper."""

import sys

from app.core.process import command_env, run_command


def test_run_command_captures_stdout():
    result = run_command([sys.executable, "-c", "print('ok')"])
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"


def test_run_command_raises_on_failure():
    try:
        run_command([sys.executable, "-c", "raise SystemExit(3)"])
    except RuntimeError as exc:
        assert "exited 3" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_run_command_check_false_keeps_status():
    result = run_command([sys.executable, "-c", "raise SystemExit(7)"], check=False)
    assert result.returncode == 7


def test_command_env_drops_keys(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/tmp/nope")
    env = command_env(drop=("PYTHONPATH",))
    assert "PYTHONPATH" not in env
    assert env.get("PATH")
