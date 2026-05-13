"""Run schema migrations against the 5 SQLite DBs.

Usage: `uv run python scripts/migrate.py` (from backend/).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `app.*` importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.migrations import migrate_all  # noqa: E402


def main() -> None:
    for path in migrate_all():
        print(f"  ✓ {path}")


if __name__ == "__main__":
    main()
