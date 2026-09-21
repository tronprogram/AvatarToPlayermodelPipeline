"""Desktop launcher: FastAPI on loopback + pywebview window."""

from __future__ import annotations

import errno
import logging
import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

import uvicorn
import webview

from app.core.paths import logs_dir
from app.core.settings import (
    APP_NAME,
    SINGLE_INSTANCE_PORT,
    get_host,
    get_port,
)
from app.main import app

_log = logging.getLogger(__name__)

if getattr(sys, "frozen", False) and sys.platform == "win32":
    try:
        for file in os.listdir(sys._MEIPASS):
            if file.startswith("python3") and file.endswith(".dll"):
                os.environ["PYTHONNET_PYDLL"] = os.path.join(sys._MEIPASS, file)
                break
        from pythonnet import load

        load("netfx")
    except Exception as exc:
        _log.warning("pythonnet initialization skipped: %s", exc)


def _log_path() -> Path:
    """Resolve the API error log next to the binary (or repo in development)."""
    return logs_dir() / "api_error.log"


def _uvicorn_log_config() -> dict:
    """Route uvicorn and app loggers to a persistent file (and stderr in dev)."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "filename": str(_log_path()),
                "encoding": "utf-8",
                "formatter": "default",
            },
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "default",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["file", "stderr"], "level": "INFO", "propagate": False},
            "uvicorn.error": {
                "handlers": ["file", "stderr"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {"handlers": ["file"], "level": "INFO", "propagate": False},
            "app": {"handlers": ["file", "stderr"], "level": "INFO", "propagate": False},
        },
    }


_instance_lock_socket: socket.socket | None = None


def _acquire_single_instance_lock() -> OSError | None:
    """Bind a sentinel TCP socket to detect whether another instance is running."""
    global _instance_lock_socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((get_host(), SINGLE_INSTANCE_PORT))
        sock.listen(1)
    except OSError as exc:
        sock.close()
        return exc
    _instance_lock_socket = sock
    return None


def _address_in_use(exc: OSError) -> bool:
    return exc.errno == errno.EADDRINUSE or getattr(exc, "winerror", None) == 10048


def _port_reserved(exc: OSError) -> bool:
    return exc.errno in (errno.EACCES, errno.EPERM) or getattr(exc, "winerror", None) == 10013


def pick_listen_port(host: str, preferred: int, span: int = 50) -> int:
    """Bind-probe a loopback port, skipping addresses Windows has reserved."""
    last_error: OSError | None = None
    for port in range(preferred, preferred + span):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
            return port
        except OSError as exc:
            last_error = exc
            if _address_in_use(exc) or _port_reserved(exc):
                continue
            raise
        finally:
            sock.close()
    if last_error is not None:
        raise last_error
    raise OSError("no listen port available")


def _friendly_startup_error(exc: OSError | None) -> str:
    """Map a low-level startup failure to a user-facing message."""
    if exc is not None and _address_in_use(exc):
        return (
            f"Another instance of {APP_NAME} is already running. "
            "Close it and try again."
        )
    return f"{APP_NAME} could not start. Check the log file for details."


def _show_error_and_exit(message: str) -> None:
    """Show a native error dialog instead of opening a doomed webview window."""
    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write(f"[{time.ctime()}] STARTUP ABORTED: {message}\n")
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    else:
        print(message, file=sys.stderr)
    sys.exit(1)


def wait_for_server(host: str, port: int, timeout: float | None = None) -> bool:
    """Poll the server port until it becomes reachable."""
    if timeout is None:
        timeout = 45.0 if getattr(sys, "frozen", False) else 10.0
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.2)
    return False


def run_api() -> None:
    """Run the FastAPI application server in a background thread."""
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] API thread starting on {get_host()}:{get_port()}\n")
        uvicorn.run(
            app,
            host=get_host(),
            port=get_port(),
            log_level="info",
            log_config=_uvicorn_log_config(),
        )
    except BaseException as exc:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] API CRASH: {exc}\n")
            f.write(traceback.format_exc())
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass


if __name__ == "__main__":
    host = get_host()
    port = pick_listen_port(host, get_port())
    os.environ["APP_PORT"] = str(port)

    lock_error = _acquire_single_instance_lock()
    if lock_error is not None:
        if _address_in_use(lock_error):
            _show_error_and_exit(_friendly_startup_error(lock_error))
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] instance lock skipped: {lock_error}\n")

    thread = threading.Thread(target=run_api, daemon=True)
    thread.start()

    is_ready = wait_for_server(host, port)
    if not is_ready:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] TIMEOUT: Server did not start on port {port}\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        _show_error_and_exit(_friendly_startup_error(None))

    class DesktopApi:
        def pick_folder(self) -> str:
            window = webview.windows[0] if webview.windows else None
            if window is not None:
                result = window.create_file_dialog(dialog_type=webview.FOLDER_DIALOG)
                if result:
                    return str(result[0])
            return ""

        def pick_file(self) -> str:
            window = webview.windows[0] if webview.windows else None
            if window is not None:
                result = window.create_file_dialog(
                    dialog_type=webview.OPEN_DIALOG,
                    file_types=("360sona (*.glb;*.gltf)",),
                )
                if result:
                    return str(result[0])
            return ""

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(
        APP_NAME,
        f"http://{host}:{port}",
        width=1280,
        height=820,
        js_api=DesktopApi(),
    )

    if sys.platform == "win32":
        webview.start(gui="edgechromium")
    else:
        webview.start()
