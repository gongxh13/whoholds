"""Run schema/*.sql against the 5 SQLite databases.

Idempotent — every statement uses `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX
IF NOT EXISTS`, so re-running on an existing DB is safe.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import DB_PATHS, ensure_data_dir

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def migrate_one(name: str) -> Path:
    path = DB_PATHS[name]
    sql = (SCHEMA_DIR / f"{name}.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
    return path


def migrate_all() -> list[Path]:
    ensure_data_dir()
    return [migrate_one(name) for name in DB_PATHS]
