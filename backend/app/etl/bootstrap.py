"""Day-0 bootstrap orchestrator.

Order matters (each step's output is the next step's input):

  1. pull_teamwork → entities.teamwork_raw (35 min single call)
  2. ingest_teamwork → entities.holder_companies + coholder_pairs
  3. disambiguate → entities.entity + appearance_entity
  4. pull_top10 → holdings.{top10_holders, top10_free_holders} (latest report
     date for every stock that appears in holder_companies)
  5. pull_prices → prices.stock_daily_price (Tencent source) for those stocks
  6. pull_wikidata → wd_cache (best-effort, low priority)

History back-fill is left for a separate `--historical` flag (the design budgets
6 hours for Day-0 latest-only and 18 days for full 20-year history).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections.abc import Iterable

from app.config import DB_PATHS
from app.etl import (
    disambiguate,
    ingest_teamwork,
    pull_prices,
    pull_teamwork,
    pull_top10,
    pull_wikidata,
)


def run(latest_only: bool = True, from_step: int = 1) -> None:
    t0 = time.time()
    if from_step <= 1:
        print("[bootstrap] step 1/6 — pull_teamwork (~35 min)", flush=True)
        pull_teamwork.pull_full()
        print(f"[bootstrap] done in {time.time()-t0:.0f}s", flush=True)

    if from_step <= 2:
        print("[bootstrap] step 2/6 — ingest_teamwork", flush=True)
        ingest_teamwork.run()

    if from_step <= 3:
        print("[bootstrap] step 3/6 — disambiguate", flush=True)
        disambiguate.run()

    if from_step <= 4:
        codes = _stocks_with_appearances()
        print(f"[bootstrap] step 4/6 — pull_top10 over {len(codes)} stocks", flush=True)
        dates = pull_top10.quarter_ends()[-1:] if latest_only else pull_top10.quarter_ends()
        pull_top10.pull_market(codes, dates)

    if from_step <= 5:
        codes = _stocks_with_appearances()
        print(f"[bootstrap] step 5/6 — pull_prices over {len(codes)} stocks", flush=True)
        pull_prices.pull_market(codes)

    if from_step <= 6:
        names = _individual_names()
        print(f"[bootstrap] step 6/6 — pull_wikidata for {len(names)} names", flush=True)
        pull_wikidata.pull_batch(names[:500])  # head only on Day-0

    print(f"[bootstrap] complete in {time.time()-t0:.0f}s", flush=True)


def _stocks_with_appearances() -> list[str]:
    path = DB_PATHS["entities"]
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT stock_code FROM holder_companies"
            ).fetchall()
        ]
    finally:
        conn.close()


def _individual_names() -> list[str]:
    path = DB_PATHS["entities"]
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [
            r[0]
            for r in conn.execute(
                """
                SELECT holder_name FROM holder_companies
                WHERE holder_type = '个人'
                GROUP BY holder_name
                ORDER BY COUNT(DISTINCT stock_code) DESC
                """
            ).fetchall()
        ]
    finally:
        conn.close()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day-0 bootstrap")
    parser.add_argument("--full-history", action="store_true", help="pull all quarter dates")
    parser.add_argument(
        "--from-step",
        type=int,
        default=1,
        choices=range(1, 7),
        help="resume from step N (1-6); earlier steps already produced their output",
    )
    args = parser.parse_args(argv)
    run(latest_only=not args.full_history, from_step=args.from_step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
