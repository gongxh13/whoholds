"""Configuration: data directory & 5 SQLite file paths.

Override `WHOHOLDS_DATA_DIR` to point at a different location (defaults to
`<repo>/backend/data/`).
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DATA_DIR: Path = Path(os.environ.get("WHOHOLDS_DATA_DIR", _DEFAULT_DATA_DIR))

DB_PATHS: dict[str, Path] = {
    "holdings": DATA_DIR / "holdings.db",
    "prices": DATA_DIR / "prices.db",
    "entities": DATA_DIR / "entities.db",
    "wd_cache": DATA_DIR / "wd_cache.db",
    "meta": DATA_DIR / "meta.db",
}


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
