"""SQLite connection, schema bootstrap, and session helper."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.paths import data_dir

_log = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Add CREATE TABLE statements here.
"""


def db_path() -> Path:
    """Resolve the SQLite file inside the portable data directory."""
    env_path = os.getenv("APP_DB_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return data_dir() / "app.db"


def connect() -> sqlite3.Connection:
    """Open a sqlite3 connection with WAL, foreign keys, and row access by name."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Yield a connection that commits on success and rolls back on error."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables for the current SQLite file."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
    _log.info("Database ready at %s", db_path())
