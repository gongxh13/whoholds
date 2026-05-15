"""Build a distributable snapshot from backend/data/.

Slices `prices.db` by year buckets, zst-compresses each shard, and packs the
other DBs (entities / holdings / wd_cache; *not* meta) into `core.tar.zst`.
Output goes to `backend/snapshot/`.

Design: docs/designs/agents/db-snapshot-distribution/design.md
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# Make `app.*` importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "snapshot"

# (label, start_date_inclusive, end_date_inclusive). Edit when rolling years.
YEAR_BUCKETS: list[tuple[str, str, str]] = [
    ("2005-2015", "20050101", "20151231"),
    ("2016-2020", "20160101", "20201231"),
    ("2021-2024", "20210101", "20241231"),
    ("2025-2026", "20250101", "20261231"),  # hot
]
HOT_LABEL = YEAR_BUCKETS[-1][0]

PRICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_daily_price (
    stock_code TEXT,
    date       TEXT,
    adjust     TEXT,
    open       REAL,
    close      REAL,
    high       REAL,
    low        REAL,
    PRIMARY KEY (stock_code, date, adjust)
);
CREATE INDEX IF NOT EXISTS idx_price_stock_date ON stock_daily_price(stock_code, date);
"""


def _check_zstd() -> None:
    if shutil.which("zstd") is None:
        raise SystemExit("zstd binary not found — install with `brew install zstd` or `apt-get install zstd`")


def build_year_shard(label: str, start: str, end: str) -> Path:
    """Slice prices.db into a year shard, zst -19 compress, return the .zst path."""
    src_path = DATA_DIR / "prices.db"
    if not src_path.exists():
        raise SystemExit(f"prices.db not found at {src_path}")

    out_db = SNAPSHOT_DIR / f"prices_{label}.db"
    out_zst = SNAPSHOT_DIR / f"prices_{label}.db.zst"
    out_db.unlink(missing_ok=True)
    out_zst.unlink(missing_ok=True)

    t0 = time.time()
    shard = sqlite3.connect(out_db)
    try:
        shard.executescript("PRAGMA journal_mode=WAL;\n" + PRICES_SCHEMA)
        # Stream rows from source — no need to ATTACH (CLAUDE.md keeps that
        # for runtime; this is a one-shot build script, but plain SELECT
        # works fine and avoids any ambiguity).
        src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
        try:
            rows = src.execute(
                "SELECT stock_code, date, adjust, open, close, high, low "
                "FROM stock_daily_price WHERE date BETWEEN ? AND ?",
                (start, end),
            )
            shard.executemany(
                "INSERT INTO stock_daily_price VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        finally:
            src.close()
        shard.commit()
    finally:
        shard.close()

    print(f"  [{label}] split in {time.time()-t0:.1f}s, raw {out_db.stat().st_size/1024/1024:.1f} MB", flush=True)

    t0 = time.time()
    subprocess.run(
        ["zstd", "-19", "-f", "-q", str(out_db), "-o", str(out_zst)],
        check=True,
    )
    out_db.unlink()
    print(f"  [{label}] zst in {time.time()-t0:.1f}s, {out_zst.stat().st_size/1024/1024:.1f} MB", flush=True)
    return out_zst


def build_core() -> Path:
    """Pack entities + holdings + wd_cache (NOT meta) into core.tar.zst."""
    out = SNAPSHOT_DIR / "core.tar.zst"
    out.unlink(missing_ok=True)

    members = ["entities.db", "holdings.db", "wd_cache.db"]
    for m in members:
        if not (DATA_DIR / m).exists():
            raise SystemExit(f"required {m} not found in {DATA_DIR}")

    t0 = time.time()
    subprocess.run(
        ["tar", "--zstd", "-cf", str(out), "-C", str(DATA_DIR), *members],
        check=True,
        env={"ZSTD_CLEVEL": "19", **__import__("os").environ},
    )
    print(f"  [core] {time.time()-t0:.1f}s, {out.stat().st_size/1024/1024:.1f} MB", flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build distributable snapshot zst files.")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="all year shards + core (first-time seed)")
    group.add_argument("--hot", action="store_true", help="only the hot year shard + core (weekly refresh)")
    group.add_argument("--core-only", action="store_true", help="only the core tarball")
    args = p.parse_args(argv)

    _check_zstd()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    if not (args.all or args.hot or args.core_only):
        p.error("pick one of --all / --hot / --core-only")

    t0 = time.time()

    if args.all:
        for label, start, end in YEAR_BUCKETS:
            build_year_shard(label, start, end)
        build_core()
    elif args.hot:
        label, start, end = YEAR_BUCKETS[-1]
        build_year_shard(label, start, end)
        build_core()
    elif args.core_only:
        build_core()

    total = time.time() - t0
    artifacts = sorted(SNAPSHOT_DIR.glob("*.zst"))
    print()
    print(f"done in {total:.1f}s; {len(artifacts)} artifact(s) in {SNAPSHOT_DIR}:")
    for a in artifacts:
        print(f"  {a.name}  {a.stat().st_size/1024/1024:>7.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
