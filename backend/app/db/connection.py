"""Read-only sqlite connection helpers.

Each of the 5 DBs is opened as a separate connection so we never cross
write-locks between them. Connections are short-lived (per-request); SQLite's
own cache hit-rate makes that cheap.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import DB_PATHS


def _connect(name: str, *, read_only: bool = True) -> sqlite3.Connection:
    path = DB_PATHS[name]
    if read_only:
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connect(name: str, *, read_only: bool = True) -> Iterator[sqlite3.Connection]:
    conn = _connect(name, read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()
