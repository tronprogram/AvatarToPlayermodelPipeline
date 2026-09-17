"""Regression tests for run_desktop's uvicorn logging config."""

from __future__ import annotations

import logging
import logging.config

import run_desktop


def test_app_logger_output_reaches_the_log_file(tmp_path, monkeypatch):
    log_file = tmp_path / "api_error.log"
    monkeypatch.setattr(run_desktop, "_log_path", lambda: log_file)

    config = run_desktop._uvicorn_log_config()
    logging.config.dictConfig(config)

    log = logging.getLogger("app.core.http_errors")
    try:
        raise ValueError("simulated mutation error")
    except ValueError:
        log.exception("mutation error trying to save the item")

    content = log_file.read_text(encoding="utf-8")
    assert "mutation error trying to save the item" in content
    assert "simulated mutation error" in content
