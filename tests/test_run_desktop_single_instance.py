"""Regression tests for run_desktop's single-instance guard."""

from __future__ import annotations

import errno
import socket

import pytest

import run_desktop


@pytest.fixture(autouse=True)
def _reset_lock_socket(monkeypatch):
    monkeypatch.setattr(run_desktop, "_instance_lock_socket", None)
    yield
    if run_desktop._instance_lock_socket is not None:
        run_desktop._instance_lock_socket.close()
        run_desktop._instance_lock_socket = None


def test_acquire_single_instance_lock_succeeds_when_port_is_free():
    assert run_desktop._acquire_single_instance_lock() is None
    assert run_desktop._instance_lock_socket is not None


def test_acquire_single_instance_lock_fails_when_already_held():
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind((run_desktop.get_host(), run_desktop.SINGLE_INSTANCE_PORT))
    holder.listen(1)
    try:
        exc = run_desktop._acquire_single_instance_lock()
        assert isinstance(exc, OSError)
        assert exc.errno == errno.EADDRINUSE
        assert run_desktop._instance_lock_socket is None
    finally:
        holder.close()


def test_friendly_startup_error_maps_address_in_use_to_business_message():
    exc = OSError(errno.EADDRINUSE, "Address already in use")
    message = run_desktop._friendly_startup_error(exc)
    assert "already running" in message
    assert run_desktop.APP_NAME in message


def test_friendly_startup_error_falls_back_to_generic_message_for_unknown_cause():
    message = run_desktop._friendly_startup_error(None)
    assert "could not start" in message.lower()

    other_exc = OSError(errno.EACCES, "Permission denied")
    assert run_desktop._friendly_startup_error(other_exc) == message


def test_show_error_and_exit_logs_and_raises_system_exit(tmp_path, monkeypatch):
    log_file = tmp_path / "api_error.log"
    monkeypatch.setattr(run_desktop, "_log_path", lambda: log_file)
    monkeypatch.setattr(run_desktop.sys, "platform", "linux")

    with pytest.raises(SystemExit):
        run_desktop._show_error_and_exit("test message")

    assert "test message" in log_file.read_text(encoding="utf-8")
